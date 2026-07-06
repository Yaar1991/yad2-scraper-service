import logging
import os
import time
from typing import Any

from packages.core.config import Settings
from packages.jobs.models import ScrapeCityJob

logger = logging.getLogger(__name__)

_scraper_configured = False


def configure_scraper(settings: Settings) -> None:
    """Point legacy scraper.py at the greenfield database and settings."""
    global _scraper_configured
    os.environ["DATABASE_URL"] = settings.database_url
    os.environ["PAGES_PER_SESSION"] = str(settings.pages_per_session)

    import scraper

    scraper.DATABASE_URL = settings.database_url
    scraper.PAGES_PER_SESSION = settings.pages_per_session
    scraper.TELEGRAM_BOT_TOKEN = settings.telegram_bot_token
    scraper.TELEGRAM_CHAT_ID = settings.telegram_chat_id
    scraper.TELEGRAM_MIN_DROP_PERCENT = settings.telegram_min_drop_percent
    _scraper_configured = True


def ensure_scraper_ready(settings: Settings) -> None:
    if not _scraper_configured:
        configure_scraper(settings)

    import scraper

    scraper.cleanup_stale_runs()


def execute_scrape_city(job: ScrapeCityJob, settings: Settings) -> dict[str, Any]:
    ensure_scraper_ready(settings)

    import scraper

    scraper_instance = scraper.Yad2Scraper()
    started = time.monotonic()
    logger.info(
        "scrape_city_start city=%s code=%s min_rooms=%s",
        job.city_name,
        job.city_code,
        job.min_rooms,
    )

    result = scraper_instance.run_city_scrape(
        job.city_name,
        job.city_code,
        min_rooms=job.min_rooms,
    )
    duration_min = max(1, int((time.monotonic() - started) / 60))

    logger.info(
        "scrape_city_done city=%s run_id=%s new=%s updated=%s price_changes=%s duration_min=%s",
        job.city_name,
        result.get("run_id"),
        result.get("listings_new"),
        result.get("listings_updated"),
        result.get("price_changes"),
        duration_min,
    )

    return {**result, "duration_min": duration_min}
