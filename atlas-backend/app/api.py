from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.routes.books import router as books_router
from app.routes.chat import router as chat_router
from app.routes.documents import router as documents_router

router = APIRouter()


@router.get("/")
async def root() -> JSONResponse:
    return JSONResponse({"message": "Atlas is Runnings"})


@router.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


router.include_router(chat_router)
router.include_router(documents_router)
router.include_router(books_router)
