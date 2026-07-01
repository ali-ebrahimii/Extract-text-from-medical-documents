from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, model_validator

class ExtractionStatus(str, Enum):
    SUCCESS="success"; LOW_CONFIDENCE="low_confidence"; POOR_QUALITY="poor_quality"; OCR_FAILED="ocr_failed"; UNSUPPORTED_FILE="unsupported_file"; INVALID_FILE="invalid_file"; UNRELATED_DOCUMENT="unrelated_document"; EXTRACTION_FAILED="extraction_failed"
class FileInputType(str, Enum):
    MULTIPART="multipart"; FILE_PATH="file_path"; FILE_URL="file_url"; BASE64="base64_content"
class ExtractionError(BaseModel):
    code:str; message:str; field:str|None=None
class ExtractionWarning(BaseModel):
    code:str; message:str; field:str|None=None
class CommonFieldResult(BaseModel):
    value: Any=None; hash: str|None=None; confidence: float=0.0; source_text:str|None=None; source_line_index:int|None=None; inferred:bool=False; calendar:str|None=None
class LabResultItem(BaseModel):
    category:str|None=None; test_name_raw:str|None=None; test_name_standard:str|None=None; result_value:str|None=None; result_numeric:float|None=None; unit:str|None=None; reference_range:str|None=None; abnormal_flag:str|None=None; method:str|None=None; sample_type:str|None=None; page_number:int|None=None; confidence:float=0.0; raw_row_text:str|None=None; evidence:list[dict[str,Any]]|None=None
class PapSmearResult(BaseModel):
    specimen_adequacy:str|None=None; interpretation_result:str|None=None; full_narrative_report:str|None=None; confidence:float=0.0
class RadiologyResult(BaseModel):
    imaging_modality:str|None=None; body_part_or_exam_name:str|None=None; findings:str|None=None; impression_conclusion:str|None=None; narrative:str|None=None; confidence:float=0.0
class OCRPageResultSchema(BaseModel):
    page_number:int; text:str|None=None; confidence:float=0.0; text_length:int=0; source_path:str|None=None
class OCRSummary(BaseModel):
    success:bool=False; confidence:float=0.0; text_length:int=0; pages:list[OCRPageResultSchema]=Field(default_factory=list); warnings:list[str]=Field(default_factory=list); errors:list[str]=Field(default_factory=list)
class QualitySummary(BaseModel):
    status:str|None=None; overall_quality_score:float|None=None; is_acceptable:bool|None=None; issues:list[str]=Field(default_factory=list); metrics:dict[str,Any]=Field(default_factory=dict); page_scores:list[float]=Field(default_factory=list); page_issues:list[dict[str,Any]]=Field(default_factory=list); worst_page_number:int|None=None; average_quality_score:float|None=None; min_quality_score:float|None=None; num_pages:int|None=None
class ExtractionRequest(BaseModel):
    document_id:str|None=None; request_id:str|None=None; file_name:str|None=None; mime_type:str|None=None; file_path:str|None=None; file_url:str|None=None; base64_content:str|None=None; debug:bool=False
    @model_validator(mode='after')
    def exactly_one_input(self):
        supplied=sum(bool(x) for x in (self.file_path,self.file_url,self.base64_content))
        if supplied!=1: raise ValueError('Exactly one of file_path, file_url, or base64_content is required')
        return self
class ExtractionResponse(BaseModel):
    request_id:str; document_id:str|None=None; status:ExtractionStatus; document_type:str="unknown_medical"; confidence:float=0.0; quality:QualitySummary=Field(default_factory=QualitySummary); ocr:OCRSummary=Field(default_factory=OCRSummary); common_fields:dict[str,CommonFieldResult]=Field(default_factory=dict); extracted_data:dict[str,Any]=Field(default_factory=dict); errors:list[ExtractionError]=Field(default_factory=list); warnings:list[ExtractionWarning]=Field(default_factory=list); debug:dict[str,Any]|None=None
