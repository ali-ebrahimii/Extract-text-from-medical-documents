from app.core.config import settings
from app.core.enums import DocumentStatus, DocumentType, VerificationStatus
from app.models.document import MedicalDocument
from app.models.quality import DocumentQualityCheck, DocumentRelevanceCheck
from app.models.preprocessing import DocumentPreprocessing
from app.models.patient import DocumentPatient
from app.models.lab_result import LabResult
from app.models.pap_smear import PapSmearReport
from app.models.radiology import RadiologyReport
from app.models.review import ReviewTask
from app.models.ocr_page import OCRPage
from app.services.file_validation_service import FileValidationService
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
from app.services.normalization_service import NormalizationService
from app.services.confidence_service import ConfidenceService

class PipelineService:
    def __init__(self):
        self.file_validator=FileValidationService(); self.analysis=DocumentAnalysisService(); self.relevance=RelevanceService(); self.quality=QualityService(); self.preprocessing=PreprocessingService(); self.ocr=OCRService(); self.classifier=ClassificationService(); self.common=CommonFieldExtractor(); self.lab=LabExtractor(); self.pap=PapSmearExtractor(); self.rad=RadiologyExtractor(); self.norm=NormalizationService(); self.conf=ConfidenceService()
    def _stop(self,db,doc,status,reason=None):
        doc.validation_status=status; doc.rejection_reason=reason; db.commit(); db.refresh(doc); return doc
    def _save_quality(self,db,doc,q):
        db.add(DocumentQualityCheck(document_id=doc.id, blur_score=q.blur_score, brightness_score=q.brightness_score, contrast_score=q.contrast_score, resolution_score=q.resolution_score, crop_score=q.crop_score, orientation_score=q.orientation_score, ocr_readability_score=q.ocr_readability_score, overall_quality_score=q.overall_quality_score, is_acceptable=q.is_acceptable, issues=q.issues))
    def _save_ocr_pages(self,db,doc,ocr):
        for p in ocr.pages:
            db.add(OCRPage(document_id=doc.id,page_number=p.page_number,source_path=p.source_path,ocr_text=p.text,ocr_confidence=p.confidence))
    def process_document(self,db,document_id:int)->MedicalDocument:
        doc=db.get(MedicalDocument, document_id); warnings=[]
        dup=db.query(MedicalDocument).filter(MedicalDocument.file_hash==doc.file_hash, MedicalDocument.id!=doc.id).order_by(MedicalDocument.id).first()
        if dup:
            warnings.append('duplicate_file_hash_detected')
            if getattr(settings,'block_duplicate_uploads',False):
                doc.warnings=warnings+[f'existing_document_id={dup.id}']
                return self._stop(db,doc,DocumentStatus.DUPLICATE_DOCUMENT.value,f'Duplicate of document {dup.id}')
        val=self.file_validator.validate(doc.original_file_path, doc.original_file_name, doc.original_file_type)
        if not val.is_valid: return self._stop(db,doc,val.status,val.reason)
        analysis=self.analysis.analyze(doc.original_file_path, doc.original_file_name)
        # ocr_paths: image paths fed to OCR (rendered or preprocessed).
        ocr_paths:list[str]=[]; q=None; ocr=None
        # Text PDF relevance uses embedded text; images/scanned PDFs OCR once and reuse.
        relevance_text=analysis.text_sample
        if analysis.should_skip_image_quality_check:
            # text_pdf: skip quality + skip preprocessing; final OCR is PDF text below.
            doc.quality_score_before=None; doc.quality_score_after=None
        else:
            is_pdf=analysis.file_type=='pdf'
            # Scanned PDFs must be rendered to images for OCR regardless of quality
            # (rendering != image enhancement). Assess quality page-by-page.
            if is_pdf:
                render=self.preprocessing.render_pdf_pages(doc.original_file_path, doc.id, max_pages=settings.max_preprocess_pages)
                if not render.success: return self._stop(db,doc,DocumentStatus.OCR_FAILED.value,render.error)
                source_paths=render.output_paths
                q=self.quality.assess_many(source_paths)
            else:
                source_paths=[doc.original_file_path]
                q=self.quality.assess(doc.original_file_path)
            doc.quality_score_before=q.overall_quality_score; doc.quality_issues=q.issues; self._save_quality(db,doc,q)
            if q.status=='poor_quality' and not q.is_fixable: return self._stop(db,doc,DocumentStatus.POOR_QUALITY.value,'Image quality is too poor to process')
            if q.status=='good_quality':
                # Do not preprocess good-quality input; OCR the original/rendered pages.
                doc.quality_score_after=q.overall_quality_score; ocr_paths=source_paths
            else:
                # needs_preprocessing, or poor_quality but fixable: enhance the image(s).
                pre=self.preprocessing.preprocess(doc.original_file_path, doc.id, max_pages=settings.max_preprocess_pages if is_pdf else 1)
                db.add(DocumentPreprocessing(document_id=doc.id,preprocessing_required=True,preprocessing_applied=pre.success,quality_score_before=q.overall_quality_score,preprocessing_steps=pre.steps,original_page_path=doc.original_file_path,preprocessed_page_path=pre.output_path,preprocessed_page_paths=pre.output_paths,preprocessing_status='completed' if pre.success else 'failed',preprocessing_error=pre.error))
                if not pre.success: return self._stop(db,doc,DocumentStatus.PREPROCESSING_FAILED.value,pre.error)
                doc.preprocessing_required=True; doc.preprocessing_status='completed'; doc.preprocessed_file_path=pre.output_path; ocr_paths=pre.output_paths
                q2=self.quality.assess_many(pre.output_paths) if pre.output_paths else q; doc.quality_score_after=q2.overall_quality_score
                # poor-but-fixable: continue only if preprocessing actually improved quality.
                if q.status=='poor_quality' and q2.status=='poor_quality' and q2.overall_quality_score<=q.overall_quality_score:
                    return self._stop(db,doc,DocumentStatus.POOR_QUALITY.value,'Quality remains poor after preprocessing')
            # Single OCR pass for image/scanned PDFs: reuse for relevance AND extraction.
            doc.validation_status=DocumentStatus.OCR_PROCESSING.value
            ocr=self.ocr.extract_images_text(ocr_paths)
            relevance_text=ocr.text
            for w in ocr.warnings:
                if w not in warnings: warnings.append(w)
        rel=self.relevance.check_from_text(relevance_text, doc.original_file_name)
        doc.relevance_score=rel.relevance_score; db.add(DocumentRelevanceCheck(document_id=doc.id,is_medical_document=rel.is_medical_document,relevance_score=rel.relevance_score,detected_keywords=rel.detected_keywords,detected_document_signals=rel.detected_document_signals,rejection_reason=rel.rejection_reason))
        if not rel.is_medical_document and relevance_text.strip():
            doc.document_type=DocumentType.UNRELATED_DOCUMENT.value; return self._stop(db,doc,DocumentStatus.UNRELATED_DOCUMENT.value,rel.rejection_reason)
        if not rel.is_medical_document and not analysis.should_skip_image_quality_check:
            warnings.append('relevance_uncertain_ocr_text_unavailable')
        # Text PDFs: final OCR is the embedded text layer (single read, no image OCR).
        if ocr is None:
            doc.validation_status=DocumentStatus.OCR_PROCESSING.value
            ocr=self.ocr.extract_any(doc.original_file_path, analysis)
        doc.ocr_text=ocr.text; doc.ocr_confidence=ocr.confidence; self._save_ocr_pages(db,doc,ocr)
        if not ocr.success:
            engine_missing='OCR engine is not available' in (ocr.error or '')
            if q is not None and q.status!='good_quality' and not (ocr.text or '').strip() and not engine_missing:
                return self._stop(db,doc,DocumentStatus.POOR_QUALITY.value,ocr.error or 'OCR produced no text on low-quality input')
            return self._stop(db,doc,DocumentStatus.OCR_FAILED.value,ocr.error)
        doc.validation_status=DocumentStatus.CLASSIFICATION_PROCESSING.value; cls=self.classifier.classify(ocr.text); doc.document_type=cls.document_type; doc.document_type_confidence=cls.confidence
        doc.validation_status=DocumentStatus.EXTRACTION_PROCESSING.value; common_s=self.common.extract_structured(ocr.text); common=self.common.extract(ocr.text)
        doc.test_or_report_name=common.get('test_or_report_name'); doc.test_or_report_date=common.get('date_of_test_or_report'); doc.center_name=common.get('center_name')
        db.add(DocumentPatient(document_id=doc.id, patient_name=common.get('patient_name'), patient_name_confidence=common_s['patient_name']['confidence'], national_id_hash=common_s['national_id']['hash'], national_id_confidence=common_s['national_id']['confidence'], age=common.get('age'), sex=common.get('sex')))
        specific=[] if cls.document_type==DocumentType.LAB.value else {}
        if cls.document_type==DocumentType.LAB.value:
            specific=self.lab.extract(ocr.text)
            for r in specific: db.add(LabResult(document_id=doc.id, **r))
        elif cls.document_type==DocumentType.PAP_SMEAR.value:
            specific=self.pap.extract(ocr.text); db.add(PapSmearReport(document_id=doc.id, **specific))
        elif cls.document_type==DocumentType.RADIOLOGY.value:
            specific=self.rad.extract(ocr.text); db.add(RadiologyReport(document_id=doc.id, **specific))
        doc.extraction_confidence=self.conf.calculate(ocr.confidence, cls.confidence, common, specific)
        missing=[k for k in ['patient_name','national_id','date_of_test_or_report','test_or_report_name'] if not common.get(k)]
        needs = cls.document_type==DocumentType.UNKNOWN_MEDICAL.value or bool(missing) or doc.extraction_confidence < .75 or (q is not None and q.status!='good_quality')
        doc.validation_status=DocumentStatus.PROCESSED.value; doc.verification_status=VerificationStatus.NEEDS_REVIEW.value if needs else VerificationStatus.UNVERIFIED.value; doc.warnings=warnings or None
        if needs: db.add(ReviewTask(document_id=doc.id, reason='; '.join(missing) or 'Low confidence or quality requires review', priority=5 if missing else 3, status='open'))
        db.commit(); db.refresh(doc); return doc
