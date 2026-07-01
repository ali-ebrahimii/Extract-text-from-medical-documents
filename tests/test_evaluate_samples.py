import csv
from scripts import evaluate_samples
from scripts.compare_annotations import compute_metrics


def test_jpg_evaluation_mime_map_uses_image_jpeg():
    assert evaluate_samples.MIME_MAP['.jpg'] == 'image/jpeg'


def test_summary_includes_stateless_columns_only():
    for col in [
        'filename','request_id','document_id','status','document_type','confidence','quality_score',
        'quality_min_score','quality_worst_page_number','ocr_confidence','ocr_text_length',
        'patient_name_found','national_id_hash_found','date_found','center_name_found',
        'tracking_number_found','age_found','sex_found','test_or_report_name_found','lab_result_count',
        'pap_smear_found','radiology_found','error_codes','warning_codes','ocr_warning_count'
    ]:
        assert col in evaluate_samples.CSV_COLUMNS
    for old in ['validation_status','verification_status','extraction_confidence','rejection_reason','warnings']:
        assert old not in evaluate_samples.CSV_COLUMNS


def test_compare_annotations_stateless_metrics():
    summary=[
        {'filename':'a.pdf','status':'low_confidence','document_type':'lab','confidence':'0.5','patient_name_found':'true','date_found':'true','lab_result_count':'2','warning_codes':'MISSING_LAB_ROWS','error_codes':''},
        {'filename':'b.pdf','status':'ocr_failed','document_type':'','confidence':'','patient_name_found':'false','date_found':'false','lab_result_count':'0','warning_codes':'','error_codes':'OCR_EMPTY_TEXT'},
    ]
    annotations=[{'filename':'a.pdf','expected_document_type':'lab','expected_patient_name':'Ali','expected_date':'2024/01/01','expected_lab_result_count':'2'}]
    metrics=compute_metrics(summary, annotations)
    assert metrics['document_type_accuracy']==1.0
    assert metrics['low_confidence_rate']==0.5
    assert metrics['rejection_rate']==0.5
    assert metrics['missing_lab_rows_rate']==0.5
    assert metrics['ocr_failure_rate']==0.5
