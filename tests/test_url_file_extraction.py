import socket

import httpx
import pytest

from app.core.config import settings
from app.schemas.extraction import ExtractionResponse, ExtractionStatus


class FakeStreamResponse:
    def __init__(self, status_code=200, headers=None, chunks=None, exc=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._chunks = chunks or []
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
    response = FakeStreamResponse(chunks=[b"%PDF-1.4\n%%EOF"])
    requested_urls = []

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def stream(self, method, url):
        self.requested_urls.append(url)
        return self.response


class FakePipeline:
    calls = []

    def process(self, inp, debug=False):
        self.calls.append(inp)
        return ExtractionResponse(request_id=inp.request_id, document_id=inp.document_id, status=ExtractionStatus.SUCCESS)


@pytest.fixture(autouse=True)
def url_test_settings(monkeypatch):
    monkeypatch.setattr(settings, "file_url_allowed_hosts", "example.com")
    monkeypatch.setattr(settings, "file_url_allow_private_hosts", False)
    monkeypatch.setattr(settings, "file_url_timeout_seconds", 15)
    monkeypatch.setattr(settings, "file_url_max_redirects", 3)
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, None, None, None, ("93.184.216.34", 443))])
    FakeClient.response = FakeStreamResponse(headers={"content-type": "application/pdf"}, chunks=[b"%PDF-1.4\n%%EOF"])
    FakeClient.requested_urls = []
    FakePipeline.calls = []


def patch_url_route(monkeypatch):
    monkeypatch.setattr("app.services.url_file_loader.httpx.Client", FakeClient)
    monkeypatch.setattr("app.api.routes.extract.ExtractionPipeline", FakePipeline)


def test_valid_pdf_url_downloads_and_calls_pipeline(client, monkeypatch):
    patch_url_route(monkeypatch)
    r = client.post("/extract", json={"request_id": "req-1", "document_id": "doc-1", "file_url": "https://example.com/report.pdf", "file_name": "report.pdf", "mime_type": "application/pdf"})
    assert r.status_code == 200
    assert r.json()["status"] == "success"
    assert FakePipeline.calls[0].file_name == "report.pdf"
    assert FakePipeline.calls[0].mime_type == "application/pdf"


def test_valid_jpg_url_uses_image_jpeg(client, monkeypatch):
    patch_url_route(monkeypatch)
    FakeClient.response = FakeStreamResponse(headers={"content-type": "image/jpg"}, chunks=[b"jpgbytes"])
    r = client.post("/extract", json={"request_id": "req-2", "file_url": "https://example.com/image.jpg"})
    assert r.status_code == 200
    assert FakePipeline.calls[0].file_name == "image.jpg"
    assert FakePipeline.calls[0].mime_type == "image/jpeg"


def test_url_no_filename_content_type_pdf_gets_pdf_extension(client, monkeypatch):
    patch_url_route(monkeypatch)
    FakeClient.response = FakeStreamResponse(headers={"content-type": "application/pdf"}, chunks=[b"%PDF-1.4\n%%EOF"])
    r = client.post("/extract", json={"file_url": "https://example.com"})
    assert r.status_code == 200
    assert r.json()["status"] == "success"
    assert FakePipeline.calls[0].file_name == "downloaded_file.pdf"
    assert FakePipeline.calls[0].mime_type == "application/pdf"


def test_url_download_path_content_type_jpeg_gets_jpg_extension(client, monkeypatch):
    patch_url_route(monkeypatch)
    FakeClient.response = FakeStreamResponse(headers={"content-type": "image/jpeg"}, chunks=[b"jpgbytes"])
    r = client.post("/extract", json={"file_url": "https://example.com/download?id=1"})
    assert r.status_code == 200
    assert FakePipeline.calls[0].file_name == "downloaded_file.jpg"
    assert FakePipeline.calls[0].mime_type == "image/jpeg"


def test_provided_file_name_without_extension_uses_mime_extension(client, monkeypatch):
    patch_url_route(monkeypatch)
    FakeClient.response = FakeStreamResponse(headers={"content-type": "application/octet-stream"}, chunks=[b"%PDF-1.4\n%%EOF"])
    r = client.post("/extract", json={"file_url": "https://example.com/blob", "file_name": "report", "mime_type": "application/pdf"})
    assert r.status_code == 200
    assert FakePipeline.calls[0].file_name == "report.pdf"
    assert FakePipeline.calls[0].mime_type == "application/pdf"


def test_unsupported_scheme_is_rejected(client):
    r = client.post("/extract", json={"file_url": "file:///etc/passwd"})
    body = r.json()
    assert body["status"] == "invalid_file"
    assert body["errors"][0]["code"] == "URL_SCHEME_NOT_ALLOWED"


def test_localhost_private_ip_url_is_rejected(client):
    r = client.post("/extract", json={"file_url": "https://127.0.0.1/report.pdf"})
    assert r.json()["errors"][0]["code"] == "URL_PRIVATE_HOST_BLOCKED"


def test_non_200_response_returns_download_failed(client, monkeypatch):
    patch_url_route(monkeypatch)
    FakeClient.response = FakeStreamResponse(status_code=404, headers={"content-type": "application/pdf"}, chunks=[b"nope"])
    r = client.post("/extract", json={"file_url": "https://example.com/missing.pdf"})
    assert r.json()["errors"][0]["code"] == "URL_DOWNLOAD_FAILED"


def test_timeout_returns_download_timeout(client, monkeypatch):
    patch_url_route(monkeypatch)
    FakeClient.response = FakeStreamResponse(exc=httpx.ReadTimeout("timeout"))
    r = client.post("/extract", json={"file_url": "https://example.com/slow.pdf"})
    assert r.json()["errors"][0]["code"] == "URL_DOWNLOAD_TIMEOUT"


def test_file_larger_than_max_upload_returns_too_large(client, monkeypatch):
    patch_url_route(monkeypatch)
    FakeClient.response = FakeStreamResponse(headers={"content-type": "application/pdf"}, chunks=[b"x" * (1024 * 1024 + 1)])
    r = client.post("/extract", json={"file_url": "https://example.com/large.pdf"})
    assert r.json()["errors"][0]["code"] == "URL_FILE_TOO_LARGE"


def test_missing_file_name_uses_url_path_filename(client, monkeypatch):
    patch_url_route(monkeypatch)
    r = client.post("/extract", json={"file_url": "https://example.com/reports/path-name.pdf?sig=1"})
    assert r.status_code == 200
    assert FakePipeline.calls[0].file_name == "path-name.pdf"


def test_invalid_request_with_multiple_inputs_returns_invalid_request(client, tmp_path):
    p = tmp_path / "x.pdf"
    p.write_bytes(b"%PDF")
    r = client.post("/extract", json={"request_id": "bad-1", "file_url": "https://example.com/a.pdf", "file_path": str(p)})
    body = r.json()
    assert r.status_code == 200
    assert body["request_id"] == "bad-1"
    assert body["errors"][0]["code"] == "INVALID_REQUEST"


def test_invalid_request_with_no_input_returns_invalid_request(client):
    r = client.post("/extract", json={"request_id": "bad-2"})
    body = r.json()
    assert r.status_code == 200
    assert body["request_id"] == "bad-2"
    assert body["errors"][0]["code"] == "INVALID_REQUEST"
