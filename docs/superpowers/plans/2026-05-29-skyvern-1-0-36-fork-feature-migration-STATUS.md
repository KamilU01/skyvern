# Skyvern 1.0.36 — Fork Feature Migration: Status Report

**Branch:** `codex/migrate-fork-features-to-1.0.36` (based on `v1.0.36`, commit `db3a30852`)
**Fork source:** `v1.0.7_2` (commit `63565e23d`) = upstream `v1.0.7` + 9 fork commits
**Date:** 2026-05-29

This report documents the migration of every fork-only feature (introduced between tag `v1.0.7`
and the fork tip `v1.0.7_2`) onto upstream `v1.0.36`. Each feature was independently checked for
native presence in `v1.0.36` before porting.

---

## Summary table

| # | Feature | Native in 1.0.36? | Action taken | Status |
|---|---------|-------------------|--------------|--------|
| 1 | Host resolver rules (per-run + global DNS) | No | Migrated in prior session (commits `73fc8cad6` + `dev`) | ✅ Done (verified, no gaps) |
| 2 | File-URL inference + upload fallbacks | Partial (URL recovery + child-input lookup exist) | Ported additive parts only | ✅ Done |
| 3 | `terminate_criterion` prompt guidance | Infra yes, prompt text no | Ported prompt edits (static+dynamic+full kept consistent) | ✅ Done |
| 4 | Downloaded files over HTTP + run file endpoints | Partial (signed-artifact infra exists; local still `file://`) | Ported, **config-gated** + hardened traversal check | ✅ Done (adapted) |
| 5 | `/health` endpoint + recording/disk cleanup | Partial (`/heartbeat` + temp cleanup only) | Ported, scoped deletion to controlled roots, config-gated | ✅ Done (adapted) |
| 6 | Configurable LLM generation params | No | Ported to the v1.0.36 lazy-sentinel schema pattern | ✅ Done |
| 6b| tiktoken insecure-SSL workaround | No | Ported as **opt-in** (`TIKTOKEN_ALLOW_INSECURE_SSL`, default off) | ✅ Done (adapted) |
| 6c| Local artifact share link (`artifact.uri`) | **Yes (already native)** | Skipped — no work needed | ✅ Native |
| 7 | `empty_page_retry_wait` default 3→15s | No | Ported as config setting `EMPTY_PAGE_RETRY_WAIT_SECONDS` | ✅ Done (improved) |
| 7b| Video dir creation + diagnostics | No | Ported | ✅ Done |

All fork features are now present on the migration branch. Nothing was dropped; the only item not
re-implemented (local share link) was already native in `v1.0.36`.

---

## Feature detail

### 1. Host resolver rules — already migrated (verified)
Migrated by the prior session across config, schemas, DB models + Alembic migration
(`8c2b0a2f1d9e`), repositories, routes, services, browser launch (`_build_host_resolver_rules`),
SDK clients, TS client, and OpenAPI. Independent end-to-end re-verification found **no gaps**.
Regression tests (`test_host_resolver_generated_artifacts`, `test_run_blocks_host_resolver_rules`,
`test_task_v2_host_resolver_request`, `test_real_browser_manager`) still pass.

### 2. File-URL inference + upload fallbacks (fork `332dfe32a`)
- `skyvern/webeye/actions/parse_actions.py`: added `FILE_EXTENSIONS`, `extract_file_urls_from_text`,
  `parse_attached_files`, `parse_inline_file_references`, `find_matching_file_url`, and a post-parse
  injection pass that fills `file_url` on `ClickAction`/`UploadFileAction` from the task text.
- `skyvern/webeye/utils/dom.py`: added `SkyvernElement.find_nearby_file_input` (parent/sibling search, ≤3 levels).
- `skyvern/webeye/actions/handler.py`: nearby-input lookup + `input`/`change` event dispatch after
  `set_input_files` in `handle_upload_file_action`; direct-upload fallback in `chain_click` before
  `WrongElementToUploadFile`.
