# Skyvern 1.0.36 Fork Feature Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebase the fork-only behavior currently on `v1.0.7_2` onto upstream `v1.0.36` while avoiding duplicate work for features already present upstream.

**Architecture:** Start from a clean branch at `v1.0.36` and re-implement each fork feature against the current upstream architecture instead of cherry-picking old patches. Treat native `v1.0.36` behavior as canonical, especially the newer artifact signing, DB repository, LLM schema, browser session, and action handling layers.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy/Alembic, Playwright, LiteLLM/OpenAI-compatible clients, uv, pytest, ruff, Docker Compose.

---

## Investigation Summary

Current workspace:
- Current branch: `v1.0.7_2`
- Comparison base requested by user: `v1.0.7`
- Target upstream tag: `v1.0.36`
- Merge base of `HEAD` and `v1.0.36`: `v1.0.7`
- Fork commits after `v1.0.7`: 9 commits, 33 files, about 1018 insertions and 17 deletions
- `git cherry -v v1.0.36 HEAD`: every fork commit is `+`, so no fork patch is patch-identical to `v1.0.36`

Fork commits grouped by feature:
- `332dfe32a` file upload resilience, file URL inference, video recording diagnostics, terminate prompt wording, local artifact share link, tiktoken SSL workaround
- `cc8c206ed`, `d0e10c23e`, `ac40d662a`, `00993b6e8` per-run and global `host_resolver_rules` through SDK/API/DB/browser launch
- `6bb6c7c61` local downloaded files exposed as HTTP URLs plus run file download endpoints
- `d0107ef52`, `0b93c6471` healthcheck endpoint and disk cleanup for recordings/artifacts
- `63565e23d` extra generation parameters on LLM configs

Native status in `v1.0.36`:
- Host resolver rules: not native. `v1.0.36` has `BROWSER_ADDITIONAL_ARGS`, which can supply global Chromium flags, but there is no request-level `host_resolver_rules`, no DB persistence, and no workflow/task propagation.
- File upload resilience: partially native. `v1.0.36` has `UPLOAD_FILE`, `file_url`, `filechooser`, child file input lookup, and corrupted URL recovery, but it lacks fork-only URL inference from task text, nearby parent/sibling file input lookup, event dispatch after `set_input_files`, and direct-upload fallback when the file chooser does not open.
- Video recording: mostly native. `v1.0.36` records video, but it does not create/log the dated video directory before passing it to Playwright.
- Terminate criterion in action extraction prompts: partially native. `v1.0.36` has termination-specific prompts elsewhere, but `extract-action*.j2` does not include the fork's terminate-criterion guidance.
- Local artifact share links: native. `v1.0.36` already returns `artifact.uri` from local storage share link methods.
- Downloaded file URLs: partially native. `v1.0.36` has signed `/v1/artifacts/{artifact_id}/content` infrastructure and richer S3/Azure download artifact handling, but local storage still returns `file://...` from `get_downloaded_files` and does not include the fork's run-file HTTP endpoints.
- Healthcheck: partially native. Docker Compose checks `/api/v1/heartbeat`; no `/health` endpoint with disk checks/cleanup exists.
- Disk cleanup: not native.
- LLM config generation params: not native. `v1.0.36` only resolves max tokens and temperature in `skyvern/schemas/llm.py`; `top_p`, `top_k`, `min_p`, `presence_penalty`, and `repetition_penalty` are absent.
- Token counter SSL workaround: not native. The fork globally disables SSL verification before importing `tiktoken`; do not port that exact behavior without an explicit opt-in because it weakens TLS for the process.
- Empty page retry wait default: not native. Fork changes `empty_page_retry_wait` default from 3s to 15s.

## File Structure

Host resolver rules:
- Create: `alembic/versions/2026_05_29-<revision>_add_host_resolver_rules_to_runs.py`
- Modify: `skyvern/config.py`
- Modify: `skyvern/schemas/runs.py`
- Modify: `skyvern/forge/sdk/schemas/tasks.py`
- Modify: `skyvern/forge/sdk/workflow/models/workflow.py`
- Modify: `skyvern/forge/sdk/db/models.py`
- Modify: `skyvern/forge/sdk/db/repositories/tasks.py`
- Modify: `skyvern/forge/sdk/db/repositories/workflow_runs.py`
- Modify: `skyvern/forge/sdk/db/utils.py`
- Modify: `skyvern/forge/agent.py`
- Modify: `skyvern/forge/sdk/routes/agent_protocol.py`
- Modify: `skyvern/forge/sdk/workflow/service.py`
- Modify: `skyvern/webeye/browser_factory.py`
- Modify: `skyvern/webeye/real_browser_manager.py`
- Modify: `skyvern/client/client.py`
- Modify: `skyvern/client/raw_client.py`
- Modify: `skyvern/client/types/task_run_request.py`
- Modify: `skyvern/client/types/workflow_run_request.py`
- Modify: `skyvern/library/skyvern.py`

