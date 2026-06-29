import cv2, numpy as np
from app.services.quality_service import QualityService

def test_low_quality_image_returns_needs_preprocessing_or_poor_quality(tmp_path):
    p=tmp_path/'low.png'; cv2.imwrite(str(p), np.full((50,50), 127, dtype=np.uint8))
    r=QualityService().assess(str(p))
    assert r.status in {'needs_preprocessing','poor_quality'}
