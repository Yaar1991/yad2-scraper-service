import urllib.parse
import urllib.request

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from apps.api.deps import get_settings
from packages.core.config import Settings

router = APIRouter(prefix="", tags=["telegram"])


@router.get("/telegram/status")
def telegram_status(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "configured": bool(settings.telegram_bot_token and settings.telegram_chat_id),
        "min_drop_percent": settings.telegram_min_drop_percent,
    }


@router.post("/telegram/test", response_model=None)
def telegram_test(settings: Settings = Depends(get_settings)):
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return JSONResponse(
            status_code=400,
            content={"error": "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars not set"},
        )

    try:
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        data = urllib.parse.urlencode(
            {
                "chat_id": settings.telegram_chat_id,
                "text": "Yad2 Scraper: Test notification - Telegram is configured correctly!",
                "parse_mode": "HTML",
            }
        ).encode()
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=10)
        return {"success": True, "message": "Test message sent"}
    except Exception:
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to send Telegram message. Check bot token and chat ID."},
        )
