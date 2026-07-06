import logging

from packages.core.config import Settings
from packages.jobs.models import NotifyScrapeCompleteJob
from packages.jobs.scrape import configure_scraper

logger = logging.getLogger(__name__)


def execute_notify_scrape_complete(
    job: NotifyScrapeCompleteJob, settings: Settings
) -> None:
    configure_scraper(settings)

    import scraper

    scraper.notify_scrape_summary(
        run_id=job.run_id,
        run_type=job.run_type,
        pages=job.pages_scraped,
        total_pages=job.total_pages,
        new_count=job.listings_new,
        updated=job.listings_updated,
        price_changes=job.price_changes,
        duration_min=job.duration_min,
    )
    logger.info("notify_scrape_complete run_id=%s run_type=%s", job.run_id, job.run_type)


def maybe_send_weekly_digest(settings: Settings) -> None:
    configure_scraper(settings)

    import scraper

    scraper.maybe_send_weekly_digest()