File upload and action parsing:
- Modify: `skyvern/webeye/actions/parse_actions.py`
- Modify: `skyvern/webeye/actions/handler.py`
- Modify: `skyvern/webeye/utils/dom.py`
- Modify: `skyvern/forge/prompts/skyvern/extract-action-dynamic.j2`
- Modify: `skyvern/forge/prompts/skyvern/extract-action-static.j2`
- Modify: `skyvern/forge/prompts/skyvern/extract-action.j2`
- Test: `tests/unit/test_actions.py` or create `tests/unit/test_parse_actions_file_urls.py`

Downloaded file HTTP access:
- Modify: `skyvern/forge/sdk/artifact/storage/local.py`
- Modify: `skyvern/forge/sdk/artifact/storage/test_local_storage.py`
- Modify: `skyvern/forge/sdk/routes/agent_protocol.py`
- Test: create `tests/unit/forge/sdk/test_run_file_download_routes.py`

Healthcheck and cleanup:
- Create: `skyvern/services/recording_cleanup.py`
- Create or modify: `scripts/healthcheck.py`
- Modify: `skyvern/config.py`
- Modify: `skyvern/forge/api_app.py`
- Modify: `docker-compose.yml`
- Test: create `tests/unit/services/test_recording_cleanup.py`

LLM parameters and token counter:
- Modify: `skyvern/config.py`
- Modify: `skyvern/schemas/llm.py`
- Modify: `skyvern/forge/sdk/api/llm/api_handler_factory.py`
- Modify only if needed: `skyvern/forge/sdk/api/llm/models.py` public shim
- Modify: `skyvern/utils/token_counter.py`
- Test: `tests/unit/test_llm_prompt_config.py` or create `tests/unit/test_llm_generation_params.py`

Operational wait/video tweaks:
- Modify: `skyvern/experimentation/wait_utils.py`
- Modify: `skyvern/webeye/browser_factory.py`
- Modify: `skyvern/webeye/real_browser_state.py`
- Test: targeted unit tests around browser args and wait defaults

## Task 1: Prepare Migration Branch

**Files:**
- No application code changes

- [ ] **Step 1: Confirm clean working tree**

Run:
```bash
git status --short --branch
```
Expected: current branch is `v1.0.7_2`; no uncommitted application changes except this plan if it has been saved.

- [ ] **Step 2: Create implementation branch from target tag**

Run:
```bash
git switch -c codex/migrate-fork-features-to-1.0.36 v1.0.36
```
Expected: new branch points at `v1.0.36`.

- [ ] **Step 3: Record upstream baseline**

Run:
```bash
git rev-parse HEAD
git describe --tags --exact-match HEAD
```
Expected:
```text
db3a30852bd64f5202a94f19eb0d7070b530ece9
v1.0.36
```

- [ ] **Step 4: Run a narrow baseline test set**

Run:
```bash
uv run pytest tests/unit/test_actions.py tests/unit/test_real_browser_manager.py skyvern/forge/sdk/artifact/storage/test_local_storage.py -q
```
Expected: either PASS, or failures documented as pre-existing before migration.

## Task 2: Port Host Resolver Rules

