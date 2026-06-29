from app.services.lab_extractor import LabExtractor
from app.services.common_field_extractor import CommonFieldExtractor, hash_national_id
from app.services.relevance_service import normalize_digits


def test_normalize_digits_persian_and_arabic():
    assert normalize_digits("۰۱۲۳۴۵۶۷۸۹")=="0123456789"
    assert normalize_digits("٠١٢٣٤٥٦٧٨٩")=="0123456789"


def test_lab_row_with_persian_digits():
    rows={r['test_name_standard']: r for r in LabExtractor().extract('FBS ۱۰۱ mg/dL 70-115')}
    assert rows['FBS']['result_numeric']==101


def test_common_national_id_with_persian_digits():
    d=CommonFieldExtractor().extract_structured('کد ملي : ۰۰۲۱۴۵۶۶۳۱')
    assert d['national_id']['hash']==hash_national_id('0021456631')
    assert d['national_id']['value'] is None  # raw hidden by default


def test_common_date_with_persian_digits():
    d=CommonFieldExtractor().extract_structured('تاريخ پذيرش : ۱۴۰۴/۱۲/۰۹')
    assert d['date_of_test_or_report']['value']=='1404/12/09'
    assert d['date_of_test_or_report']['calendar']=='jalali'
