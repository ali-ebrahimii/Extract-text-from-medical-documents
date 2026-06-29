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
