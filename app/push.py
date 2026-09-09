import json

from pywebpush import WebPushException, webpush

from app.config import VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY, VAPID_SUBJECT
from app.db import get_db

_configured = bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY)

if not _configured:
    print("[push] VAPID keys not set — web push notifications disabled. Run scripts/generate_vapid.py.")


def is_configured() -> bool:
    return _configured


def public_key() -> str:
    return VAPID_PUBLIC_KEY


def save_subscription(user_id: int, subscription: dict):
    db = get_db()
    keys = subscription.get("keys", {})
    db.execute(
        """INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth) VALUES (?, ?, ?, ?)
           ON CONFLICT(endpoint) DO UPDATE SET user_id = excluded.user_id, p256dh = excluded.p256dh, auth = excluded.auth""",
        (user_id, subscription["endpoint"], keys.get("p256dh"), keys.get("auth")),
    )
    db.commit()


def remove_subscription(endpoint: str):
    db = get_db()
    db.execute("DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,))
    db.commit()


def notify_user(user_id: int, payload: dict):
    if not _configured:
        return
    db = get_db()
    subs = db.execute("SELECT * FROM push_subscriptions WHERE user_id = ?", (user_id,)).fetchall()
    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub["endpoint"],
                    "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
                },
                data=json.dumps(payload),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_SUBJECT},
            )
        except WebPushException as err:
            status_code = err.response.status_code if err.response is not None else None
            if status_code in (404, 410):
                remove_subscription(sub["endpoint"])
            else:
                print(f"[push] send failed: {err}")
