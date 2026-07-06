from typing import Any

from packages.data.db import Database
from packages.data.serialize import serialize_rows


class RunsRepository:
    def __init__(self, db: Database):
        self._db = db

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT id, started_at, finished_at, total_pages, pages_scraped,
                       pages_failed, listings_found, listings_new, listings_updated,
                       price_changes, status, error_message, run_type, last_page_scraped
                FROM scrape_runs
                ORDER BY started_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return serialize_rows([dict(row) for row in cur.fetchall()])

    def cleanup_stale_runs(self) -> int:
        with self._db.cursor() as cur:
            cur.execute(
                """
                UPDATE scrape_runs
                SET status = 'abandoned', finished_at = NOW(),
                    error_message = 'Abandoned: no pages scraped before restart'
                WHERE status = 'running' AND (pages_scraped IS NULL OR pages_scraped = 0)
                """
            )
            return cur.rowcount
