from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import logfire
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.observability.langfuse import langfuse_lifespan
from app.observability.logfire import configure_logfire

configure_logfire()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with langfuse_lifespan(app):
        yield


app = FastAPI(
    title="Advanced RAG API",
    version="0.1.0",
    description="Hybrid + GraphRAG + agentic retrieval over Google Gemini.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
logfire.instrument_fastapi(app)
