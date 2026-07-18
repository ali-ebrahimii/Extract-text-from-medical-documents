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
    assert row.row_save_allowed is True and row.backend_row_save_recommendation is False
