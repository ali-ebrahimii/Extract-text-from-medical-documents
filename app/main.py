from fastapi import FastAPI
from app.api.routes.health import router as health_router
from app.api.routes.extract import router as extract_router

app = FastAPI(title="Stateless Medical Document Extraction Service")

app.include_router(health_router)
app.include_router(extract_router)
