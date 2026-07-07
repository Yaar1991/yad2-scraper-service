from fastapi import APIRouter, Depends, Query

from apps.api.deps import get_price_changes_repo
from packages.data.repositories.price_changes import PriceChangesRepository

router = APIRouter(prefix="", tags=["price-changes"])


@router.get("/price-changes")
def list_price_changes(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    city: str | None = None,
    days: int = Query(default=7, ge=1, le=365),
    repo: PriceChangesRepository = Depends(get_price_changes_repo),
) -> dict:
    return repo.list_price_changes(limit=limit, offset=offset, city=city, days=days)
