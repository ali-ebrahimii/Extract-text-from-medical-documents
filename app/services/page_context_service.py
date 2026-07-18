from __future__ import annotations
from app.schemas.extraction_v2 import PageContext
class PageContextService:
    def detect(self,text:str,mime_type:str|None,fields:dict,lab_count:int)->PageContext:
        is_pdf=(mime_type or '').startswith('application/pdf')
        patient=fields.get('patient_name',{}).get('field_backend_usable'); date=fields.get('date_of_test_or_report',{}).get('field_backend_usable')
        template='generic_lab'
        if is_pdf and ('TAV' in text or 'O-' in text or 'کد ملی' in text): template='tav_text_pdf'
        elif not is_pdf and 'Nobin' in text: template='nobin_photo_with_history_charts'
        if 'culture' in text.lower() and lab_count<=2: role='culture_result_page'
        elif patient and date: role='standalone_report_page'
        elif lab_count and not (patient and date): role='continuation_or_body_only_page'
        elif patient or date: role='header_or_demographic_page'
        else: role='unknown_page_role'
        return PageContext(page_role=role,template_type=template,requires_backend_context_for_save=(role=='continuation_or_body_only_page'))
