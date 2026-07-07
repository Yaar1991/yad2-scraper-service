import logging
import time

import redis.exceptions

from packages.core.config import load_settings
from packages.core.queue import JobQueue, NOTIFY_QUEUE
from packages.jobs.constants import JOB_TYPE_NOTIFY_SCRAPE_COMPLETE
from packages.jobs.models import NotifyScrapeCompleteJob
from packages.jobs.notify import execute_notify_scrape_complete

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run() -> None:
    settings = load_settings()
    queue = JobQueue(settings.queue_url)

    queue.ping()
    logger.info("notifier_start env=%s queue=%s", settings.app_env, settings.queue_url)

    while True:
        try:
            message = queue.dequeue(NOTIFY_QUEUE, timeout=5)
            if not message:
                continue

            job_type = message.get("type")
            payload = message.get("payload") or {}
            logger.info("notifier_job_received type=%s run_id=%s", job_type, payload.get("run_id"))

            if job_type == JOB_TYPE_NOTIFY_SCRAPE_COMPLETE:
                job = NotifyScrapeCompleteJob.from_payload(payload)
                execute_notify_scrape_complete(job, settings)
            else:
                logger.warning("notifier_unknown_job type=%s", job_type)
        except redis.exceptions.TimeoutError:
            continue
        except Exception:
            logger.exception("notifier_job_failed")
            time.sleep(5)


if __name__ == "__main__":
    run()
