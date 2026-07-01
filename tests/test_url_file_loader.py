import os
import socket

import httpx
import pytest

from app.core.config import settings
from app.services.url_file_loader import UrlFileLoadError, load_url_to_tempfile


class FakeStreamResponse:
    def __init__(self, status_code=200, headers=None, chunks=None, exc=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._chunks = chunks if chunks is not None else [b"%PDF-1.4\n%%EOF"]
        self._exc = exc

    def __enter__(self):
        if self._exc:
            raise self._exc
        return self

    def __exit__(self, *args):
        return False

    def iter_bytes(self, chunk_size=1024 * 1024):
        yield from self._chunks


class FakeClient:
    response = FakeStreamResponse()

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def stream(self, method, url):
        return self.response


@pytest.fixture(autouse=True)
def url_loader_settings(monkeypatch):
    monkeypatch.setattr(settings, "file_url_allowed_hosts", "example.com")
    monkeypatch.setattr(settings, "file_url_allow_private_hosts", False)
    monkeypatch.setattr(settings, "file_url_timeout_seconds", 15)
    monkeypatch.setattr(settings, "file_url_max_redirects", 3)
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, None, None, None, ("93.184.216.34", 443))],
    )
    monkeypatch.setattr("app.services.url_file_loader.httpx.Client", FakeClient)
    FakeClient.response = FakeStreamResponse(headers={"content-type": "application/pdf"})


def assert_url_error(code, fn):
    with pytest.raises(UrlFileLoadError) as exc_info:
        fn()
    assert exc_info.value.code == code


def test_valid_presigned_pdf_url_downloads_to_temp_pdf():
    FakeClient.response = FakeStreamResponse(headers={"content-type": "application/pdf"}, chunks=[b"%PDF-1.4"])
    downloaded = load_url_to_tempfile("https://example.com/report.pdf?X-Amz-Signature=test")
    try:
        assert os.path.exists(downloaded.path)
        assert downloaded.file_name == "report.pdf"
        assert downloaded.file_name.endswith(".pdf")
        assert downloaded.mime_type == "application/pdf"
    finally:
        os.unlink(downloaded.path)


def test_url_without_filename_uses_pdf_extension_from_content_type():
    FakeClient.response = FakeStreamResponse(headers={"content-type": "application/pdf"}, chunks=[b"%PDF-1.4"])
    downloaded = load_url_to_tempfile("https://example.com/download?id=123")
    try:
        assert downloaded.file_name == "downloaded_file.pdf"
        assert downloaded.mime_type == "application/pdf"
    finally:
        os.unlink(downloaded.path)


def test_valid_image_jpeg_url_uses_jpg_extension_and_mime_type():
    FakeClient.response = FakeStreamResponse(headers={"content-type": "image/jpeg"}, chunks=[b"jpeg-bytes"])
    downloaded = load_url_to_tempfile("https://example.com/download?id=456")
    try:
        assert downloaded.file_name.endswith((".jpg", ".jpeg"))
        assert downloaded.mime_type == "image/jpeg"
    finally:
        os.unlink(downloaded.path)


def test_unsupported_scheme_is_rejected():
    assert_url_error("URL_SCHEME_NOT_ALLOWED", lambda: load_url_to_tempfile("file:///etc/passwd"))


@pytest.mark.parametrize(
    "url,expected_codes",
    [
        ("http://localhost/file.pdf", {"URL_PRIVATE_HOST_BLOCKED", "URL_SCHEME_NOT_ALLOWED", "URL_HOST_NOT_ALLOWED"}),
        ("http://127.0.0.1/file.pdf", {"URL_PRIVATE_HOST_BLOCKED", "URL_SCHEME_NOT_ALLOWED"}),
        ("http://169.254.169.254/latest/meta-data", {"URL_PRIVATE_HOST_BLOCKED", "URL_SCHEME_NOT_ALLOWED"}),
    ],
)
def test_localhost_and_private_ips_are_rejected(url, expected_codes, monkeypatch):
    monkeypatch.setattr(settings, "file_url_allowed_hosts", "")
    with pytest.raises(UrlFileLoadError) as exc_info:
        load_url_to_tempfile(url)
    assert exc_info.value.code in expected_codes


def test_non_200_response_raises_download_failed():
    FakeClient.response = FakeStreamResponse(status_code=404, headers={"content-type": "application/pdf"}, chunks=[b"nope"])
    assert_url_error("URL_DOWNLOAD_FAILED", lambda: load_url_to_tempfile("https://example.com/missing.pdf"))


def test_timeout_raises_download_timeout():
    FakeClient.response = FakeStreamResponse(exc=httpx.ReadTimeout("timeout"))
    assert_url_error("URL_DOWNLOAD_TIMEOUT", lambda: load_url_to_tempfile("https://example.com/slow.pdf"))


def test_oversized_download_raises_file_too_large():
    FakeClient.response = FakeStreamResponse(headers={"content-type": "application/pdf"}, chunks=[b"x" * (1024 * 1024 + 1)])
    assert_url_error("URL_FILE_TOO_LARGE", lambda: load_url_to_tempfile("https://example.com/large.pdf"))


def test_empty_response_raises_empty_file():
    FakeClient.response = FakeStreamResponse(headers={"content-type": "application/pdf"}, chunks=[])
    assert_url_error("URL_EMPTY_FILE", lambda: load_url_to_tempfile("https://example.com/empty.pdf"))


def test_unsupported_content_type_raises_content_type_unsupported():
    FakeClient.response = FakeStreamResponse(headers={"content-type": "text/html"}, chunks=[b"<html></html>"])
    assert_url_error("URL_CONTENT_TYPE_UNSUPPORTED", lambda: load_url_to_tempfile("https://example.com/index.html"))
