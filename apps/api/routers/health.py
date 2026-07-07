from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from apps.api.deps import get_database
from packages.data.db import Database

router = APIRouter(prefix="", tags=["health"])


@router.get("/health", response_model=None)
def health(db: Database = Depends(get_database)):
    try:
        db.ping()
        return {"status": "healthy", "database": "connected"}
    except Exception:
        return JSONResponse(
            status_code=500,
            content={"status": "unhealthy", "error": "database connection failed"},
        )
