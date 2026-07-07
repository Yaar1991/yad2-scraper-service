import json
import logging
from datetime import datetime, timezone
from typing import Optional

from packages.data.db import Database

logger = logging.getLogger(__name__)


class ScrapeSink:
    """Persistence sink for scrape runs and listings.

    Notification delivery is intentionally out of scope here: the worker
    enqueues a notify job on scrape completion and the notifier service is
    responsible for Telegram/WhatsApp fan-out.
    """

    def __init__(self, db: Database):
        self._db = db

    # ── run lifecycle ────────────────────────────────────────────────────
    def cleanup_stale_runs(self) -> int:
        """Mark all 'running' runs with 0 pages scraped as 'abandoned'."""
        with self._db.cursor() as cur:
            cur.execute(
                """
                UPDATE scrape_runs
                SET status = 'abandoned', finished_at = NOW(),
                    error_message = 'Abandoned: no pages scraped before restart'
                WHERE status = 'running' AND (pages_scraped IS NULL OR pages_scraped = 0)
                """
            )
            abandoned = cur.rowcount
        if abandoned > 0:
            logger.info(f"Cleaned up {abandoned} stale runs with 0 pages scraped")
        return abandoned

    def start_scrape_run(self, run_type: str = "full") -> int:
        with self._db.cursor() as cur:
            cur.execute(
                "INSERT INTO scrape_runs (started_at, status, run_type) "
                "VALUES (NOW(), 'running', %s) RETURNING id",
                (run_type,),
            )
            return cur.fetchone()["id"]

    def update_scrape_progress(self, run_id: int, pages_scraped: int, pages_failed: int,
                               listings_found: int, listings_new: int,
                               listings_updated: int, price_changes: int,
                               last_page_scraped: int, scraped_pages: set,
                               total_pages: int = None) -> None:
        """Save current scrape progress to DB (called after each page)."""
        pages_list = json.dumps(sorted(scraped_pages))
        with self._db.cursor() as cur:
            if total_pages is not None:
                cur.execute(
                    """
                    UPDATE scrape_runs SET
                        total_pages = %s, pages_scraped = %s, pages_failed = %s,
                        listings_found = %s, listings_new = %s, listings_updated = %s,
                        price_changes = %s, last_page_scraped = %s, scraped_pages = %s
                    WHERE id = %s
                    """,
                    (total_pages, pages_scraped, pages_failed, listings_found,
                     listings_new, listings_updated, price_changes,
                     last_page_scraped, pages_list, run_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE scrape_runs SET
                        pages_scraped = %s, pages_failed = %s,
                        listings_found = %s, listings_new = %s, listings_updated = %s,
                        price_changes = %s, last_page_scraped = %s, scraped_pages = %s
                    WHERE id = %s
                    """,
                    (pages_scraped, pages_failed, listings_found,
                     listings_new, listings_updated, price_changes,
                     last_page_scraped, pages_list, run_id),
                )

    def finish_scrape_run(self, run_id: int, total_pages: int, pages_scraped: int,
                          pages_failed: int, listings_found: int,
                          listings_new: int, listings_updated: int,
                          price_changes: int = 0,
                          status: str = "completed", error: str = None) -> None:
        """Update scrape run with final stats."""
        with self._db.cursor() as cur:
            cur.execute(
                """
                UPDATE scrape_runs SET
                    finished_at = NOW(),
                    total_pages = %s,
                    pages_scraped = %s,
                    pages_failed = %s,
                    listings_found = %s,
                    listings_new = %s,
                    listings_updated = %s,
                    price_changes = %s,
                    status = %s,
                    error_message = %s
                WHERE id = %s
                """,
                (total_pages, pages_scraped, pages_failed, listings_found,
                 listings_new, listings_updated, price_changes, status, error, run_id),
            )

    def get_interrupted_run(self) -> Optional[dict]:
        """Return an interrupted scrape run (status='running') that has real progress."""
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT id, run_type, total_pages, pages_scraped, pages_failed,
                       listings_found, listings_new, listings_updated, price_changes,
                       last_page_scraped, scraped_pages, started_at
                FROM scrape_runs
                WHERE status = 'running' AND pages_scraped > 0
                ORDER BY id DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()

        if not row:
            return None

        scraped_pages = row["scraped_pages"] or []
        if isinstance(scraped_pages, str):
            scraped_pages = json.loads(scraped_pages)

        return {
            "run_id": row["id"],
            "run_type": row["run_type"] or "full",
            "total_pages": row["total_pages"] or 0,
            "pages_scraped": row["pages_scraped"] or 0,
            "pages_failed": row["pages_failed"] or 0,
            "listings_found": row["listings_found"] or 0,
            "listings_new": row["listings_new"] or 0,
            "listings_updated": row["listings_updated"] or 0,
            "price_changes": row["price_changes"] or 0,
            "last_page_scraped": row["last_page_scraped"] or 0,
            "scraped_pages": set(scraped_pages),
            "started_at": row["started_at"],
        }

    # ── listings ─────────────────────────────────────────────────────────
    def save_listings(self, listings: list[dict], run_id: int) -> tuple[int, int, int]:
        """Save listings to database. Returns (new_count, updated_count, price_changes)."""
        if not listings:
            return 0, 0, 0

        now = datetime.now(timezone.utc)
        new_count = 0
        updated_count = 0
        price_changes = 0

        with self._db.cursor() as cur:
            for listing in listings:
                price_numeric = None
                price_str = listing.get("price", "")
                if price_str:
                    try:
                        price_numeric = int(
                            price_str.replace(",", "").replace("₪", "").replace(" ", "")
                        )
                    except ValueError:
                        pass

                date_added = None
                date_str = listing.get("date_added", "")
                if date_str:
                    try:
                        date_added = datetime.strptime(date_str[:19], "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        pass

                coords = listing.get("coordinates", {})
                lat = coords.get("latitude") if coords else None
                lon = coords.get("longitude") if coords else None

                cur.execute("SELECT id, price_numeric FROM listings WHERE id = %s", (listing["id"],))
                existing = cur.fetchone()

                if existing:
                    old_price = existing["price_numeric"]

                    if price_numeric is not None and old_price is not None and price_numeric != old_price:
                        cur.execute(
                            """
                            INSERT INTO price_history (listing_id, price, price_numeric, recorded_at, scrape_run_id)
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            (listing["id"], price_str, price_numeric, now, run_id),
                        )
                        price_changes += 1
                        logger.info(f"Price change for {listing['id']}: {old_price} -> {price_numeric}")

                    cur.execute(
                        """
                        UPDATE listings SET
                            price = %s,
                            price_numeric = %s,
                            updated_at = %s,
                            last_seen_at = %s,
                            is_active = TRUE,
                            raw_data = %s
                        WHERE id = %s
                        """,
                        (
                            listing.get("price"),
                            price_numeric,
                            listing.get("updated_at"),
                            now,
                            json.dumps(listing),
                            listing["id"],
                        ),
                    )
                    updated_count += 1
                else:
                    cur.execute(
                        """
                        INSERT INTO listings (
                            id, ad_number, link_token, street, property_type,
                            description_line, city, neighborhood, price, price_numeric,
                            currency, rooms, floor, size_sqm, date_added, updated_at,
                            contact_name, is_merchant, merchant_name, latitude, longitude,
                            image_url, images_count, amenities, raw_data, first_seen_at,
                            last_seen_at, is_active
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, TRUE
                        )
                        """,
                        (
                            listing["id"],
                            listing.get("ad_number"),
                            listing.get("link_token"),
                            listing.get("street"),
                            listing.get("property_type"),
                            listing.get("description_line"),
                            listing.get("city"),
                            listing.get("neighborhood"),
                            listing.get("price"),
                            price_numeric,
                            listing.get("currency"),
                            listing.get("rooms"),
                            listing.get("floor"),
                            listing.get("size_sqm"),
                            date_added,
                            listing.get("updated_at"),
                            listing.get("contact_name"),
                            listing.get("is_merchant", False),
                            listing.get("merchant_name"),
                            lat,
                            lon,
                            listing.get("image_url"),
                            listing.get("images_count", 0),
                            json.dumps(listing.get("amenities", {})),
                            json.dumps(listing),
                            now,
                            now,
                        ),
                    )
                    new_count += 1

                    if price_numeric is not None:
                        cur.execute(
                            """
                            INSERT INTO price_history (listing_id, price, price_numeric, recorded_at, scrape_run_id)
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            (listing["id"], price_str, price_numeric, now, run_id),
                        )

        return new_count, updated_count, price_changes

    def mark_inactive_listings_by_run(self, run_started_at, city_name: str = None) -> None:
        """Mark listings not seen in this scrape run as inactive.

        If city_name is given, only that city's listings are affected.
        """
        with self._db.cursor() as cur:
            if city_name:
                cur.execute(
                    """
                    UPDATE listings
                    SET is_active = FALSE
                    WHERE is_active = TRUE AND last_seen_at < %s AND city = %s
                    """,
                    (run_started_at, city_name),
                )
            else:
                cur.execute(
                    """
                    UPDATE listings
                    SET is_active = FALSE
                    WHERE is_active = TRUE AND last_seen_at < %s
                    """,
                    (run_started_at,),
                )
            affected = cur.rowcount

        if affected > 0:
            scope = f"city={city_name}" if city_name else "all cities"
            logger.info(f"Marked {affected} listings as inactive ({scope}, not seen since {run_started_at})")