- Native `v1.0.36` URL recovery (`_find_similar_url_in_text`) and `find_file_input_in_children` were
  **preserved** — the fork logic is purely additive (task-text parsing, which 1.0.36 lacked).
- Tests: `tests/unit/test_parse_actions_file_urls.py` (new, 11 tests).

### 3. `terminate_criterion` prompt guidance (fork `332dfe32a`)
- `extract-action-dynamic.j2`, `extract-action.j2`: render a `Terminate criterion:` block when set.
- `extract-action-static.j2`, `extract-action.j2`: `TERMINATE` action doc now references the
  terminate criterion conditionally. Native `KEYPRESS`/`SCROLL`/`CLOSE_PAGE` guidance preserved.
- The static-prefix / dynamic-suffix consistency required by `prompts/skyvern/CLAUDE.md` was
  verified (static = first 56 lines of full; dynamic = last 52 lines). Jinja render verified with
  and without the variable.

### 4. Downloaded files over HTTP + run file endpoints (fork `6bb6c7c61`)  — adapted
- `skyvern/forge/sdk/artifact/storage/local.py`: `get_downloaded_files` returns the public HTTP URL
  **only when `ENABLE_PUBLIC_RUN_FILE_ENDPOINT=true`**, otherwise the native `file://` URI. Filename
  is `quote()`-escaped. Checksum/`file_size` preserved.
- `skyvern/forge/sdk/routes/agent_protocol.py`: added `GET /v1/runs/{run_id}/files/{filename}`
  (authenticated) and `GET /v1/public/runs/{run_id}/files/{filename}` (no-auth, returns 404 unless
  the flag is enabled). Shared helper `_resolve_run_file_path` rejects traversal using
  `os.path.realpath` + `os.path.commonpath` (avoids the `startswith` prefix pitfall).
- **Security decision:** the public no-auth endpoint is **off by default**. Setting
  `ENABLE_PUBLIC_RUN_FILE_ENDPOINT=true` restores the fork's original always-public behavior.
- Tests: `tests/unit/forge/sdk/test_run_file_download_routes.py` (new) and a new
  `TestLocalStorageDownloadedFiles` class in `test_local_storage.py`.

### 5. `/health` endpoint + recording/disk cleanup (fork `d0107ef52` + `0b93c6471`) — adapted
- New `skyvern/services/recording_cleanup.py` (ported verbatim from the fork's final state, incl. the
  broadened "all files" cleanup). **Deletion is strictly scoped to `VIDEO_PATH` and
  `ARTIFACT_STORAGE_PATH`** — no files outside those configured roots are ever touched.
- `skyvern/forge/api_app.py`: new `GET /health` that runs disk checks + conditional cleanup; native
  `/api/v1/heartbeat` left untouched.
- `scripts/healthcheck.py` (new) + `docker-compose.yml` healthcheck now calls it. The longer
  `start_period: 180s` from 1.0.36 was kept.
- Config (all gated): `RECORDING_CLEANUP_ENABLED` (default true), `RECORDING_CLEANUP_DISK_THRESHOLD_PERCENT`
  (5.0), `RECORDING_CLEANUP_RETENTION_DAYS` (14), `HEALTHCHECK_REQUIRED_FILE`.
- Tests: `tests/unit/services/test_recording_cleanup.py` (new, 9 tests).

### 6. LLM generation params + token counter (fork `63565e23d` + `332dfe32a`)
- `skyvern/config.py`: `LLM_CONFIG_TOP_P/TOP_K/MIN_P/PRESENCE_PENALTY/REPETITION_PENALTY` (all `None`).
- `skyvern/schemas/llm.py`: added the five fields to `LLMConfig` and `LLMRouterConfig` using the
  **existing lazy-sentinel pattern** (`_resolve_generation_defaults` was generalized to a field→setting
  map). Adapting to 1.0.36's frozen-dataclass schema was the main divergence from the fork.
- `api_handler_factory.get_api_parameters`: forwards each param to LiteLLM only when non-None; the
  OpenAI-compatible path forwards `top_p`/`presence_penalty`.
