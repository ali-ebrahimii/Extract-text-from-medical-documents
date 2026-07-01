from pydantic import BaseModel, ConfigDict, Field
from typing import Any
class DocumentUploadResponse(BaseModel):
    document_id:int; status:str|None=None; validation_status:str|None=None; verification_status:str; document_type:str|None=None; document_type_confidence:float|None=None; rejection_reason:str|None=None; next_action:str; original_file:dict[str,Any]|None=None; preprocessing:dict[str,Any]|None=None; quality:dict[str,Any]|None=None; relevance:dict[str,Any]|None=None; ocr:dict[str,Any]|None=None; common_fields:dict[str,Any]|None=None; extracted_data:dict[str,Any]|None=None; warnings:list[str]=Field(default_factory=list); quality_score_before:float|None=None; quality_score_after:float|None=None; relevance_score:float|None=None; extraction_confidence:float|None=None
class DocumentListItem(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int; original_file_name:str; validation_status:str; verification_status:str; document_type:str|None=None; extraction_confidence:float|None=None
class DocumentDetail(DocumentUploadResponse):
    pass
