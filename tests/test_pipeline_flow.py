import hashlib
from pathlib import Path
import fitz
import cv2, numpy as np

from app.core.config import settings
from app.models.document import MedicalDocument
from app.services.pipeline_service import PipelineService
from app.services.preprocessing_service import PreprocessingService, PreprocessingResult, RenderResult
from app.services.quality_service import QualityResult
from app.services.ocr_service import OCRResult, OCRPageResult


def _good_quality(_path):
    return QualityResult('good_quality', 0.8, True, [], 0.8, 0.8, 0.8, 0.8)


def _needs_pre(_path):
    return QualityResult('needs_preprocessing', 0.4, True, ['low_contrast'], 0.4, 0.5, 0.4, 0.5)


def _fake_ocr_text(text='CBC WBC Result Unit Reference Range'):
    def _images(paths):
        return OCRResult(True, text, 0.9, [OCRPageResult(i+1, text, 0.9, p) for i, p in enumerate(paths)])
    return _images


def _make_doc(db, path, name, ctype):
    data=Path(path).read_bytes()
    doc=MedicalDocument(original_file_path=str(path), original_file_name=name, original_file_type=ctype,
                        file_size_bytes=len(data), file_hash=hashlib.sha256(data).hexdigest(),
                        validation_status='uploaded', verification_status='unverified')
    db.add(doc); db.commit(); db.refresh(doc)
    return doc


def _png(tmp_path, name='img.png'):
    p=tmp_path/name; cv2.imwrite(str(p), np.full((200, 200, 3), 255, dtype=np.uint8)); return p


def _text_pdf(tmp_path, name='lab.pdf'):
    p=tmp_path/name; doc=fitz.open(); page=doc.new_page()
    page.insert_text((72, 72), 'Laboratory CBC Result Unit Reference Range WBC 7.2 10^3/uL 4.0-10.0')
    doc.save(str(p)); doc.close(); return p


def _scanned_pdf(tmp_path, pages=1, name='scan.pdf'):
    p=tmp_path/name; doc=fitz.open()
    for _ in range(pages):
        doc.new_page()  # empty page, no text layer -> scanned
    doc.save(str(p)); doc.close(); return p


def test_good_quality_image_skips_preprocessing(db_session, tmp_path, monkeypatch):
    doc=_make_doc(db_session, _png(tmp_path), 'img.png', 'image/png')
    pipe=PipelineService()
    monkeypatch.setattr(pipe.quality, 'assess', _good_quality)
    called={'pre': 0}
    monkeypatch.setattr(pipe.preprocessing, 'preprocess', lambda *a, **k: called.__setitem__('pre', called['pre']+1) or PreprocessingResult(True, 'x', ['x']))
    monkeypatch.setattr(pipe.ocr, 'extract_images_text', _fake_ocr_text())
    monkeypatch.setattr(pipe.ocr, 'extract_any', lambda *a, **k: _fake_ocr_text()([str(doc.original_file_path)]))
    pipe.process_document(db_session, doc.id)
    assert called['pre']==0


def test_needs_preprocessing_image_calls_preprocessing(db_session, tmp_path, monkeypatch):
    doc=_make_doc(db_session, _png(tmp_path), 'img.png', 'image/png')
    pipe=PipelineService()
    monkeypatch.setattr(pipe.quality, 'assess', _needs_pre)
    called={'pre': 0}
    def fake_pre(*a, **k):
        called['pre']+=1
        return PreprocessingResult(True, str(tmp_path/'out.png'), [str(tmp_path/'out.png')], ['denoise'])
    monkeypatch.setattr(pipe.preprocessing, 'preprocess', fake_pre)
    monkeypatch.setattr(pipe.ocr, 'extract_images_text', _fake_ocr_text())
    monkeypatch.setattr(pipe.ocr, 'extract_any', lambda *a, **k: _fake_ocr_text()(['out.png']))
    pipe.process_document(db_session, doc.id)
    assert called['pre']==1


def test_text_pdf_skips_quality_and_preprocessing(db_session, tmp_path, monkeypatch):
    doc=_make_doc(db_session, _text_pdf(tmp_path), 'lab.pdf', 'application/pdf')
    pipe=PipelineService()
    flags={'q': 0, 'pre': 0}
    monkeypatch.setattr(pipe.quality, 'assess', lambda p: flags.__setitem__('q', flags['q']+1) or _good_quality(p))
    monkeypatch.setattr(pipe.preprocessing, 'preprocess', lambda *a, **k: flags.__setitem__('pre', flags['pre']+1) or PreprocessingResult(True, 'x', ['x']))
    pipe.process_document(db_session, doc.id)
    assert flags['q']==0 and flags['pre']==0
    assert db_session.get(MedicalDocument, doc.id).quality_score_before is None


