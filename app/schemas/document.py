from pydantic import BaseModel, ConfigDict
from typing import Any
class DocumentUploadResponse(BaseModel):
    document_id:int; status:str; verification_status:str; rejection_reason:str|None=None; quality_score_before:float|None=None; quality_score_after:float|None=None; relevance_score:float|None=None; document_type:str|None=None; extraction_confidence:float|None=None; next_action:str; extracted_data:dict[str,Any]|None=None
class DocumentListItem(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int; original_file_name:str; validation_status:str; verification_status:str; document_type:str|None=None; extraction_confidence:float|None=None
class DocumentDetail(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int; original_file_name:str; original_file_path:str; preprocessed_file_path:str|None=None; validation_status:str; verification_status:str; document_type:str|None=None; rejection_reason:str|None=None; ocr_text:str|None=None; relevance_score:float|None=None; quality_score_before:float|None=None; quality_score_after:float|None=None; extraction_confidence:float|None=None; extracted_data:dict[str,Any]|None=None
