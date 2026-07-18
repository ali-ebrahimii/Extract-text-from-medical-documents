from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field

FieldStatus = Literal['valid','review','missing','missing_required','missing_optional','invalid','unsafe_ocr_context','not_applicable']
ColumnStatus = Literal['valid','review','missing_required','missing_optional','invalid','not_applicable','unsafe_ocr_context']

class PageContext(BaseModel):
    page_role: str = 'unknown_page_role'
    template_type: str = 'generic_lab'
    requires_backend_context_for_save: bool = False

class DocumentInfoV2(BaseModel):
    filename: str | None = None
    mime_type: str | None = None
    document_type: str = 'lab'
    document_type_confidence: float = 0.0
    extraction_status: str = 'extracted_partial'
    page_context: PageContext = Field(default_factory=PageContext)

class QualityV2(BaseModel):
    quality_status: str = 'unknown'
    quality_score: float = 0.0
    quality_issues: list[str] = Field(default_factory=list)

class OCRInfoV2(BaseModel):
    success: bool = False
    confidence: float = 0.0
    text_length: int = 0
    layout_status: str = 'empty_text'
    final_unsafe_ocr_context: bool = False
    selected_variant: str | None = None
    psm: int | None = None
    lang: str | None = None
    score_details: dict[str, Any] = Field(default_factory=dict)

class PersistenceRecommendation(BaseModel):
    recommended_action: str = 'manual_review'
    recommended_save: bool = False
    review_required: bool = True
    reupload_required: bool = False
    reason_codes: list[str] = Field(default_factory=list)

class CommonFieldV2(BaseModel):
    value: Any = None
    confidence: float = 0.0
    source_text: str | None = None
    source_text_masked: str | None = None
    field_validation_status: FieldStatus = 'missing'
    field_backend_usable: bool = False

class NationalIdField(BaseModel):
    raw_value: str | None = None
    masked_value: str | None = None
    hash_sha256: str | None = None
    checksum_valid: bool | None = None
    extraction_method: str | None = None
    confidence: float = 0.0
    source_text_masked: str | None = None
    field_validation_status: FieldStatus = 'missing'
    field_backend_usable: bool = False

class ColumnStatuses(BaseModel):
    test_name_status: ColumnStatus = 'missing_required'
    result_status: ColumnStatus = 'missing_required'
    unit_status: ColumnStatus = 'missing_optional'
    reference_range_status: ColumnStatus = 'missing_optional'
    source_flag_status: ColumnStatus = 'missing_optional'
    computed_flag_status: ColumnStatus = 'not_applicable'
    method_status: ColumnStatus = 'missing_optional'

class LabResultV2(BaseModel):
    test_name_standard: str
    test_name_raw: str | None = None
    result_value: str | None = None
    result_numeric: float | None = None
    unit: str | None = None
    reference_range: str | None = None
    source_flag: str | None = None
    computed_flag: str | None = None
    flag: str | None = None
    flag_source: str | None = None
    method: str | None = None
    section: str | None = None
    confidence: float = 0.0
    source_text: str | None = None
    extraction_mode: str = 'visual_line'
    row_validation_status: str = 'review'
    row_save_allowed: bool = False
    backend_row_save_recommendation: bool = False
    reason_codes: list[str] = Field(default_factory=list)
    backend_reason_codes: list[str] = Field(default_factory=list)
    corrected_numeric: float | None = None
    corrected_value: str | None = None
    column_statuses: ColumnStatuses = Field(default_factory=ColumnStatuses)

class ExtractionResponseV2(BaseModel):
    api_version: str = 'v2'
    request_id: str
    document_id: str | None = None
    document: DocumentInfoV2
    quality: QualityV2 = Field(default_factory=QualityV2)
    ocr: OCRInfoV2 = Field(default_factory=OCRInfoV2)
    persistence_recommendation: PersistenceRecommendation = Field(default_factory=PersistenceRecommendation)
    common_fields: dict[str, Any] = Field(default_factory=dict)
    lab_results: list[LabResultV2] = Field(default_factory=list)
    safe_payload_candidate: dict[str, Any] = Field(default_factory=dict)
    review_payload: dict[str, Any] = Field(default_factory=dict)
    debug: dict[str, Any] = Field(default_factory=dict)