**Files:**
- Create: `alembic/versions/2026_05_29-<revision>_add_host_resolver_rules_to_runs.py`
- Modify: `skyvern/config.py`
- Modify: `skyvern/schemas/runs.py`
- Modify: `skyvern/forge/sdk/schemas/tasks.py`
- Modify: `skyvern/forge/sdk/workflow/models/workflow.py`
- Modify: `skyvern/forge/sdk/db/models.py`
- Modify: `skyvern/forge/sdk/db/repositories/tasks.py`
- Modify: `skyvern/forge/sdk/db/repositories/workflow_runs.py`
- Modify: `skyvern/forge/sdk/db/utils.py`
- Modify: `skyvern/forge/agent.py`
- Modify: `skyvern/forge/sdk/routes/agent_protocol.py`
- Modify: `skyvern/forge/sdk/workflow/service.py`
- Modify: `skyvern/webeye/browser_factory.py`
- Modify: `skyvern/webeye/real_browser_manager.py`
- Modify: `skyvern/client/client.py`
- Modify: `skyvern/client/raw_client.py`
- Modify: `skyvern/client/types/task_run_request.py`
- Modify: `skyvern/client/types/workflow_run_request.py`
- Modify: `skyvern/library/skyvern.py`

- [ ] **Step 1: Write DB migration**

Create one Alembic migration chained after `78a8db531e69` that adds nullable `host_resolver_rules` columns to `tasks` and `workflow_runs`.

Migration body:
```python
def upgrade() -> None:
    op.add_column("tasks", sa.Column("host_resolver_rules", sa.String(), nullable=True))
    op.add_column("workflow_runs", sa.Column("host_resolver_rules", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("workflow_runs", "host_resolver_rules")
    op.drop_column("tasks", "host_resolver_rules")
```

- [ ] **Step 2: Add config and schemas**

Add `BROWSER_HOST_RESOLVER_RULES: str = ""` to `skyvern/config.py`.

Add this field to `TaskRunRequest`, `WorkflowRunRequest`, `TaskBase`, `WorkflowRequestBody`, and `WorkflowRun`:
```python
host_resolver_rules: str | None = Field(
    default=None,
    description="Custom host-to-IP mappings for DNS resolution. Format: 'hostname:ip,hostname2:ip2'.",
    examples=["example.com:192.168.1.100", "app.local:10.0.0.5,api.local:10.0.0.6"],
)
```
Use plain `str | None = None` in non-Pydantic dataclass/model classes where `Field` is not used.

- [ ] **Step 3: Persist and hydrate the value**

Add `host_resolver_rules = Column(String, nullable=True)` to `TaskModel` and `WorkflowRunModel`.

Thread the parameter through:
```python
TasksRepository.create_task(..., host_resolver_rules: str | None = None)
WorkflowRunsRepository.create_workflow_run(..., host_resolver_rules: str | None = None)
convert_to_task(..., host_resolver_rules=task_obj.host_resolver_rules)
convert_to_workflow_run(..., host_resolver_rules=workflow_run_model.host_resolver_rules)
```

- [ ] **Step 4: Propagate API run requests**

In `agent_protocol.py`, pass request values into task/workflow creation:
```python
host_resolver_rules=run_request.host_resolver_rules
host_resolver_rules=workflow_run_request.host_resolver_rules
```

In workflow service and agent code, propagate workflow-level rules to child tasks:
```python
host_resolver_rules=workflow_request.host_resolver_rules
host_resolver_rules=workflow_run.host_resolver_rules
host_resolver_rules=task_request.host_resolver_rules
```

- [ ] **Step 5: Apply rules in browser creation**

In `skyvern/webeye/browser_factory.py`, add `_build_host_resolver_rules(request_rules: str | None) -> str` that combines `settings.BROWSER_HOST_RESOLVER_RULES` and request rules into Chromium `MAP host ip` entries.

Preserve `v1.0.36` native behavior:
```python
browser_args.extend(settings.BROWSER_ADDITIONAL_ARGS)
```
Then append:
```python
combined_host_rules = _build_host_resolver_rules(host_resolver_rules)
if combined_host_rules:
    browser_args.append(f"--host-resolver-rules={combined_host_rules}")
```

Pass `host_resolver_rules` through `_create_headless_chromium`, `_create_headful_chromium`, `BrowserContextFactory.create_browser_context`, and `RealBrowserManager._create_browser_state`.

- [ ] **Step 6: Update SDK surfaces**

Add `host_resolver_rules` next to `browser_address` in sync/async `run_task` and `run_workflow` methods in `skyvern/client/client.py`, `skyvern/client/raw_client.py`, request type models, and `skyvern/library/skyvern.py`.

- [ ] **Step 7: Test host resolver rules**

