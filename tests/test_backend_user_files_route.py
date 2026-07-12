import os
import tempfile

from app.schemas.extraction import ExtractionResponse, ExtractionStatus
from app.services.backend_file_client import DownloadedBackendFile, BackendFileClientError


def ok_response(request_id='req-123', document_id='doc'):
    return ExtractionResponse(request_id=request_id, document_id=document_id, status=ExtractionStatus.SUCCESS, document_type='lab')


def test_extract_user_files_all_succeed(client, monkeypatch):
    paths = []
    class FakeBackend:
        def list_user_files(self, user_id):
            from app.schemas.extraction import BackendFileDescriptor
            return [BackendFileDescriptor(file_name='a.pdf', document_id='doc-a'), BackendFileDescriptor(file_name='b.pdf', document_id='doc-b')]
        def fetch_file_to_tempfile(self, user_id, descriptor):
            fd, path = tempfile.mkstemp(suffix='.pdf'); os.close(fd); paths.append(path)
            return DownloadedBackendFile(path, descriptor.file_name, 'application/pdf', descriptor.document_id)
    def fake_process(self, inp, debug=False):
        return ok_response(inp.request_id, inp.document_id)
    monkeypatch.setattr('app.api.routes.extract.BackendFileClient', FakeBackend)
    monkeypatch.setattr('app.api.routes.extract.ExtractionPipeline.process', fake_process)
    r = client.post('/extract/user-files', json={'request_id': 'req-123', 'user_id': 'user-1'})
    body = r.json()
    assert r.status_code == 200
    assert body['status'] == 'success'
    assert body['processed_files'] == 2
    assert all(not os.path.exists(p) for p in paths)


def test_extract_user_files_partial_success(client, monkeypatch):
    class FakeBackend:
        def list_user_files(self, user_id):
            from app.schemas.extraction import BackendFileDescriptor
            return [BackendFileDescriptor(file_name='a.pdf'), BackendFileDescriptor(file_name='b.pdf')]
        def fetch_file_to_tempfile(self, user_id, descriptor):
            if descriptor.file_name == 'b.pdf':
                raise BackendFileClientError('BACKEND_FETCH_FILE_FAILED', 'failed')
            fd, path = tempfile.mkstemp(suffix='.pdf'); os.close(fd)
            return DownloadedBackendFile(path, descriptor.file_name, 'application/pdf', descriptor.document_id)
    monkeypatch.setattr('app.api.routes.extract.BackendFileClient', FakeBackend)
    monkeypatch.setattr('app.api.routes.extract.ExtractionPipeline.process', lambda self, inp, debug=False: ok_response(inp.request_id, inp.document_id))
    body = client.post('/extract/user-files', json={'user_id': 'user-1'}).json()
    assert body['status'] == 'partial_success'
    assert body['processed_files'] == 1
    assert body['failed_files'] == 1


def test_extract_user_files_all_fail(client, monkeypatch):
    class FakeBackend:
        def list_user_files(self, user_id):
            from app.schemas.extraction import BackendFileDescriptor
            return [BackendFileDescriptor(file_name='a.pdf')]
        def fetch_file_to_tempfile(self, user_id, descriptor):
            raise BackendFileClientError('BACKEND_FETCH_FILE_FAILED', 'failed')
    monkeypatch.setattr('app.api.routes.extract.BackendFileClient', FakeBackend)
    body = client.post('/extract/user-files', json={'user_id': 'user-1'}).json()
    assert body['status'] == 'failed'
    assert body['processed_files'] == 0
    assert body['failed_files'] == 1


def test_extract_user_files_temp_files_deleted(client, monkeypatch):
    created = []
    class FakeBackend:
        def list_user_files(self, user_id):
            from app.schemas.extraction import BackendFileDescriptor
            return [BackendFileDescriptor(file_name='a.pdf')]
        def fetch_file_to_tempfile(self, user_id, descriptor):
            fd, path = tempfile.mkstemp(suffix='.pdf'); os.close(fd); created.append(path)
            return DownloadedBackendFile(path, descriptor.file_name, 'application/pdf')
    monkeypatch.setattr('app.api.routes.extract.BackendFileClient', FakeBackend)
    monkeypatch.setattr('app.api.routes.extract.ExtractionPipeline.process', lambda self, inp, debug=False: ok_response(inp.request_id, inp.document_id))
    client.post('/extract/user-files', json={'user_id': 'user-1'})
    assert created and not os.path.exists(created[0])


def test_existing_extract_endpoint_still_works(client, tmp_path, monkeypatch):
    p = tmp_path / 'x.pdf'
    p.write_bytes(b'%PDF-1.4')
    monkeypatch.setattr('app.api.routes.extract.ExtractionPipeline.process', lambda self, inp, debug=False: ok_response(inp.request_id, inp.document_id))
    r = client.post('/extract', json={'document_id': 'doc-x', 'file_path': str(p), 'file_name': 'x.pdf', 'mime_type': 'application/pdf'})
    assert r.status_code == 200
    assert r.json()['document_id'] == 'doc-x'
