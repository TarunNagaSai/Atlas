"""One-off: persist the 3-page JPMorgan test PDF into pgvector and report."""

from __future__ import annotations

import sys
from pathlib import Path

# Running a file inside scripts/ puts that dir on sys.path, not the project root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.pipeline import IngestionPipeline

TEST_PDF = (
    "/private/tmp/claude-501/-Users-tarunkodali-Projects-ai-atlas-backend/"
    "32791866-30e4-4649-975d-7166a0404fca/scratchpad/jpm_3pages.pdf"
)

if __name__ == "__main__":
    report = IngestionPipeline().ingest(source=TEST_PDF, persist=True)
    print("persisted:", report.persisted)
    print("n_chunks :", report.n_chunks)
    print("embed_dim:", report.embed_dim)
    print("note     :", report.note)
