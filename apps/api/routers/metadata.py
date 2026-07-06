from fastapi import APIRouter, Depends, Query

from apps.api.deps import get_listings_repo
from packages.data.repositories.listings import ListingsRepository

router = APIRouter(prefix="", tags=["metadata"])


@router.get("/cities")
def list_cities(repo: ListingsRepository = Depends(get_listings_repo)) -> dict:
    return {"cities": repo.list_cities()}


@router.get("/neighborhoods")
def list_neighborhoods(
    city: str | None = None,
    repo: ListingsRepository = Depends(get_listings_repo),
) -> dict:
    return {"neighborhoods": repo.list_neighborhoods(city=city)}
