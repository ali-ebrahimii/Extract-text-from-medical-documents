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
