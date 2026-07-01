from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.api.routes.health import router as health_router
from app.api.routes.extract import router as extract_router
from app.schemas.extraction import ExtractionError, ExtractionResponse, ExtractionStatus

app = FastAPI(title="Stateless Medical Document Extraction Service")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    body = exc.body if isinstance(exc.body, dict) else {}
    request_id = body.get("request_id") or ""
    message = "Invalid extraction request"
    for error in exc.errors():
        if error.get("type") == "value_error":
            message = str(error.get("msg", message)).removeprefix("Value error, ")
            break
    payload = ExtractionResponse(
        request_id=request_id,
        document_id=body.get("document_id"),
        status=ExtractionStatus.INVALID_FILE,
        errors=[ExtractionError(code="INVALID_REQUEST", message=message)],
    )
    return JSONResponse(status_code=200, content=payload.model_dump(mode="json"))

app.include_router(health_router)
app.include_router(extract_router)
