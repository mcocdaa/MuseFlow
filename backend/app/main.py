from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.db import init_db
from app.api import (
    assets,
    collections,
    supersets,
    stream,
    telemetry,
    recommend,
    scan,
    system,
    ai,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite tables
    init_db()
    yield

app = FastAPI(
    title="MuseFlow API",
    description="Local Media DAM & Algorithmic Streaming Platform",
    version="0.1.0",
    lifespan=lifespan
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(assets.router)
app.include_router(collections.router)
app.include_router(supersets.router)
app.include_router(stream.router)
app.include_router(telemetry.router)
app.include_router(recommend.router)
app.include_router(scan.router)
app.include_router(system.router)
app.include_router(ai.router)

@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "MuseFlow", "version": "0.1.0"}

# Static build serving if frontend/dist exists
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="static")
