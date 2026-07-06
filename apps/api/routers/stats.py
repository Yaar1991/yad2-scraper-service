from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from apps.api.deps import get_stats_repo
from packages.data.repositories.stats import StatsRepository

router = APIRouter(prefix="", tags=["stats"])

_ERROR_BODY = {
    "error": "Failed to load stats",
    "total_listings": 0,
    "active_listings": 0,
    "cities": 0,
    "neighborhoods": 0,
    "top_cities": [],
    "rooms_distribution": [],
    "price_history": {
        "total_price_records": 0,
        "listings_with_history": 0,
        "changes_last_24h": 0,
        "changes_last_7d": 0,
    },
}


@router.get("/stats")
def stats(repo: StatsRepository = Depends(get_stats_repo)):
    try:
        return repo.get_stats()
    except Exception:
        return JSONResponse(status_code=500, content=_ERROR_BODY)
