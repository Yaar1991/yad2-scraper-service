import json
from typing import Any

import redis

SCRAPE_QUEUE = "yad2:queue:scrape"
NOTIFY_QUEUE = "yad2:queue:notify"


class JobQueue:
    def __init__(self, redis_url: str):
        self._redis = redis.from_url(redis_url, decode_responses=True)

    def ping(self) -> None:
        self._redis.ping()

    def queue_depth(self, queue: str) -> int:
        return int(self._redis.llen(queue))

    def enqueue(self, queue: str, job_type: str, payload: dict[str, Any]) -> None:
        message = json.dumps({"type": job_type, "payload": payload})
        self._redis.lpush(queue, message)

    def dequeue(self, queue: str, timeout: int = 5) -> dict[str, Any] | None:
        result = self._redis.brpop(queue, timeout=timeout)
        if not result:
            return None
        _, raw = result
        return json.loads(raw)