Run:
```bash
uv run pytest tests/unit/test_real_browser_manager.py tests/unit/forge/sdk/db/test_workflow_runs_repository.py -q
uv run python -m compileall skyvern/webeye/browser_factory.py skyvern/webeye/real_browser_manager.py skyvern/schemas/runs.py
```
Expected: tests pass and compileall reports no syntax errors.

- [ ] **Step 8: Commit**

Run:
```bash
git add alembic skyvern tests
git commit -m "[Browser] Add per-run host resolver rules"
```

## Task 3: Port File Upload Fallbacks and File URL Inference

**Files:**
- Modify: `skyvern/webeye/actions/parse_actions.py`
- Modify: `skyvern/webeye/actions/handler.py`
- Modify: `skyvern/webeye/utils/dom.py`
- Modify: `skyvern/forge/prompts/skyvern/extract-action-dynamic.j2`
- Modify: `skyvern/forge/prompts/skyvern/extract-action-static.j2`
- Modify: `skyvern/forge/prompts/skyvern/extract-action.j2`
- Test: create `tests/unit/test_parse_actions_file_urls.py`

- [ ] **Step 1: Add pure parser tests**

Create tests for:
```python
parse_attached_files("Attached files:\n- resume.pdf: https://example.com/resume.pdf")
parse_inline_file_references("Upload [resume.pdf](https://example.com/resume.pdf)")
extract_file_urls_from_text("Upload https://example.com/resume.pdf")
```
Expected mappings:
```python
{"resume.pdf": "https://example.com/resume.pdf"}
{"file_1": "https://example.com/resume.pdf"}
```

- [ ] **Step 2: Implement pure helpers**

Add fork helpers to `parse_actions.py`, keeping them independent and unit-testable:
```python
FILE_EXTENSIONS = {".pdf", ".csv", ".xlsx", ".xls", ".doc", ".docx", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".txt", ".zip"}
def extract_file_urls_from_text(text: str | None) -> list[str]: ...
def parse_attached_files(text: str | None) -> dict[str, str]: ...
def parse_inline_file_references(text: str | None) -> dict[str, str]: ...
def find_matching_file_url(action: Action, attached_files: dict[str, str], used_files: set[str]) -> str | None: ...
```

- [ ] **Step 3: Inject missing file URLs after action parsing**

After parsing actions, build `goal_text = f"{task.navigation_goal or ''} {task.navigation_payload or ''}"`.

For `ClickAction` and `UploadFileAction` where `file_url` is missing, assign a matched URL. Keep `v1.0.36`'s later imaginary/corrupted URL validation in `handler.py`.

- [ ] **Step 4: Add nearby file input lookup**

Add to `SkyvernElement`:
```python
async def find_nearby_file_input(self) -> Locator | None:
    current = self.get_locator()
    for level in range(1, 4):
        parent = current.locator("..")
        file_input = parent.locator('input[type="file"]')
        count = await file_input.count()
        if count == 1:
            return file_input
        if count > 1:
            return None
        current = parent
    return None
```

- [ ] **Step 5: Add direct upload fallback and event dispatch**

In `handle_upload_file_action`, after `find_file_input_in_children`, call `find_nearby_file_input`.

After successful `set_input_files`, dispatch:
```python
await locator.dispatch_event("input")
await locator.dispatch_event("change")
```
Log and continue if dispatch fails.

In `chain_click`, if a file URL exists but no filechooser fires, try child and nearby file inputs before returning `WrongElementToUploadFile`.

- [ ] **Step 6: Merge prompt changes without losing upstream additions**

Add fork terminate-criterion wording to `extract-action-dynamic.j2`, `extract-action-static.j2`, and `extract-action.j2`, but preserve `v1.0.36` native `KEYPRESS`, `SCROLL`, user-data-agnostic `user_detail_query`, captcha, and close-page instructions.

- [ ] **Step 7: Test upload parsing**

Run:
```bash
uv run pytest tests/unit/test_parse_actions_file_urls.py tests/unit/test_actions.py -q
uv run python -m compileall skyvern/webeye/actions/parse_actions.py skyvern/webeye/actions/handler.py skyvern/webeye/utils/dom.py
```
Expected: parser tests pass; existing action tests do not regress.

- [ ] **Step 8: Commit**

Run:
```bash
git add skyvern/webeye skyvern/forge/prompts tests
git commit -m "[Actions] Improve file upload URL recovery"
```

## Task 4: Port Downloaded File HTTP Access Safely

