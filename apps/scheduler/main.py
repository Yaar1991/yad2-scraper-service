import logging
import time

from packages.core.config import load_settings
from packages.core.queue import JobQueue, SCRAPE_QUEUE
from packages.data.db import Database
from packages.data.repositories.subscriptions import SubscriptionsRepository
from packages.jobs.enqueue import enqueue_scrape_jobs
from packages.jobs.notify import maybe_send_weekly_digest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def enqueue_scrape_cycle(queue: JobQueue, repo: SubscriptionsRepository) -> int:
    enqueued = enqueue_scrape_jobs(queue, repo)
    for job in enqueued:
        logger.info(
            "scheduler_enqueued city=%s code=%s queue_depth=%s",
            job["city_name"],
            job["city_code"],
            queue.queue_depth(SCRAPE_QUEUE),
        )
    return len(enqueued)


def run() -> None:
    settings = load_settings()
    queue = JobQueue(settings.queue_url)
    db = Database(settings.database_url)
    repo = SubscriptionsRepository(db)

    queue.ping()
    repo.ensure_default_cities()

    logger.info(
        "scheduler_start env=%s interval=%ss queue=%s",
        settings.app_env,
        settings.scrape_interval_seconds,
        settings.queue_url,
    )

    while True:
        try:
            enqueued = enqueue_scrape_cycle(queue, repo)
            if enqueued:
                logger.info("scheduler_cycle_enqueued count=%s", enqueued)
            else:
                logger.info("scheduler_cycle_skipped no_cities")

            maybe_send_weekly_digest(settings)
        except Exception:
            logger.exception("scheduler_cycle_failed")

        logger.info("scheduler_sleep seconds=%s", settings.scrape_interval_seconds)
        time.sleep(settings.scrape_interval_seconds)


if __name__ == "__main__":
    run()
