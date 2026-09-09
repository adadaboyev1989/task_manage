import html
import threading
import time
import uuid
from pathlib import Path

import requests

from app.config import APP_URL, BOT_TOKEN, BOT_USERNAME, UPLOAD_DIR
from app.datetime_utils import format_datetime_uz
from app.db import get_db

API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"
FILE_BASE = f"https://api.telegram.org/file/bot{BOT_TOKEN}"

_offset = 0
_running = False


def is_configured() -> bool:
    return bool(BOT_TOKEN)


def _api_call(method: str, params: dict | None = None) -> dict:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured")
    res = requests.post(f"{API_BASE}/{method}", json=params or {}, timeout=35)
    data = res.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error ({method}): {data.get('description')}")
    return data["result"]


def send_message(chat_id, text: str, extra: dict | None = None):
    if not is_configured() or not chat_id:
        return None
    try:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if extra:
            payload.update(extra)
        return _api_call("sendMessage", payload)
    except Exception as err:  # noqa: BLE001
        print(f"[telegram] sendMessage failed: {err}")
        return None


def login_deep_link(token: str) -> str | None:
    if not BOT_USERNAME:
        return None
    return f"https://t.me/{BOT_USERNAME}?start=login-{token}"


def attach_deep_link(task_id: int) -> str | None:
    if not BOT_USERNAME:
        return None
    return f"https://t.me/{BOT_USERNAME}?start=attach-{task_id}"


def _find_user_by_chat_id(chat_id):
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE telegram_chat_id = ?", (str(chat_id),)).fetchone()
    return dict(row) if row else None


def _priority_label(task_type: str) -> str:
    return "🔴 Ijrosi nazoratda" if task_type == "control" else "ℹ️ Ma'lumot uchun"


def notify_new_task(user: dict, task: dict, org: dict):
    if not user.get("telegram_chat_id"):
        return
    lines = ["<b>🆕 Yangi topshiriq</b>", _priority_label(task["type"]), "", f"<b>{html.escape(task['title'])}</b>"]
    if task.get("description"):
        lines.append(html.escape(task["description"]))
    if task.get("deadline_at"):
        lines += ["", f"⏰ Muddat: {format_datetime_uz(task['deadline_at'])}"]
    lines += ["", f"Tashkilot: {html.escape(org['name'])}"]

    send_message(
        user["telegram_chat_id"],
        "\n".join(lines),
        {"reply_markup": {"inline_keyboard": [[{"text": "📋 Saytda ochish", "url": f"{APP_URL}/#/task/{task['id']}"}]]}},
    )


def _extract_file_meta(message: dict) -> dict | None:
    if message.get("document"):
        doc = message["document"]
        return {
            "file_id": doc["file_id"],
            "file_name": doc.get("file_name") or f"document_{doc['file_unique_id']}",
            "mime_type": doc.get("mime_type") or "application/octet-stream",
            "file_size": doc.get("file_size"),
        }
    if message.get("photo"):
        largest = message["photo"][-1]
        return {
            "file_id": largest["file_id"],
            "file_name": f"photo_{largest['file_unique_id']}.jpg",
            "mime_type": "image/jpeg",
            "file_size": largest.get("file_size"),
        }
    if message.get("video"):
        vid = message["video"]
        return {
            "file_id": vid["file_id"],
            "file_name": vid.get("file_name") or f"video_{vid['file_unique_id']}.mp4",
            "mime_type": vid.get("mime_type") or "video/mp4",
            "file_size": vid.get("file_size"),
        }
    if message.get("audio"):
        audio = message["audio"]
        return {
            "file_id": audio["file_id"],
            "file_name": audio.get("file_name") or f"audio_{audio['file_unique_id']}",
            "mime_type": audio.get("mime_type") or "audio/mpeg",
            "file_size": audio.get("file_size"),
        }
    if message.get("voice"):
        voice = message["voice"]
        return {
            "file_id": voice["file_id"],
            "file_name": f"voice_{voice['file_unique_id']}.ogg",
            "mime_type": voice.get("mime_type") or "audio/ogg",
            "file_size": voice.get("file_size"),
        }
    return None


