import logging
import random

from curl_cffi import requests as curl_requests

from packages.scraper.config import BROWSER_PROFILES

logger = logging.getLogger(__name__)

_SEC_CH_PLATFORM = {"Windows": '"Windows"', "Mac": '"macOS"', "Linux": '"Linux"'}


class Yad2Session:
    """Owns a curl_cffi session with browser impersonation and rotation."""

    def __init__(self):
        self.session = None
        self.current_platform = "Windows"
        self.requests_this_session = 0

    def new_session(self) -> bool:
        """Create a fresh impersonated session and warm it against the homepage."""
        self.close()

        profile, platform = random.choice(BROWSER_PROFILES)
        self.session = curl_requests.Session(impersonate=profile)
        self.current_platform = platform
        self.requests_this_session = 0

        headers = self.headers(is_api=False)
        try:
            resp = self.session.get("https://www.yad2.co.il/", headers=headers, timeout=20)
            self.requests_this_session += 1
            cookies = list(self.session.cookies.keys())
            logger.info(f"New session: {profile}/{platform}, cookies={cookies}")
            return not self.is_blocked(resp)
        except Exception as e:
            logger.error(f"Session creation failed: {e}")
            return False

    def headers(self, is_api: bool = False, platform: str = None) -> dict:
        plat = _SEC_CH_PLATFORM.get(platform or self.current_platform, '"Windows"')

        if is_api:
            return {
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Referer": "https://www.yad2.co.il/realestate/rent",
                "Sec-Ch-Ua": '"Chromium";v="131", "Not_A Brand";v="24"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": plat,
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            }
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Ch-Ua": '"Chromium";v="131", "Not_A Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": plat,
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }

    @staticmethod
    def is_blocked(resp) -> bool:
        if resp.status_code in (403, 429, 503):
            return True
        text_lower = resp.text[:5000].lower()
        if "shieldsquare captcha" in text_lower:
            return True
        if len(resp.text) < 30000 and "access denied" in text_lower:
            return True
        return False

    def close(self) -> None:
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass
