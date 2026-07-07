from typing import Any

from packages.data.db import Database
from packages.data.serialize import serialize_row, serialize_rows


class PriceChangesRepository:
    def __init__(self, db: Database):
        self._db = db

    def list_price_changes(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        city: str | None = None,
        days: int = 7,
    ) -> dict[str, Any]:
        days = max(1, min(days, 365))
        conditions = ["ph.recorded_at > NOW() - make_interval(days => %s)"]
        params: list[Any] = [days]

        if city:
            conditions.append("l.city ILIKE %s")
            params.append(f"%{city}%")

        where_clause = " AND ".join(conditions)

        try:
            with self._db.cursor() as cur:
                cur.execute(
                    f"""
                    WITH changes AS (
                        SELECT
                            ph.listing_id,
                            l.link_token,
                            l.city,
                            l.street,
                            l.neighborhood,
                            l.rooms,
                            ph.price,
                            ph.price_numeric,
                            ph.recorded_at,
                            LAG(ph.price_numeric) OVER (
                                PARTITION BY ph.listing_id ORDER BY ph.recorded_at
                            ) AS previous_price
                        FROM price_history ph
                        JOIN listings l ON l.id = ph.listing_id
                        WHERE {where_clause}
                    )
                    SELECT * FROM changes
                    WHERE previous_price IS NOT NULL
                    ORDER BY recorded_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    params + [limit, offset],
                )

                changes = []
                for row in cur.fetchall():
                    item = serialize_row(dict(row))
                    item["price_diff"] = item["price_numeric"] - item["previous_price"]
                    if item["previous_price"]:
                        item["price_diff_percent"] = round(
                            (item["price_diff"] / item["previous_price"]) * 100, 1
                        )
                    else:
                        item["price_diff_percent"] = 0
                    changes.append(item)

                cur.execute(
                    f"""
                    WITH changes AS (
                        SELECT ph.listing_id,
                            LAG(ph.price_numeric) OVER (
                                PARTITION BY ph.listing_id ORDER BY ph.recorded_at
                            ) AS previous_price
                        FROM price_history ph
                        JOIN listings l ON l.id = ph.listing_id
                        WHERE {where_clause}
                    )
                    SELECT COUNT(*) AS count FROM changes WHERE previous_price IS NOT NULL
                    """,
                    params,
                )
                total = cur.fetchone()["count"]

                cur.execute(
                    f"""
                    SELECT
                        COUNT(DISTINCT ph.listing_id) AS listings_with_changes,
                        COUNT(*) AS total_price_records
                    FROM price_history ph
                    JOIN listings l ON l.id = ph.listing_id
                    WHERE {where_clause}
                    """,
                    params,
                )
                summary = serialize_row(dict(cur.fetchone()))
        except Exception:
            return {
                "total": 0,
                "limit": limit,
                "offset": offset,
                "days": days,
                "count": 0,
                "summary": {
                    "listings_with_changes": 0,
                    "total_price_records": 0,
                },
                "changes": [],
            }

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "days": days,
            "count": len(changes),
            "summary": summary,
            "changes": changes,
        }
