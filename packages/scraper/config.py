import os
from dataclasses import dataclass

# Browser profiles for curl_cffi impersonation rotation.
BROWSER_PROFILES: list[tuple[str, str]] = [
    ("chrome131", "Windows"),
    ("chrome131", "Mac"),
    ("chrome124", "Linux"),
    ("firefox133", "Windows"),
]


@dataclass(frozen=True)
class ScraperConfig:
    """Tuning knobs for the scraping engine (session rotation, delays, retries)."""

    pages_per_session: int = 5
    max_retries: int = 3
    smart_stop_threshold: int = 10
    full_scrape_every: int = 6
    delay_within_batch: tuple[int, int] = (3, 6)
    delay_between_batches: tuple[int, int] = (12, 25)

    @classmethod
    def from_env(cls) -> "ScraperConfig":
        return cls(
            pages_per_session=int(os.getenv("PAGES_PER_SESSION", "5")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            smart_stop_threshold=int(os.getenv("SMART_STOP_THRESHOLD", "10")),
            full_scrape_every=int(os.getenv("FULL_SCRAPE_EVERY", "6")),
        )
