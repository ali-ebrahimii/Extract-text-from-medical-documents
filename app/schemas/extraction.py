from pydantic import BaseModel
class ExtractedField(BaseModel): value: str|float|None=None; confidence: float|None=None; raw_source_text: str|None=None