def _download_telegram_file(file_id: str, dest_name: str) -> tuple[str, int]:
    file_info = _api_call("getFile", {"file_id": file_id})
    res = requests.get(f"{FILE_BASE}/{file_info['file_path']}", timeout=60)
    if res.status_code != 200:
        raise RuntimeError(f"File download failed: {res.status_code}")
    ext = Path(file_info["file_path"]).suffix or Path(dest_name).suffix or ""
    stored_name = f"{uuid.uuid4()}{ext}"
    (UPLOAD_DIR / stored_name).write_bytes(res.content)
    return stored_name, len(res.content)


def _active_forward_session(chat_id):
    db = get_db()
    row = db.execute(
        "SELECT * FROM forward_sessions WHERE chat_id = ? AND expires_at > datetime('now') ORDER BY id DESC LIMIT 1",
        (str(chat_id),),
    ).fetchone()
    return dict(row) if row else None


def _handle_attach_to_session(session: dict, message: dict, user: dict):
    db = get_db()
    meta = _extract_file_meta(message)
    try:
        if meta:
            stored_name, size = _download_telegram_file(meta["file_id"], meta["file_name"])
            db.execute(
                """INSERT INTO attachments (task_id, original_name, stored_name, mime_type, size, source, telegram_file_id, uploaded_by)
                   VALUES (?, ?, ?, ?, ?, 'telegram', ?, ?)""",
                (
                    session["task_id"],
                    meta["file_name"],
                    stored_name,
                    meta["mime_type"],
                    size or meta.get("file_size") or 0,
                    meta["file_id"],
                    user["id"],
                ),
            )
            db.commit()
            send_message(
                session["chat_id"],
                f"📎 Fayl biriktirildi: <b>{html.escape(meta['file_name'])}</b>\nYana fayl yuborishingiz mumkin yoki /done buyrug'i bilan yakunlang.",
            )
        elif message.get("text"):
            db.execute(
                """INSERT INTO attachments (task_id, original_name, source, text_content, uploaded_by)
                   VALUES (?, 'Telegram xabar', 'telegram', ?, ?)""",
                (session["task_id"], message["text"], user["id"]),
            )
            db.commit()
            send_message(
                session["chat_id"],
                "📝 Matn topshiriqqa biriktirildi.\nYana yuborishingiz mumkin yoki /done buyrug'i bilan yakunlang.",
            )
    except Exception as err:  # noqa: BLE001
        print(f"[telegram] attach failed: {err}")
        send_message(session["chat_id"], "❌ Faylni biriktirishda xatolik yuz berdi.")


def _not_registered_message(chat_id):
    return send_message(
        chat_id,
        f"⚠️ Siz tizimda ro'yxatdan o'tmagansiz.\n\nSizning Telegram ID'ingiz: <code>{chat_id}</code>\n\n"
        "Ushbu ID'ni administratorga yuboring — u sizni tizimga admin panel orqali qo'shadi. "
        "Shundan so'ng shu botga qayta /start yozing.",
    )


