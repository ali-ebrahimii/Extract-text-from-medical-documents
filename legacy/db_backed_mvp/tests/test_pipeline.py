import fitz
from app.services.classification_service import ClassificationService
from app.services.lab_extractor import LabExtractor
from app.services.confidence_service import ConfidenceService

def test_text_based_lab_sample_can_classify_as_lab():
    text='Patient Name: Ali\nCBC Result Unit Reference Range\nWBC 7.2 10^3/uL 4.0-10.0\nFBS 90 mg/dL 70-100'
    r=ClassificationService().classify(text)
    assert r.document_type=='lab'

def test_lab_line_parser_extracts_priority_fields():
    rows=LabExtractor().extract('WBC 7.2 10^3/uL 4.0-10.0')
    assert rows[0]['test_name_standard']=='WBC'
    assert rows[0]['result_value']=='7.2'
    assert rows[0]['unit']=='10^3/uL'
    assert rows[0]['reference_range']=='4.0-10.0'

def test_missing_priority_fields_leads_to_needs_review(client, tmp_path):
    p=tmp_path/'lab.pdf'; doc=fitz.open(); page=doc.new_page(); page.insert_text((72,72),'Laboratory CBC Result Unit WBC 7.2 10^3/uL 4.0-10.0'); doc.save(str(p)); doc.close()
    with p.open('rb') as f:
        resp=client.post('/documents/upload', files={'file':('lab.pdf', f, 'application/pdf')})
    assert resp.status_code==200
    assert resp.json()['verification_status']=='needs_review'
from app.services.common_field_extractor import CommonFieldExtractor, hash_national_id
from app.services.document_analysis_service import DocumentAnalysisService
from app.services.relevance_service import RelevanceService
from app.core.enums import DocumentStatus

def test_realistic_lab_lines_extract_columns():
    text='''SGOT(AST) *47 U/L Photometr <37 High
TSH *5.60 µIU/mL ELISA 0.4 - 5.0 High
Fasting blood sugar 101 mg/dL Photometr 70-115
Platelets 265 10^3 /uL 150 - 450
Lymphocytes 43 % 20 - 40 High'''
    rows={r['test_name_standard']:r for r in LabExtractor().extract(text)}
    assert rows['AST']['result_numeric']==47
    assert rows['AST']['unit']=='U/L'
    assert rows['AST']['method']=='Photometr'
    assert rows['AST']['reference_range']=='<37'
    assert rows['AST']['abnormal_flag']=='High'
    assert rows['TSH']['unit']=='µIU/mL'
    assert rows['TSH']['method']=='ELISA'
    assert rows['TSH']['reference_range']=='0.4 - 5.0'
    assert rows['FBS']['result_numeric']==101
    assert rows['Platelets']['unit']=='10^3 /uL'
    assert rows['Lymphocytes']['abnormal_flag']=='High'

def test_common_persian_fields_and_hashing():
    text='''کد ملي : 0021456631
تاريخ پذيرش : 14:12:57 - 1404/12/09
خانم سپیده - سلطاني سن : 27'''
    data=CommonFieldExtractor().extract_structured(text)
    assert data['national_id']['value'] is None
    assert data['national_id']['hash']==hash_national_id('0021456631')
    assert data['date_of_test_or_report']['value']=='1404/12/09'
    assert data['date_of_test_or_report']['calendar']=='jalali'
    assert data['sex']['value']=='female'
    assert data['age']['value']==27

def test_common_persian_male_tavo_line():
    data=CommonFieldExtractor().extract_structured('آقاي کورش - امیني تهران سن : 34')
    assert data['sex']['value']=='male'
    assert data['age']['value']==34
    assert 'کورش' in data['patient_name']['value']

def test_text_pdf_analysis_skips_quality_check(tmp_path):
    p=tmp_path/'lab.pdf'; doc=fitz.open(); page=doc.new_page(); page.insert_text((72,72),'Laboratory CBC Result Unit Reference Range WBC 7.2 10^3/uL 4.0-10.0'); doc.save(str(p)); doc.close()
    analysis=DocumentAnalysisService().analyze(str(p),'lab.pdf')
    assert analysis.pdf_type=='text_pdf'
    assert analysis.should_skip_image_quality_check is True

def test_image_relevance_uses_ocr_text_not_filename():
    rel=RelevanceService().check_from_text('CBC WBC Result Unit Reference Range','random-vacation.jpg')
    assert rel.is_medical_document is True