- `skyvern/utils/token_counter.py`: SSL workaround is now **opt-in** via `TIKTOKEN_ALLOW_INSECURE_SSL`
  (default off) — the fork's unconditional global SSL disable was intentionally **not** carried over.
- Local artifact share link is already native in 1.0.36 → skipped.
- Tests: `tests/unit/test_llm_generation_params.py` (new, 4 tests).

### 7. Operational tweaks (fork `332dfe32a` + `cc8c206ed`)
- `EMPTY_PAGE_RETRY_WAIT_SECONDS` config setting (15.0) used by `wait_utils.empty_page_retry_wait`
  (fork hard-coded 15; made configurable).
- `browser_factory.build_browser_args`: `os.makedirs(video_dir, exist_ok=True)` + log.
- `real_browser_state.set_working_page`: video-path diagnostics added to both code paths.

---

## Verification

- `ruff check` on all changed files — **passed**.
- `ruff format` — applied (2 files), all formatted.
- `python -m compileall skyvern scripts` — **passed**.
- `alembic heads` — single head `8c2b0a2f1d9e` (no new migration added; host-resolver migration intact).
- Targeted + regression unit tests — **all green** (new feature tests, host-resolver suite, prompt
  render, action handler).
- `mypy` — **not installed in this environment**; could not run. Type-sensitive changes (`schemas/llm.py`,
  `token_counter.py`) compile and pass ruff. Run `mypy skyvern` in a dev env with the type-check extra
  before merge.

### Pre-existing failures (NOT caused by this migration)
Confirmed by re-running on the pre-migration baseline (`git stash`) — identical failures:
- `tests/unit/test_api_handler_factory.py` (5) + `test_api_handler_cached_content_fix.py` (1): the test
  mocks `litellm.completion_cost` with a signature the installed litellm no longer uses
  (`completion_response` kwarg). litellm version mismatch in the local env.
- `tests/unit/test_real_browser_manager.py` (2, ffmpeg video artifacts) and
  `tests/unit/test_download_file_action_handler.py` (1, file-write-error): environment-specific.
- `test_local_storage.py::TestLocalStorageBuildURIs` (6): Windows replaces `:` with `-` in artifact
  timestamps (`_safe_timestamp`), so these Linux-oriented assertions fail on Windows. Untouched code.

---

## Configuration knobs added (all default to safe/native behavior)

| Setting | Default | Effect |
|---|---|---|
| `ENABLE_PUBLIC_RUN_FILE_ENDPOINT` | `false` | Enables no-auth public file URLs + HTTP URLs from `get_downloaded_files` |
| `RECORDING_CLEANUP_ENABLED` | `true` | Disk cleanup on `/health` when below threshold |
| `RECORDING_CLEANUP_DISK_THRESHOLD_PERCENT` | `5.0` | Free-space % that triggers cleanup |
| `RECORDING_CLEANUP_RETENTION_DAYS` | `14` | Age cutoff for phase-1 cleanup |
| `HEALTHCHECK_REQUIRED_FILE` | `/app/.streamlit/secrets.toml` | File whose absence marks unhealthy ("" disables) |
| `LLM_CONFIG_TOP_P/TOP_K/MIN_P/PRESENCE_PENALTY/REPETITION_PENALTY` | `None` | Optional sampling params |
| `TIKTOKEN_ALLOW_INSECURE_SSL` | `false` | Opt-in TLS-verification disable for tiktoken download |
| `EMPTY_PAGE_RETRY_WAIT_SECONDS` | `15.0` | Wait before retrying an empty-page scrape |

## Notes / open items
- The working tree changes are **not yet committed**. Suggested per-feature commits mirror the plan
  (Tasks 3–7).
- Decide whether `ENABLE_PUBLIC_RUN_FILE_ENDPOINT` and the broadened cleanup scope should be enabled
  by default for this deployment (currently safe-by-default).
- Run `mypy skyvern` in CI / a dev environment before merging.
