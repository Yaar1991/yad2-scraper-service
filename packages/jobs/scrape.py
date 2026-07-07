import logging
import time
from typing import Any

from packages.core.config import Settings
from packages.data.db import Database
from packages.jobs.models import ScrapeCityJob
from packages.scraper import ScrapeSink, ScraperConfig, Yad2Scraper

logger = logging.getLogger(__name__)

_sink: ScrapeSink | None = None
_config: ScraperConfig | None = None


def _get_sink(settings: Settings) -> ScrapeSink:
    global _sink
    if _sink is None:
        _sink = ScrapeSink(Database(settings.database_url))
    return _sink


def _get_config(settings: Settings) -> ScraperConfig:
    global _config
    if _config is None:
        _config = ScraperConfig(pages_per_session=settings.pages_per_session)
    return _config


def ensure_scraper_ready(settings: Settings) -> None:
    sink = _get_sink(settings)
    sink.cleanup_stale_runs()


def execute_scrape_city(job: ScrapeCityJob, settings: Settings) -> dict[str, Any]:
    sink = _get_sink(settings)
    config = _get_config(settings)
    scraper = Yad2Scraper(sink, config)

    started = time.monotonic()
    logger.info(
        "scrape_city_start city=%s code=%s min_rooms=%s",
        job.city_name,
        job.city_code,
        job.min_rooms,
    )

    result = scraper.run_city_scrape(
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
