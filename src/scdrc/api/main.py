"""
FastAPI application entrypoint for SCDRC.
"""

from __future__ import annotations
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from scdrc.api.routes import router
from scdrc.data.seed import seed_database
from scdrc.retrieval.ingest import ingest_documents
from scdrc.core.config import load_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure database and vector store are ready
    settings = load_settings()
    db_file = settings.paths.database_url.replace("sqlite:///", "")
    if not os.path.exists(db_file):
        seed_database(db_file, settings.paths.seed_dir)

    chroma_dir = settings.paths.chroma_persist_dir
    if not os.path.exists(chroma_dir):
        ingest_documents(docs_dir="./data/documents", persist_dir=chroma_dir)

    yield


app = FastAPI(
    title="Supply Chain Disruption Response Coordinator (SCDRC)",
    description="Multi-Agent Blackboard System for Autonomous Enterprise Disruption Mitigation",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
app.include_router(router)  # Root level routes for convenience


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("scdrc.api.main:app", host="0.0.0.0", port=8000, reload=True)
