import logging
import time

import redis.exceptions

from packages.core.config import load_settings
from packages.core.queue import JobQueue, NOTIFY_QUEUE, SCRAPE_QUEUE
from packages.jobs.constants import JOB_TYPE_NOTIFY_SCRAPE_COMPLETE, JOB_TYPE_SCRAPE_CITY
from packages.jobs.models import NotifyScrapeCompleteJob, ScrapeCityJob
from packages.jobs.scrape import ensure_scraper_ready, execute_scrape_city

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def handle_scrape_job(
    queue: JobQueue, settings, payload: dict
) -> None:
    job = ScrapeCityJob.from_payload(payload)
    result = execute_scrape_city(job, settings)

    notify_job = NotifyScrapeCompleteJob(
        run_id=int(result["run_id"]),
        run_type=str(result.get("run_type", f"city:{job.city_name}")),
        pages_scraped=int(result.get("pages_scraped", 0)),
        total_pages=int(result.get("total_pages", 0)),
        listings_new=int(result.get("listings_new", 0)),
        listings_updated=int(result.get("listings_updated", 0)),
        price_changes=int(result.get("price_changes", 0)),
        duration_min=int(result.get("duration_min", 1)),
    )
    queue.enqueue(
        NOTIFY_QUEUE,
        JOB_TYPE_NOTIFY_SCRAPE_COMPLETE,
        notify_job.to_payload(),
    )


def run() -> None:
    settings = load_settings()
    queue = JobQueue(settings.queue_url)

    queue.ping()
    ensure_scraper_ready(settings)

    logger.info("worker_start env=%s queue=%s", settings.app_env, settings.queue_url)

    while True:
        try:
            message = queue.dequeue(SCRAPE_QUEUE, timeout=5)
            if not message:
                continue

            job_type = message.get("type")
            payload = message.get("payload") or {}
            logger.info("worker_job_received type=%s payload=%s", job_type, payload)

            if job_type == JOB_TYPE_SCRAPE_CITY:
                handle_scrape_job(queue, settings, payload)
            else:
                logger.warning("worker_unknown_job type=%s", job_type)
        except redis.exceptions.TimeoutError:
            continue
        except Exception:
            logger.exception("worker_job_failed")
            time.sleep(5)


if __name__ == "__main__":
    run()
