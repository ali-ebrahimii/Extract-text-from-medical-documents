from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import logging
import tempfile
import uuid

from app.core.config import settings
from app.schemas.extraction import (
    ExtractionError,
    ExtractionResponse,
    ExtractionStatus,
    ExtractionWarning,
    OCRPageResultSchema,
    OCRSummary,
    QualitySummary,
)
from app.services.classification_service import ClassificationService
from app.services.common_field_extractor import CommonFieldExtractor
from app.services.confidence_service import ConfidenceService
from app.services.document_analysis_service import DocumentAnalysisService
from app.services.file_validation_service import FileValidationService, MIME_ALIASES
from app.services.lab_extractor import LabExtractor
from app.services.ocr_service import OCRService
from app.services.pap_smear_extractor import PapSmearExtractor
from app.services.preprocessing_service import PreprocessingService
from app.services.quality_service import QualityService
from app.services.radiology_extractor import RadiologyExtractor
from app.services.relevance_service import RelevanceService

log = logging.getLogger(__name__)


@dataclass
class ExtractionInput:
    file_path: str
    file_name: str
    mime_type: str | None = None
    document_id: str | None = None
    request_id: str | None = None
    debug: bool = False


def _err(code, msg, field=None):
    return ExtractionError(code=code, message=msg, field=field)


def _warn(code, msg, field=None):
    return ExtractionWarning(code=code, message=msg, field=field)


