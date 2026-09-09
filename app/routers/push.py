from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import push as push_module
from app.deps import get_current_user

router = APIRouter(prefix="/api/push", tags=["push"])


class SubscribeBody(BaseModel):
    subscription: dict


class UnsubscribeBody(BaseModel):
    endpoint: Optional[str] = None


@router.get("/public-key")
def public_key():
    return {"publicKey": push_module.public_key(), "configured": push_module.is_configured()}


@router.post("/subscribe")
def subscribe(body: SubscribeBody, current_user: dict = Depends(get_current_user)):
    sub = body.subscription
    if not sub.get("endpoint") or not sub.get("keys"):
        raise HTTPException(status_code=400, detail="Noto'g'ri obuna ma'lumoti")
    push_module.save_subscription(current_user["id"], sub)
    return {"ok": True}


@router.post("/unsubscribe")
def unsubscribe(body: UnsubscribeBody, current_user: dict = Depends(get_current_user)):
    if body.endpoint:
        push_module.remove_subscription(body.endpoint)
    return {"ok": True}
