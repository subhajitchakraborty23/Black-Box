from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from db import init_db
import models  # Import models to register them with SQLAlchemy
import webhooks
from routers.telemetry import router as telemetry_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(webhooks.router, prefix="/webhooks")
app.include_router(telemetry_router)

@app.on_event("startup")
async def startup():
    """Initialize database tables on startup"""
    await init_db()

@app.get("/health")
async def health_check():
    return {"status": "ok"}