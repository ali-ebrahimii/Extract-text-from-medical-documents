import cv2, numpy as np
from app.services.preprocessing_service import PreprocessingService

def test_preprocessing_creates_separate_processed_file(tmp_path, monkeypatch):
    p=tmp_path/'img.png'; cv2.imwrite(str(p), np.random.randint(0,255,(200,200,3), dtype=np.uint8))
    r=PreprocessingService().preprocess(str(p))
    assert r.success
    assert r.output_path != str(p)
