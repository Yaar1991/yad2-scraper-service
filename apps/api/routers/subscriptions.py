from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from apps.api.deps import get_subscriptions_repo
from packages.data.repositories.subscriptions import SubscriptionsRepository

router = APIRouter(prefix="", tags=["subscriptions"])


class AlertSubscribeBody(BaseModel):
    chat_id: str
    city: str | None = None
    neighborhood: str | None = None
    max_price: int | None = Field(default=None, alias="maxPrice")
    min_rooms: float | None = Field(default=None, alias="minRooms")
    label: str = ""
    notify_new: bool = True
    notify_price_drop: bool = True

    model_config = {"populate_by_name": True}


class CitySubscribeBody(BaseModel):
    city_name: str
    city_code: str
    min_rooms: float | None = None


@router.get("/alerts/subscriptions", response_model=None)
def list_subscriptions(
    chat_id: str | None = None,
    repo: SubscriptionsRepository = Depends(get_subscriptions_repo),
):
    if not chat_id:
        return JSONResponse(status_code=400, content={"error": "chat_id required"})
    try:
        return repo.list_alert_subscriptions(chat_id)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/alerts/subscribe", response_model=None)
def subscribe_alert(
    body: AlertSubscribeBody,
    repo: SubscriptionsRepository = Depends(get_subscriptions_repo),
):
    max_price = body.max_price
    min_rooms = body.min_rooms

    if not any([body.city, body.neighborhood, max_price, min_rooms]):
        return JSONResponse(status_code=400, content={"error": "At least one filter required"})

    try:
        return repo.create_alert_subscription(
            chat_id=body.chat_id,
            city=body.city,
            neighborhood=body.neighborhood,
            max_price=max_price,
            min_rooms=min_rooms,
            label=body.label,
            notify_new=body.notify_new,
            notify_price_drop=body.notify_price_drop,
        )
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.delete("/alerts/subscriptions/{sub_id}", response_model=None)
def unsubscribe_alert(
    sub_id: int,
    repo: SubscriptionsRepository = Depends(get_subscriptions_repo),
):
    try:
        if not repo.delete_alert_subscription(sub_id):
            return JSONResponse(status_code=404, content={"error": "Subscription not found"})
        return {"message": "Unsubscribed", "id": sub_id}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/cities/subscriptions", response_model=None)
def list_city_subscriptions(
    repo: SubscriptionsRepository = Depends(get_subscriptions_repo),
):
    try:
        return {"cities": repo.list_city_subscriptions()}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/cities/subscriptions", status_code=201, response_model=None)
def add_city_subscription(
    body: CitySubscribeBody,
    repo: SubscriptionsRepository = Depends(get_subscriptions_repo),
):
    city_name = body.city_name.strip()
    city_code = str(body.city_code).strip()
    if not city_name or not city_code:
        return JSONResponse(
            status_code=400,
            content={"error": "city_name and city_code are required"},
        )

    try:
        city = repo.add_city_subscription(city_name, city_code, body.min_rooms)
        return {"message": "City added", "city": city}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.delete("/cities/subscriptions/{city_name:path}", response_model=None)
def remove_city_subscription(
    city_name: str,
    repo: SubscriptionsRepository = Depends(get_subscriptions_repo),
):
    try:
        if not repo.remove_city_subscription(city_name):
            return JSONResponse(status_code=404, content={"error": "City not found"})
        return {"message": f"City '{city_name}' deactivated"}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})
