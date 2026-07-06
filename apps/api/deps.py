from functools import lru_cache

from packages.core.config import Settings, load_settings
from packages.core.queue import JobQueue
from packages.data.db import Database
from packages.data.repositories.analytics import AnalyticsRepository
from packages.data.repositories.listings import ListingsRepository
from packages.data.repositories.price_changes import PriceChangesRepository
from packages.data.repositories.runs import RunsRepository
from packages.data.repositories.stats import StatsRepository
from packages.data.repositories.subscriptions import SubscriptionsRepository


@lru_cache
def get_settings() -> Settings:
    return load_settings()


@lru_cache
def get_database() -> Database:
    settings = get_settings()
    return Database(settings.database_url)


def get_analytics_repo() -> AnalyticsRepository:
    return AnalyticsRepository(get_database())


def get_listings_repo() -> ListingsRepository:
    return ListingsRepository(get_database())


def get_runs_repo() -> RunsRepository:
    return RunsRepository(get_database())


def get_stats_repo() -> StatsRepository:
    return StatsRepository(get_database())


def get_price_changes_repo() -> PriceChangesRepository:
    return PriceChangesRepository(get_database())


def get_subscriptions_repo() -> SubscriptionsRepository:
    return SubscriptionsRepository(get_database())


@lru_cache
def get_job_queue() -> JobQueue:
    settings = get_settings()
    return JobQueue(settings.queue_url)
