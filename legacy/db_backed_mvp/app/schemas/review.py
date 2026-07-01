from pydantic import BaseModel
class RejectRequest(BaseModel): reason: str
class ReviewResponse(BaseModel): document_id:int; status:str; verification_status:str; rejection_reason:str|None=None
