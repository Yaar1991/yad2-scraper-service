from typing import Any

from packages.data.db import Database
from packages.data.serialize import serialize_row, serialize_rows


class StatsRepository:
    def __init__(self, db: Database):
        self._db = db

    def get_stats(self) -> dict[str, Any]:
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) AS total_listings,
                    COUNT(*) FILTER (WHERE is_active) AS active_listings,
                    COUNT(DISTINCT city) AS cities,
                    COUNT(DISTINCT neighborhood) AS neighborhoods,
                    MIN(price_numeric) FILTER (WHERE price_numeric > 0) AS min_price,
                    MAX(price_numeric) AS max_price,
                    ROUND(AVG(price_numeric) FILTER (WHERE price_numeric > 0)) AS avg_price,
                    MIN(first_seen_at) AS oldest_listing,
                    MAX(last_seen_at) AS newest_update
                FROM listings
                """
            )
            result = serialize_row(dict(cur.fetchone()))

            cur.execute(
                """
                SELECT city, COUNT(*) AS count
                FROM listings
                WHERE is_active = TRUE
                GROUP BY city
                ORDER BY count DESC
                LIMIT 20
                """
            )
            result["top_cities"] = serialize_rows([dict(row) for row in cur.fetchall()])

            cur.execute(
                """
                SELECT rooms, COUNT(*) AS count
                FROM listings
                WHERE is_active = TRUE
                GROUP BY rooms
                ORDER BY rooms
                """
            )
            result["rooms_distribution"] = serialize_rows(
                [dict(row) for row in cur.fetchall()]
            )

            try:
                cur.execute(
                    """
                    SELECT
                        COUNT(*) AS total_price_records,
                        COUNT(DISTINCT listing_id) AS listings_with_history,
                        COUNT(*) FILTER (WHERE recorded_at > NOW() - INTERVAL '24 hours')
                            AS changes_last_24h,
                        COUNT(*) FILTER (WHERE recorded_at > NOW() - INTERVAL '7 days')
                            AS changes_last_7d
                    FROM price_history
                    """
                )
                result["price_history"] = serialize_row(dict(cur.fetchone()))
            except Exception:
                result["price_history"] = {
                    "total_price_records": 0,
                    "listings_with_history": 0,
                    "changes_last_24h": 0,
                    "changes_last_7d": 0,
                }

        return result
