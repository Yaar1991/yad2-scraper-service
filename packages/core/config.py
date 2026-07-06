import os
from dataclasses import dataclass


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    database_url: str
    queue_url: str
    scrape_interval_seconds: int
    pages_per_session: int
    telegram_bot_token: str
    telegram_chat_id: str
    telegram_min_drop_percent: float


def load_settings() -> Settings:
    app_env = os.getenv("APP_ENV", "development")
    queue_url = os.getenv("QUEUE_URL", "redis://redis:6379/0")
    scrape_interval_seconds = int(os.getenv("SCRAPE_INTERVAL_SECONDS", "3600"))
    pages_per_session = int(os.getenv("PAGES_PER_SESSION", "5"))
    try:
        telegram_min_drop_percent = float(os.getenv("TELEGRAM_MIN_DROP_PERCENT", "5"))
    except (ValueError, TypeError):
        telegram_min_drop_percent = 5.0
    return Settings(
        app_name=os.getenv("APP_NAME", "yad2-scraper-service"),
        app_env=app_env,
        database_url=_required("DATABASE_URL"),
        queue_url=queue_url,
        scrape_interval_seconds=scrape_interval_seconds,
        pages_per_session=pages_per_session,
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        telegram_min_drop_percent=telegram_min_drop_percent,
    )
