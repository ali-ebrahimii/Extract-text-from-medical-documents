"""End-to-end integration tests using locally generated files (no external data)."""
import shutil
import fitz
import pytest
from PIL import Image, ImageDraw

from app.core.config import settings
from app.schemas.document import DocumentUploadResponse

HAS_TESSERACT = shutil.which('tesseract') is not None


def _text_pdf(tmp_path, lines_per_page, name='lab.pdf'):
    doc=fitz.open()
    for lines in lines_per_page:
        page=doc.new_page()
        y=72
        for line in lines:
            page.insert_text((72, y), line); y+=22
    p=tmp_path/name; doc.save(str(p)); doc.close(); return p


_TAVO_LINES=[
    'Laboratory Tavo',
    'Patient Name: Ali Rezaei',
    'Report Date: 2024/03/01',
    'Test: CBC',
    'SGOT(AST) *47 U/L Photometr <37 High',
    'Hemoglobin 15.0 g/dL 13.5 - 17.5',
    'Platelets 265 10^3 /uL 150 - 450',
]


def test_text_pdf_processed_and_skips_preprocessing(client, tmp_path):
    p=_text_pdf(tmp_path, [_TAVO_LINES])
    with p.open('rb') as f:
        resp=client.post('/documents/upload', files={'file': ('lab.pdf', f, 'application/pdf')})
    assert resp.status_code==200
    body=resp.json()
    DocumentUploadResponse(**body)                       # schema conformance
    assert body['validation_status']=='processed'
    assert body['preprocessing'] is None                 # text PDFs skip preprocessing
    assert body['quality_score_before'] is None          # and skip image quality
    assert body['document_type']=='lab'
    assert len(body['extracted_data']['lab_results']) >= 3   # lab rows extracted


def test_text_pdf_multipage_keeps_page_numbers(client, tmp_path):
    page1=_TAVO_LINES
    page2=['SGPT(ALT) *46 U/L Photometr < 40 High', 'TSH 5.60 mIU/mL ELISA 0.4 - 5.0 High']
    p=_text_pdf(tmp_path, [page1, page2], name='multi.pdf')
    with p.open('rb') as f:
        resp=client.post('/documents/upload', files={'file': ('multi.pdf', f, 'application/pdf')})
    assert resp.status_code==200
    rows=resp.json()['extracted_data']['lab_results']
    assert any(r['page_number']==2 for r in rows)         # second page parsed


def test_duplicate_blocked_when_setting_enabled(client, tmp_path, monkeypatch):
    p=_text_pdf(tmp_path, [_TAVO_LINES], name='dup.pdf')
    with p.open('rb') as f:
        first=client.post('/documents/upload', files={'file': ('dup.pdf', f, 'application/pdf')})
    monkeypatch.setattr(settings, 'block_duplicate_uploads', True, raising=False)
    with p.open('rb') as f:
        resp=client.post('/documents/upload', files={'file': ('dup.pdf', f, 'application/pdf')})
    body=resp.json()
    assert body['validation_status']=='duplicate_document'
    assert f"existing_document_id={first.json()['document_id']}" in body['warnings']


@pytest.mark.skipif(not HAS_TESSERACT, reason='tesseract not installed')
def test_real_tesseract_reads_generated_image(tmp_path):
    from app.services.ocr_service import OCRService
    img=Image.new('RGB', (600, 120), 'white')
    ImageDraw.Draw(img).text((10, 40), 'HELLO LAB 123', fill='black')
    p=tmp_path/'txt.png'; img.save(str(p))
    r=OCRService().extract_image_text(str(p))
    assert r.success
    assert 'LAB' in r.text.upper() or 'HELLO' in r.text.upper()
