import logging
import random
import time
from datetime import datetime, timezone

from packages.scraper.config import ScraperConfig
from packages.scraper.fetcher import PageFetcher
from packages.scraper.parser import extract_listings
from packages.scraper.persistence import ScrapeSink
from packages.scraper.session import Yad2Session

logger = logging.getLogger(__name__)


class Yad2Scraper:
    """Orchestrates session rotation, page fetching, parsing, and persistence."""

    def __init__(self, sink: ScrapeSink, config: ScraperConfig | None = None):
        self._sink = sink
        self._config = config or ScraperConfig()
        self._session = Yad2Session()
        self._fetcher = PageFetcher(self._session)

    def run_full_scrape(self, resume: dict = None) -> dict:
        """Scrape entire site with batch session rotation. Supports resume."""
        cfg = self._config
        if resume:
            run_id = resume["run_id"]
            pages_scraped = resume["pages_scraped"]
            pages_failed = resume["pages_failed"]
            total_new = resume["listings_new"]
            total_updated = resume["listings_updated"]
            total_price_changes = resume["price_changes"]
            total_listings_found = resume["listings_found"]
            scraped_pages = resume["scraped_pages"]
            total_pages = resume["total_pages"]
            run_started_at = resume["started_at"]
            logger.info(f"RESUMING full scrape run #{run_id} — {pages_scraped}/{total_pages} pages done, "
                        f"resuming from {len(scraped_pages)} completed pages")
        else:
            run_id = self._sink.start_scrape_run(run_type="full")
            pages_scraped = 0
            pages_failed = 0
            total_new = 0
            total_updated = 0
            total_price_changes = 0
            total_listings_found = 0
            scraped_pages = set()
            total_pages = 0
            run_started_at = datetime.now(timezone.utc)
            logger.info(f"Starting FULL scrape run #{run_id}")

        try:
            if not self._session.new_session():
                raise Exception("Cannot create initial session")
            time.sleep(random.uniform(2, 4))

            if total_pages == 0:
                data = self._fetcher.fetch_page(1)
                if not data:
                    raise Exception("Cannot fetch page 1")

                listings = extract_listings(data)
                pages_scraped += 1
                scraped_pages.add(1)
                total_listings_found += len(listings)

                total_pages = self._fetcher.get_total_pages(data)
                logger.info(f"Page 1: {len(listings)} listings, total pages: {total_pages}")

                new, updated, price_changes = self._sink.save_listings(listings, run_id)
                total_new += new
                total_updated += updated
                total_price_changes += price_changes

                self._sink.update_scrape_progress(run_id, pages_scraped, pages_failed,
                                                  total_listings_found, total_new, total_updated,
                                                  total_price_changes, 1, scraped_pages, total_pages)

            remaining = [p for p in range(1, total_pages + 1) if p not in scraped_pages]
            random.shuffle(remaining)
            logger.info(f"Pages remaining: {len(remaining)}/{total_pages}")
            attempt = 0

            while remaining and attempt < cfg.max_retries:
                attempt += 1
                if attempt > 1:
                    logger.info(f"Retry round {attempt}, {len(remaining)} pages remaining")
                    random.shuffle(remaining)

                batches = [remaining[i:i + cfg.pages_per_session]
                           for i in range(0, len(remaining), cfg.pages_per_session)]
                next_remaining = []

                for batch_idx, batch in enumerate(batches):
                    if batch_idx > 0 or attempt > 1:
                        cooldown = random.uniform(*cfg.delay_between_batches)
                        logger.info(f"Cooldown {cooldown:.0f}s before batch {batch_idx+1}/{len(batches)}")
                        time.sleep(cooldown)

                    if not self._session.new_session():
                        logger.warning("Session creation failed, retry later")
                        next_remaining.extend(batch)
                        continue

                    time.sleep(random.uniform(2, 4))
                    batch_blocked = False

                    for page in batch:
                        if batch_blocked:
                            next_remaining.append(page)
                            continue

                        delay = random.uniform(*cfg.delay_within_batch)
                        time.sleep(delay)

                        page_data = self._fetcher.fetch_page(page)

                        if page_data is None:
                            next_remaining.append(page)
                            batch_blocked = True
                            pages_failed += 1
                            continue

                        page_listings = extract_listings(page_data)
                        pages_scraped += 1
                        scraped_pages.add(page)
                        total_listings_found += len(page_listings)

                        new, updated, price_changes = self._sink.save_listings(page_listings, run_id)
                        total_new += new
                        total_updated += updated
                        total_price_changes += price_changes

                        self._sink.update_scrape_progress(run_id, pages_scraped, pages_failed,
                                                          total_listings_found, total_new, total_updated,
                                                          total_price_changes, page, scraped_pages)

                        logger.info(f"Page {page}: {len(page_listings)} listings "
                                    f"(scraped: {pages_scraped}/{total_pages}, new: {new}, updated: {updated}, price_changes: {price_changes})")

                remaining = next_remaining

            final_failed = len(remaining)

            success_rate = pages_scraped / total_pages if total_pages > 0 else 0
            if success_rate >= 0.8:
                self._sink.mark_inactive_listings_by_run(run_started_at)
            else:
                logger.warning(f"Skipping mark_inactive: only scraped {pages_scraped}/{total_pages} "
                               f"pages ({success_rate:.0%}), need >= 80%")
            self._sink.finish_scrape_run(
                run_id, total_pages, pages_scraped, final_failed,
                total_listings_found, total_new, total_updated, total_price_changes, "completed"
            )

            logger.info(f"Full scrape #{run_id} completed: "
                        f"{pages_scraped}/{total_pages} pages, {total_new} new, {total_updated} updated, {total_price_changes} price changes")

            return {
                "run_id": run_id,
                "total_pages": total_pages,
                "pages_scraped": pages_scraped,
                "pages_failed": final_failed,
                "listings_new": total_new,
                "listings_updated": total_updated,
                "price_changes": total_price_changes,
                "status": "completed",
                "run_type": "full",
            }

        except Exception as e:
            logger.error(f"Full scrape failed: {e}")
            self._sink.finish_scrape_run(run_id, total_pages, pages_scraped, pages_failed,
                                         total_listings_found, total_new, total_updated,
                                         total_price_changes, "failed", str(e))
            raise

    def run_smart_scrape(self, resume: dict = None) -> dict:
        """Smart scrape: scrape pages sequentially, stop when no new listings found."""
        cfg = self._config
        if resume:
            run_id = resume["run_id"]
            pages_scraped = resume["pages_scraped"]
            pages_failed = resume["pages_failed"]
            total_new = resume["listings_new"]
            total_updated = resume["listings_updated"]
            total_price_changes = resume["price_changes"]
            total_listings_found = resume["listings_found"]
            start_page = resume["last_page_scraped"] + 1
            total_pages = resume["total_pages"]
            consecutive_no_new = 0
            scraped_pages = resume["scraped_pages"]
            logger.info(f"RESUMING smart scrape run #{run_id} — continuing from page {start_page}")
        else:
            run_id = self._sink.start_scrape_run(run_type="smart")
            pages_scraped = 0
            pages_failed = 0
            total_new = 0
            total_updated = 0
            total_price_changes = 0
            total_listings_found = 0
            consecutive_no_new = 0
            start_page = 1
            total_pages = 0
            scraped_pages = set()
            logger.info(f"Starting SMART scrape run #{run_id} (stop after {cfg.smart_stop_threshold} pages with no new listings)")

        try:
            if not self._session.new_session():
                raise Exception("Cannot create initial session")
            time.sleep(random.uniform(2, 4))

            if start_page == 1:
                data = self._fetcher.fetch_page(1)
                if not data:
                    raise Exception("Cannot fetch page 1")

                listings = extract_listings(data)
                pages_scraped += 1
                total_listings_found += len(listings)
                scraped_pages.add(1)

                total_pages = self._fetcher.get_total_pages(data)
                logger.info(f"Smart scrape page 1: {len(listings)} listings, total pages available: {total_pages}")

                new, updated, price_changes = self._sink.save_listings(listings, run_id)
                total_new += new
                total_updated += updated
                total_price_changes += price_changes

                if new == 0:
                    consecutive_no_new += 1
                else:
                    consecutive_no_new = 0

                self._sink.update_scrape_progress(run_id, pages_scraped, pages_failed,
                                                  total_listings_found, total_new, total_updated,
                                                  total_price_changes, 1, scraped_pages, total_pages)
                start_page = 2

            if total_pages == 0:
                data = self._fetcher.fetch_page(1)
                if data:
                    total_pages = self._fetcher.get_total_pages(data)
                else:
                    raise Exception("Cannot determine total pages")

            page = start_page
            while page <= total_pages:
                if consecutive_no_new >= cfg.smart_stop_threshold:
                    logger.info(f"Smart scrape stopping: {cfg.smart_stop_threshold} consecutive pages with no new listings (at page {page})")
                    break

                if self._session.requests_this_session >= cfg.pages_per_session:
                    cooldown = random.uniform(*cfg.delay_between_batches)
                    logger.info(f"Session rotation cooldown {cooldown:.0f}s")
                    time.sleep(cooldown)

                    if not self._session.new_session():
                        logger.warning("Session creation failed, waiting and retrying...")
                        time.sleep(random.uniform(30, 60))
                        if not self._session.new_session():
                            pages_failed += 1
                            page += 1
                            continue
                    time.sleep(random.uniform(2, 4))

                delay = random.uniform(*cfg.delay_within_batch)
                time.sleep(delay)

                page_data = self._fetcher.fetch_page(page)

                if page_data is None:
                    pages_failed += 1
                    logger.warning(f"Smart scrape page {page} failed, rotating session")
                    time.sleep(random.uniform(*cfg.delay_between_batches))
                    if self._session.new_session():
                        time.sleep(random.uniform(2, 4))
                        page_data = self._fetcher.fetch_page(page)

                    if page_data is None:
                        page += 1
                        continue

                page_listings = extract_listings(page_data)
                pages_scraped += 1
                total_listings_found += len(page_listings)
                scraped_pages.add(page)

                new, updated, price_changes = self._sink.save_listings(page_listings, run_id)
                total_new += new
                total_updated += updated
                total_price_changes += price_changes

                if new == 0:
                    consecutive_no_new += 1
                else:
                    consecutive_no_new = 0

                self._sink.update_scrape_progress(run_id, pages_scraped, pages_failed,
                                                  total_listings_found, total_new, total_updated,
                                                  total_price_changes, page, scraped_pages)

                logger.info(f"Smart page {page}: {len(page_listings)} listings "
                            f"(new: {new}, updated: {updated}, consecutive_no_new: {consecutive_no_new}/{cfg.smart_stop_threshold})")

                page += 1

            self._sink.finish_scrape_run(
                run_id, total_pages, pages_scraped, pages_failed,
                total_listings_found, total_new, total_updated,
                total_price_changes, "completed"
            )

            logger.info(f"Smart scrape #{run_id} completed: {pages_scraped}/{total_pages} pages, "
                        f"{total_listings_found} listings seen, {total_new} new, "
                        f"{total_updated} updated, {total_price_changes} price changes")

            return {
                "run_id": run_id,
                "total_pages": total_pages,
                "pages_scraped": pages_scraped,
                "pages_failed": pages_failed,
                "listings_found": total_listings_found,
                "listings_new": total_new,
                "listings_updated": total_updated,
                "price_changes": total_price_changes,
                "status": "completed",
                "run_type": "smart",
            }

        except Exception as e:
            logger.error(f"Smart scrape failed: {e}")
            self._sink.finish_scrape_run(run_id, total_pages, pages_scraped, pages_failed,
                                         total_listings_found, total_new, total_updated,
                                         total_price_changes, "failed", str(e))
            raise

    def run_city_scrape(self, city_name: str, city_code: str, min_rooms=None) -> dict:
        """Scrape all rental listings for one city only."""
        cfg = self._config
        run_id = self._sink.start_scrape_run(run_type=f"city:{city_name}")
        pages_scraped = 0
        pages_failed = 0
        total_new = 0
        total_updated = 0
        total_price_changes = 0
        total_listings_found = 0
        scraped_pages: set = set()
        total_pages = 0
        run_started_at = datetime.now(timezone.utc)

        rooms_label = f", min_rooms={int(min_rooms)}" if min_rooms else ""
        logger.info(f"Starting city scrape: {city_name} (code={city_code}{rooms_label}), run #{run_id}")

        try:
            if not self._session.new_session():
                raise Exception("Cannot create initial session")
            time.sleep(random.uniform(2, 4))

            data = self._fetcher.fetch_page(1, city_code=city_code, min_rooms=min_rooms)
            if not data:
                raise Exception(f"Cannot fetch page 1 for city {city_name}")

            listings = extract_listings(data)
            pages_scraped += 1
            scraped_pages.add(1)
            total_listings_found += len(listings)
            total_pages = self._fetcher.get_total_pages(data)
            logger.info(f"{city_name}: page 1 → {len(listings)} listings, total pages={total_pages}")

            new, updated, price_changes = self._sink.save_listings(listings, run_id)
            total_new += new
            total_updated += updated
            total_price_changes += price_changes

            self._sink.update_scrape_progress(run_id, pages_scraped, pages_failed,
                                              total_listings_found, total_new, total_updated,
                                              total_price_changes, 1, scraped_pages, total_pages)

            remaining = list(range(2, total_pages + 1))
            random.shuffle(remaining)
            attempt = 0

            while remaining and attempt < cfg.max_retries:
                attempt += 1
                if attempt > 1:
                    random.shuffle(remaining)

                batches = [remaining[i:i + cfg.pages_per_session]
                           for i in range(0, len(remaining), cfg.pages_per_session)]
                next_remaining = []

                for batch_idx, batch in enumerate(batches):
                    if batch_idx > 0 or attempt > 1:
                        cooldown = random.uniform(*cfg.delay_between_batches)
                        logger.info(f"{city_name}: cooldown {cooldown:.0f}s before batch {batch_idx+1}/{len(batches)}")
                        time.sleep(cooldown)

                    if not self._session.new_session():
                        next_remaining.extend(batch)
                        continue

                    time.sleep(random.uniform(2, 4))
                    batch_blocked = False

                    for page in batch:
                        if batch_blocked:
                            next_remaining.append(page)
                            continue

                        time.sleep(random.uniform(*cfg.delay_within_batch))
                        page_data = self._fetcher.fetch_page(page, city_code=city_code, min_rooms=min_rooms)

                        if page_data is None:
                            next_remaining.append(page)
                            batch_blocked = True
                            pages_failed += 1
                            continue

                        page_listings = extract_listings(page_data)
                        pages_scraped += 1
                        scraped_pages.add(page)
                        total_listings_found += len(page_listings)

                        new, updated, price_changes = self._sink.save_listings(page_listings, run_id)
                        total_new += new
                        total_updated += updated
                        total_price_changes += price_changes

                        self._sink.update_scrape_progress(run_id, pages_scraped, pages_failed,
                                                          total_listings_found, total_new, total_updated,
                                                          total_price_changes, page, scraped_pages)

                        logger.info(f"{city_name} page {page}/{total_pages}: "
                                    f"{len(page_listings)} listings (new={new}, updated={updated})")

                remaining = next_remaining

            success_rate = pages_scraped / total_pages if total_pages > 0 else 0
            if success_rate >= 0.8:
                self._sink.mark_inactive_listings_by_run(run_started_at, city_name=city_name)
            else:
                logger.warning(f"{city_name}: skipping mark_inactive, only {pages_scraped}/{total_pages} pages scraped")

            self._sink.finish_scrape_run(run_id, total_pages, pages_scraped, len(remaining),
                                         total_listings_found, total_new, total_updated,
                                         total_price_changes, "completed")

            logger.info(f"{city_name} scrape #{run_id} done: {pages_scraped}/{total_pages} pages, "
                        f"{total_new} new, {total_updated} updated, {total_price_changes} price changes")

            return {
                "run_id": run_id,
                "city": city_name,
                "city_code": city_code,
                "total_pages": total_pages,
                "pages_scraped": pages_scraped,
                "pages_failed": len(remaining),
                "listings_found": total_listings_found,
                "listings_new": total_new,
                "listings_updated": total_updated,
                "price_changes": total_price_changes,
                "status": "completed",
                "run_type": f"city:{city_name}",
            }

        except Exception as e:
            logger.error(f"{city_name} scrape failed: {e}")
            self._sink.finish_scrape_run(run_id, total_pages, pages_scraped, pages_failed,
                                         total_listings_found, total_new, total_updated,
                                         total_price_changes, "failed", str(e))
            raise
