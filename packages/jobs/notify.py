import logging
import os

from packages.core.config import Settings
from packages.jobs.models import NotifyScrapeCompleteJob

logger = logging.getLogger(__name__)


def _configure_legacy_notifier(settings: Settings) -> None:
    """Point legacy scraper.py notification helpers at greenfield settings.

    Telegram/WhatsApp delivery still lives in legacy scraper.py (Phase 4).
    The notifier reuses those helpers until notifications are extracted.
    """
    os.environ["DATABASE_URL"] = settings.database_url

    import scraper

    scraper.DATABASE_URL = settings.database_url
    scraper.TELEGRAM_BOT_TOKEN = settings.telegram_bot_token
    scraper.TELEGRAM_CHAT_ID = settings.telegram_chat_id
    scraper.TELEGRAM_MIN_DROP_PERCENT = settings.telegram_min_drop_percent


def execute_notify_scrape_complete(
    job: NotifyScrapeCompleteJob, settings: Settings
) -> None:
    _configure_legacy_notifier(settings)

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
    _configure_legacy_notifier(settings)

    import scraper

    scraper.maybe_send_weekly_digest()
