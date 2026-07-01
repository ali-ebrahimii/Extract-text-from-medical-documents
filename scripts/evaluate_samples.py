#!/usr/bin/env python
"""Stateless offline evaluation harness.

Example:
    python scripts/evaluate_samples.py --input-dir samples/raw --output-dir samples/output --limit 20 --debug
"""
from __future__ import annotations
import argparse, csv, json, mimetypes, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.extraction_pipeline import ExtractionInput, ExtractionPipeline
from app.services.file_validation_service import SUPPORTED

MIME_MAP={".pdf":"application/pdf",".jpg":"image/jpeg",".jpeg":"image/jpeg",".png":"image/png",".webp":"image/webp"}
CSV_COLUMNS=["filename","request_id","document_id","status","document_type","confidence","relevance_score","quality_score","ocr_confidence","ocr_text_length","patient_name_found","national_id_hash_found","date_found","center_name_found","tracking_number_found","age_found","sex_found","test_or_report_name_found","lab_result_count","pap_smear_found","radiology_found","error_codes","warning_codes","patient_name_value_masked_or_present","false_positive_suspected_count","ocr_warning_count","quality_worst_page_number","quality_min_score","validation_status","verification_status","document_type_confidence","quality_score_before","quality_score_after","extraction_confidence","rejection_reason","warnings"]

def dump_model(m): return m.model_dump(mode='json') if hasattr(m,'model_dump') else m.dict()
def found(common,k):
    f=common.get(k) or {}; return bool(f.get('value') if isinstance(f,dict) else f)
def row(filename, resp):
    common=resp.get('common_fields') or {}; ext=resp.get('extracted_data') or {}; dbg=resp.get('debug') or {}; rel=(dbg.get('relevance') or {}).get('relevance_score')
    return {"filename":filename,"request_id":resp.get('request_id'),"document_id":resp.get('document_id'),"status":resp.get('status'),"document_type":resp.get('document_type'),"confidence":resp.get('confidence'),"relevance_score":rel,"quality_score":(resp.get('quality') or {}).get('overall_quality_score'),"ocr_confidence":(resp.get('ocr') or {}).get('confidence'),"ocr_text_length":(resp.get('ocr') or {}).get('text_length'),"patient_name_found":found(common,'patient_name'),"national_id_hash_found":bool((common.get('national_id') or {}).get('hash')),"date_found":found(common,'date_of_test_or_report'),"center_name_found":found(common,'center_name'),"tracking_number_found":found(common,'tracking_number'),"age_found":found(common,'age'),"sex_found":found(common,'sex'),"test_or_report_name_found":found(common,'test_or_report_name'),"lab_result_count":len(ext.get('lab_results') or []),"pap_smear_found":bool(ext.get('pap_smear')),"radiology_found":bool(ext.get('radiology')),"error_codes":"|".join(e.get('code','') for e in resp.get('errors',[])),"warning_codes":"|".join(w.get('code','') for w in resp.get('warnings',[])),"patient_name_value_masked_or_present":found(common,'patient_name'),"false_positive_suspected_count":0,"ocr_warning_count":len((resp.get('ocr') or {}).get('warnings') or []),"quality_worst_page_number":(resp.get('quality') or {}).get('worst_page_number'),"quality_min_score":(resp.get('quality') or {}).get('min_quality_score'),"validation_status":resp.get('status'),"verification_status":None,"document_type_confidence":None,"quality_score_before":(resp.get('quality') or {}).get('overall_quality_score'),"quality_score_after":None,"extraction_confidence":resp.get('confidence'),"rejection_reason":"|".join(e.get('message','') for e in resp.get('errors',[])),"warnings":"|".join(w.get('message','') for w in resp.get('warnings',[]))}

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--input-dir',required=True); ap.add_argument('--output-dir',required=True); ap.add_argument('--limit',type=int,default=0); ap.add_argument('--debug',action='store_true')
    args=ap.parse_args(argv); inp=Path(args.input_dir); out=Path(args.output_dir)
    if not inp.is_dir(): print(f'Input dir not found: {inp}',file=sys.stderr); return 2
    (out/'json').mkdir(parents=True,exist_ok=True); (out/'ocr').mkdir(parents=True,exist_ok=True)
    files=sorted(p for p in inp.rglob('*') if p.is_file() and p.suffix.lower() in SUPPORTED)
    if args.limit: files=files[:args.limit]
    pipe=ExtractionPipeline(); rows=[]
    for i,p in enumerate(files,1):
        resp=pipe.process(ExtractionInput(file_path=str(p),file_name=p.name,mime_type=MIME_MAP.get(p.suffix.lower()),document_id=p.stem,debug=args.debug),debug=args.debug)
        d=dump_model(resp); (out/'json'/f'{p.stem}.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
        ocr_text=((d.get('debug') or {}).get('ocr_text') or '') if args.debug else ''
        (out/'ocr'/f'{p.stem}.txt').write_text(ocr_text,encoding='utf-8')
        rows.append(row(p.name,d)); print(f"[{i}/{len(files)}] {p.name} -> {d.get('status')}")
    with (out/'summary.csv').open('w',newline='',encoding='utf-8') as f: w=csv.DictWriter(f,fieldnames=CSV_COLUMNS); w.writeheader(); w.writerows(rows)
    print(f"Wrote {len(rows)} rows to {out/'summary.csv'}"); return 0
if __name__=='__main__': raise SystemExit(main())
