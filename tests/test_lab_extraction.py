from app.services.lab_extractor import LabExtractor


def _rows(text):
    return {r['test_name_standard']: r for r in LabExtractor().extract(text)}


def test_new_supported_rows():
    text='''SGPT(ALT) *46 U/L Photometr < 40 High
Hemoglobin 15.0 g/dL 13.5 - 17.5
H.C.T 45.0 % 38.8-50 %
M.C.V 91.8 fL 81.2-95.1 fl
RDW-CV 12.6 % 11.8-15.6 %
Basophils 0.1 % 0.3-1.4 %'''
    rows=_rows(text)
    assert rows['ALT']['result_numeric']==46
    assert rows['ALT']['unit']=='U/L'
    assert rows['ALT']['method']=='Photometr'
    assert rows['ALT']['reference_range']=='< 40'
    assert rows['ALT']['abnormal_flag']=='High'
    assert rows['Hb']['result_numeric']==15.0
    assert rows['Hb']['unit']=='g/dL'
    assert rows['Hb']['reference_range']=='13.5 - 17.5'
    assert rows['HCT']['reference_range']=='38.8-50 %'
    assert rows['MCV']['unit']=='fL'
    assert rows['MCV']['reference_range']=='81.2-95.1 fl'
    assert rows['RDW-CV']['reference_range']=='11.8-15.6 %'
    assert rows['Basophils']['reference_range']=='0.3-1.4 %'


def test_existing_rows_still_supported():
    text='''SGOT(AST) *47 U/L Photometr <37 High
TSH *5.60 µIU/mL ELISA 0.4 - 5.0 High
Fasting blood sugar 101 mg/dL Photometr 70-115
Platelets 265 10^3 /uL 150 - 450
Lymphocytes 43 % 20 - 40 High'''
    rows=_rows(text)
    assert rows['AST']['reference_range']=='<37'
    assert rows['TSH']['reference_range']=='0.4 - 5.0'
    assert rows['FBS']['result_numeric']==101
    assert rows['Platelets']['unit']=='10^3 /uL'
    assert rows['Lymphocytes']['abnormal_flag']=='High'


def test_non_lab_lines_are_not_parsed():
    text='''Patient Name: Ali Rezaei
Doctor: Dr. Smith
Print On : 1404/12/09
تاريخ پذيرش : 14:12:57 - 1404/12/09
Laboratory CBC Result Unit Reference Range
WBC 7.2 10^3/uL 4.0-10.0'''
    rows=_rows(text)
    assert set(rows.keys())=={'WBC'}
    assert rows['WBC']['reference_range']=='4.0-10.0'


def test_flag_letters_supported():
    rows=_rows('Hemoglobin 11.0 g/dL 13.5 - 17.5 L')
    assert rows['Hb']['abnormal_flag']=='L'


def test_missing_unit_and_range_lowers_confidence_for_known_test():
    # known test, but no unit/range -> kept with low confidence
    rows={r['test_name_standard']: r for r in LabExtractor().extract('TSH 5.6 ELISA')}
    assert 'TSH' in rows
    assert rows['TSH']['confidence'] <= 0.7


def test_guideline_reference_comments_are_not_lab_rows():
    ex=LabExtractor()
    assert ex.extract('High >400 l') == []
    assert ex.extract('Desirable <200') == []
    assert ex.extract('Average risk : 4.4 - 7.1') == []


def test_real_rows_with_flags_and_guidelines_still_parse():
    rows=_rows('Lymphocytes 43 % 20 - 40 High\nTriglycerides 130 mg/dL Desirable <200 Photometr')
    assert rows['Lymphocytes']['abnormal_flag']=='High'
    assert rows['Triglycerides']['result_numeric']==130


def test_tavo_column_major_biochemistry_fixture():
    text=__import__('pathlib').Path('tests/fixtures/tavo/column_major_biochemistry.txt').read_text(encoding='utf-8')
    rows=_rows(text)
    assert rows['FBS']['result_numeric']==88
    assert rows['FBS']['unit']=='mg/dL'
    assert rows['Triglycerides']['reference_range'].startswith('Desirable <200')
    assert rows['Cholesterol']['test_name_raw']=='Cholestrol'
    assert rows['AST']['abnormal_flag']=='High'
    assert rows['ALT']['method']=='Photometr'
    assert 'High' not in rows
    assert len(rows) >= 5


def test_tavo_column_major_cbc_block():
    text='''Test\nResult\nHematology\nUnit\nNormal Range\nMethod\nWBC\n7.2\n10^3/uL\n4.0-10.0\nRBC\n5.1\n10^6/uL\n4.5-5.9\nHemoglobin\n14.0\ng/dL\n13-17\nPlatelets\n250\n10^3/uL\n150-450'''
    rows=_rows(text)
    assert {'WBC','RBC','Hb','Platelets'} <= set(rows)


def test_deduplicates_single_line_and_column_major_results():
    text='''Fasting blood sugar 88 mg/dL 70-115\nTest\nResult\nUnit\nNormal Range\nMethod\nFasting blood sugar\n88\nmg/dL\n70-115\nPhotometr'''
    rows=[r for r in LabExtractor().extract(text) if r['test_name_standard']=='FBS']
    assert len(rows)==1
