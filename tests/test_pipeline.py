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
