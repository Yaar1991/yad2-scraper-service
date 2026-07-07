import json
import logging
from typing import Optional

from curl_cffi import requests as curl_requests

from packages.scraper.session import Yad2Session

logger = logging.getLogger(__name__)

FEED_URL = "https://www.yad2.co.il/api/pre-load/getFeedIndex/realestate/rent"


class PageFetcher:
    """Fetches feed pages through a (rotating) Yad2Session."""

    def __init__(self, session: Yad2Session):
        self._session = session

    def fetch_page(self, page: int, city_code: str = None, min_rooms=None) -> Optional[dict]:
        """Fetch a single feed page via API, optionally filtered by city and min rooms."""
        params = {}
        if page > 1:
            params["page"] = str(page)
        if city_code:
            params["city"] = city_code
        if min_rooms is not None:
            params["rooms"] = str(int(min_rooms))
        headers = self._session.headers(is_api=True)

        try:
            resp = self._session.session.get(FEED_URL, params=params, headers=headers, timeout=20)
            self._session.requests_this_session += 1
        except Exception as e:
            logger.error(f"Page {page} request error: {e}")
            return None

        if self._session.is_blocked(resp):
            logger.warning(f"Page {page} BLOCKED (status={resp.status_code})")
            return None

        if resp.status_code != 200:
            logger.warning(f"Page {page} HTTP {resp.status_code}")
            return None

        try:
            return resp.json()
        except json.JSONDecodeError:
            logger.error(f"Page {page} invalid JSON")
            return None

    @staticmethod
    def get_total_pages(data: dict) -> int:
        feed = data.get("feed", {})
        total = feed.get("total_pages", 0)
        if total:
            return int(total)
        pag = data.get("pagination", {})
        return int(pag.get("last_page", 0))


def fetch_all_item_images(link_token: str) -> list[str]:
    """Fetch all image URLs for a listing from the Yad2 item API."""
    try:
        session = curl_requests.Session(impersonate="chrome131")
        session.get("https://www.yad2.co.il/", timeout=15)
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.yad2.co.il/realestate/rent",
            "Sec-Ch-Ua": '"Chromium";v="131", "Not_A Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
        r = session.get(f"https://www.yad2.co.il/api/item/{link_token}", headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json().get("images_urls") or []
    except Exception as e:
        logger.warning(f"fetch_all_item_images failed for {link_token}: {e}")
    return []
