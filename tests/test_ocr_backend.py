import sys
from types import SimpleNamespace
import cv2, numpy as np
from app.core.config import settings
from app.services.ocr_service import OCRService


def test_tesseract_backend_uses_tesseract_path(monkeypatch):
    monkeypatch.setattr(settings, 'ocr_backend', 'tesseract', raising=False)
    monkeypatch.setattr(settings, 'enable_paddleocr', False, raising=False)
    svc=OCRService()
    calls={'paddle': 0, 'tess': 0}
    monkeypatch.setattr(svc, '_paddle_text', lambda p: calls.__setitem__('paddle', calls['paddle']+1) or None)
    monkeypatch.setattr(svc, '_tesseract_text', lambda p: (calls.__setitem__('tess', calls['tess']+1) or ('hello', 0.9)))
    r=svc.extract_image_text('x.png')
    assert r.success and r.text=='hello'
    assert calls['tess']==1 and calls['paddle']==0


def test_missing_engine_returns_failure_not_crash(monkeypatch):
    monkeypatch.setattr(settings, 'ocr_backend', 'tesseract', raising=False)
    monkeypatch.setattr(settings, 'enable_paddleocr', False, raising=False)
    svc=OCRService()
    monkeypatch.setattr(svc, '_tesseract_text', lambda p: (None, 'tesseract not installed'))
    r=svc.extract_image_text('x.png')
    assert r.success is False
    assert 'OCR engine is not available' in (r.error or '')


def test_language_config_passed_to_pytesseract(monkeypatch, tmp_path):
    p=tmp_path/'img.png'; cv2.imwrite(str(p), np.full((20,20,3), 255, dtype=np.uint8))
    captured={}

    def image_to_data(img, lang=None, output_type=None):
        captured['lang']=lang
        return {'text': ['hi'], 'conf': ['90']}

    fake=SimpleNamespace(
        image_to_data=image_to_data,
        image_to_string=lambda img, lang=None: 'hi',
        Output=SimpleNamespace(DICT='dict'),
    )
    monkeypatch.setitem(sys.modules, 'pytesseract', fake)
    monkeypatch.setattr(settings, 'tesseract_lang', 'eng+fas', raising=False)
    text, conf=OCRService()._tesseract_text(str(p))
    assert captured['lang']=='eng+fas'
    assert text=='hi'


def test_paddle_backend_falls_back_to_tesseract_when_unavailable(monkeypatch):
    monkeypatch.setattr(settings, 'ocr_backend', 'paddleocr', raising=False)
    svc=OCRService()
    monkeypatch.setattr(svc, '_paddle_text', lambda p: None)  # paddle unavailable
    monkeypatch.setattr(svc, '_tesseract_text', lambda p: ('fallback', 0.7))
    r=svc.extract_image_text('x.png')
    assert r.text=='fallback'
