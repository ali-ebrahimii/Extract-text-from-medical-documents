from app.services.relevance_service import RelevanceService, normalize_persian

def test_unrelated_text_file_returns_unrelated():
    r=RelevanceService().check('/tmp/missing.png','vacation_photo.png','mountain sunset family holiday')
    assert not r.is_medical_document
    assert r.relevance_score < .15


def test_persian_national_id_phrase_detected():
    r=RelevanceService().check_from_text('کد ملی : 0021456631')
    assert 'کد ملی' in r.detected_keywords


def test_arabic_variant_admission_date_phrase_detected():
    # uses Arabic yeh/kaf; normalization should still match the Persian phrase
    r=RelevanceService().check_from_text('تاريخ پذيرش : 1404/12/09')
    assert any('تاریخ پذیرش' == normalize_persian(k) for k in r.detected_keywords)


def test_normal_range_phrase_detected():
    r=RelevanceService().check_from_text('محدوده نرمال 4.0 - 10.0')
    assert 'محدوده نرمال' in r.detected_keywords


def test_persian_lab_text_is_medical():
    text='آزمایشگاه پاتوبیولوژی تاو\nنتیجه\nمحدوده نرمال\nخون'
    r=RelevanceService().check_from_text(text)
    assert r.is_medical_document is True
