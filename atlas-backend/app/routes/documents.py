from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.rag.loaders import SUPPORTED_SUFFIXES
from app.rag.pipeline import IngestionPipeline, IngestReport

router = APIRouter(prefix="/documents", tags=["documents"])


class SampleChunkOut(BaseModel):
    loc: str
    approx_tokens: int
    preview: str


class UploadResponse(BaseModel):
    source: str
    n_documents: int
    n_chunks: int
    sample_chunks: list[SampleChunkOut]
    embedded_sample: int
    embed_dim: int | None
    persisted: bool
    note: str


def _to_response(report: IngestReport) -> UploadResponse:
    return UploadResponse(
        source=report.source,
        n_documents=report.n_documents,
        n_chunks=report.n_chunks,
        sample_chunks=[
            SampleChunkOut(loc=s.loc, approx_tokens=s.approx_tokens, preview=s.preview)
            for s in report.sample_chunks
        ],
        embedded_sample=report.embedded_sample,
        embed_dim=report.embed_dim,
        persisted=report.persisted,
        note=report.note,
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    kind: str | None = Form(None),
    persist: bool = False,
    semantic: bool = False,
) -> UploadResponse:
    """Upload a document and run it through the ingestion pipeline.

    Default is a dry-run preview: load -> chunk -> embed a small sample, no DB
    writes. Pass ``persist=true`` (once DATABASE_URL is connected) to embed every
    chunk and store it in pgvector.

    ``title`` is the friendly book name shown in the picker and hashed into the
    shared ``book_id``. It defaults to the uploaded filename stem — never the
    random temp path the file is staged at.
    """
    suffix = Path(file.filename or "upload.txt").suffix.lower() or ".txt"
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{suffix}'. Supported: "
            f"{sorted(SUPPORTED_SUFFIXES)}.",
        )

    book_title = (title or "").strip() or Path(file.filename or "upload").stem

    data = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        pipeline = IngestionPipeline()
        report = pipeline.ingest(
            source=tmp_path,
            title=book_title,
            kind=kind,
            persist=persist,
            semantic=semantic,
        )
    except RuntimeError as e:
        # Persist requested but DB not reachable/configured — clean 503, not a 500.
        raise HTTPException(status_code=503, detail=str(e))
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    # The temp path leaks into the report source; show the original filename instead.
    report.source = file.filename or report.source
    return _to_response(report)