def _handle_start_payload(chat_id, payload: str, user: dict | None):
    db = get_db()

    if payload.startswith("login-"):
        token = payload[len("login-") :]
        if not user:
            return _not_registered_message(chat_id)

        row = db.execute(
            "SELECT * FROM login_tokens WHERE token = ? AND status = 'pending' AND expires_at > datetime('now')",
            (token,),
        ).fetchone()
        if not row:
            return send_message(chat_id, "❌ Kirish havolasi eskirgan. Saytda qaytadan urinib ko'ring.")

        db.execute("UPDATE login_tokens SET status = 'verified', user_id = ? WHERE token = ?", (user["id"], token))
        db.commit()
        return send_message(
            chat_id,
            f"✅ Tizimga kirish tasdiqlandi.\nXush kelibsiz, <b>{html.escape(user['full_name'])}</b>! "
            "Saytga qaytib, kirishni davom eting.",
        )

    if payload.startswith("attach-"):
        try:
            task_id = int(payload[len("attach-") :])
        except ValueError:
            return send_message(chat_id, "❌ Topshiriq topilmadi.")

        if not user:
            return _not_registered_message(chat_id)

        task_row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not task_row:
            return send_message(chat_id, "❌ Topshiriq topilmadi.")
        task = dict(task_row)

        if user["role"] == "director":
            owns = db.execute(
                "SELECT 1 FROM task_targets WHERE task_id = ? AND org_id = ?", (task_id, user["org_id"])
            ).fetchone()
            if not owns:
                return send_message(chat_id, "❌ Bu topshiriq sizning tashkilotingizga tegishli emas.")
        elif user["role"] not in ("department", "admin"):
            return send_message(chat_id, "❌ Ruxsat yo'q.")

        db.execute(
            "INSERT INTO forward_sessions (task_id, chat_id, user_id, expires_at) VALUES (?, ?, ?, datetime('now', '+10 minutes'))",
            (task_id, str(chat_id), user["id"]),
        )
        db.commit()
        return send_message(
            chat_id,
            f"📎 \"<b>{html.escape(task['title'])}</b>\" topshirig'iga fayl yoki xabar biriktirish rejimi yoqildi.\n\n"
            "Endi kerakli xabarni forward qiling yoki fayl yuboring (10 daqiqa ichida). Tugatgach /done deb yozing.",
        )

    return send_message(chat_id, "Noma'lum havola.")


def _handle_update(update: dict):
    message = update.get("message")
    if not message:
        return
    chat_id = message["chat"]["id"]
    user = _find_user_by_chat_id(chat_id)
    text = message.get("text", "") or ""
    db = get_db()

    if user and message.get("from", {}).get("username") and message["from"]["username"] != user.get("telegram_username"):
        db.execute("UPDATE users SET telegram_username = ? WHERE id = ?", (message["from"]["username"], user["id"]))
        db.commit()

    if text.startswith("/start"):
        parts = text.split(" ", 1)
        payload = parts[1].strip() if len(parts) > 1 else ""
        if not payload:
            if user:
                return send_message(
                    chat_id,
                    f"Salom, <b>{html.escape(user['full_name'])}</b>! Siz tizimga ulangansiz. "
                    'Saytda "Telegram orqali kirish" tugmasini bosing.',
                )
            return _not_registered_message(chat_id)
        return _handle_start_payload(chat_id, payload, user)

    if text == "/done":
        db.execute("DELETE FROM forward_sessions WHERE chat_id = ?", (str(chat_id),))
        db.commit()
        return send_message(chat_id, "✅ Biriktirish rejimi yakunlandi.")

    session = _active_forward_session(chat_id)
    if session and user:
        return _handle_attach_to_session(session, message, user)

    if not user:
        return _not_registered_message(chat_id)

    return send_message(chat_id, "Noma'lum buyruq. Yordam uchun /start yozing.")


def _poll_loop():
    global _offset, _running
    _running = True
    print("[telegram] Long polling started")
    while _running:
        try:
            updates = _api_call("getUpdates", {"offset": _offset, "timeout": 25, "allowed_updates": ["message"]})
            for update in updates:
                _offset = update["update_id"] + 1
                try:
                    _handle_update(update)
                except Exception as err:  # noqa: BLE001
                    print(f"[telegram] handle_update error: {err}")
        except Exception as err:  # noqa: BLE001
            print(f"[telegram] getUpdates failed: {err}")
            time.sleep(3)


def start():
    if not is_configured():
        print("[telegram] BOT_TOKEN not set — Telegram bot disabled. Auth/notify features will not work until configured.")
        return
    thread = threading.Thread(target=_poll_loop, daemon=True)
    thread.start()


def stop():
    global _running
    _running = False
