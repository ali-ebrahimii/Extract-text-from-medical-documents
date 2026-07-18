#!/usr/bin/env python
from __future__ import annotations
import argparse, json, mimetypes, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.extraction_pipeline_v2 import ExtractionInputV2, ExtractionPipelineV2

def is_image(p): return p.suffix.lower() in {'.png','.jpg','.jpeg','.tif','.tiff','.bmp','.webp'}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--samples-dir',required=True); ap.add_argument('--reference-dir'); ap.add_argument('--output-dir',required=True); args=ap.parse_args()
    sd=Path(args.samples_dir); out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    if not sd.exists(): print('samples_dir_missing'); return 0
    pipe=ExtractionPipelineV2(); metrics=dict.fromkeys(['total_files_processed','recommended_save_count','manual_review_count','reupload_recommended_count','clean_pdfs_recommended_save_count','image_recommended_save_count','backend_safe_row_count','image_rows_with_backend_row_save_recommendation_true','unsafe_doctor_name_in_safe_payload_count','false_bacteria_48_or_culture_48_count','normal_ast_alt_falsely_low_count','national_id_schema_violations_count','tracking_number_missing_in_clean_pdfs_count'],0)
    for p in sorted(x for x in sd.rglob('*') if x.is_file()):
        mt=mimetypes.guess_type(p.name)[0] or 'application/octet-stream'; res=pipe.process(ExtractionInputV2(str(p),p.name,mt,privacy_mode='internal'))
        data=res.model_dump(mode='json',exclude_none=True); (out/(p.name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2))
        metrics['total_files_processed']+=1; rec=res.persistence_recommendation
        metrics['recommended_save_count']+=rec.recommended_save; metrics['manual_review_count']+=rec.recommended_action=='manual_review'; metrics['reupload_recommended_count']+=rec.recommended_action=='reupload_recommended'
        img=is_image(p); pdf=p.suffix.lower()=='.pdf'
        metrics['image_recommended_save_count']+= img and rec.recommended_save; metrics['clean_pdfs_recommended_save_count']+= pdf and rec.recommended_save
        metrics['backend_safe_row_count']+=sum(r.backend_row_save_recommendation for r in res.lab_results)
        metrics['image_rows_with_backend_row_save_recommendation_true']+=sum(r.backend_row_save_recommendation for r in res.lab_results) if img else 0
        metrics['unsafe_doctor_name_in_safe_payload_count']+='doctor_name' in res.safe_payload_candidate.get('common_fields',{})
        for r in res.lab_results:
            metrics['false_bacteria_48_or_culture_48_count']+= r.test_name_standard in ('Bacteria','Urine Culture','Culture') and r.result_numeric==48
            metrics['normal_ast_alt_falsely_low_count']+= r.test_name_standard in ('AST','ALT') and r.unit in ('U/L','IU/L') and r.flag=='Low'
        nid=res.common_fields.get('national_id',{})
        metrics['national_id_schema_violations_count']+= 'value' in nid or (nid and not {'raw_value','masked_value','hash_sha256'} & set(nid))
        metrics['tracking_number_missing_in_clean_pdfs_count']+= pdf and res.document.page_context.template_type=='tav_text_pdf' and not res.common_fields.get('tracking_number',{}).get('field_backend_usable')
    for k,v in metrics.items(): print(f'{k}: {v}')
if __name__=='__main__': raise SystemExit(main())