**Files:**
- Modify: `skyvern/forge/sdk/artifact/storage/local.py`
- Modify: `skyvern/forge/sdk/artifact/storage/test_local_storage.py`
- Modify: `skyvern/forge/sdk/routes/agent_protocol.py`
- Modify: `skyvern/config.py`
- Test: create `tests/unit/forge/sdk/test_run_file_download_routes.py`

- [ ] **Step 1: Preserve native artifact content behavior**

Do not replace `v1.0.36` signed artifact content behavior. Use the fork behavior only to solve the remaining local-storage `file://` gap.

- [ ] **Step 2: Add config gate for public no-auth links**

Add:
```python
ENABLE_PUBLIC_RUN_FILE_ENDPOINT: bool = False
```
Default to authenticated route unless this flag is explicitly enabled. This preserves the fork capability for deployments that need webhook-accessible no-auth local file URLs without making public file serving the default.

- [ ] **Step 3: Add route with path traversal protection**

Add authenticated route:
```python
@base_router.get("/runs/{run_id}/files/{filename}")
async def download_run_file(..., current_org: Organization = Depends(...)) -> FileResponse:
    ...
```

Add public route only when config is enabled:
```python
@base_router.get("/public/runs/{run_id}/files/{filename}")
async def download_run_file_public(...) -> FileResponse:
    ...
```

Use `Path.resolve()` and `relative_to()` instead of prefix string checks:
```python
download_dir_path = Path(get_download_dir(run_id=run_id)).resolve()
file_path = (download_dir_path / filename).resolve()
file_path.relative_to(download_dir_path)
```

- [ ] **Step 4: Return HTTP URLs from local storage**

In `LocalStorage.get_downloaded_files`, preserve checksum and `file_size` from `v1.0.36`, but return:
```python
base = settings.SKYVERN_BASE_URL.rstrip("/")
path = "public/runs" if settings.ENABLE_PUBLIC_RUN_FILE_ENDPOINT else "runs"
url = f"{base}/v1/{path}/{run_id}/files/{quote(file_or_folder)}"
```

- [ ] **Step 5: Test local URL generation and route safety**

Run:
```bash
uv run pytest skyvern/forge/sdk/artifact/storage/test_local_storage.py tests/unit/forge/sdk/test_run_file_download_routes.py -q
```
Expected: local storage returns HTTP URL, route serves a file inside the run download dir, traversal with `../` or encoded separators returns 403 or 404.

- [ ] **Step 6: Commit**

Run:
```bash
git add skyvern/forge/sdk/artifact/storage skyvern/forge/sdk/routes skyvern/config.py tests
git commit -m "[Artifacts] Serve local downloaded files over HTTP"
```

## Task 5: Port Healthcheck and Cleanup

**Files:**
- Create: `skyvern/services/recording_cleanup.py`
- Create or modify: `scripts/healthcheck.py`
- Modify: `skyvern/config.py`
- Modify: `skyvern/forge/api_app.py`
- Modify: `docker-compose.yml`
- Test: create `tests/unit/services/test_recording_cleanup.py`

- [ ] **Step 1: Add cleanup settings**

Add:
```python
RECORDING_CLEANUP_ENABLED: bool = True
RECORDING_CLEANUP_DISK_THRESHOLD_PERCENT: float = 5.0
RECORDING_CLEANUP_RETENTION_DAYS: int = 14
HEALTHCHECK_REQUIRED_FILE: str = "/app/.streamlit/secrets.toml"
```

- [ ] **Step 2: Implement cleanup service**

Port the fork's dataclasses and functions:
```python
DiskSpaceInfo
CleanupResult
HealthStatus
check_disk_space()
cleanup_old_files()
run_cleanup_if_needed()
```

Keep the fork's broadened "all files" cleanup only for explicitly configured cleanup roots. Avoid deleting arbitrary files outside `VIDEO_PATH` and controlled artifact/download directories.

- [ ] **Step 3: Add `/health` endpoint**

In `create_api_app`, add:
```python
@fastapi_app.get("/health", tags=["Health"])
async def healthcheck() -> JSONResponse:
    health = await run_cleanup_if_needed()
    return JSONResponse(status_code=200 if health.status == "healthy" else 503, content=...)
```

Keep `/api/v1/heartbeat` unchanged because `v1.0.36` already uses it as a lightweight liveness route.

