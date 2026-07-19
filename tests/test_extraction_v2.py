from app.services.privacy_service import normalize_persian_text, validate_iranian_national_id, mask_national_id
from app.services.common_field_validation_service import CommonFieldValidationService, valid_tracking_number
from app.services.lab_extractor_v2 import LabExtractorV2
from app.services.lab_row_validation_service import LabRowValidationService
from app.schemas.extraction_v2 import LabResultV2


def test_persian_character_normalization():
    assert normalize_persian_text('مھلا طھران ك ي ة') == 'مهلا تهران ک ی ه'

def test_iranian_national_id_checksum_and_mask():
    assert validate_iranian_national_id('0014161672')
    assert not validate_iranian_national_id('1111111111')
    assert mask_national_id('0014161672') == '001****672'

def test_national_id_schema_safe_share_has_no_value_or_raw():
    fields=CommonFieldValidationService().extract('کد ملی : 0014161672', privacy_mode='safe_share')
    nid=fields['national_id']
    assert 'value' not in nid
    assert nid['raw_value'] is None
    assert nid['masked_value']=='001****672' and nid['hash_sha256']

def test_tracking_number_validation_rejection():
    assert valid_tracking_number('O-40412-1721')
    assert not valid_tracking_number('1404')
    assert not valid_tracking_number('Culture')
    assert not valid_tracking_number('1404/01/01')

def test_clean_tav_tracking_number_patterns():
    service=CommonFieldValidationService()
    for text in ['شماره : O-40412-1721', 'شماره:O-40412-1721', 'آزمایشگاه تاو\nO-40412-1721\nنام بیمار']:
        field=service.extract(text)['tracking_number']
        assert field['value']=='O-40412-1721'
        assert field['field_validation_status']=='valid'
    for text in ['شماره : 1404', 'شماره : 1404/12/09', 'Result', 'Hormone', 'Culture']:
        field=service.extract(text)['tracking_number']
        assert field['field_validation_status']=='missing_optional'

def test_clean_tav_date_patterns():
    service=CommonFieldValidationService()
    for text in ['تاریخ پذیرش1404/12/09', 'تاریخ پذیرش : 1404/12/09', 'تاریخ جوابدهی1404/12/09']:
        field=service.extract(text)['date_of_test_or_report']
        assert field['value']=='1404/12/09'
        assert field['field_validation_status']=='valid'

def test_clean_tav_compact_patient_sex_age_line_male():
    fields=CommonFieldValidationService().extract('امینی تهران- آقای کورش- دکتر34 : سن')
    assert fields['patient_name']['value']=='کورش امینی تهران'
    assert fields['sex']['value']=='male'
    assert fields['age']['value']==34
    assert fields['doctor_name']['field_validation_status']=='missing_optional'

def test_clean_tav_compact_patient_sex_age_line_female():
    fields=CommonFieldValidationService().extract('روشن- خانم مهلا- دکتر27 : سن')
    assert fields['patient_name']['value']=='مهلا روشن'
    assert fields['sex']['value']=='female'
    assert fields['age']['value']==27
    assert fields['doctor_name']['field_validation_status']=='missing_optional'

def test_national_id_preserves_leading_zeros_schema():
    fields=CommonFieldValidationService().extract('کد ملی : 0014161672')
    nid=fields['national_id']
    assert nid['raw_value']=='0014161672'
    assert nid['masked_value']=='001****672'
    assert nid['hash_sha256']

def test_doctor_rejected_from_patient_age_line():
    fields=CommonFieldValidationService().extract('دکتر34 : سن')
    assert fields['doctor_name']['field_validation_status']=='missing_optional'

def test_ul_not_low_and_one_sided_reference():
    row=LabResultV2(test_name_standard='AST',result_value='19',result_numeric=19,unit='U/L',reference_range='<37')
    row=LabRowValidationService().validate(row)
    assert row.source_flag is None and row.computed_flag is None and row.flag is None

def test_printed_high_preserved():
    rows=LabExtractorV2().extract('AST 47 U/L <37 High')
    ast=rows[0]
    assert ast.source_flag=='High' and ast.flag=='High' and ast.flag_source=='source'

def test_culture_phrase_no_false_bacteria_48():
    rows=LabExtractorV2().extract('No bacteria growth after 48 hrs.')
    assert len(rows)==1
    assert rows[0].test_name_standard=='Urine Culture'
    assert rows[0].result_numeric is None

