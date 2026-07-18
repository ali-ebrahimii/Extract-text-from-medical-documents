from __future__ import annotations
from dataclasses import dataclass
import uuid
from app.schemas.extraction_v2 import ExtractionResponseV2, DocumentInfoV2, QualityV2, OCRInfoV2
from app.services.file_validation_service import FileValidationService, MIME_ALIASES
from app.services.ocr_layout_service import OCRLayoutService
from app.services.common_field_validation_service import CommonFieldValidationService
from app.services.lab_extractor_v2 import LabExtractorV2
from app.services.page_context_service import PageContextService
from app.services.persistence_recommendation_service import PersistenceRecommendationService

@dataclass
class ExtractionInputV2:
    file_path: str; file_name: str; mime_type: str|None=None; document_id: str|None=None; request_id: str|None=None; debug: bool=False; privacy_mode: str='internal'

class ExtractionPipelineV2:
    def __init__(self):
        self.validator=FileValidationService(); self.ocr=OCRLayoutService(); self.common=CommonFieldValidationService(); self.lab=LabExtractorV2(); self.context=PageContextService(); self.persist=PersistenceRecommendationService()
    def process(self,inp:ExtractionInputV2,debug:bool=False,privacy_mode:str|None=None)->ExtractionResponseV2:
        request_id=inp.request_id or str(uuid.uuid4()); mime=MIME_ALIASES.get(inp.mime_type or '',inp.mime_type)
        privacy_mode=privacy_mode or inp.privacy_mode
        val=self.validator.validate(inp.file_path,inp.file_name,mime)
        if not val.is_valid:
            doc=DocumentInfoV2(filename=inp.file_name,mime_type=mime,document_type='unknown',extraction_status='invalid_file')
            return ExtractionResponseV2(request_id=request_id,document_id=inp.document_id,document=doc,quality=QualityV2(quality_status=val.status or 'invalid',quality_issues=[val.reason or 'invalid_file']))
        cand=self.ocr.extract(inp.file_path,mime)
        unsafe=cand.layout_status in ('gibberish_or_bad_layout_text','poor_ocr_text','empty_text')
        fields=self.common.extract(cand.text,unsafe,privacy_mode)
        rows=self.lab.extract(cand.text,cand.visual_lines,unsafe)
        page_context=self.context.detect(cand.text,mime,fields,len(rows))
        ocr_info=OCRInfoV2(success=bool(cand.text.strip()) and not unsafe,confidence=cand.confidence,text_length=len(cand.text),layout_status=cand.layout_status,final_unsafe_ocr_context=unsafe,selected_variant=cand.variant_name,psm=cand.psm,lang=cand.lang,score_details=cand.score_details)
        rec,safe,review=self.persist.recommend(request_id,inp.document_id,inp.file_name,'lab',page_context,ocr_info,fields,rows,mime or '')
        status='extracted_good' if rec.recommended_save else 'needs_review' if rec.review_required else 'not_extractable'
        doc=DocumentInfoV2(filename=inp.file_name,mime_type=mime,document_type='lab' if rows else 'unknown_medical',document_type_confidence=.85 if rows else .2,extraction_status=status,page_context=page_context)
        dbg={}
        if debug or inp.debug: dbg={'ocr_text':cand.text,'ocr_words':cand.words,'visual_lines':cand.visual_lines,'ocr_candidate':cand.__dict__}
        return ExtractionResponseV2(request_id=request_id,document_id=inp.document_id,document=doc,quality=QualityV2(quality_status='usable' if not unsafe else 'poor_ocr',quality_score=cand.confidence/100,quality_issues=[] if not unsafe else [cand.layout_status]),ocr=ocr_info,persistence_recommendation=rec,common_fields=fields,lab_results=rows,safe_payload_candidate=safe,review_payload=review,debug=dbg)
