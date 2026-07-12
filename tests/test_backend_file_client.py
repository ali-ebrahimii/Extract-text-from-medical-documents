import base64
import os

import httpx
import pytest

from app.core.config import settings
from app.schemas.extraction import BackendFileDescriptor
from app.services import backend_file_client as mod
from app.services.backend_file_client import BackendFileClient, BackendFileClientError


class FakeStream:
    def __init__(self, response): self.response = response
    def __enter__(self): return self.response
    def __exit__(self, *args): return False


class FakeClient:
    get_response = None
    stream_response = None
    last_url = None
    def __init__(self, *args, **kwargs): pass
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def get(self, url, headers=None):
        FakeClient.last_url = url
        return FakeClient.get_response
    def stream(self, method, url, headers=None):
        FakeClient.last_url = url
        return FakeStream(FakeClient.stream_response)


def resp(status=200, content=b'', json_data=None, headers=None):
    request = httpx.Request('GET', 'https://backend.test/file')
    if json_data is not None:
        import json
        content = json.dumps(json_data).encode()
        headers = {'content-type': 'application/json', **(headers or {})}
    return httpx.Response(status, content=content, headers=headers or {}, request=request)


@pytest.fixture(autouse=True)
def fake_http(monkeypatch):
    monkeypatch.setattr(mod.httpx, 'Client', FakeClient)
    monkeypatch.setattr(settings, 'backend_file_list_url_template', 'https://backend.test/users/{user_id}/files')
    monkeypatch.setattr(settings, 'backend_file_fetch_url_template', 'https://backend.test/users/{user_id}/files/{file_name}')
    monkeypatch.setattr(settings, 'backend_api_token', '')
    monkeypatch.setattr(settings, 'backend_api_max_files', 50)
    monkeypatch.setattr(settings, 'backend_api_file_response_mode', 'auto')
    monkeypatch.setattr(settings, 'max_upload_mb', 20)


def test_list_user_files_string_array():
    FakeClient.get_response = resp(json_data=['lab1.pdf', 'image1.jpg'])
    files = BackendFileClient().list_user_files('user 1')
    assert [f.file_name for f in files] == ['lab1.pdf', 'image1.jpg']


def test_list_user_files_object_array():
    FakeClient.get_response = resp(json_data=[{'file_name': 'lab1.pdf', 'document_id': 'doc-1', 'mime_type': 'application/pdf', 'size_bytes': 12345}])
    files = BackendFileClient().list_user_files('user-1')
    assert files[0].document_id == 'doc-1'
    assert files[0].mime_type == 'application/pdf'


def test_list_user_files_non_200():
    FakeClient.get_response = resp(status=500, json_data={'error': 'bad'})
    with pytest.raises(BackendFileClientError) as exc:
        BackendFileClient().list_user_files('user-1')
    assert exc.value.code == 'BACKEND_LIST_FILES_FAILED'


def test_list_user_files_invalid_json():
    FakeClient.get_response = resp(content=b'not json')
    with pytest.raises(BackendFileClientError) as exc:
        BackendFileClient().list_user_files('user-1')
    assert exc.value.code == 'BACKEND_LIST_FILES_INVALID_RESPONSE'


def test_list_user_files_too_many(monkeypatch):
    monkeypatch.setattr(settings, 'backend_api_max_files', 1)
    FakeClient.get_response = resp(json_data=['a.pdf', 'b.pdf'])
    with pytest.raises(BackendFileClientError) as exc:
        BackendFileClient().list_user_files('user-1')
    assert exc.value.code == 'BACKEND_TOO_MANY_FILES'


def test_fetch_binary_pdf_response():
    FakeClient.stream_response = resp(content=b'%PDF data', headers={'content-type': 'application/pdf'})
    downloaded = BackendFileClient().fetch_file_to_tempfile('user-1', BackendFileDescriptor(file_name='report name.pdf'))
    try:
        assert os.path.exists(downloaded.path)
        assert open(downloaded.path, 'rb').read() == b'%PDF data'
        assert downloaded.mime_type == 'application/pdf'
        assert FakeClient.last_url.endswith('/report%20name.pdf')
    finally:
        os.unlink(downloaded.path)


def test_fetch_binary_jpg_response():
    FakeClient.stream_response = resp(content=b'jpgdata', headers={'content-type': 'image/jpeg'})
    downloaded = BackendFileClient().fetch_file_to_tempfile('user-1', BackendFileDescriptor(file_name='image.jpg'))
    try:
        assert downloaded.mime_type == 'image/jpeg'
    finally:
        os.unlink(downloaded.path)


def test_fetch_json_file_url(monkeypatch, tmp_path):
    p = tmp_path / 'url.pdf'
    p.write_bytes(b'pdf')
    def fake_load(url, file_name=None, mime_type=None):
        from app.services.url_file_loader import DownloadedUrlFile
        return DownloadedUrlFile(str(p), file_name or 'url.pdf', mime_type or 'application/pdf')
    monkeypatch.setattr(mod, 'load_url_to_tempfile', fake_load)
    FakeClient.stream_response = resp(json_data={'file_url': 'https://storage.test/url.pdf', 'file_name': 'url.pdf', 'mime_type': 'application/pdf'})
    downloaded = BackendFileClient().fetch_file_to_tempfile('user-1', BackendFileDescriptor(file_name='x.pdf'))
    assert downloaded.path == str(p)


def test_fetch_json_base64_response():
    FakeClient.stream_response = resp(json_data={'base64_content': base64.b64encode(b'hello').decode(), 'file_name': 'x.pdf', 'mime_type': 'application/pdf'})
    downloaded = BackendFileClient().fetch_file_to_tempfile('user-1', BackendFileDescriptor(file_name='x.pdf'))
    try:
        assert open(downloaded.path, 'rb').read() == b'hello'
    finally:
        os.unlink(downloaded.path)


def test_fetch_non_200_response():
    FakeClient.stream_response = resp(status=404, content=b'no')
    with pytest.raises(BackendFileClientError) as exc:
        BackendFileClient().fetch_file_to_tempfile('user-1', BackendFileDescriptor(file_name='x.pdf'))
    assert exc.value.code == 'BACKEND_FETCH_FILE_FAILED'


def test_fetch_oversized_file(monkeypatch):
    monkeypatch.setattr(settings, 'max_upload_mb', 0)
    FakeClient.stream_response = resp(content=b'too large')
    with pytest.raises(BackendFileClientError) as exc:
        BackendFileClient().fetch_file_to_tempfile('user-1', BackendFileDescriptor(file_name='x.pdf'))
    assert exc.value.code == 'BACKEND_FETCH_FILE_TOO_LARGE'


def test_fetch_empty_file_response():
    FakeClient.stream_response = resp(content=b'')
    with pytest.raises(BackendFileClientError) as exc:
        BackendFileClient().fetch_file_to_tempfile('user-1', BackendFileDescriptor(file_name='x.pdf'))
    assert exc.value.code == 'BACKEND_FETCH_FILE_EMPTY'