class ExtractionPipeline:
    def __init__(self):
        self.file_validator = FileValidationService()
        self.analysis = DocumentAnalysisService()
        self.relevance = RelevanceService()
        self.quality = QualityService()
        self.preprocessing = PreprocessingService()
        self.ocr = OCRService()
        self.classifier = ClassificationService()
        self.common = CommonFieldExtractor()
        self.lab = LabExtractor()
        self.pap = PapSmearExtractor()
        self.rad = RadiologyExtractor()
        self.conf = ConfidenceService()

    def process(self, input: ExtractionInput, debug: bool = False) -> ExtractionResponse:
        debug = debug or input.debug
        warnings: list[ExtractionWarning] = []

        try:
            invalid_response = self._validate_input(input)
            if invalid_response:
                return invalid_response

            with tempfile.TemporaryDirectory(prefix="extract_pipeline_") as tmp_dir:
                analysis = self.analysis.analyze(input.file_path, input.file_name)
                quality = None
                ocr = None
                relevance_text = analysis.text_sample

                early_response = self._check_relevance(
                    input, relevance_text, quality, ocr, warnings, debug, early_pdf=analysis.file_type == "pdf"
                )
                if early_response:
                    return early_response

                if not analysis.should_skip_image_quality_check:
                    ocr, quality, relevance_text = self._prepare_ocr(input, analysis, warnings, tmp_dir)
                    if isinstance(ocr, ExtractionResponse):
                        return ocr

                relevance_response = self._check_relevance(
                    input, relevance_text, quality, ocr, warnings, debug
                )
                if relevance_response:
                    return relevance_response

                if ocr is None:
                    ocr = self.ocr.extract_any(input.file_path, analysis)
                if not ocr.success:
                    return self._build_error_response(input, ExtractionStatus.OCR_FAILED, ocr, quality, warnings)

                return self._build_response(input, ocr, quality, relevance_text, warnings, debug)
        except Exception:
            log.exception("Extraction failed")
            return self._base(input, ExtractionStatus.EXTRACTION_FAILED, [_err("EXTRACTION_FAILED", "Extraction failed")])

    def _validate_input(self, inp: ExtractionInput) -> ExtractionResponse | None:
        mime_type = MIME_ALIASES.get(inp.mime_type or "", inp.mime_type)
        validation = self.file_validator.validate(inp.file_path, inp.file_name, mime_type)
        if validation.is_valid:
            return None

        reason = validation.reason or "Invalid file"
        if "Unsupported" in reason or validation.status == "unsupported_file_type":
            code = "UNSUPPORTED_FILE_TYPE"
            status = ExtractionStatus.UNSUPPORTED_FILE
        elif "Password" in reason:
            code = "PDF_PASSWORD_PROTECTED"
            status = ExtractionStatus.INVALID_FILE
        elif "MIME" in reason:
            code = "INVALID_MIME_TYPE"
            status = ExtractionStatus.INVALID_FILE
        else:
            code = "FILE_READ_ERROR"
            status = ExtractionStatus.INVALID_FILE
        return self._base(inp, status, [_err(code, reason)])

    def _prepare_ocr(self, inp: ExtractionInput, analysis, warnings, tmp_dir: str):
        if analysis.file_type == "pdf":
            render = self.preprocessing.render_pdf_pages(
                inp.file_path, None, settings.max_preprocess_pages, output_dir=tmp_dir
            )
            if not render.success:
                return self._base(
                    inp, ExtractionStatus.OCR_FAILED, [_err("OCR_FAILED", render.error or "PDF render failed")]
                ), None, ""
            source_paths = render.output_paths
            quality = self.quality.assess_many(source_paths)
        else:
            source_paths = [inp.file_path]
            quality = self.quality.assess(inp.file_path)

        if quality.status == "poor_quality" and not quality.is_fixable:
            return self._base(
                inp,
                ExtractionStatus.POOR_QUALITY,
                [_err("POOR_IMAGE_QUALITY", "Image quality is too poor to process")],
            ), quality, ""

        if quality.status == "good_quality":
            ocr_paths = source_paths
        else:
            pre = self.preprocessing.preprocess(
                inp.file_path,
                None,
                settings.max_preprocess_pages if analysis.file_type == "pdf" else 1,
                output_dir=tmp_dir,
            )
            if pre.success:
                warnings.append(_warn("QUALITY_PREPROCESSING_APPLIED", "Preprocessing was applied before OCR"))
                ocr_paths = pre.output_paths
            else:
                warnings.append(
                    _warn(
                        "POSSIBLE_TABLE_LAYOUT_ISSUE",
                        pre.error or "Preprocessing failed; OCR used original image",
                    )
                )
                ocr_paths = source_paths

        ocr = self.ocr.extract_images_text(ocr_paths)
        return ocr, quality, ocr.text

    def _check_relevance(self, inp, text, quality, ocr, warnings, debug, early_pdf: bool = False):
        if early_pdf and not text.strip():
            return None
        rel = self.relevance.check_from_text(text, inp.file_name)
        if rel.is_medical_document or not text.strip():
            return None
        return ExtractionResponse(
            request_id=inp.request_id or str(uuid.uuid4()),
            document_id=inp.document_id,
            status=ExtractionStatus.UNRELATED_DOCUMENT,
            document_type="unrelated_document",
            confidence=rel.relevance_score,
            quality=self._quality_schema(quality),
            ocr=OCRSummary(success=True, confidence=0.95, text_length=len(text), pages=[]) if early_pdf else self._ocr_schema(ocr, debug),
            errors=[_err("UNRELATED_DOCUMENT", rel.rejection_reason or "Unrelated document")],
            warnings=warnings,
            debug={"ocr_text": text, "relevance": rel.__dict__} if debug else None,
        )

    def _extract_structured_data(self, document_type: str, text: str, common, warnings):
        if document_type == "lab":
            rows = self.lab.extract(text)
            if rows and not common.get("test_or_report_name", {}).get("value"):
                common["test_or_report_name"] = {
                    "value": "Lab Report",
                    "confidence": 0.5,
                    "source_text": None,
                    "source_line_index": None,
                    "inferred": True,
                }
                warnings.append(
                    _warn("INFERRED_REPORT_NAME", "Inferred lab report name from extracted lab rows", "test_or_report_name")
                )
            if not rows:
                warnings.append(_warn("MISSING_LAB_ROWS", "No lab result rows were extracted", "lab_results"))
            return {"lab_results": rows}
        if document_type == "pap_smear":
            return {"pap_smear": self.pap.extract(text)}
        if document_type == "radiology":
            return {"radiology": self.rad.extract(text)}
        return {}

    def _build_response(self, inp, ocr, quality, relevance_text, warnings, debug):
        rel = self.relevance.check_from_text(relevance_text, inp.file_name)
        cls = self.classifier.classify(ocr.text)
        common = self.common.extract_structured(ocr.text)
        specific = self._extract_structured_data(cls.document_type, ocr.text, common, warnings)
        common_simple = {k: (v.get("value") if isinstance(v, dict) else v) for k, v in common.items()}
        confidence = self.conf.calculate(ocr.confidence, cls.confidence, common_simple, specific.get("lab_results", specific))

        if not common.get("patient_name", {}).get("value"):
            warnings.append(_warn("MISSING_PATIENT_NAME", "Patient name was not found", "patient_name"))
        if not common.get("date_of_test_or_report", {}).get("value"):
            warnings.append(_warn("MISSING_REPORT_DATE", "Report date was not found", "date_of_test_or_report"))

        status = ExtractionStatus.SUCCESS if confidence >= 0.75 else ExtractionStatus.LOW_CONFIDENCE
        if status == ExtractionStatus.LOW_CONFIDENCE:
            warnings.append(_warn("LOW_EXTRACTION_CONFIDENCE", "Overall extraction confidence is low"))

        return ExtractionResponse(
            request_id=inp.request_id or str(uuid.uuid4()),
            document_id=inp.document_id,
            status=status,
            document_type=cls.document_type,
            confidence=confidence,
            quality=self._quality_schema(quality),
            ocr=self._ocr_schema(ocr, debug),
            common_fields=common,
            extracted_data=specific,
            errors=[],
            warnings=warnings,
            debug={
                "ocr_text": ocr.text,
                "page_text": [p.text for p in ocr.pages],
                "classification": cls.__dict__,
                "relevance": rel.__dict__,
            }
            if debug
            else None,
        )

    def _build_error_response(self, inp, status, ocr, quality, warnings):
        if status == ExtractionStatus.OCR_FAILED:
            if "not available" in (ocr.error or ""):
                code = "OCR_ENGINE_MISSING"
            elif not (ocr.text or "").strip():
                code = "OCR_EMPTY_TEXT"
            else:
                code = "OCR_FAILED"
            return ExtractionResponse(
                request_id=inp.request_id or str(uuid.uuid4()),
                document_id=inp.document_id,
                status=status,
                quality=self._quality_schema(quality),
                ocr=self._ocr_schema(ocr, False),
                errors=[_err(code, ocr.error or "OCR failed")],
                warnings=warnings,
            )
        return self._base(inp, status, [_err(status.value.upper(), "Extraction failed")])

    def _quality_schema(self, q):
        if not q:
            return QualitySummary()
        return QualitySummary(
            status=q.status,
            overall_quality_score=q.overall_quality_score,
            is_acceptable=q.is_acceptable,
            issues=q.issues,
            metrics=q.metrics,
            page_scores=q.page_scores,
            page_issues=q.page_issues,
            worst_page_number=q.worst_page_number,
            average_quality_score=q.average_quality_score,
            min_quality_score=q.min_quality_score,
            num_pages=q.num_pages,
        )

    def _ocr_schema(self, o, include_text=False):
        if not o:
            return OCRSummary()
        pages = [
            OCRPageResultSchema(
                page_number=p.page_number,
                text=p.text if include_text else None,
                confidence=p.confidence,
                text_length=len(p.text or ""),
                source_path=p.source_path if include_text else None,
            )
            for p in o.pages
        ]
        return OCRSummary(
            success=o.success,
            confidence=o.confidence,
            text_length=len(o.text or ""),
            pages=pages,
            warnings=o.warnings,
            errors=[o.error] if o.error else [],
        )

    def _base(self, inp: ExtractionInput, status=ExtractionStatus.EXTRACTION_FAILED, errors=None):
        return ExtractionResponse(
            request_id=inp.request_id or str(uuid.uuid4()),
            document_id=inp.document_id,
            status=status,
            errors=errors or [],
        )
