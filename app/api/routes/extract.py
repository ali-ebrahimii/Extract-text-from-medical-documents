from __future__ import annotations
import base64, os, shutil, tempfile, uuid
from pathlib import Path
from fastapi import APIRouter, File, Form, UploadFile
from app.schemas.extraction import (
    BackendUserFilesRequest,
    BatchExtractionItem,
    BatchExtractionResponse,
    ExtractionRequest,
    ExtractionResponse,
    ExtractionStatus,
    ExtractionError,
)
from app.services.extraction_pipeline import ExtractionInput, ExtractionPipeline
from app.services.extraction_pipeline_v2 import ExtractionInputV2, ExtractionPipelineV2
from app.schemas.extraction_v2 import ExtractionResponseV2
from app.services.backend_file_client import BackendFileClient, BackendFileClientError
from app.services.file_validation_service import SUPPORTED, MIME_ALIASES
from app.services.url_file_loader import UrlFileLoadError, load_url_to_tempfile

router=APIRouter(prefix='/extract', tags=['stateless-extraction'])

def _mime_for(name, provided=None):
    mt=MIME_ALIASES.get(provided or '', provided)
    return mt or SUPPORTED.get(Path(name or '').suffix.lower()) or 'application/octet-stream'

@router.get('/health')
def health(): return {'status':'ok','service':'stateless-extraction'}


@router.post('/v2/file', response_model=ExtractionResponseV2)
async def extract_file_v2(file: UploadFile=File(...), document_id:str|None=Form(None), request_id:str|None=Form(None), debug:bool=Form(False), privacy_mode:str=Form('internal')):
    request_id=request_id or str(uuid.uuid4())
    suffix=Path(file.filename or 'upload').suffix
    try:
        with tempfile.NamedTemporaryFile(prefix='extract_v2_upload_', suffix=suffix, delete=True) as tmp:
            shutil.copyfileobj(file.file, tmp); tmp.flush()
            inp=ExtractionInputV2(document_id=document_id,request_id=request_id,file_path=tmp.name,file_name=file.filename or f'upload{suffix}',mime_type=_mime_for(file.filename,file.content_type),debug=debug,privacy_mode=privacy_mode)
            return ExtractionPipelineV2().process(inp, debug=debug, privacy_mode=privacy_mode)
    except Exception:
        doc={'filename': file.filename, 'mime_type': file.content_type, 'document_type':'unknown', 'document_type_confidence':0.0, 'extraction_status':'invalid_file', 'page_context':{'page_role':'unknown_page_role','template_type':'generic_lab','requires_backend_context_for_save':False}}
        return ExtractionResponseV2(request_id=request_id,document_id=document_id,document=doc)

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



@router.post('/user-files', response_model=BatchExtractionResponse)
def extract_user_files(req: BackendUserFilesRequest):
    request_id = req.request_id or str(uuid.uuid4())
    client = BackendFileClient()
    try:
        descriptors = client.list_user_files(req.user_id)
    except BackendFileClientError as exc:
        return BatchExtractionResponse(
            request_id=request_id,
            user_id=req.user_id,
            status='failed',
            total_files=0,
            processed_files=0,
            failed_files=0,
            results=[],
            errors=[ExtractionError(code=exc.code, message=exc.message)],
            warnings=[],
        )

    if req.max_files is not None:
        descriptors = descriptors[: req.max_files]

    results: list[BatchExtractionItem] = []
    pipeline = ExtractionPipeline()
    for descriptor in descriptors:
        downloaded = None
        try:
            downloaded = client.fetch_file_to_tempfile(req.user_id, descriptor)
            result = pipeline.process(
                ExtractionInput(
                    file_path=downloaded.path,
                    file_name=downloaded.file_name,
                    mime_type=downloaded.mime_type,
                    document_id=downloaded.document_id,
                    request_id=request_id,
                    debug=req.debug,
                ),
                debug=req.debug,
            )
            item_status = 'success' if not result.errors and result.status == ExtractionStatus.SUCCESS else str(result.status.value)
            results.append(
                BatchExtractionItem(
                    file_name=descriptor.file_name,
                    document_id=descriptor.document_id,
                    status=item_status,
                    result=result,
                    errors=result.errors,
                    warnings=result.warnings,
                )
            )
        except BackendFileClientError as exc:
            results.append(
                BatchExtractionItem(
                    file_name=descriptor.file_name,
                    document_id=descriptor.document_id,
                    status='failed',
                    result=None,
                    errors=[ExtractionError(code=exc.code, message=exc.message)],
                    warnings=[],
                )
            )
        except Exception:
            results.append(
                BatchExtractionItem(
                    file_name=descriptor.file_name,
                    document_id=descriptor.document_id,
                    status='failed',
                    result=None,
                    errors=[ExtractionError(code='EXTRACTION_FAILED', message='Extraction failed')],
                    warnings=[],
                )
            )
        finally:
            if downloaded:
                try:
                    os.unlink(downloaded.path)
                except OSError:
                    pass

    failed = sum(1 for item in results if item.status != 'success')
    processed = len(results) - failed
    if not results or processed == 0:
        status = 'failed'
    elif failed:
        status = 'partial_success'
    else:
        status = 'success'
    return BatchExtractionResponse(
        request_id=request_id,
        user_id=req.user_id,
        status=status,
        total_files=len(results),
        processed_files=processed,
        failed_files=failed,
        results=results,
        errors=[],
        warnings=[],
    )

@router.post('', response_model=ExtractionResponse)
def extract(req: ExtractionRequest):
    request_id=req.request_id or str(uuid.uuid4())
    if req.file_url:
        downloaded = None
        try:
            downloaded = load_url_to_tempfile(req.file_url, req.file_name, req.mime_type)
            inp = ExtractionInput(downloaded.path, downloaded.file_name, downloaded.mime_type, req.document_id, request_id, req.debug)
            return ExtractionPipeline().process(inp, debug=req.debug)
        except UrlFileLoadError as exc:
            return ExtractionResponse(request_id=request_id,document_id=req.document_id,status=ExtractionStatus.INVALID_FILE,errors=[ExtractionError(code=exc.code,message=exc.message)])
        except Exception:
            return ExtractionResponse(request_id=request_id,document_id=req.document_id,status=ExtractionStatus.INVALID_FILE,errors=[ExtractionError(code='URL_DOWNLOAD_FAILED',message='file_url download failed')])
        finally:
            if downloaded:
                try:
                    os.unlink(downloaded.path)
                except OSError:
                    pass
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