def test_unsafe_ocr_forces_unsafe_statuses():
    rows=LabExtractorV2().extract('WBC 5 10^3/uL', unsafe_ocr=True)
    assert rows[0].row_validation_status=='unsafe_ocr_context'
    assert rows[0].column_statuses.result_status=='unsafe_ocr_context'

def test_backend_row_save_recommendation_is_conjunction():
    row=LabResultV2(test_name_standard='WBC',result_value='5',result_numeric=5)
    row=LabRowValidationService().validate(row)
    recommended_save=False
    row.backend_row_save_recommendation = recommended_save and row.row_save_allowed
    assert row.row_save_allowed is False and row.backend_row_save_recommendation is False

def test_expected_unit_mismatch_blocks_backend_safe_row():
    row=LabResultV2(test_name_standard='HCT',result_value='42',result_numeric=42,unit='g/dL')
    row=LabRowValidationService().validate(row)
    assert row.column_statuses.unit_status in ('invalid','review')
    assert row.row_validation_status in ('invalid','review')
    assert row.row_save_allowed is False


def test_tsh_ul_unit_is_not_valid():
    row=LabResultV2(test_name_standard='TSH',result_value='2.1',result_numeric=2.1,unit='U/L')
    row=LabRowValidationService().validate(row)
    assert row.column_statuses.unit_status in ('invalid','review')
    assert row.row_validation_status in ('invalid','review')
    assert row.row_save_allowed is False


def test_ast_alt_ul_and_iul_units_valid():
    for test_name, unit in [('AST','U/L'),('AST','IU/L'),('ALT','U/L'),('ALT','IU/L')]:
        row=LabResultV2(test_name_standard=test_name,result_value='19',result_numeric=19,unit=unit)
        row=LabRowValidationService().validate(row)
        assert row.column_statuses.unit_status=='valid'
        assert row.row_validation_status=='valid'
        assert row.row_save_allowed is True


def test_qualitative_value_invalid_for_quantitative_non_urine_tests():
    row=LabResultV2(test_name_standard='TSH',result_value='Negative',result_numeric=None,unit='uIU/mL')
    row=LabRowValidationService().validate(row)
    assert row.row_validation_status=='invalid'
    assert row.row_save_allowed is False
def test_v2_tav_cbc_multiline_rows():
    rows=LabExtractorV2().extract('''W.B.C
7.24
10^3/uL
3.5-10.5''')
    wbc=next(row for row in rows if row.test_name_standard=='WBC')
    assert wbc.result_value=='7.24'
    assert wbc.result_numeric==7.24
    assert wbc.unit=='10^3/uL'
    assert wbc.reference_range=='3.5-10.5'


def test_v2_tav_ast_alt_multiline_one_sided_refs():
    rows=LabExtractorV2().extract('''SGOT(AST)
19
U/L
<37

SGPT(ALT)
21
U/L
<40''')
    by_name={row.test_name_standard: row for row in rows}
    ast=by_name['AST']
    alt=by_name['ALT']
    assert ast.result_value=='19' and ast.unit=='U/L' and ast.reference_range=='<37'
    assert alt.result_value=='21' and alt.unit=='U/L' and alt.reference_range=='<40'
    assert ast.flag is None and ast.source_flag is None
    assert alt.flag is None and alt.source_flag is None


def test_v2_tav_multiline_printed_high_is_source_flag():
    rows=LabExtractorV2().extract('''AST
47
U/L
<37
High''')
    ast=next(row for row in rows if row.test_name_standard=='AST')
    assert ast.source_flag=='High'
    assert ast.flag=='High'
    assert ast.flag_source=='source'


def test_v2_tav_ul_unit_does_not_create_false_low_flag():
    rows=LabExtractorV2().extract('''AST
19
U/L
<37''')
    ast=next(row for row in rows if row.test_name_standard=='AST')
    assert ast.unit=='U/L'
    assert ast.source_flag is None
    assert ast.flag is None


def test_persian_presentation_forms_normalize_before_extraction():
    text = 'اﻣﯿﻨﻲ ﺗﻬﺮان- آﻗﺎی کورش- دﻛﺘﺮ34 : ﺳﻦ\nﮐﺪ ﻣﻠﻲ : 0014161672'
    normalized = normalize_persian_text(text)
    assert 'امینی تهران' in normalized
    assert 'آقای کورش' in normalized
    assert 'دکتر34 : سن' in normalized
    assert 'کد ملی' in normalized
    fields = CommonFieldValidationService().extract(text)
    assert fields['patient_name']['value'] == 'کورش امینی تهران'
    assert fields['sex']['value'] == 'male'
    assert fields['age']['value'] == 34
    assert fields['national_id']['raw_value'] == '0014161672'


