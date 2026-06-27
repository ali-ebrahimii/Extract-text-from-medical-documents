from fastapi import FastAPI
from app.api.routes.health import router as health_router
from app.api.routes.documents import router as documents_router
from app.api.routes.review import router as review_router
from app.db.base import init_db
app=FastAPI(title='Medical Document Extraction MVP')
@app.on_event('startup')
def startup(): init_db()
app.include_router(health_router)
app.include_router(documents_router)
app.include_router(review_router)
