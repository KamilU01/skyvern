from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from skyvern.services import recording_cleanup
from skyvern.services.recording_cleanup import (
    check_disk_space,
    check_required_file,
    cleanup_old_files,
    run_cleanup_if_needed,
)


def test_check_disk_space_missing_path(tmp_path: Path) -> None:
    info = check_disk_space(str(tmp_path / "does_not_exist"))
    assert info.exists is False


def test_check_disk_space_existing_path(tmp_path: Path) -> None:
    info = check_disk_space(str(tmp_path))
    assert info.exists is True
    assert info.total_bytes > 0
    assert 0.0 <= info.free_percent <= 100.0


def test_cleanup_old_files_removes_old_keeps_new(tmp_path: Path) -> None:
    old_file = tmp_path / "old.webm"
    new_file = tmp_path / "new.webm"
    old_file.write_bytes(b"x" * 100)
    new_file.write_bytes(b"y" * 100)
    old_time = time.time() - 100 * 86400  # 100 days ago
    os.utime(old_file, (old_time, old_time))

    result = cleanup_old_files(str(tmp_path), max_age_seconds=14 * 86400)
    assert result.files_deleted == 1
    assert not old_file.exists()
    assert new_file.exists()


def test_cleanup_old_files_deletes_all_file_types(tmp_path: Path) -> None:
    # Final fork behavior (commit 0b93c6471): cleanup is not limited to .webm files.
    f = tmp_path / "artifact.json"
    f.write_bytes(b"data")
    old = time.time() - 100 * 86400
    os.utime(f, (old, old))

    result = cleanup_old_files(str(tmp_path), max_age_seconds=14 * 86400)
    assert result.files_deleted == 1
    assert not f.exists()


def test_cleanup_old_files_missing_directory(tmp_path: Path) -> None:
    result = cleanup_old_files(str(tmp_path / "nope"), max_age_seconds=1)
    assert result.files_deleted == 0


def test_check_required_file_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(recording_cleanup.settings, "HEALTHCHECK_REQUIRED_FILE", "", raising=False)
    assert check_required_file() is True


def test_check_required_file_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    missing = str(tmp_path / "nope.toml")
    monkeypatch.setattr(recording_cleanup.settings, "HEALTHCHECK_REQUIRED_FILE", missing, raising=False)
    assert check_required_file() is False


@pytest.mark.asyncio
async def test_run_cleanup_if_needed_healthy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(recording_cleanup.settings, "HEALTHCHECK_REQUIRED_FILE", "", raising=False)
    monkeypatch.setattr(recording_cleanup.settings, "RECORDING_CLEANUP_ENABLED", False, raising=False)
    monkeypatch.setattr(recording_cleanup.settings, "RECORDING_CLEANUP_DISK_THRESHOLD_PERCENT", 0.0, raising=False)

    health = await run_cleanup_if_needed()
    assert health.required_file_ok is True
    assert health.cleanup_triggered is False
    assert health.status == "healthy"


@pytest.mark.asyncio
async def test_run_cleanup_if_needed_unhealthy_when_required_file_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        recording_cleanup.settings, "HEALTHCHECK_REQUIRED_FILE", str(tmp_path / "missing.toml"), raising=False
    )
    monkeypatch.setattr(recording_cleanup.settings, "RECORDING_CLEANUP_ENABLED", False, raising=False)
    monkeypatch.setattr(recording_cleanup.settings, "RECORDING_CLEANUP_DISK_THRESHOLD_PERCENT", 0.0, raising=False)

    health = await run_cleanup_if_needed()
    assert health.required_file_ok is False
    assert health.status == "unhealthy"
