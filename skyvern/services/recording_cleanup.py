from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import psutil
import structlog

from skyvern.config import settings

LOG = structlog.get_logger()

_cleanup_lock = asyncio.Lock()

_ESCALATION_BATCH_SIZE = 50
_ESCALATION_BYTES_BETWEEN_CHECKS = 100 * 1024 * 1024  # 100 MB


@dataclass
class DiskSpaceInfo:
    path: str
    total_bytes: int = 0
    used_bytes: int = 0
    free_bytes: int = 0
    free_percent: float = 0.0
    exists: bool = True


@dataclass
class CleanupResult:
    files_deleted: int = 0
    bytes_freed: int = 0
    directories_removed: int = 0
    errors: list[str] = field(default_factory=list)
    escalation_used: bool = False


@dataclass
class HealthStatus:
    status: str  # "healthy" or "unhealthy"
    message: str = ""
    required_file_ok: bool = True
    video_path_disk: DiskSpaceInfo | None = None
    artifact_path_disk: DiskSpaceInfo | None = None
    cleanup_triggered: bool = False
    cleanup_result: CleanupResult | None = None


def check_disk_space(path: str) -> DiskSpaceInfo:
    """Check disk space for the given path."""
    info = DiskSpaceInfo(path=path)
    if not os.path.exists(path):
        info.exists = False
        return info

    try:
        usage = psutil.disk_usage(path)
        info.total_bytes = usage.total
        info.used_bytes = usage.used
        info.free_bytes = usage.free
        info.free_percent = round((usage.free / usage.total) * 100, 2) if usage.total > 0 else 0.0
    except OSError as e:
        LOG.warning("Failed to check disk space", path=path, error=str(e))
        info.exists = False

    return info


def _collect_all_files(directory: str) -> list[tuple[Path, float, int]]:
    """Scan directory and return list of (path, mtime, size) for all files, sorted oldest first."""
    files: list[tuple[Path, float, int]] = []
    if not os.path.exists(directory):
        return files

    for root, _dirs, filenames in os.walk(directory):
        for filename in filenames:
            filepath = Path(root) / filename
            try:
                stat = filepath.stat()
                files.append((filepath, stat.st_mtime, stat.st_size))
            except OSError:
                continue

    files.sort(key=lambda x: x[1])  # sort by mtime, oldest first
    return files


def cleanup_old_files(directory: str, max_age_seconds: float) -> CleanupResult:
    """Remove all files older than max_age_seconds and clean up empty directories."""
    result = CleanupResult()
    if not os.path.exists(directory):
        return result

    cutoff = time.time() - max_age_seconds

    for root, dirs, filenames in os.walk(directory, topdown=False):
        for filename in filenames:
            filepath = Path(root) / filename
            try:
                st = filepath.stat()
                if st.st_mtime < cutoff:
                    filepath.unlink()
                    result.files_deleted += 1
                    result.bytes_freed += st.st_size
            except FileNotFoundError:
                pass
            except OSError as e:
                result.errors.append(f"{filepath}: {e}")

        # Try to remove empty directories (os.rmdir only removes empty dirs)
        for dirname in dirs:
            dirpath = Path(root) / dirname
            try:
                os.rmdir(dirpath)
                result.directories_removed += 1
            except OSError:
                pass

    return result


def _escalation_cleanup(directory: str, threshold_percent: float) -> CleanupResult:
    """Remove files from oldest until free space exceeds threshold or no files remain."""
    result = CleanupResult()
    result.escalation_used = True

    files = _collect_all_files(directory)
    if not files:
        return result

    files_since_check = 0
    bytes_since_check = 0

    for filepath, _mtime, size in files:
        try:
            filepath.unlink()
            result.files_deleted += 1
            result.bytes_freed += size
            files_since_check += 1
            bytes_since_check += size
        except FileNotFoundError:
            pass
        except OSError as e:
            result.errors.append(f"{filepath}: {e}")
            continue

        if files_since_check >= _ESCALATION_BATCH_SIZE or bytes_since_check >= _ESCALATION_BYTES_BETWEEN_CHECKS:
            disk = check_disk_space(directory)
            if disk.exists and disk.free_percent >= threshold_percent:
                break
            files_since_check = 0
            bytes_since_check = 0

    # Clean up empty directories
    if os.path.exists(directory):
        for root, dirs, _filenames in os.walk(directory, topdown=False):
            for dirname in dirs:
                try:
                    os.rmdir(Path(root) / dirname)
                    result.directories_removed += 1
                except OSError:
                    pass

    return result


def _merge_cleanup_results(base: CleanupResult, extra: CleanupResult) -> CleanupResult:
    """Merge two cleanup results into one."""
    return CleanupResult(
        files_deleted=base.files_deleted + extra.files_deleted,
        bytes_freed=base.bytes_freed + extra.bytes_freed,
        directories_removed=base.directories_removed + extra.directories_removed,
        errors=base.errors + extra.errors,
        escalation_used=base.escalation_used or extra.escalation_used,
    )