def test_v2_tav_dotted_cbc_aliases_extract_and_validate_units():
    rows = LabExtractorV2().extract('''R.B.C
5.01
10^6/uL
4.5-5.9

Hemoglobin
14.2
g/dL
13-17

H.C.T
42
%
40-52

M.C.V
84
fL
80-100

M.C.H
28
pg
27-33

M.C.H.C
33
g/dL
32-36

Platelets count
250
10^3/uL
150-450

RDW-CV
13
%
11-15

PDW
11
fL
9-17

Fasting blood sugar
91
mg/dL
70-100''')
    by_name = {row.test_name_standard: row for row in rows}
    assert by_name['RBC'].test_name_raw == 'R.B.C'
    assert by_name['HGB'].test_name_raw == 'Hemoglobin'
    assert by_name['HCT'].test_name_raw == 'H.C.T'
    assert by_name['MCV'].test_name_raw == 'M.C.V'
    assert by_name['MCH'].test_name_raw == 'M.C.H'
    assert by_name['MCHC'].test_name_raw == 'M.C.H.C'
    assert by_name['PLT'].test_name_raw == 'Platelets count'
    assert by_name['RDW-CV'].test_name_raw == 'RDW-CV'
    assert by_name['PDW'].test_name_raw == 'PDW'
    assert by_name['FBS'].test_name_raw == 'Fasting blood sugar'
    assert all(row.row_save_allowed for row in by_name.values())


def test_expected_unit_missing_blocks_quantitative_backend_safe_row():
    row = LabResultV2(test_name_standard='WBC', result_value='5', result_numeric=5)
    row = LabRowValidationService().validate(row)
    assert row.column_statuses.unit_status == 'missing_optional'
    assert row.row_validation_status == 'invalid'
    assert 'expected_unit_missing' in row.reason_codes
    assert row.row_save_allowed is False


def test_v2_tav_real_like_cbc_rows_with_ref_units_and_spaced_units():
    rows = LabExtractorV2().extract('''W.B.C
7.24
10^3/uL
3.5-10.5

R.B.C
4.90
10^6/uL
4.32 - 5.72

Hemoglobin
15.0
g/dL
13.5-17.5

H.C.T
45.0
%
38.8-50 %

M.C.V
91.8
fl
81.2-95.1 fl

M.C.H
30.6
pg
25.8-33.1 pg

M.C.H.C
33.3
g/dl
32-36 g/dl

Platelets
265
10^3 /uL
150 - 450

RDW-CV
12.6
%
11.8-15.6 %

RDW-SD
40.7
fl
36 - 54

Monocytes
5.5
%
4.1-12.4 %

Eosinophils
1.7
%
0.4-6.7 %

Basophils
0.1
%
0.3-1.4 %

Fasting blood sugar
91
mg/dl
70-100

SGOT(AST)
19
U/L
<37

SGPT(ALT)
21
IU/L
< 40''')
    by_name = {row.test_name_standard: row for row in rows}
    expected = ['WBC','RBC','HGB','HCT','MCV','MCH','MCHC','PLT','RDW-CV','RDW-SD','Monocytes','Eosinophils','Basophils','FBS','AST','ALT']
    assert set(expected).issubset(by_name)
    assert by_name['PLT'].unit == '10^3/uL'
    assert by_name['RBC'].unit == '10^6/uL'
    assert by_name['MCV'].unit == 'fL'
    assert by_name['MCHC'].unit == 'g/dL'
    assert by_name['FBS'].unit == 'mg/dL'
    assert by_name['RDW-CV'].test_name_raw == 'RDW-CV'
    assert by_name['RDW-SD'].test_name_raw == 'RDW-SD'
    assert by_name['AST'].flag is None and by_name['ALT'].flag is None
    assert all(by_name[name].row_save_allowed for name in expected)


def test_quantitative_negative_not_allowed_from_extractor():
    row = LabExtractorV2().extract('TSH Negative uIU/mL')[0]
    assert row.row_validation_status == 'invalid'
    assert row.row_save_allowed is False
