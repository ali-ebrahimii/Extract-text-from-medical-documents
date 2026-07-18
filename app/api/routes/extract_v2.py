from __future__ import annotations
import shutil, tempfile, uuid
from pathlib import Path
from fastapi import APIRouter, File, Form, UploadFile
from app.api.routes.extract import _mime_for
from app.schemas.extraction_v2 import ExtractionResponseV2
from app.services.extraction_pipeline_v2 import ExtractionInputV2, ExtractionPipelineV2

router=APIRouter(prefix='/api/v2/extract', tags=['stateless-extraction-v2'])

@router.post('/file', response_model=ExtractionResponseV2)
async def extract_api_v2_file(file: UploadFile=File(...), document_id:str|None=Form(None), request_id:str|None=Form(None), debug:bool=Form(False), privacy_mode:str=Form('internal')):
    request_id=request_id or str(uuid.uuid4())
    suffix=Path(file.filename or 'upload').suffix
    with tempfile.NamedTemporaryFile(prefix='extract_api_v2_upload_', suffix=suffix, delete=True) as tmp:
        shutil.copyfileobj(file.file,tmp); tmp.flush()
        return ExtractionPipelineV2().process(ExtractionInputV2(tmp.name,file.filename or f'upload{suffix}',_mime_for(file.filename,file.content_type),document_id,request_id,debug,privacy_mode),debug=debug,privacy_mode=privacy_mode)
