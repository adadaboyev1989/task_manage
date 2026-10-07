from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from app import telegram_bot

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


@router.post("/webhook")
def webhook(update: dict, x_telegram_bot_api_secret_token: Optional[str] = Header(default=None)):
    if not telegram_bot.is_configured():
        raise HTTPException(status_code=404, detail="Topilmadi")
    if not x_telegram_bot_api_secret_token or x_telegram_bot_api_secret_token != telegram_bot.WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")

    try:
        telegram_bot.handle_update(update)
    except Exception as err:  # noqa: BLE001
        print(f"[telegram] webhook handle_update error: {err}")

    return {"ok": True}
