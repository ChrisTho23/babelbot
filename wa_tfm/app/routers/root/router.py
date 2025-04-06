from fastapi import APIRouter

router = APIRouter(
    responses={404: {"description": "Not found"}},
)

@router.get("/")
async def root():
    return {
        "message": "WhatsApp Message Handler API",
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }