import cv2, numpy as np
from app.services.quality_service import QualityService


def _low_contrast(tmp_path, name='lc.png'):
    rng=np.random.default_rng(0)
    img=np.clip(np.full((600,600),127,dtype=np.int16)+rng.integers(-6,7,(600,600)),0,255).astype('uint8')
    p=tmp_path/name; cv2.imwrite(str(p), np.stack([img]*3,-1)); return p


def _blank(tmp_path, name='blank.png'):
    p=tmp_path/name; cv2.imwrite(str(p), np.full((600,600,3),127,dtype=np.uint8)); return p


def test_low_quality_image_returns_needs_preprocessing_or_poor_quality(tmp_path):
    p=tmp_path/'low.png'; cv2.imwrite(str(p), np.full((50,50), 127, dtype=np.uint8))
    r=QualityService().assess(str(p))
    assert r.status in {'needs_preprocessing','poor_quality'}


def test_low_contrast_image_is_fixable(tmp_path):
    r=QualityService().assess(str(_low_contrast(tmp_path)))
    assert r.status in {'needs_preprocessing','poor_quality'}
    assert r.is_fixable is True
    assert 'low_contrast' in r.issues


def test_unreadable_image_is_not_fixable(tmp_path):
    r=QualityService().assess(str(_blank(tmp_path)))
    assert r.status=='poor_quality'
    assert r.is_acceptable is False
    assert r.is_fixable is False
    assert 'unreadable_image' in r.issues


def test_good_quality_image_is_acceptable_not_fixable(tmp_path):
    rng=np.random.default_rng(1)
    img=np.clip(np.full((1200,1200),127,dtype=np.int16)+rng.integers(-90,91,(1200,1200)),0,255).astype('uint8')
    p=tmp_path/'good.png'; cv2.imwrite(str(p), np.stack([img]*3,-1))
    r=QualityService().assess(str(p))
    assert r.status=='good_quality'
    assert r.is_acceptable is True
    assert r.is_fixable is False


def test_assess_many_uses_worst_page_conservatively(tmp_path):
    good=_low_contrast(tmp_path, 'g.png')  # needs_preprocessing (acceptable)
    bad=_blank(tmp_path, 'b.png')          # poor_quality / unreadable
    r=QualityService().assess_many([str(good), str(bad)])
    assert r.num_pages==2
    assert r.status=='poor_quality'        # follows the worst page
    assert r.is_acceptable is False        # not all pages acceptable
    assert r.worst_page_number==2
    assert r.min_quality_score <= r.average_quality_score
    assert len(r.page_issues)==2
    assert any('unreadable_image' in pi['issues'] for pi in r.page_issues)


def test_quality_result_page_details_shape():
    from app.services.quality_service import QualityResult
    from app.services.extraction_pipeline import ExtractionPipeline
    q=QualityResult('poor_quality',0.5,False,['low_contrast'],0,0,0,0,page_scores=[.9,.2],page_issues=[{'page_number':2,'issues':['low_contrast']}],worst_page_number=2,average_quality_score=.55,min_quality_score=.2,num_pages=2,metrics={'x':1})
    schema=ExtractionPipeline()._quality_schema(q)
    assert schema.page_issues[0]['page_number']==2
    assert schema.worst_page_number==2
