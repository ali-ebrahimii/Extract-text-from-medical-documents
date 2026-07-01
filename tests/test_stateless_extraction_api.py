import base64, csv, fitz
from pathlib import Path


def _text_pdf(tmp_path, name='lab.pdf', lines=None):
    lines=lines or ['Laboratory Tavo','Patient Name: Ali Rezaei','Report Date: 2024/03/01','Test: CBC','WBC 7.2 10^3/uL 4.0-10.0']
    doc=fitz.open(); page=doc.new_page(); y=72
    for line in lines: page.insert_text((72,y),line); y+=22
    p=tmp_path/name; doc.save(str(p)); doc.close(); return p


def test_extract_file_stateless_without_database(client, tmp_path):
    p=_text_pdf(tmp_path)
    with p.open('rb') as f:
        r=client.post('/extract/file', files={'file':('lab.pdf',f,'application/pdf')}, data={'document_id':'doc-1'})
    assert r.status_code==200
    body=r.json()
    assert body['document_id']=='doc-1'
    assert body['status'] in {'success','low_confidence'}
    assert body['document_type']=='lab'
    assert body['extracted_data']['lab_results']


def test_extract_json_file_path_text_pdf(client, tmp_path):
    p=_text_pdf(tmp_path)
    r=client.post('/extract', json={'document_id':'doc-2','file_path':str(p),'file_name':'lab.pdf','mime_type':'application/pdf','debug':True})
    body=r.json()
    assert r.status_code==200
    assert body['ocr']['success'] is True
    assert body['debug']['ocr_text']


def test_extract_json_base64(client, tmp_path):
    p=_text_pdf(tmp_path)
    b64=base64.b64encode(p.read_bytes()).decode()
    r=client.post('/extract', json={'document_id':'doc-b64','file_name':'lab.pdf','mime_type':'application/pdf','base64_content':b64})
    assert r.status_code==200
    assert r.json()['document_id']=='doc-b64'


def test_invalid_file_returns_json_error(client, tmp_path):
    p=tmp_path/'bad.pdf'; p.write_text('not a pdf')
    r=client.post('/extract', json={'file_path':str(p),'file_name':'bad.pdf','mime_type':'application/pdf'})
    body=r.json()
    assert r.status_code==200
    assert body['status']=='invalid_file'
    assert body['errors'][0]['code'] in {'FILE_READ_ERROR','PDF_PASSWORD_PROTECTED','INVALID_MIME_TYPE'}


def test_unrelated_document_returns_unrelated(client, tmp_path):
    p=_text_pdf(tmp_path, lines=['Invoice','Total due 10 dollars','Thank you'])
    r=client.post('/extract', json={'file_path':str(p),'file_name':'invoice.pdf','mime_type':'application/pdf'})
    assert r.json()['status']=='unrelated_document'


def test_evaluation_script_produces_summary_csv(tmp_path):
    from scripts.evaluate_samples import main
    raw=tmp_path/'raw'; out=tmp_path/'out'; raw.mkdir(); _text_pdf(raw, name='lab.pdf')
    assert main(['--input-dir',str(raw),'--output-dir',str(out),'--limit','1','--debug'])==0
    rows=list(csv.DictReader((out/'summary.csv').open()))
    assert len(rows)==1
    assert rows[0]['filename']=='lab.pdf'
    assert (out/'json'/'lab.json').exists()
