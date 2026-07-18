from __future__ import annotations
from app.schemas.extraction_v2 import PersistenceRecommendation
class PersistenceRecommendationService:
    def recommend(self,request_id,document_id,filename,document_type,page_context,ocr,fields,rows,mime_type):
        valid_fields={k:v for k,v in fields.items() if v.get('field_backend_usable') and not (k=='doctor_name' and not v.get('source_text'))}
        if ocr.final_unsafe_ocr_context:
            rec=PersistenceRecommendation(recommended_action='reupload_recommended',review_required=True,reupload_required=True,reason_codes=['unsafe_ocr_context'])
        elif page_context.requires_backend_context_for_save:
            rec=PersistenceRecommendation(recommended_action='manual_review',review_required=True,reason_codes=['requires_backend_context_for_save'])
        elif not rows:
            rec=PersistenceRecommendation(recommended_action='reject_or_ignore',review_required=False,reason_codes=['no_lab_rows'])
        elif (mime_type or '').startswith('application/pdf') and fields.get('patient_name',{}).get('field_backend_usable') and fields.get('date_of_test_or_report',{}).get('field_backend_usable') and any(r.row_save_allowed for r in rows):
            rec=PersistenceRecommendation(recommended_action='save_candidate',recommended_save=True,review_required=False)
        else:
            rec=PersistenceRecommendation(recommended_action='manual_review',review_required=True,reason_codes=['image_or_incomplete_context'])
        for r in rows: r.backend_row_save_recommendation=bool(rec.recommended_save and r.row_save_allowed)
        meta={'request_id':request_id,'document_id':document_id,'filename':filename,'document_type':document_type,'page_role':page_context.page_role,'template_type':page_context.template_type}
        if fields.get('tracking_number',{}).get('field_backend_usable'): meta['tracking_number']=fields['tracking_number'].get('value')
        safe={**meta,'common_fields':valid_fields,'lab_results':[r.model_dump(exclude_none=True) for r in rows if r.backend_row_save_recommendation]} if rec.recommended_save else {}
        review={**meta,'common_fields':fields,'lab_results':[r.model_dump(exclude_none=True) for r in rows]}
        return rec,safe,review
