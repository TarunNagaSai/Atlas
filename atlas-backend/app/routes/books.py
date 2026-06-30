from __future__ import annotations

import logfire
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.rag.store import HybridStore
from app.schema.llm_settings import get_settings

router = APIRouter(prefix="/books", tags=["books"])


class BookOut(BaseModel):
    book_id: str
    title: str
    n_chunks: int


class BooksResponse(BaseModel):
    books: list[BookOut]


# Cached module-level singleton (mirrors the get_X() convention); the store's
# own _connect() handles pooled-connection liveness and reconnects on its own.
_store: HybridStore | None = None


def _get_store() -> HybridStore:
    global _store
    if _store is None:
        _store = HybridStore(get_settings())
    return _store


@router.get("", response_model=BooksResponse)
async def list_books() -> BooksResponse:
    """List the ingested books for the frontend picker.

    Returns one entry per distinct ``book_id`` with its display ``title`` and
    chunk count, ordered by size (largest first). Used by the frontend to let
    the user scope a chat to a single book.
    """
    try:
        books = _get_store().list_books()
    except Exception as e:  # noqa: BLE001
        logfire.exception("listing books failed: {error}", error=str(e))
        raise HTTPException(
            status_code=503,
            detail="Couldn't load the book list right now. Please try again in a moment.",
        )
    return BooksResponse(books=[BookOut(**b) for b in books])
