from pydantic import BaseModel
class ValidationResultSchema(BaseModel): is_valid: bool; status: str; reason: str|None=None
