from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/")
async def root():
    return {"message": "EcoFlood API is running", "status": "healthy", "version": "1.0.0"}


@router.get("/health")
async def health_check():
    return {"status": "ok"}
