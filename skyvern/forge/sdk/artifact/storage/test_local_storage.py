import pytest
from freezegun import freeze_time

from skyvern.config import settings
from skyvern.forge.sdk.artifact.models import ArtifactType, LogEntityType
from skyvern.forge.sdk.artifact.storage.local import LocalStorage
from skyvern.forge.sdk.artifact.storage.test_helpers import (
    create_fake_for_ai_suggestion,
    create_fake_step,
    create_fake_task_v2,
    create_fake_thought,
    create_fake_workflow_run_block,
)

# Test constants
TEST_BUCKET = "test-skyvern-bucket"
TEST_ORGANIZATION_ID = "test-org-123"
TEST_TASK_ID = "tsk_123456789"
TEST_STEP_ID = "step_123456789"
TEST_WORKFLOW_RUN_ID = "wfr_123456789"
TEST_BLOCK_ID = "block_123456789"
TEST_AI_SUGGESTION_ID = "ai_sugg_test_123"


@pytest.fixture
def local_storage() -> LocalStorage:
    return LocalStorage()


@freeze_time("2025-06-09T12:00:00")
class TestLocalStorageBuildURIs:
    def test_build_uri(self, local_storage: LocalStorage) -> None:
        step = create_fake_step(TEST_STEP_ID)
        uri = local_storage.build_uri(
            organization_id=TEST_ORGANIZATION_ID,
            artifact_id="artifact123",
            step=step,
            artifact_type=ArtifactType.LLM_PROMPT,
        )
        assert (
            uri
            == f"file://{local_storage.artifact_path}/{TEST_ORGANIZATION_ID}/{TEST_TASK_ID}/01_0_{TEST_STEP_ID}/2025-06-09T12:00:00_artifact123_llm_prompt.txt"
        )

    def test_build_log_uri(self, local_storage: LocalStorage) -> None:
        uri = local_storage.build_log_uri(
            organization_id=TEST_ORGANIZATION_ID,
            log_entity_type=LogEntityType.WORKFLOW_RUN_BLOCK,
            log_entity_id="log_id",
            artifact_type=ArtifactType.SKYVERN_LOG,
        )
        assert (
            uri
            == f"file://{local_storage.artifact_path}/logs/workflow_run_block/log_id/2025-06-09T12:00:00_skyvern_log.log"
        )

    def test_build_thought_uri(self, local_storage: LocalStorage) -> None:
        thought = create_fake_thought("cruise123", "thought123")
        uri = local_storage.build_thought_uri(
            organization_id=TEST_ORGANIZATION_ID,
            artifact_id="artifact123",
            thought=thought,
            artifact_type=ArtifactType.VISIBLE_ELEMENTS_TREE,
        )
        assert (
            uri
            == f"file://{local_storage.artifact_path}/{settings.ENV}/{TEST_ORGANIZATION_ID}/tasks/cruise123/thought123/2025-06-09T12:00:00_artifact123_visible_elements_tree.json"
        )

    def test_build_task_v2_uri(self, local_storage: LocalStorage) -> None:
        task_v2 = create_fake_task_v2("cruise123")
        uri = local_storage.build_task_v2_uri(
            organization_id=TEST_ORGANIZATION_ID,
            artifact_id="artifact123",
            task_v2=task_v2,
            artifact_type=ArtifactType.HTML_ACTION,
        )
        assert (
            uri
            == f"file://{local_storage.artifact_path}/{settings.ENV}/{TEST_ORGANIZATION_ID}/observers/cruise123/2025-06-09T12:00:00_artifact123_html_action.html"
        )

    def test_build_workflow_run_block_uri(self, local_storage: LocalStorage) -> None:
        workflow_run_block = create_fake_workflow_run_block(TEST_WORKFLOW_RUN_ID, TEST_BLOCK_ID)
        uri = local_storage.build_workflow_run_block_uri(
            organization_id=TEST_ORGANIZATION_ID,
            artifact_id="artifact123",
            workflow_run_block=workflow_run_block,
            artifact_type=ArtifactType.HAR,
        )
        assert (
            uri
            == f"file://{local_storage.artifact_path}/{settings.ENV}/{TEST_ORGANIZATION_ID}/workflow_runs/{TEST_WORKFLOW_RUN_ID}/{TEST_BLOCK_ID}/2025-06-09T12:00:00_artifact123_har.har"
        )

    def test_build_ai_suggestion_uri(self, local_storage: LocalStorage) -> None:
        ai_suggestion = create_fake_for_ai_suggestion(TEST_AI_SUGGESTION_ID)
        uri = local_storage.build_ai_suggestion_uri(
            organization_id=TEST_ORGANIZATION_ID,
            artifact_id="artifact123",
            ai_suggestion=ai_suggestion,
            artifact_type=ArtifactType.SCREENSHOT_LLM,
        )
        assert (
            uri
            == f"file://{local_storage.artifact_path}/{settings.ENV}/{TEST_ORGANIZATION_ID}/ai_suggestions/{TEST_AI_SUGGESTION_ID}/2025-06-09T12:00:00_artifact123_screenshot_llm.png"
        )


class TestLocalStorageDownloadedFiles:
    """Tests for get_downloaded_files returning HTTP URLs."""

    @pytest.mark.asyncio
    async def test_get_downloaded_files_returns_http_urls(self, local_storage: LocalStorage, tmp_path) -> None:
        """Verify that get_downloaded_files returns HTTP URLs instead of file:// URIs."""
        import os
        from skyvern.forge.sdk.api.files import get_download_dir

        run_id = "test_run_http_urls"
        download_dir = get_download_dir(run_id=run_id)
        os.makedirs(download_dir, exist_ok=True)
        test_file_path = os.path.join(download_dir, "test_document.pdf")

        try:
            # Create a test file
            with open(test_file_path, "wb") as f:
                f.write(b"test content for http url verification")

            files = await local_storage.get_downloaded_files(TEST_ORGANIZATION_ID, run_id)

            assert len(files) == 1
            assert files[0].filename == "test_document.pdf"
            # Verify HTTP URL format - should NOT start with file://
            assert not files[0].url.startswith("file://")
            # Verify it's a proper HTTP URL with the expected endpoint
            assert files[0].url.startswith(settings.SKYVERN_BASE_URL)
            assert f"/v1/public/runs/{run_id}/files/test_document.pdf" in files[0].url
            # Verify checksum is present
            assert files[0].checksum is not None
        finally:
            # Cleanup
            if os.path.exists(test_file_path):
                os.remove(test_file_path)
            if os.path.exists(download_dir):
                try:
                    os.rmdir(download_dir)
                except OSError:
                    pass  # Directory might not be empty if other tests created files

