from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import shutil, tempfile, uuid, logging
from app.schemas.extraction import *
from app.services.file_validation_service import FileValidationService, MIME_ALIASES, SUPPORTED
from app.services.document_analysis_service import DocumentAnalysisService
from app.services.relevance_service import RelevanceService
from app.services.quality_service import QualityService
from app.services.preprocessing_service import PreprocessingService
from app.services.ocr_service import OCRService
from app.services.classification_service import ClassificationService
from app.services.common_field_extractor import CommonFieldExtractor
from app.services.lab_extractor import LabExtractor
from app.services.pap_smear_extractor import PapSmearExtractor
from app.services.radiology_extractor import RadiologyExtractor
from app.services.confidence_service import ConfidenceService
from app.core.config import settings

log=logging.getLogger(__name__)

@dataclass
class ExtractionInput:
    file_path:str; file_name:str; mime_type:str|None=None; document_id:str|None=None; request_id:str|None=None; debug:bool=False

def _err(code,msg,field=None): return ExtractionError(code=code,message=msg,field=field)
def _warn(code,msg,field=None): return ExtractionWarning(code=code,message=msg,field=field)

class ExtractionPipeline:
    def __init__(self):
        self.file_validator=FileValidationService(); self.analysis=DocumentAnalysisService(); self.relevance=RelevanceService(); self.quality=QualityService(); self.preprocessing=PreprocessingService(); self.ocr=OCRService(); self.classifier=ClassificationService(); self.common=CommonFieldExtractor(); self.lab=LabExtractor(); self.pap=PapSmearExtractor(); self.rad=RadiologyExtractor(); self.conf=ConfidenceService()
    def _base(self, inp:ExtractionInput, status=ExtractionStatus.EXTRACTION_FAILED, errors=None):
        return ExtractionResponse(request_id=inp.request_id or str(uuid.uuid4()), document_id=inp.document_id, status=status, errors=errors or [])
    def _quality_schema(self,q):
        if not q: return QualitySummary()
        return QualitySummary(status=q.status,overall_quality_score=q.overall_quality_score,is_acceptable=q.is_acceptable,issues=q.issues,metrics=q.metrics,page_scores=q.page_scores,page_issues=q.page_issues,worst_page_number=q.worst_page_number,average_quality_score=q.average_quality_score,min_quality_score=q.min_quality_score,num_pages=q.num_pages)
    def _ocr_schema(self,o, include_text=False):
        if not o: return OCRSummary()
        pages=[OCRPageResultSchema(page_number=p.page_number,text=p.text if include_text else None,confidence=p.confidence,text_length=len(p.text or ''),source_path=p.source_path if include_text else None) for p in o.pages]
        return OCRSummary(success=o.success,confidence=o.confidence,text_length=len(o.text or ''),pages=pages,warnings=o.warnings,errors=[o.error] if o.error else [])
    def process(self, input:ExtractionInput, debug:bool=False)->ExtractionResponse:
        debug=debug or input.debug; inp=input; warnings=[]
        try:
            mt=MIME_ALIASES.get(inp.mime_type or '', inp.mime_type)
            val=self.file_validator.validate(inp.file_path, inp.file_name, mt)
            if not val.is_valid:
                code='UNSUPPORTED_FILE_TYPE' if 'Unsupported' in (val.reason or '') or val.status=='unsupported_file_type' else ('PDF_PASSWORD_PROTECTED' if 'Password' in (val.reason or '') else 'INVALID_MIME_TYPE' if 'MIME' in (val.reason or '') else 'FILE_READ_ERROR')
                status=ExtractionStatus.UNSUPPORTED_FILE if code=='UNSUPPORTED_FILE_TYPE' else ExtractionStatus.INVALID_FILE
                return self._base(inp,status,[_err(code,val.reason or 'Invalid file')])
            with tempfile.TemporaryDirectory(prefix='extract_pipeline_') as td:
                analysis=self.analysis.analyze(inp.file_path, inp.file_name); q=None; ocr=None; relevance_text=analysis.text_sample; ocr_paths=[]
                # If a PDF has any extractable text, reject clearly non-medical documents before image OCR.
                if analysis.file_type=='pdf' and relevance_text.strip():
                    early_rel=self.relevance.check_from_text(relevance_text, inp.file_name)
                    if not early_rel.is_medical_document:
                        return ExtractionResponse(request_id=inp.request_id or str(uuid.uuid4()),document_id=inp.document_id,status=ExtractionStatus.UNRELATED_DOCUMENT,document_type='unrelated_document',confidence=early_rel.relevance_score,quality=self._quality_schema(q),ocr=OCRSummary(success=True,confidence=.95,text_length=len(relevance_text),pages=[]),errors=[_err('UNRELATED_DOCUMENT',early_rel.rejection_reason or 'Unrelated document')],warnings=warnings,debug={'ocr_text': relevance_text,'relevance': early_rel.__dict__} if debug else None)
                if not analysis.should_skip_image_quality_check:
                    if analysis.file_type=='pdf':
                        render=self.preprocessing.render_pdf_pages(inp.file_path, None, settings.max_preprocess_pages, output_dir=td)
                        if not render.success: return self._base(inp,ExtractionStatus.OCR_FAILED,[_err('OCR_FAILED',render.error or 'PDF render failed')])
                        source_paths=render.output_paths; q=self.quality.assess_many(source_paths)
                    else:
                        source_paths=[inp.file_path]; q=self.quality.assess(inp.file_path)
                    if q.status=='poor_quality' and not q.is_fixable:
                        return self._base(inp,ExtractionStatus.POOR_QUALITY,[_err('POOR_IMAGE_QUALITY','Image quality is too poor to process')])
                    if q.status=='good_quality': ocr_paths=source_paths
                    else:
                        pre=self.preprocessing.preprocess(inp.file_path,None,settings.max_preprocess_pages if analysis.file_type=='pdf' else 1, output_dir=td)
                        if pre.success: warnings.append(_warn('QUALITY_PREPROCESSING_APPLIED','Preprocessing was applied before OCR')); ocr_paths=pre.output_paths
                        else: ocr_paths=source_paths; warnings.append(_warn('POSSIBLE_TABLE_LAYOUT_ISSUE',pre.error or 'Preprocessing failed; OCR used original image'))
                    ocr=self.ocr.extract_images_text(ocr_paths); relevance_text=ocr.text
                rel=self.relevance.check_from_text(relevance_text, inp.file_name)
                if not rel.is_medical_document and relevance_text.strip():
                    return ExtractionResponse(request_id=inp.request_id or str(uuid.uuid4()),document_id=inp.document_id,status=ExtractionStatus.UNRELATED_DOCUMENT,document_type='unrelated_document',confidence=rel.relevance_score,quality=self._quality_schema(q),ocr=self._ocr_schema(ocr,debug),errors=[_err('UNRELATED_DOCUMENT',rel.rejection_reason or 'Unrelated document')],warnings=warnings,debug={'ocr_text': relevance_text,'relevance': rel.__dict__} if debug else None)
                if ocr is None: ocr=self.ocr.extract_any(inp.file_path, analysis)
                if not ocr.success:
                    code='OCR_ENGINE_MISSING' if 'not available' in (ocr.error or '') else 'OCR_EMPTY_TEXT' if not (ocr.text or '').strip() else 'OCR_FAILED'
                    return ExtractionResponse(request_id=inp.request_id or str(uuid.uuid4()),document_id=inp.document_id,status=ExtractionStatus.OCR_FAILED,quality=self._quality_schema(q),ocr=self._ocr_schema(ocr,debug),errors=[_err(code,ocr.error or 'OCR failed')],warnings=warnings)
                cls=self.classifier.classify(ocr.text); common=self.common.extract_structured(ocr.text); specific={}
                if cls.document_type=='lab':
                    rows=self.lab.extract(ocr.text)
                    if rows and not common.get('test_or_report_name',{}).get('value'):
                        common['test_or_report_name']={'value':'Lab Report','confidence':0.5,'source_text':None,'source_line_index':None,'inferred':True}; warnings.append(_warn('INFERRED_REPORT_NAME','Inferred lab report name from extracted lab rows','test_or_report_name'))
                    if not rows: warnings.append(_warn('MISSING_LAB_ROWS','No lab result rows were extracted','lab_results'))
                    specific={'lab_results':rows}
                elif cls.document_type=='pap_smear': specific={'pap_smear':self.pap.extract(ocr.text)}
                elif cls.document_type=='radiology': specific={'radiology':self.rad.extract(ocr.text)}
                else: specific={}
                common_simple={k:(v.get('value') if isinstance(v,dict) else v) for k,v in common.items()}; conf=self.conf.calculate(ocr.confidence, cls.confidence, common_simple, specific.get('lab_results',specific))
                if not common.get('patient_name',{}).get('value'): warnings.append(_warn('MISSING_PATIENT_NAME','Patient name was not found','patient_name'))
                if not common.get('date_of_test_or_report',{}).get('value'): warnings.append(_warn('MISSING_REPORT_DATE','Report date was not found','date_of_test_or_report'))
                status=ExtractionStatus.SUCCESS if conf>=0.75 else ExtractionStatus.LOW_CONFIDENCE
                if status==ExtractionStatus.LOW_CONFIDENCE: warnings.append(_warn('LOW_EXTRACTION_CONFIDENCE','Overall extraction confidence is low'))
                return ExtractionResponse(request_id=inp.request_id or str(uuid.uuid4()),document_id=inp.document_id,status=status,document_type=cls.document_type,confidence=conf,quality=self._quality_schema(q),ocr=self._ocr_schema(ocr,debug),common_fields=common,extracted_data=specific,errors=[],warnings=warnings,debug={'ocr_text':ocr.text,'page_text':[p.text for p in ocr.pages],'classification':cls.__dict__,'relevance':rel.__dict__} if debug else None)
        except Exception as e:
            log.exception('Extraction failed')
            return self._base(inp,ExtractionStatus.EXTRACTION_FAILED,[_err('EXTRACTION_FAILED','Extraction failed')])
