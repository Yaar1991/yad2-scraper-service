from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, RedirectResponse

router = APIRouter(prefix="", tags=["dashboard"])

DASHBOARD_PATH = Path(__file__).resolve().parents[3] / "dashboard.html"


@router.get("/")
def index():
    return RedirectResponse(url="/dashboard")


@router.get("/dashboard")
def dashboard():
    return FileResponse(DASHBOARD_PATH)


@router.get("/api")
def api_index() -> dict:
    return {
        "service": "Yad2 Scraper API",
        "dashboard": "/dashboard",
        "endpoints": {
            "/dashboard": "GET - Interactive dashboard UI",
            "/listings": "GET - List all active listings with filters",
            "/listings/{id}": "GET - Get single listing by ID",
            "/listings/{id}/price-history": "GET - Get price history for a listing",
            "/price-changes": "GET - Get recent price changes across all listings",
            "/stats": "GET - Get database statistics",
            "/runs": "GET - Get scrape run history",
            "/runs/trigger": "POST - Enqueue scrape jobs (optional city_name in body)",
            "/cities": "GET - List all cities",
            "/neighborhoods": "GET - List neighborhoods (optional city filter)",
            "/health": "GET - Health check",
        },
    }
