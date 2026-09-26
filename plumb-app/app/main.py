from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
import app.prompts.registration  # noqa: F401 — registers all prompts on import
import app.agent.tools.registration  # noqa: F401 — registers all agent tools on import
from app.storage.s3 import ensure_bucket


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure S3 bucket exists
    ensure_bucket()
    yield
    # Shutdown: nothing to clean up


app = FastAPI(
    title="Plumb",
    description="AI-Native Capital Advisory Back Office",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
