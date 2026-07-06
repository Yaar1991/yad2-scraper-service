from typing import Any

from packages.core.queue import JobQueue, SCRAPE_QUEUE
from packages.data.repositories.subscriptions import SubscriptionsRepository
from packages.jobs.constants import JOB_TYPE_SCRAPE_CITY
from packages.jobs.models import ScrapeCityJob


def enqueue_scrape_jobs(
    queue: JobQueue,
    repo: SubscriptionsRepository,
    city_name: str | None = None,
) -> list[dict[str, Any]]:
    if city_name:
        city = repo.get_active_city(city_name.strip())
        cities = [city] if city else []
    else:
        cities = repo.list_active_cities()

    enqueued: list[dict[str, Any]] = []
    for city in cities:
        job = ScrapeCityJob(
            city_name=city["city_name"],
            city_code=city["city_code"],
            min_rooms=city.get("min_rooms"),
        )
        queue.enqueue(SCRAPE_QUEUE, JOB_TYPE_SCRAPE_CITY, job.to_payload())
        enqueued.append(
            {
                "city_name": job.city_name,
                "city_code": job.city_code,
                "min_rooms": job.min_rooms,
            }
        )

    return enqueued