def test_scanned_pdf_is_rendered_for_ocr(db_session, tmp_path, monkeypatch):
    doc=_make_doc(db_session, _scanned_pdf(tmp_path, pages=2), 'scan.pdf', 'application/pdf')
    pipe=PipelineService()
    monkeypatch.setattr(pipe.quality, 'assess', _good_quality)
    render_calls={'n': 0, 'max_pages': None}
    def fake_render(path, document_id=None, max_pages=None):
        render_calls['n']+=1; render_calls['max_pages']=max_pages
        return RenderResult(True, [str(tmp_path/'r1.png')], 1)
    pre_calls={'n': 0}
    monkeypatch.setattr(pipe.preprocessing, 'render_pdf_pages', fake_render)
    monkeypatch.setattr(pipe.preprocessing, 'preprocess', lambda *a, **k: pre_calls.__setitem__('n', pre_calls['n']+1) or PreprocessingResult(True, 'x', ['x']))
    monkeypatch.setattr(pipe.ocr, 'extract_images_text', _fake_ocr_text())
    monkeypatch.setattr(pipe.ocr, 'extract_any', lambda *a, **k: _fake_ocr_text()(['r1.png']))
    pipe.process_document(db_session, doc.id)
    assert render_calls['n']==1
    assert pre_calls['n']==0
    # page limit comes from settings, never hardcoded to 2
    assert render_calls['max_pages']==settings.max_preprocess_pages


def test_render_respects_page_limit_fewer_pages(tmp_path):
    p=_scanned_pdf(tmp_path, pages=3, name='three.pdf')
    r=PreprocessingService().render_pdf_pages(str(p), document_id=1, max_pages=5)
    assert r.success
    assert len(r.output_paths)==3  # only available pages


def test_render_respects_page_limit_caps_at_max(tmp_path):
    p=_scanned_pdf(tmp_path, pages=10, name='ten.pdf')
    r=PreprocessingService().render_pdf_pages(str(p), document_id=2, max_pages=5)
    assert len(r.output_paths)==5  # capped at default max


def test_duplicate_allowed_by_default_adds_warning(client, tmp_path):
    p=_text_pdf(tmp_path)
    with p.open('rb') as f:
        client.post('/documents/upload', files={'file': ('lab.pdf', f, 'application/pdf')})
    with p.open('rb') as f:
        resp=client.post('/documents/upload', files={'file': ('lab.pdf', f, 'application/pdf')})
    assert resp.status_code==200
    assert 'duplicate_file_hash_detected' in resp.json()['warnings']
    assert resp.json()['validation_status']=='processed'


def test_duplicate_blocked_when_setting_enabled(client, tmp_path, monkeypatch):
    p=_text_pdf(tmp_path)
    with p.open('rb') as f:
        first=client.post('/documents/upload', files={'file': ('lab.pdf', f, 'application/pdf')})
    monkeypatch.setattr(settings, 'block_duplicate_uploads', True, raising=False)
    with p.open('rb') as f:
        resp=client.post('/documents/upload', files={'file': ('lab.pdf', f, 'application/pdf')})
    assert resp.status_code==200
    body=resp.json()
    assert body['validation_status']=='duplicate_document'
    assert any(w.startswith('existing_document_id=') for w in body['warnings'])
    first_id=first.json()['document_id']
    assert f'existing_document_id={first_id}' in body['warnings']


def test_upload_response_validates_against_schema(client, tmp_path):
    from app.schemas.document import DocumentUploadResponse
    p=_text_pdf(tmp_path)
    with p.open('rb') as f:
        resp=client.post('/documents/upload', files={'file': ('lab.pdf', f, 'application/pdf')})
    assert resp.status_code==200
    DocumentUploadResponse(**resp.json())


def test_review_endpoints_preserve_validation_status(client, tmp_path):
    p=_text_pdf(tmp_path)
    with p.open('rb') as f:
        up=client.post('/documents/upload', files={'file': ('lab.pdf', f, 'application/pdf')})
    doc_id=up.json()['document_id']
    val_before=up.json()['validation_status']
    r=client.post(f'/documents/{doc_id}/review/verify')
    assert r.status_code==200
    body=r.json()
    assert body['verification_status']=='verified'
    assert body['status']==val_before  # validation_status unchanged
    rj=client.post(f'/documents/{doc_id}/review/reject', json={'reason': 'blurry'})
    assert rj.json()['verification_status']=='rejected'
    assert rj.json()['status']==val_before
    assert rj.json()['rejection_reason']=='blurry'
