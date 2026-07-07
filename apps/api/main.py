from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.deps import get_database, get_settings
from apps.api.routers.analytics import router as analytics_router
from apps.api.routers.dashboard import router as dashboard_router
from apps.api.routers.health import router as health_router
from apps.api.routers.listings import router as listings_router
from apps.api.routers.metadata import router as metadata_router
from apps.api.routers.price_changes import router as price_changes_router
from apps.api.routers.runs import router as runs_router
from apps.api.routers.stats import router as stats_router
from apps.api.routers.subscriptions import router as subscriptions_router
from apps.api.routers.telegram import router as telegram_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    get_database().close()


settings = get_settings()

app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard_router)
app.include_router(health_router)
app.include_router(analytics_router)
app.include_router(listings_router)
app.include_router(stats_router)
app.include_router(runs_router)
app.include_router(metadata_router)
app.include_router(price_changes_router)
app.include_router(subscriptions_router)
app.include_router(telegram_router)
