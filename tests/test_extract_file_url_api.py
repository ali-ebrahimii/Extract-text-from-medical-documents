import uuid

from app.schemas.extraction import ExtractionResponse, ExtractionStatus
from app.services.url_file_loader import DownloadedUrlFile, UrlFileLoadError


class FakePipeline:
    calls = []

    def process(self, inp, debug=False):
        self.calls.append(inp)
        return ExtractionResponse(
            request_id=inp.request_id,
            document_id=inp.document_id,
            status=ExtractionStatus.SUCCESS,
            confidence=0.88,
            extracted_data={"ok": True},
        )


def test_post_extract_file_url_returns_extraction_response_shape(client, monkeypatch, tmp_path):
    temp_file = tmp_path / "download.pdf"
    temp_file.write_bytes(b"%PDF-1.4")

    def fake_load_url_to_tempfile(file_url, file_name=None, mime_type=None):
        return DownloadedUrlFile(str(temp_file), file_name or "download.pdf", mime_type or "application/pdf")

    FakePipeline.calls = []
    monkeypatch.setattr("app.api.routes.extract.load_url_to_tempfile", fake_load_url_to_tempfile)
    monkeypatch.setattr("app.api.routes.extract.ExtractionPipeline", FakePipeline)

    response = client.post(
        "/extract",
        json={"request_id": "req-url-1", "document_id": "doc-url-1", "file_url": "https://example.com/download.pdf"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["request_id"] == "req-url-1"
    assert body["document_id"] == "doc-url-1"
    assert body["status"] == "success"
    assert isinstance(body["quality"], dict)
    assert isinstance(body["ocr"], dict)
    assert isinstance(body["common_fields"], dict)
    assert isinstance(body["extracted_data"], dict)
    assert isinstance(body["errors"], list)
    assert FakePipeline.calls[0].file_name == "download.pdf"
    assert FakePipeline.calls[0].mime_type == "application/pdf"


def test_post_extract_file_url_maps_url_file_load_error(client, monkeypatch):
    def fake_load_url_to_tempfile(*args, **kwargs):
        raise UrlFileLoadError("URL_DOWNLOAD_FAILED", "file_url download failed")

    monkeypatch.setattr("app.api.routes.extract.load_url_to_tempfile", fake_load_url_to_tempfile)

    response = client.post("/extract", json={"request_id": "req-url-2", "file_url": "https://example.com/missing.pdf"})
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "invalid_file"
    assert body["errors"][0]["code"] == "URL_DOWNLOAD_FAILED"
    assert body["errors"][0]["message"] == "file_url download failed"


def test_post_extract_file_url_unexpected_exception_returns_standard_json_without_traceback(client, monkeypatch):
    def fake_load_url_to_tempfile(*args, **kwargs):
        raise RuntimeError("sensitive traceback detail")

    monkeypatch.setattr("app.api.routes.extract.load_url_to_tempfile", fake_load_url_to_tempfile)

    response = client.post("/extract", json={"file_url": "https://example.com/error.pdf"})
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "invalid_file"
    assert body["errors"][0]["code"] == "URL_DOWNLOAD_FAILED"
    assert body["errors"][0]["message"] == "file_url download failed"
    assert "traceback" not in str(body).lower()
    assert "sensitive traceback detail" not in str(body)


def test_post_extract_no_input_returns_invalid_request_with_request_id(client):
    response = client.post("/extract", json={"document_id": "doc-invalid"})
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "invalid_file"
    assert body["errors"][0]["code"] == "INVALID_REQUEST"
    uuid.UUID(body["request_id"])


def test_post_extract_multiple_inputs_returns_invalid_request_preserving_request_id(client):
    response = client.post(
        "/extract",
        json={"request_id": "req-invalid", "file_path": "/tmp/a.pdf", "file_url": "https://example.com/a.pdf"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["request_id"] == "req-invalid"
    assert body["status"] == "invalid_file"
    assert body["errors"][0]["code"] == "INVALID_REQUEST"


def test_post_extract_missing_request_id_generates_uuid_style_request_id(client, monkeypatch, tmp_path):
    temp_file = tmp_path / "download.pdf"
    temp_file.write_bytes(b"%PDF-1.4")

    def fake_load_url_to_tempfile(*args, **kwargs):
        return DownloadedUrlFile(str(temp_file), "download.pdf", "application/pdf")

    FakePipeline.calls = []
    monkeypatch.setattr("app.api.routes.extract.load_url_to_tempfile", fake_load_url_to_tempfile)
    monkeypatch.setattr("app.api.routes.extract.ExtractionPipeline", FakePipeline)

    response = client.post("/extract", json={"file_url": "https://example.com/download.pdf"})
    body = response.json()

    assert response.status_code == 200
    uuid.UUID(body["request_id"])
    assert body["request_id"]
