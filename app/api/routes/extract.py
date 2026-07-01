from __future__ import annotations
import base64, shutil, tempfile, uuid
from pathlib import Path
from fastapi import APIRouter, File, Form, UploadFile
from app.schemas.extraction import ExtractionRequest, ExtractionResponse, ExtractionStatus, ExtractionError
from app.services.extraction_pipeline import ExtractionInput, ExtractionPipeline
from app.services.file_validation_service import SUPPORTED, MIME_ALIASES

router=APIRouter(prefix='/extract', tags=['stateless-extraction'])

def _mime_for(name, provided=None):
    mt=MIME_ALIASES.get(provided or '', provided)
    return mt or SUPPORTED.get(Path(name or '').suffix.lower()) or 'application/octet-stream'

@router.get('/health')
def health(): return {'status':'ok','service':'stateless-extraction'}

@router.post('/file', response_model=ExtractionResponse)
async def extract_file(file: UploadFile=File(...), document_id:str|None=Form(None), request_id:str|None=Form(None), debug:bool=Form(False)):
    request_id=request_id or str(uuid.uuid4())
    suffix=Path(file.filename or 'upload').suffix
    try:
        with tempfile.NamedTemporaryFile(prefix='extract_upload_', suffix=suffix, delete=True) as tmp:
            shutil.copyfileobj(file.file, tmp); tmp.flush()
            inp=ExtractionInput(document_id=document_id,request_id=request_id,file_path=tmp.name,file_name=file.filename or f'upload{suffix}',mime_type=_mime_for(file.filename,file.content_type),debug=debug)
            return ExtractionPipeline().process(inp, debug=debug)
    except Exception:
        return ExtractionResponse(request_id=request_id,document_id=document_id,status=ExtractionStatus.INVALID_FILE,errors=[ExtractionError(code='FILE_READ_ERROR',message='Could not read uploaded file')])

@router.post('', response_model=ExtractionResponse)
def extract(req: ExtractionRequest):
    request_id=req.request_id or str(uuid.uuid4())
    if req.file_url:
        return ExtractionResponse(request_id=request_id,document_id=req.document_id,status=ExtractionStatus.EXTRACTION_FAILED,errors=[ExtractionError(code='URL_DOWNLOAD_FAILED',message='file_url download is not implemented in this MVP')])
    if req.file_path:
        name=req.file_name or Path(req.file_path).name
        return ExtractionPipeline().process(ExtractionInput(req.file_path,name,_mime_for(name,req.mime_type),req.document_id,request_id,req.debug),debug=req.debug)
    suffix=Path(req.file_name or 'upload.bin').suffix
    try:
        data=base64.b64decode(req.base64_content or '', validate=True)
    except Exception:
        return ExtractionResponse(request_id=request_id,document_id=req.document_id,status=ExtractionStatus.INVALID_FILE,errors=[ExtractionError(code='BASE64_DECODE_FAILED',message='base64_content could not be decoded')])
    with tempfile.NamedTemporaryFile(prefix='extract_b64_', suffix=suffix, delete=True) as tmp:
        tmp.write(data); tmp.flush()
        name=req.file_name or f'upload{suffix}'
        return ExtractionPipeline().process(ExtractionInput(tmp.name,name,_mime_for(name,req.mime_type),req.document_id,request_id,req.debug),debug=req.debug)