def check_required_file() -> bool:
    """Check if the healthcheck required file exists. Returns True if no file is configured."""
    if not settings.HEALTHCHECK_REQUIRED_FILE:
        return True
    return os.path.isfile(settings.HEALTHCHECK_REQUIRED_FILE)


def _run_cleanup_for_path(directory: str, threshold_percent: float, retention_days: int) -> CleanupResult:
    """Run phased cleanup for a single directory. Phase 1: age-based, Phase 2: escalation if needed."""
    max_age_seconds = retention_days * 86400
    result = cleanup_old_files(directory, max_age_seconds)

    disk = check_disk_space(directory)
    if disk.exists and disk.free_percent < threshold_percent:
        LOG.warning(
            "Disk space still below threshold after age-based cleanup, escalating",
            path=directory,
            free_percent=disk.free_percent,
            threshold=threshold_percent,
        )
        escalation_result = _escalation_cleanup(directory, threshold_percent)
        result = _merge_cleanup_results(result, escalation_result)

    return result


async def run_cleanup_if_needed() -> HealthStatus:
    """Main health check function: checks required file, disk space, and triggers cleanup if needed.

    Cleanup is strictly scoped to VIDEO_PATH and ARTIFACT_STORAGE_PATH (the configured cleanup
    roots). No files outside those directories are ever touched.
    """
    health = HealthStatus(status="healthy")

    # Check required file
    health.required_file_ok = check_required_file()
    if not health.required_file_ok:
        health.status = "unhealthy"
        health.message = f"Required file missing: {settings.HEALTHCHECK_REQUIRED_FILE}"

    video_path = settings.VIDEO_PATH or "./video"
    artifact_path = settings.ARTIFACT_STORAGE_PATH

    health.video_path_disk = check_disk_space(video_path)
    health.artifact_path_disk = check_disk_space(artifact_path)

    threshold = settings.RECORDING_CLEANUP_DISK_THRESHOLD_PERCENT
    cleanup_enabled = settings.RECORDING_CLEANUP_ENABLED
    retention_days = settings.RECORDING_CLEANUP_RETENTION_DAYS

    needs_cleanup = False
    if cleanup_enabled:
        if health.video_path_disk.exists and health.video_path_disk.free_percent < threshold:
            needs_cleanup = True
        if health.artifact_path_disk.exists and health.artifact_path_disk.free_percent < threshold:
            needs_cleanup = True

    if needs_cleanup:
        async with _cleanup_lock:
            health.cleanup_triggered = True
            total_result = CleanupResult()

            # Re-check after acquiring lock (another request may have already cleaned)
            health.video_path_disk = check_disk_space(video_path)
            health.artifact_path_disk = check_disk_space(artifact_path)

            if health.video_path_disk.exists and health.video_path_disk.free_percent < threshold:
                result = await asyncio.to_thread(_run_cleanup_for_path, video_path, threshold, retention_days)
                total_result = _merge_cleanup_results(total_result, result)
                health.video_path_disk = check_disk_space(video_path)

            if health.artifact_path_disk.exists and health.artifact_path_disk.free_percent < threshold:
                result = await asyncio.to_thread(_run_cleanup_for_path, artifact_path, threshold, retention_days)
                total_result = _merge_cleanup_results(total_result, result)
                health.artifact_path_disk = check_disk_space(artifact_path)

            health.cleanup_result = total_result

            if total_result.files_deleted > 0:
                if total_result.escalation_used:
                    LOG.warning(
                        "Recording cleanup escalation was used - retention period was insufficient",
                        files_deleted=total_result.files_deleted,
                        bytes_freed=total_result.bytes_freed,
                        directories_removed=total_result.directories_removed,
                        errors=len(total_result.errors),
                    )
                else:
                    LOG.info(
                        "Recording cleanup completed",
                        files_deleted=total_result.files_deleted,
                        bytes_freed=total_result.bytes_freed,
                        directories_removed=total_result.directories_removed,
                    )

    # Build status message and determine final health
    messages: list[str] = []
    if not health.required_file_ok:
        messages.append(f"Required file missing: {settings.HEALTHCHECK_REQUIRED_FILE}")

    for label, disk_info in [("VIDEO_PATH", health.video_path_disk), ("ARTIFACT_PATH", health.artifact_path_disk)]:
        if disk_info and disk_info.exists and disk_info.free_percent < threshold:
            health.status = "unhealthy"
            messages.append(f"{label} free space: {disk_info.free_percent}%")

    if health.cleanup_triggered and health.cleanup_result:
        cr = health.cleanup_result
        messages.append(f"Cleanup: {cr.files_deleted} files deleted, {cr.bytes_freed} bytes freed")

    if not messages:
        health.message = "All checks passed"
    else:
        health.message = " | ".join(messages)

    return health