- [ ] **Step 4: Add script-based Docker check**

Create `scripts/healthcheck.py` to call `http://localhost:8000/health`.

Update `docker-compose.yml` healthcheck to:
```yaml
healthcheck:
  test: ["CMD", "python", "scripts/healthcheck.py"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 180s
```
Keep the longer `v1.0.36` startup grace period unless testing shows it is no longer needed.

- [ ] **Step 5: Test cleanup**

Run:
```bash
uv run pytest tests/unit/services/test_recording_cleanup.py -q
uv run python -m compileall skyvern/services/recording_cleanup.py skyvern/forge/api_app.py scripts/healthcheck.py
docker compose config
```
Expected: cleanup tests pass, compileall succeeds, compose config validates.

- [ ] **Step 6: Commit**

Run:
```bash
git add skyvern/services skyvern/forge/api_app.py skyvern/config.py scripts/healthcheck.py docker-compose.yml tests
git commit -m "[Health] Add disk-aware healthcheck cleanup"
```

## Task 6: Port LLM Generation Parameters and Safe Token Counter Behavior

**Files:**
- Modify: `skyvern/config.py`
- Modify: `skyvern/schemas/llm.py`
- Modify: `skyvern/forge/sdk/api/llm/api_handler_factory.py`
- Modify: `skyvern/utils/token_counter.py`
- Test: create `tests/unit/test_llm_generation_params.py`

- [ ] **Step 1: Add settings**

Add:
```python
LLM_CONFIG_TOP_P: float | None = None
LLM_CONFIG_TOP_K: int | None = None
LLM_CONFIG_MIN_P: float | None = None
LLM_CONFIG_PRESENCE_PENALTY: float | None = None
LLM_CONFIG_REPETITION_PENALTY: float | None = None
TIKTOKEN_ALLOW_INSECURE_SSL: bool = False
```

- [ ] **Step 2: Add LLM schema fields with lazy defaults**

In `skyvern/schemas/llm.py`, extend the sentinel default pattern used for max tokens and temperature so these fields resolve from settings when config objects are constructed.

Fields:
```python
top_p: float | None
top_k: int | None
min_p: float | None
presence_penalty: float | None
repetition_penalty: float | None
```

- [ ] **Step 3: Pass parameters to LiteLLM**

In `LLMAPIHandlerFactory.get_api_parameters`, include each non-None field:
```python
for key in ("top_p", "top_k", "min_p", "presence_penalty", "repetition_penalty"):
    value = getattr(llm_config, key, None)
    if value is not None:
        params[key] = value
```

For the direct OpenAI-compatible path, pass only OpenAI-supported values:
```python
for key in ("temperature", "top_p", "presence_penalty"):
    if key in active_parameters:
        openai_params[key] = active_parameters[key]
```

- [ ] **Step 4: Replace global SSL disable with explicit opt-in**

Do not globally disable SSL verification unconditionally. If `TIKTOKEN_ALLOW_INSECURE_SSL` is true, apply the fork workaround before resolving `_ENCODING`; otherwise leave `tiktoken` normal.

- [ ] **Step 5: Test LLM parameter behavior**

Run:
```bash
uv run pytest tests/unit/test_llm_generation_params.py tests/unit/test_llm_prompt_config.py tests/unit/test_llm_types_public_shim.py -q
uv run python -m compileall skyvern/schemas/llm.py skyvern/forge/sdk/api/llm/api_handler_factory.py skyvern/utils/token_counter.py
```
Expected: generation parameters appear in `get_api_parameters`; public shim still imports LLM types; token counter imports without changing SSL unless opt-in is enabled.

- [ ] **Step 6: Commit**

Run:
```bash
git add skyvern/config.py skyvern/schemas/llm.py skyvern/forge/sdk/api/llm/api_handler_factory.py skyvern/utils/token_counter.py tests
git commit -m "[LLM] Add configurable generation parameters"
```

## Task 7: Port Operational Wait and Video Directory Tweaks

**Files:**
- Modify: `skyvern/experimentation/wait_utils.py`
- Modify: `skyvern/webeye/browser_factory.py`
- Modify: `skyvern/webeye/real_browser_state.py`
- Test: add focused assertions to existing browser/wait tests if available

- [ ] **Step 1: Make empty page retry wait configurable**

