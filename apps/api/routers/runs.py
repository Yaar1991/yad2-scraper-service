from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from apps.api.deps import get_job_queue, get_runs_repo, get_subscriptions_repo
from packages.core.queue import JobQueue, SCRAPE_QUEUE
from packages.data.repositories.runs import RunsRepository
from packages.data.repositories.subscriptions import SubscriptionsRepository
from packages.jobs.enqueue import enqueue_scrape_jobs

router = APIRouter(prefix="", tags=["runs"])


class TriggerScrapeBody(BaseModel):
    city_name: str | None = None


@router.get("/runs")
def list_runs(
    limit: int = Query(default=20, ge=1, le=100),
    repo: RunsRepository = Depends(get_runs_repo),
) -> dict:
    return {"runs": repo.list_runs(limit=limit)}


@router.post("/runs/trigger", status_code=202, response_model=None)
def trigger_scrape(
    body: TriggerScrapeBody | None = None,
    queue: JobQueue = Depends(get_job_queue),
    repo: SubscriptionsRepository = Depends(get_subscriptions_repo),
):
    city_name = body.city_name if body else None

    try:
        queue.ping()
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"error": f"Job queue unavailable: {exc}"},
        )

    enqueued = enqueue_scrape_jobs(queue, repo, city_name=city_name)
    if not enqueued:
        if city_name:
            return JSONResponse(
                status_code=404,
                content={"error": f"Active city not found: {city_name}"},
            )
        return JSONResponse(
            status_code=400,
            content={"error": "No active cities configured"},
        )

    return {
        "message": "Scrape jobs enqueued",
        "enqueued": enqueued,
        "queue_depth": queue.queue_depth(SCRAPE_QUEUE),
    }
