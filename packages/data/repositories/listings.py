from dataclasses import dataclass
from typing import Any

from packages.data.db import Database
from packages.data.serialize import serialize_row, serialize_rows


@dataclass
class ListingsQuery:
    city: str | None = None
    neighborhood: str | None = None
    min_price: int | None = None
    max_price: int | None = None
    min_rooms: int | None = None
    max_rooms: int | None = None
    is_merchant: bool | None = None
    active_only: bool = True
    limit: int = 100
    offset: int = 0
    sort_by: str = "last_seen_at"
    sort_order: str = "desc"
    fields: str = "full"


ALLOWED_SORTS = {"last_seen_at", "first_seen_at", "price_numeric", "date_added", "rooms"}

FULL_COLUMNS = """id, ad_number, link_token, street, property_type,
    description_line, city, neighborhood, price, price_numeric,
    rooms, floor, size_sqm, date_added, updated_at,
    contact_name, is_merchant, merchant_name,
    latitude, longitude, image_url, images_count,
    amenities, first_seen_at, last_seen_at, is_active"""

MINIMAL_COLUMNS = """id, link_token, city, neighborhood, street, price_numeric,
    rooms, floor, size_sqm, is_merchant, merchant_name,
    image_url, first_seen_at, last_seen_at, is_active"""


def _build_conditions(query: ListingsQuery) -> tuple[list[str], list[Any]]:
    conditions: list[str] = []
    params: list[Any] = []

    if query.active_only:
        conditions.append("is_active = TRUE")

    if query.city:
        conditions.append("city ILIKE %s")
        params.append(f"%{query.city}%")

    if query.neighborhood:
        conditions.append("neighborhood ILIKE %s")
        params.append(f"%{query.neighborhood}%")

    if query.min_price is not None:
        conditions.append("price_numeric >= %s")
        params.append(query.min_price)

    if query.max_price is not None:
        conditions.append("price_numeric <= %s")
        params.append(query.max_price)

    if query.min_rooms is not None:
        conditions.append(
            "CASE WHEN rooms ~ '^[0-9.]+$' THEN rooms::numeric ELSE 0 END >= %s"
        )
        params.append(query.min_rooms)

    if query.max_rooms is not None:
        conditions.append(
            "CASE WHEN rooms ~ '^[0-9.]+$' THEN rooms::numeric ELSE 0 END <= %s"
        )
        params.append(query.max_rooms)

    if query.is_merchant is not None:
        conditions.append("is_merchant = %s")
        params.append(query.is_merchant)

    return conditions, params


class ListingsRepository:
    def __init__(self, db: Database):
        self._db = db

    def list_listings(self, query: ListingsQuery) -> dict[str, Any]:
        conditions, params = _build_conditions(query)
        where_clause = " AND ".join(conditions) if conditions else "1=1"

        sort_by = query.sort_by if query.sort_by in ALLOWED_SORTS else "last_seen_at"
        sort_order = "DESC" if query.sort_order.lower() == "desc" else "ASC"
        columns = MINIMAL_COLUMNS if query.fields == "minimal" else FULL_COLUMNS

        with self._db.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) AS count FROM listings WHERE {where_clause}",
                params,
            )
            total = cur.fetchone()["count"]

            cur.execute(
                f"""
                SELECT {columns}
                FROM listings
                WHERE {where_clause}
                ORDER BY {sort_by} {sort_order}
                LIMIT %s OFFSET %s
                """,
                params + [query.limit, query.offset],
            )
            listings = serialize_rows([dict(row) for row in cur.fetchall()])

        return {
            "total": total,
            "limit": query.limit,
            "offset": query.offset,
            "count": len(listings),
            "listings": listings,
        }

    def get_listing(self, listing_id: str) -> dict[str, Any] | None:
        with self._db.cursor() as cur:
            cur.execute("SELECT * FROM listings WHERE id = %s", (listing_id,))
            row = cur.fetchone()
            if not row:
                return None

            result = serialize_row(dict(row))

            cur.execute(
                "SELECT COUNT(*) AS count FROM price_history WHERE listing_id = %s",
                (listing_id,),
            )
            result["price_history_count"] = cur.fetchone()["count"]

        return result

    def get_price_history(self, listing_id: str) -> dict[str, Any] | None:
        with self._db.cursor() as cur:
            cur.execute(
                "SELECT id, city, street, neighborhood FROM listings WHERE id = %s",
                (listing_id,),
            )
            listing = cur.fetchone()
            if not listing:
                return None

            cur.execute(
                """
                SELECT price, price_numeric, recorded_at, scrape_run_id
                FROM price_history
                WHERE listing_id = %s
                ORDER BY recorded_at ASC
                """,
                (listing_id,),
            )
            history = serialize_rows([dict(row) for row in cur.fetchall()])

        listing_data = serialize_row(dict(listing))
        return {
            "listing_id": listing_id,
            "city": listing_data["city"],
            "street": listing_data["street"],
            "neighborhood": listing_data["neighborhood"],
            "price_changes": len(history) - 1 if history else 0,
            "history": history,
        }

    def list_cities(self) -> list[dict[str, Any]]:
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT city, COUNT(*) AS listings_count
                FROM listings
                WHERE is_active = TRUE AND city IS NOT NULL
                GROUP BY city
                ORDER BY listings_count DESC
                """
            )
            return serialize_rows([dict(row) for row in cur.fetchall()])

    def list_neighborhoods(self, city: str | None = None) -> list[dict[str, Any]]:
        with self._db.cursor() as cur:
            if city:
                cur.execute(
                    """
                    SELECT neighborhood, COUNT(*) AS listings_count
                    FROM listings
                    WHERE is_active = TRUE AND neighborhood IS NOT NULL AND city ILIKE %s
                    GROUP BY neighborhood
                    ORDER BY listings_count DESC
                    """,
                    (f"%{city}%",),
                )
            else:
                cur.execute(
                    """
                    SELECT neighborhood, city, COUNT(*) AS listings_count
                    FROM listings
                    WHERE is_active = TRUE AND neighborhood IS NOT NULL
                    GROUP BY neighborhood, city
                    ORDER BY listings_count DESC
                    LIMIT 100
                    """
                )
            return serialize_rows([dict(row) for row in cur.fetchall()])
