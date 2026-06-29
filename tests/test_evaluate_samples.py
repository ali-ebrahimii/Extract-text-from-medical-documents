from pathlib import Path
from scripts import evaluate_samples


def test_jpg_evaluation_mime_map_uses_image_jpeg():
    assert evaluate_samples.MIME_MAP['.jpg'] == 'image/jpeg'


def test_summary_includes_new_columns():
    for col in ['patient_name_value_masked_or_present','center_name_found','tracking_number_found','age_found','sex_found','false_positive_suspected_count','ocr_warning_count','quality_worst_page_number','quality_min_score']:
        assert col in evaluate_samples.CSV_COLUMNS
