from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from apps.api.deps import get_analytics_repo
from packages.data.repositories.analytics import AnalyticsRepository

router = APIRouter(prefix="", tags=["analytics"])


@router.get("/analytics/market-summary")
def market_summary(repo: AnalyticsRepository = Depends(get_analytics_repo)) -> dict:
    return repo.get_market_summary()


@router.get("/analytics/neighborhoods")
def neighborhood_analytics(
    city: str | None = None,
    min_listings: int = Query(default=3, ge=1),
    repo: AnalyticsRepository = Depends(get_analytics_repo),
):
    return repo.get_neighborhood_analytics(city, min_listings)


@router.get("/analytics/price-map")
def price_map(
    city: str | None = None,
    limit: int = Query(default=500, ge=1, le=2000),
    repo: AnalyticsRepository = Depends(get_analytics_repo),
):
    return repo.get_price_map(city, limit)


@router.get("/analytics/trends")
def price_trends(
    city: str | None = None,
    days: int = Query(default=30, ge=1, le=365),
    repo: AnalyticsRepository = Depends(get_analytics_repo),
):
    return repo.get_price_trends(city, days)


@router.get("/analytics/deals", response_model=None)
def deals_finder(
    city: str | None = None,
    min_discount: int = Query(default=15, ge=0),
    min_listings: int = Query(default=5, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    repo: AnalyticsRepository = Depends(get_analytics_repo),
):
    try:
        return repo.get_deals(city, min_discount, min_listings, limit)
    except Exception:
        return JSONResponse(
            status_code=500,
            content={"count": 0, "min_discount": min_discount, "deals": [], "error": "Query failed"},
        )


@router.get("/analytics/compare", response_model=None)
def compare_neighborhoods(
    n1: str = "",
    n2: str = "",
    c1: str = "",
    c2: str = "",
    repo: AnalyticsRepository = Depends(get_analytics_repo),
):
    if not n1 or not n2:
        return JSONResponse(
            status_code=400,
            content={"error": "Both n1 and n2 (neighborhood names) are required"},
        )
    return repo.compare_neighborhoods(n1, n2, c1, c2)


@router.get("/analytics/stale", response_model=None)
def stale_listings(
    city: str | None = None,
    min_days: int = Query(default=14, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    repo: AnalyticsRepository = Depends(get_analytics_repo),
):
    try:
        return repo.get_stale_listings(city, min_days, limit)
    except Exception:
        return JSONResponse(
            status_code=500,
            content={"count": 0, "listings": [], "error": "Query failed"},
        )


@router.get("/analytics/city/{city_name}", response_model=None)
def city_stats(
    city_name: str,
    repo: AnalyticsRepository = Depends(get_analytics_repo),
):
    try:
        result = repo.get_city_stats(city_name)
        if result is None:
            return JSONResponse(status_code=404, content={"error": "City not found"})
        return result
    except Exception:
        return JSONResponse(status_code=500, content={"error": "Failed to load city stats"})


@router.get("/analytics/price-drops", response_model=None)
def price_drop_leaderboard(
    days: int = Query(default=30, ge=1, le=365),
    min_drops: int = Query(default=2, ge=1),
    repo: AnalyticsRepository = Depends(get_analytics_repo),
):
    try:
        return repo.get_price_drop_leaderboard(days, min_drops)
    except Exception:
        return JSONResponse(status_code=500, content={"error": "Query failed"})