Instead of hard-coding 15 seconds directly, add:
```python
EMPTY_PAGE_RETRY_WAIT_SECONDS: float = 15.0
```
Then use:
```python
wait_seconds = get_wait_time(wait_config, "empty_page_retry_wait", default=settings.EMPTY_PAGE_RETRY_WAIT_SECONDS)
```

- [ ] **Step 2: Ensure video directory exists**

In `BrowserContextFactory.build_browser_args`, preserve `v1.0.36` behavior and add:
```python
os.makedirs(video_dir, exist_ok=True)
LOG.info("Video recording directory configured", video_dir=video_dir, exists=os.path.exists(video_dir))
```

- [ ] **Step 3: Add video path diagnostics**

In `RealBrowserState.set_working_page`, preserve existing behavior and add logging when `page.video` is present or missing.

- [ ] **Step 4: Test operational tweaks**

Run:
```bash
uv run pytest tests/unit/test_real_browser_manager.py tests/unit/test_browser_recording.py -q
uv run python -m compileall skyvern/experimentation/wait_utils.py skyvern/webeye/browser_factory.py skyvern/webeye/real_browser_state.py
```
Expected: no regressions in browser manager/recording tests.

- [ ] **Step 5: Commit**

Run:
```bash
git add skyvern/experimentation/wait_utils.py skyvern/webeye/browser_factory.py skyvern/webeye/real_browser_state.py tests
git commit -m "[Browser] Preserve recording and wait defaults"
```

## Task 8: Final Verification

**Files:**
- All modified files

- [ ] **Step 1: Run targeted backend tests**

Run:
```bash
uv run pytest tests/unit/test_actions.py tests/unit/test_real_browser_manager.py tests/unit/test_browser_recording.py skyvern/forge/sdk/artifact/storage/test_local_storage.py tests/unit/forge/sdk/db/test_workflow_runs_repository.py tests/unit/test_llm_prompt_config.py tests/unit/test_llm_types_public_shim.py -q
```
Expected: all pass.

- [ ] **Step 2: Run new migration and schema sanity checks**

Run:
```bash
uv run alembic heads
uv run python -m compileall skyvern scripts
```
Expected: one Alembic head unless upstream intentionally has multiple heads; compileall succeeds.

- [ ] **Step 3: Run lint on touched Python files**

Run:
```bash
uv run ruff check skyvern scripts tests
```
Expected: no lint errors introduced by migration.

- [ ] **Step 4: Run repository quality check**

Run:
```bash
pre-commit run --all-files
```
Expected: all hooks pass, or failures are fixed and rerun.

- [ ] **Step 5: Review duplicated/native functionality**

Run:
```bash
git grep -n "host_resolver_rules"
git grep -n "ENABLE_PUBLIC_RUN_FILE_ENDPOINT"
git grep -n "LLM_CONFIG_TOP_P"
```
Expected: every new setting has schema, storage, and runtime usage; there are no stale fork-only paths that bypass native `v1.0.36` artifact content handling.

- [ ] **Step 6: Commit final fixes**

Run:
```bash
git status --short
git add .
git commit -m "[Migration] Verify fork features on Skyvern 1.0.36"
```
Only make this commit if verification required fixups after prior feature commits.

## Rollback Strategy

- Host resolver changes are isolated behind nullable columns and optional request/config values. Revert Task 2 commit and downgrade the Alembic migration if needed.
- File upload changes are runtime fallbacks; revert Task 3 if upload behavior regresses.
- Public run file serving is config-gated; disable `ENABLE_PUBLIC_RUN_FILE_ENDPOINT` before reverting code.
- Health cleanup is config-gated; disable `RECORDING_CLEANUP_ENABLED` if healthchecks become expensive or too destructive.
- LLM extra parameters are optional and only included when non-None; clear env vars to restore native behavior.

## Open Decisions Before Execution

- Decide whether fork-compatible no-auth `/v1/public/runs/{run_id}/files/{filename}` must be enabled by default. The safer plan is authenticated by default and public only through `ENABLE_PUBLIC_RUN_FILE_ENDPOINT=true`.
- Decide whether cleanup should delete all old files in artifact paths, as the latest fork commit does, or only video/download temp files. The safer plan scopes deletion to explicit cleanup roots.
- Decide whether to keep the insecure tiktoken SSL workaround as an opt-in escape hatch or solve it purely in Docker/base image CA configuration.

