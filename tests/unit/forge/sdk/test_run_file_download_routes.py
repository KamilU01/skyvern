from __future__ import annotations

import os

import pytest
from fastapi import HTTPException

from skyvern.forge.sdk.api.files import get_download_dir
from skyvern.forge.sdk.routes.agent_protocol import _resolve_run_file_path


def test_resolve_run_file_path_returns_valid_file() -> None:
    run_id = "test_resolve_valid"
    download_dir = get_download_dir(run_id=run_id)
    os.makedirs(download_dir, exist_ok=True)
    file_path = os.path.join(download_dir, "ok.txt")
    with open(file_path, "wb") as f:
        f.write(b"hello")
    try:
        resolved = _resolve_run_file_path(run_id, "ok.txt")
        assert os.path.realpath(resolved) == os.path.realpath(file_path)
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


def test_resolve_run_file_path_rejects_traversal() -> None:
    run_id = "test_resolve_traversal"
    os.makedirs(get_download_dir(run_id=run_id), exist_ok=True)
    with pytest.raises(HTTPException) as exc_info:
        _resolve_run_file_path(run_id, "../../etc/passwd")
    assert exc_info.value.status_code == 403


def test_resolve_run_file_path_missing_file() -> None:
    run_id = "test_resolve_missing"
    os.makedirs(get_download_dir(run_id=run_id), exist_ok=True)
    with pytest.raises(HTTPException) as exc_info:
        _resolve_run_file_path(run_id, "does_not_exist.pdf")
    assert exc_info.value.status_code == 404
