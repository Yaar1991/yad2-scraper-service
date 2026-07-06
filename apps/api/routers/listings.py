from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from apps.api.deps import get_listings_repo
from packages.data.repositories.listings import ListingsQuery, ListingsRepository

router = APIRouter(prefix="", tags=["listings"])


@router.get("/listings")
def list_listings(
    city: str | None = None,
    neighborhood: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    min_rooms: int | None = None,
    max_rooms: int | None = None,
    is_merchant: str | None = None,
    active_only: bool = Query(default=True),
    limit: int = Query(default=100, ge=1, le=50000),
    offset: int = Query(default=0, ge=0),
    sort_by: str = "last_seen_at",
    sort_order: str = "desc",
    fields: str = "full",
    repo: ListingsRepository = Depends(get_listings_repo),
) -> dict:
    merchant_filter = None
    if is_merchant is not None:
        merchant_filter = is_merchant.lower() == "true"

    query = ListingsQuery(
        city=city,
        neighborhood=neighborhood,
        min_price=min_price,
        max_price=max_price,
        min_rooms=min_rooms,
        max_rooms=max_rooms,
        is_merchant=merchant_filter,
        active_only=active_only,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
        fields=fields,
    )
    return repo.list_listings(query)


@router.get("/listings/{listing_id}")
def get_listing(
    listing_id: str,
    repo: ListingsRepository = Depends(get_listings_repo),
) -> dict:
    listing = repo.get_listing(listing_id)
    if not listing:
        return JSONResponse(status_code=404, content={"error": "Listing not found"})
    return listing


@router.get("/listings/{listing_id}/price-history")
def get_listing_price_history(
    listing_id: str,
    repo: ListingsRepository = Depends(get_listings_repo),
) -> dict:
    history = repo.get_price_history(listing_id)
    if history is None:
        return JSONResponse(status_code=404, content={"error": "Listing not found"})
    return history
