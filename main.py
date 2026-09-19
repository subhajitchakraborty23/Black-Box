from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from db import init_db
import models
import webhooks
from routers.crash import router as crash_router
from routers.users import router as users_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(webhooks.router, prefix="/webhooks")
app.include_router(crash_router)
app.include_router(users_router)

@app.on_event("startup")
async def startup():
    await init_db()

@app.get("/health")
async def health_check():
    return {"status": "ok"}
