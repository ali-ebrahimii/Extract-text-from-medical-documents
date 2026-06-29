from app.services.common_field_extractor import CommonFieldExtractor


def test_tavo_lab_name_extracted_as_center():
    text='آزمايشگاه پاتوبیولوژي تاو\nکد ملي : 0021456631'
    d=CommonFieldExtractor().extract_structured(text)
    assert 'تاو' in (d['center_name']['value'] or '')


def test_header_line_not_accepted_as_center():
    text='Laboratory CBC Result Unit Reference Range\nWBC 7.2 10^3/uL 4.0-10.0'
    d=CommonFieldExtractor().extract_structured(text)
    assert d['center_name']['value'] is None


def test_tracking_number_pattern_extracted():
    d=CommonFieldExtractor().extract_structured('آزمايشگاه تاو\nO-40412-1721\nنتيجه')
    assert d['tracking_number']['value']=='O-40412-1721'


def test_presentation_form_center_normalized_and_cleaned():
    # Arabic presentation-form glyphs with surrounding '#', as seen in real PDFs.
    text='#  آزﻣﺎﻳﺸﮕﺎه ﭘﺎﺗﻮﺑﯿﻮﻟﻮژي ﺗﺎو#\nO-40412-1721'
    d=CommonFieldExtractor().extract_structured(text)
    center=d['center_name']['value']
    assert center is not None
    assert center.startswith('آزمایشگاه')
    assert '#' not in center


def test_admission_date_extracted():
    d=CommonFieldExtractor().extract_structured('تاريخ پذيرش : 14:12:57 - 1404/12/09')
    assert d['date_of_test_or_report']['value']=='1404/12/09'
    assert d['date_of_test_or_report']['calendar']=='jalali'


def test_date_field_includes_line_evidence():
    text='آزمايشگاه تاو\nکد ملي : 0021456631\nتاريخ پذيرش : 14:12:57 - 1404/12/09'
    d=CommonFieldExtractor().extract_structured(text)
    date=d['date_of_test_or_report']
    assert date['value']=='1404/12/09'
    assert date['source_line_index']==2
    assert '1404/12/09' in date['source_text']


def test_national_id_evidence_hides_raw_value():
    d=CommonFieldExtractor().extract_structured('کد ملي : 0021456631')
    nid=d['national_id']
    assert nid['value'] is None            # raw value hidden by default
    assert nid['hash'] is not None
    assert nid['source_text'] is not None
    assert '0021456631' not in nid['source_text']  # raw digits masked in evidence


def test_national_id_raw_exposed_when_allowed(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, 'allow_raw_national_id', True, raising=False)
    d=CommonFieldExtractor().extract_structured('کد ملي : 0021456631')
    assert d['national_id']['value']=='0021456631'
    assert '0021456631' in (d['national_id']['source_text'] or '')


def test_tavo_male_header_extracts_patient_sex_age():
    d=CommonFieldExtractor().extract_structured('کبیری- آقای پدرام- دکتر43 : سن')
    assert d['sex']['value']=='male'
    assert d['age']['value']==43
    assert 'پدرام' in d['patient_name']['value'] and 'کبیری' in d['patient_name']['value']
    assert d['doctor_name']['value'] is None


def test_tavo_female_header_extracts_patient_sex_age():
    d=CommonFieldExtractor().extract_structured('غفاریان- خانم غزل- دکتر45 : سن')
    assert d['sex']['value']=='female'
    assert d['age']['value']==45
    assert 'غزل' in d['patient_name']['value'] and 'غفاریان' in d['patient_name']['value']


def test_tavo_fixture_header_and_date():
    from pathlib import Path
    d=CommonFieldExtractor().extract_structured(Path('tests/fixtures/tavo/header_patient_age.txt').read_text(encoding='utf-8'))
    assert d['patient_name']['value']
    assert d['sex']['value']=='female'
    assert d['age']['value']==45
    assert d['date_of_test_or_report']['value']=='1404/12/09'
