from typing import Any

from packages.data.db import Database
from packages.data.serialize import serialize_row, serialize_rows


class AnalyticsRepository:
    def __init__(self, db: Database):
        self._db = db

    def get_market_summary(self) -> dict[str, Any]:
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE first_seen_at > NOW() - INTERVAL '24 hours') AS new_24h,
                    COUNT(*) FILTER (WHERE first_seen_at > NOW() - INTERVAL '7 days') AS new_7d,
                    COUNT(*) FILTER (
                        WHERE is_active = FALSE AND last_seen_at > NOW() - INTERVAL '7 days'
                    ) AS removed_7d,
                    COUNT(*) FILTER (WHERE is_active = TRUE) AS active_total,
                    ROUND(AVG(price_numeric) FILTER (
                        WHERE is_active = TRUE AND price_numeric > 0
                    ))::int AS avg_price_all,
                    ROUND(AVG(price_numeric) FILTER (
                        WHERE is_active = TRUE AND price_numeric > 0
                        AND first_seen_at > NOW() - INTERVAL '7 days'
                    ))::int AS avg_price_new
                FROM listings
                """
            )
            overview = serialize_row(dict(cur.fetchone()))

            cur.execute(
                """
                SELECT
                    CASE
                        WHEN price_numeric < 2000 THEN '0-2K'
                        WHEN price_numeric < 3000 THEN '2-3K'
                        WHEN price_numeric < 4000 THEN '3-4K'
                        WHEN price_numeric < 5000 THEN '4-5K'
                        WHEN price_numeric < 6000 THEN '5-6K'
                        WHEN price_numeric < 8000 THEN '6-8K'
                        WHEN price_numeric < 10000 THEN '8-10K'
                        ELSE '10K+'
                    END AS bucket,
                    COUNT(*) AS count
                FROM listings
                WHERE is_active = TRUE AND price_numeric > 0
                GROUP BY bucket
                ORDER BY MIN(price_numeric)
                """
            )
            price_dist = serialize_rows([dict(row) for row in cur.fetchall()])

            cur.execute(
                """
                SELECT city, neighborhood,
                    ROUND(AVG(price_numeric))::int AS avg_price,
                    COUNT(*) AS count
                FROM listings
                WHERE is_active = TRUE AND price_numeric > 0 AND neighborhood IS NOT NULL
                GROUP BY city, neighborhood
                HAVING COUNT(*) >= 5
                ORDER BY avg_price ASC
                LIMIT 5
                """
            )
            cheapest = serialize_rows([dict(row) for row in cur.fetchall()])

            cur.execute(
                """
                SELECT city, neighborhood,
                    ROUND(AVG(price_numeric))::int AS avg_price,
                    COUNT(*) AS count
                FROM listings
                WHERE is_active = TRUE AND price_numeric > 0 AND neighborhood IS NOT NULL
                GROUP BY city, neighborhood
                HAVING COUNT(*) >= 5
                ORDER BY avg_price DESC
                LIMIT 5
                """
            )
            expensive = serialize_rows([dict(row) for row in cur.fetchall()])

        return {
            "overview": overview,
            "price_distribution": price_dist,
            "cheapest_neighborhoods": cheapest,
            "most_expensive_neighborhoods": expensive,
        }

    def get_neighborhood_analytics(
        self, city: str | None, min_listings: int
    ) -> dict[str, Any]:
        conditions = ["is_active = TRUE", "price_numeric > 0", "neighborhood IS NOT NULL"]
        params: list[Any] = []

        if city:
            conditions.append("city ILIKE %s")
            params.append(f"%{city}%")

        where = " AND ".join(conditions)

        with self._db.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    city,
                    neighborhood,
                    COUNT(*) AS listings_count,
                    ROUND(AVG(price_numeric))::int AS avg_price,
                    MIN(price_numeric) AS min_price,
                    MAX(price_numeric) AS max_price,
                    (PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price_numeric))::int AS median_price,
                    ROUND(AVG(CASE WHEN size_sqm ~ '^[0-9]+$' AND size_sqm::int > 0
                        THEN price_numeric::numeric / size_sqm::int END))::int AS avg_price_per_sqm,
                    ROUND(AVG(CASE WHEN rooms ~ '^[0-9.]+$' THEN rooms::numeric END), 1) AS avg_rooms
                FROM listings
                WHERE {where}
                GROUP BY city, neighborhood
                HAVING COUNT(*) >= %s
                ORDER BY avg_price ASC
                """,
                params + [min_listings],
            )
            neighborhoods = serialize_rows([dict(row) for row in cur.fetchall()])

        return {
            "count": len(neighborhoods),
            "min_listings": min_listings,
            "neighborhoods": neighborhoods,
        }

    def get_price_map(self, city: str | None, limit: int) -> dict[str, Any]:
        conditions = [
            "is_active = TRUE",
            "latitude IS NOT NULL",
            "longitude IS NOT NULL",
            "price_numeric > 0",
        ]
        params: list[Any] = []

        if city:
            conditions.append("city ILIKE %s")
            params.append(f"%{city}%")

        where = " AND ".join(conditions)

        with self._db.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, city, neighborhood, street, rooms, price_numeric,
                       size_sqm, floor, latitude, longitude, link_token,
                       is_merchant, first_seen_at
                FROM listings
                WHERE {where}
                ORDER BY price_numeric ASC
                LIMIT %s
                """,
                params + [limit],
            )
            listings = serialize_rows([dict(row) for row in cur.fetchall()])

        return {"count": len(listings), "listings": listings}

    def get_price_trends(self, city: str | None, days: int) -> dict[str, Any]:
        conditions = ["ph.recorded_at > NOW() - make_interval(days => %s)"]
        params: list[Any] = [days]

        if city:
            conditions.append("l.city ILIKE %s")
            params.append(f"%{city}%")

        where = " AND ".join(conditions)

        with self._db.cursor() as cur:
            cur.execute(
                f"""
                WITH ph_with_lag AS (
                    SELECT
                        ph.listing_id,
                        ph.price_numeric,
                        ph.recorded_at,
                        LAG(ph.price_numeric) OVER (
                            PARTITION BY ph.listing_id ORDER BY ph.recorded_at
                        ) AS prev_price
                    FROM price_history ph
                    JOIN listings l ON l.id = ph.listing_id
                    WHERE {where}
                )
                SELECT
                    DATE(recorded_at) AS date,
                    COUNT(*) AS price_changes,
                    COUNT(DISTINCT listing_id) AS listings_affected,
                    ROUND(AVG(price_numeric))::int AS avg_price,
                    SUM(CASE WHEN prev_price IS NOT NULL AND price_numeric < prev_price THEN 1 ELSE 0 END) AS drops,
                    SUM(CASE WHEN prev_price IS NOT NULL AND price_numeric > prev_price THEN 1 ELSE 0 END) AS raises
                FROM ph_with_lag
                GROUP BY DATE(recorded_at)
                ORDER BY date ASC
                """,
                params,
            )
            trends = serialize_rows([dict(row) for row in cur.fetchall()])

        return {"days": days, "count": len(trends), "trends": trends}

    def get_deals(
        self,
        city: str | None,
        min_discount: int,
        min_listings_in_area: int,
        limit: int,
    ) -> dict[str, Any]:
        conditions = [
            "l.is_active = TRUE",
            "l.price_numeric > 0",
            "l.neighborhood IS NOT NULL",
        ]
        params: list[Any] = []

        if city:
            conditions.append("l.city ILIKE %s")
            params.append(f"%{city}%")

        where = " AND ".join(conditions)

        query_params: list[Any] = []
        if city:
            query_params.append(f"%{city}%")
        query_params.append(min_listings_in_area)
        query_params.extend(params)
        query_params.append(min_discount)
        query_params.append(limit)

        with self._db.cursor() as cur:
            cur.execute(
                f"""
                WITH neighborhood_stats AS (
                    SELECT city, neighborhood,
                        AVG(price_numeric) AS avg_price,
                        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price_numeric) AS median_price,
                        COUNT(*) AS area_count
                    FROM listings
                    WHERE is_active = TRUE AND price_numeric > 0 AND neighborhood IS NOT NULL
                        {('AND city ILIKE %s' if city else '')}
                    GROUP BY city, neighborhood
                    HAVING COUNT(*) >= %s
                )
                SELECT
                    l.id, l.link_token, l.city, l.neighborhood, l.street,
                    l.rooms, l.price_numeric, l.size_sqm, l.floor,
                    l.image_url, l.is_merchant, l.first_seen_at,
                    ns.avg_price::int AS area_avg,
                    ns.median_price::int AS area_median,
                    ns.area_count,
                    ROUND(((1 - l.price_numeric::numeric / ns.avg_price) * 100)::numeric, 1) AS discount_pct
                FROM listings l
                JOIN neighborhood_stats ns ON l.city = ns.city AND l.neighborhood = ns.neighborhood
                WHERE {where}
                    AND l.price_numeric < ns.avg_price * (1 - %s / 100.0)
                ORDER BY discount_pct DESC
                LIMIT %s
                """,
                query_params,
            )
            deals = serialize_rows([dict(row) for row in cur.fetchall()])

        return {
            "count": len(deals),
            "min_discount": min_discount,
            "deals": deals,
        }

    def compare_neighborhoods(
        self, n1: str, n2: str, c1: str, c2: str
    ) -> dict[str, Any]:
        results: dict[str, Any] = {}

        with self._db.cursor() as cur:
            for label, neigh, city in [("n1", n1, c1), ("n2", n2, c2)]:
                conditions = ["is_active = TRUE", "price_numeric > 0", "neighborhood ILIKE %s"]
                params: list[Any] = [f"%{neigh}%"]
                if city:
                    conditions.append("city ILIKE %s")
                    params.append(f"%{city}%")

                where = " AND ".join(conditions)

                cur.execute(
                    f"""
                    SELECT
                        city,
                        neighborhood,
                        COUNT(*) AS listings_count,
                        ROUND(AVG(price_numeric))::int AS avg_price,
                        MIN(price_numeric) AS min_price,
                        MAX(price_numeric) AS max_price,
                        (PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price_numeric))::int AS median_price,
                        ROUND(AVG(CASE WHEN size_sqm ~ '^[0-9]+$' AND size_sqm::int > 0
                            THEN price_numeric::numeric / size_sqm::int END))::int AS avg_price_per_sqm,
                        ROUND(AVG(CASE WHEN rooms ~ '^[0-9.]+$' THEN rooms::numeric END), 1) AS avg_rooms,
                        ROUND(AVG(CASE WHEN size_sqm ~ '^[0-9]+$' THEN size_sqm::int END))::int AS avg_sqm,
                        COUNT(*) FILTER (WHERE is_merchant) AS agents,
                        COUNT(*) FILTER (WHERE NOT is_merchant) AS private
                    FROM listings
                    WHERE {where}
                    GROUP BY city, neighborhood
                    ORDER BY COUNT(*) DESC
                    LIMIT 1
                    """,
                    params,
                )
                row = cur.fetchone()
                if row:
                    results[label] = serialize_row(dict(row))
                else:
                    results[label] = {
                        "neighborhood": neigh,
                        "city": city or "Not found",
                        "listings_count": 0,
                    }

                cur.execute(
                    f"""
                    SELECT rooms, COUNT(*) AS count
                    FROM listings
                    WHERE {where} AND rooms IS NOT NULL AND rooms != ''
                    GROUP BY rooms
                    ORDER BY rooms
                    """,
                    params,
                )
                results[f"{label}_rooms"] = serialize_rows([dict(r) for r in cur.fetchall()])

        return results

    def get_stale_listings(
        self, city: str | None, min_days: int, limit: int
    ) -> dict[str, Any]:
        conditions = [
            "is_active = TRUE",
            "price_numeric > 0",
            "first_seen_at < NOW() - make_interval(days => %s)",
        ]
        params: list[Any] = [min_days]

        if city:
            conditions.append("city ILIKE %s")
            params.append(f"%{city}%")

        where = " AND ".join(conditions)

        with self._db.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, link_token, city, neighborhood, street, rooms,
                       price_numeric, size_sqm, floor, image_url,
                       is_merchant, first_seen_at, last_seen_at,
                       EXTRACT(DAY FROM NOW() - first_seen_at)::int AS days_on_market
                FROM listings
                WHERE {where}
                ORDER BY first_seen_at ASC
                LIMIT %s
                """,
                params + [limit],
            )
            listings = serialize_rows([dict(row) for row in cur.fetchall()])

            cur.execute(
                f"""
                SELECT
                    COUNT(*) AS total_stale,
                    ROUND(AVG(price_numeric))::int AS avg_price,
                    ROUND(AVG(EXTRACT(DAY FROM NOW() - first_seen_at)))::int AS avg_days
                FROM listings
                WHERE {where}
                """,
                params,
            )
            summary = serialize_row(dict(cur.fetchone()))

        return {
            "count": len(listings),
            "min_days": min_days,
            "summary": summary,
            "listings": listings,
        }

    def get_city_stats(self, city_name: str) -> dict[str, Any] | None:
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT
                    city,
                    COUNT(*) AS total_listings,
                    COUNT(*) FILTER (WHERE is_active) AS active_listings,
                    ROUND(AVG(price_numeric) FILTER (WHERE is_active AND price_numeric > 0))::int AS avg_price,
                    MIN(price_numeric) FILTER (WHERE is_active AND price_numeric > 0) AS min_price,
                    MAX(price_numeric) FILTER (WHERE is_active AND price_numeric > 0) AS max_price,
                    (PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY CASE WHEN is_active AND price_numeric > 0 THEN price_numeric END))::int AS median_price,
                    ROUND(AVG(CASE WHEN is_active AND rooms ~ '^[0-9.]+$' THEN rooms::numeric END), 1) AS avg_rooms,
                    ROUND(AVG(CASE WHEN is_active AND size_sqm ~ '^[0-9]+$' AND size_sqm::int > 0
                        THEN price_numeric::numeric / size_sqm::int END))::int AS avg_price_per_sqm,
                    COUNT(*) FILTER (WHERE is_active AND is_merchant) AS agent_listings,
                    COUNT(*) FILTER (WHERE is_active AND NOT is_merchant) AS private_listings,
                    COUNT(*) FILTER (WHERE first_seen_at > NOW() - INTERVAL '24 hours') AS new_24h,
                    COUNT(*) FILTER (WHERE first_seen_at > NOW() - INTERVAL '7 days') AS new_7d,
                    COUNT(DISTINCT neighborhood) FILTER (WHERE is_active) AS neighborhoods
                FROM listings
                WHERE city ILIKE %s
                GROUP BY city
                ORDER BY COUNT(*) DESC
                LIMIT 1
                """,
                (f"%{city_name}%",),
            )
            overview = cur.fetchone()
            if not overview or overview["total_listings"] == 0:
                return None

            result: dict[str, Any] = {"overview": serialize_row(dict(overview))}

            cur.execute(
                """
                SELECT neighborhood, COUNT(*) AS count,
                    ROUND(AVG(price_numeric) FILTER (WHERE price_numeric > 0))::int AS avg_price,
                    MIN(price_numeric) FILTER (WHERE price_numeric > 0) AS min_price,
                    MAX(price_numeric) FILTER (WHERE price_numeric > 0) AS max_price
                FROM listings
                WHERE is_active AND city ILIKE %s AND neighborhood IS NOT NULL
                GROUP BY neighborhood
                ORDER BY count DESC
                LIMIT 20
                """,
                (f"%{city_name}%",),
            )
            result["neighborhoods"] = serialize_rows([dict(r) for r in cur.fetchall()])

            cur.execute(
                """
                SELECT rooms, COUNT(*) AS count
                FROM listings
                WHERE is_active AND city ILIKE %s AND rooms IS NOT NULL AND rooms != ''
                GROUP BY rooms
                ORDER BY rooms
                """,
                (f"%{city_name}%",),
            )
            result["rooms_distribution"] = serialize_rows([dict(r) for r in cur.fetchall()])

            cur.execute(
                """
                SELECT
                    CASE
                        WHEN price_numeric < 2000 THEN '0-2K'
                        WHEN price_numeric < 3000 THEN '2-3K'
                        WHEN price_numeric < 4000 THEN '3-4K'
                        WHEN price_numeric < 5000 THEN '4-5K'
                        WHEN price_numeric < 6000 THEN '5-6K'
                        WHEN price_numeric < 8000 THEN '6-8K'
                        WHEN price_numeric < 10000 THEN '8-10K'
                        ELSE '10K+'
                    END AS bucket,
                    COUNT(*) AS count
                FROM listings
                WHERE is_active AND city ILIKE %s AND price_numeric > 0
                GROUP BY bucket
                ORDER BY MIN(price_numeric)
                """,
                (f"%{city_name}%",),
            )
            result["price_distribution"] = serialize_rows([dict(r) for r in cur.fetchall()])

        return result

    def get_price_drop_leaderboard(
        self, days: int, min_drops: int
    ) -> dict[str, Any]:
        with self._db.cursor() as cur:
            cur.execute(
                """
                WITH drops AS (
                    SELECT
                        ph.listing_id,
                        l.city,
                        l.neighborhood,
                        ph.price_numeric AS new_price,
                        LAG(ph.price_numeric) OVER (
                            PARTITION BY ph.listing_id ORDER BY ph.recorded_at
                        ) AS old_price,
                        ph.recorded_at
                    FROM price_history ph
                    JOIN listings l ON l.id = ph.listing_id
                    WHERE ph.recorded_at > NOW() - make_interval(days => %s)
                ),
                actual_drops AS (
                    SELECT * FROM drops
                    WHERE old_price IS NOT NULL AND new_price < old_price
                )
                SELECT
                    city,
                    neighborhood,
                    COUNT(*) AS drop_count,
                    COUNT(DISTINCT listing_id) AS listings_affected,
                    ROUND(AVG(old_price - new_price))::int AS avg_drop_amount,
                    ROUND(AVG((old_price - new_price)::numeric / NULLIF(old_price, 0) * 100), 1) AS avg_drop_pct,
                    MAX(old_price - new_price) AS biggest_drop
                FROM actual_drops
                WHERE neighborhood IS NOT NULL
                GROUP BY city, neighborhood
                HAVING COUNT(*) >= %s
                ORDER BY drop_count DESC
                LIMIT 30
                """,
                (days, min_drops),
            )
            neighborhoods = serialize_rows([dict(r) for r in cur.fetchall()])

            cur.execute(
                """
                WITH drops AS (
                    SELECT
                        ph.price_numeric AS new_price,
                        LAG(ph.price_numeric) OVER (
                            PARTITION BY ph.listing_id ORDER BY ph.recorded_at
                        ) AS old_price
                    FROM price_history ph
                    WHERE ph.recorded_at > NOW() - make_interval(days => %s)
                )
                SELECT
                    COUNT(*) FILTER (WHERE old_price IS NOT NULL AND new_price < old_price) AS total_drops,
                    COUNT(*) FILTER (WHERE old_price IS NOT NULL AND new_price > old_price) AS total_raises
                FROM drops
                """,
                (days,),
            )
            summary = serialize_row(dict(cur.fetchone()))

        return {
            "days": days,
            "count": len(neighborhoods),
            "summary": summary,
            "neighborhoods": neighborhoods,
        }
