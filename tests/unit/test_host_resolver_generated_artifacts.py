import inspect
import json
from pathlib import Path

import pytest

from skyvern.client.client import AsyncSkyvern, Skyvern
from skyvern.client.raw_client import AsyncRawSkyvern, RawSkyvern
from skyvern.forge.api_app import create_api_app
from skyvern.library.skyvern import Skyvern as LibrarySkyvern


ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_WITH_HOST_RESOLVER_RULES = {
    "TaskRunRequest",
    "WorkflowRunRequest",
    "WorkflowRun",
    "LoginRequest",
    "DownloadFilesRequest",
}
OPTIONAL_SCHEMAS_WITH_HOST_RESOLVER_RULES = {
    "TaskV2Request",
}
SCHEMAS_WITHOUT_HOST_RESOLVER_RULES = {
    "BrowserSessionResponse",
    "RunSdkActionRequest",
}
STATIC_OPENAPI_PATHS = [
    ROOT / "docs/api-reference/openapi.json",
    ROOT / "fern/openapi/skyvern_openapi.json",
]
TS_FILES_WITH_HOST_RESOLVER_RULES = [
    ROOT / "skyvern-ts/client/src/api/types/TaskRunRequest.ts",
    ROOT / "skyvern-ts/client/src/api/types/WorkflowRunRequest.ts",
    ROOT / "skyvern-ts/client/src/api/types/WorkflowRun.ts",
    ROOT / "skyvern-ts/client/src/api/client/requests/LoginRequest.ts",
    ROOT / "skyvern-ts/client/src/api/client/requests/DownloadFilesRequest.ts",
]


def _schema_has_property(openapi_schema: dict, schema_name: str, property_name: str) -> bool:
    schema = openapi_schema["components"]["schemas"][schema_name]
    return property_name in schema.get("properties", {})


def _schema_exists(openapi_schema: dict, schema_name: str) -> bool:
    return schema_name in openapi_schema["components"]["schemas"]


@pytest.fixture(scope="module")
def live_openapi_schema() -> dict:
    return create_api_app().openapi()


@pytest.mark.parametrize("schema_name", sorted(SCHEMAS_WITH_HOST_RESOLVER_RULES))
def test_static_openapi_matches_live_host_resolver_rules(
    live_openapi_schema: dict,
    schema_name: str,
) -> None:
    assert _schema_has_property(live_openapi_schema, schema_name, "host_resolver_rules")

    for static_openapi_path in STATIC_OPENAPI_PATHS:
        static_schema = json.loads(static_openapi_path.read_text(encoding="utf-8"))
        if schema_name == "WorkflowRun" and not _schema_exists(static_schema, schema_name):
            continue
        assert _schema_has_property(static_schema, schema_name, "host_resolver_rules"), static_openapi_path


@pytest.mark.parametrize("schema_name", sorted(OPTIONAL_SCHEMAS_WITH_HOST_RESOLVER_RULES))
def test_optional_static_openapi_schema_matches_live_host_resolver_rules(
    live_openapi_schema: dict,
    schema_name: str,
) -> None:
    live_schema_exists = _schema_exists(live_openapi_schema, schema_name)
    if live_schema_exists:
        assert _schema_has_property(live_openapi_schema, schema_name, "host_resolver_rules")

    for static_openapi_path in STATIC_OPENAPI_PATHS:
        static_schema = json.loads(static_openapi_path.read_text(encoding="utf-8"))
        static_schema_exists = _schema_exists(static_schema, schema_name)
        assert static_schema_exists is live_schema_exists, static_openapi_path
        if static_schema_exists:
            assert _schema_has_property(static_schema, schema_name, "host_resolver_rules"), static_openapi_path


@pytest.mark.parametrize("schema_name", sorted(SCHEMAS_WITHOUT_HOST_RESOLVER_RULES))
def test_static_openapi_does_not_add_unexposed_host_resolver_rules(
    live_openapi_schema: dict,
    schema_name: str,
) -> None:
    assert not _schema_has_property(live_openapi_schema, schema_name, "host_resolver_rules")

    for static_openapi_path in STATIC_OPENAPI_PATHS:
        static_schema = json.loads(static_openapi_path.read_text(encoding="utf-8"))
        assert not _schema_has_property(static_schema, schema_name, "host_resolver_rules"), static_openapi_path


@pytest.mark.parametrize("ts_file", TS_FILES_WITH_HOST_RESOLVER_RULES)
def test_generated_ts_types_expose_host_resolver_rules(ts_file: Path) -> None:
    assert "host_resolver_rules?: string;" in ts_file.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "client_class,method_name",
    [
        (Skyvern, "login"),
        (Skyvern, "download_files"),
        (RawSkyvern, "login"),
        (RawSkyvern, "download_files"),
        (AsyncSkyvern, "login"),
        (AsyncSkyvern, "download_files"),
        (AsyncRawSkyvern, "login"),
        (AsyncRawSkyvern, "download_files"),
        (LibrarySkyvern, "login"),
    ],
)
def test_generated_python_login_download_methods_expose_host_resolver_rules(
    client_class: type,
    method_name: str,
) -> None:
    signature = inspect.signature(getattr(client_class, method_name))

    assert "host_resolver_rules" in signature.parameters
    if client_class in {RawSkyvern, AsyncRawSkyvern}:
        source = inspect.getsource(getattr(client_class, method_name))
        assert '"host_resolver_rules": host_resolver_rules' in source
