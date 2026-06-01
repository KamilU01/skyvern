from __future__ import annotations

from types import SimpleNamespace

from skyvern.webeye.actions.parse_actions import (
    extract_file_urls_from_text,
    find_matching_file_url,
    parse_attached_files,
    parse_inline_file_references,
)


def test_parse_attached_files_section_format() -> None:
    text = "Attached files:\n- resume.pdf: https://example.com/resume.pdf\n- data.csv: https://example.com/data.csv"
    result = parse_attached_files(text)
    assert result == {
        "resume.pdf": "https://example.com/resume.pdf",
        "data.csv": "https://example.com/data.csv",
    }


def test_parse_attached_files_dash_separator() -> None:
    text = "- report.xlsx - https://example.com/report.xlsx"
    assert parse_attached_files(text) == {"report.xlsx": "https://example.com/report.xlsx"}


def test_parse_inline_file_references() -> None:
    text = "Upload the [resume.pdf](https://example.com/resume.pdf) file to the form"
    assert parse_inline_file_references(text) == {"resume.pdf": "https://example.com/resume.pdf"}


def test_extract_file_urls_from_text() -> None:
    text = "Please upload https://example.com/resume.pdf to the form"
    assert extract_file_urls_from_text(text) == ["https://example.com/resume.pdf"]


def test_extract_file_urls_ignores_non_file_urls() -> None:
    text = "Go to https://example.com/page and click submit"
    assert extract_file_urls_from_text(text) == []


def test_extract_file_urls_strips_trailing_punctuation() -> None:
    text = "Upload https://example.com/resume.pdf."
    assert extract_file_urls_from_text(text) == ["https://example.com/resume.pdf"]


def test_empty_inputs() -> None:
    assert parse_attached_files(None) == {}
    assert parse_attached_files("") == {}
    assert parse_inline_file_references(None) == {}
    assert parse_inline_file_references("") == {}
    assert extract_file_urls_from_text(None) == []
    assert extract_file_urls_from_text("") == []


def test_find_matching_file_url_by_filename_mention() -> None:
    files = {
        "resume.pdf": "https://example.com/resume.pdf",
        "contract.pdf": "https://example.com/contract.pdf",
    }
    action = SimpleNamespace(response=None, reasoning="upload the contract document", intention=None)
    # Matched by mention of "contract", not by dict order.
    assert find_matching_file_url(action, files, set()) == "https://example.com/contract.pdf"


def test_find_matching_file_url_fallback_first_unused() -> None:
    files = {"xyz123.pdf": "https://example.com/xyz123.pdf"}
    action = SimpleNamespace(response=None, reasoning="click the submit button", intention=None)
    assert find_matching_file_url(action, files, set()) == "https://example.com/xyz123.pdf"


def test_find_matching_file_url_skips_used() -> None:
    files = {"only.pdf": "https://example.com/only.pdf"}
    action = SimpleNamespace(response=None, reasoning="upload the only file", intention=None)
    assert find_matching_file_url(action, files, {"only.pdf"}) is None


def test_find_matching_file_url_empty() -> None:
    action = SimpleNamespace(response=None, reasoning="upload", intention=None)
    assert find_matching_file_url(action, {}, set()) is None
