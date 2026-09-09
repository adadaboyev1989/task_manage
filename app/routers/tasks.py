import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

from app import push, telegram_bot
from app.config import UPLOAD_DIR
from app.datetime_utils import normalize_datetime, parse_stored_datetime
from app.db import get_db
from app.deps import get_current_user, require_roles

router = APIRouter(tags=["tasks"])


class CreateTaskBody(BaseModel):
    title: str
    description: str = ""
    type: str
    deadlineAt: Optional[str] = None
    orgIds: list[int]


class AssignCloserBody(BaseModel):
    userId: Optional[int] = None


def _task_with_targets(db, task_id: int) -> Optional[dict]:
    task_row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task_row:
        return None
    task = dict(task_row)
    targets = db.execute(
        """SELECT tt.*, o.name AS org_name, o.type AS org_type
           FROM task_targets tt JOIN orgs o ON o.id = tt.org_id
           WHERE tt.task_id = ? ORDER BY o.name""",
        (task_id,),
    ).fetchall()
    attachments = db.execute(
        "SELECT id, original_name, mime_type, size, source, text_content, created_at FROM attachments WHERE task_id = ? ORDER BY id",
        (task_id,),
    ).fetchall()
    creator = db.execute("SELECT id, full_name FROM users WHERE id = ?", (task["created_by"],)).fetchone()

    additional_closer = None
    if task.get("additional_closer_id"):
        closer_row = db.execute(
            "SELECT id, full_name FROM users WHERE id = ?", (task["additional_closer_id"],)
        ).fetchone()
        if closer_row:
            additional_closer = {"id": closer_row["id"], "fullName": closer_row["full_name"]}

    task["targets"] = [dict(t) for t in targets]
    task["attachments"] = [dict(a) for a in attachments]
    task["creator"] = dict(creator) if creator else None
    task["additionalCloser"] = additional_closer
    return task


def _is_overdue(status_: str, task_type: str, deadline_at: Optional[str]) -> bool:
    if task_type != "control" or status_ != "pending" or not deadline_at:
        return False
    from datetime import datetime

    return parse_stored_datetime(deadline_at) < datetime.now()


@router.get("/api/tasks")
def list_tasks(
    status: Optional[str] = None,
    type: Optional[str] = None,
    orgId: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()

    if current_user["role"] == "director":
        rows = db.execute(
            """SELECT t.*, tt.status AS target_status, tt.completed_at, tt.org_id, u.full_name AS creator_name
               FROM task_targets tt JOIN tasks t ON t.id = tt.task_id JOIN users u ON u.id = t.created_by
               WHERE tt.org_id = ? ORDER BY t.created_at DESC""",
            (current_user["org_id"],),
        ).fetchall()
    elif orgId:
        rows = db.execute(
            """SELECT t.*, tt.status AS target_status, tt.completed_at, tt.org_id, o.name AS org_name, o.type AS org_type, u.full_name AS creator_name
               FROM task_targets tt JOIN tasks t ON t.id = tt.task_id JOIN orgs o ON o.id = tt.org_id JOIN users u ON u.id = t.created_by
               WHERE tt.org_id = ? ORDER BY t.created_at DESC""",
            (orgId,),
        ).fetchall()
    else:
        # Department/admin overview with no org filter: one row per TASK, not per
        # (task, org) pair — otherwise a task broadcast to every school/kindergarten
        # would flood the list with one row per recipient instead of one per task.
        agg_rows = db.execute(
            """SELECT t.*, u.full_name AS creator_name,
                      COUNT(tt.id) AS target_count,
                      SUM(CASE WHEN tt.status IN ('closed','done') THEN 1 ELSE 0 END) AS done_count,
                      SUM(CASE WHEN t.type = 'control' AND tt.status = 'pending' AND t.deadline_at < datetime('now','localtime') THEN 1 ELSE 0 END) AS overdue_count
               FROM tasks t
               JOIN task_targets tt ON tt.task_id = t.id
               JOIN users u ON u.id = t.created_by
               GROUP BY t.id
               ORDER BY t.created_at DESC"""
        ).fetchall()

        result = []
        for r in agg_rows:
            r = dict(r)
            result.append(
                {
                    "id": r["id"],
                    "title": r["title"],
                    "type": r["type"],
                    "deadlineAt": r["deadline_at"],
                    "createdAt": r["created_at"],
                    "createdByName": r["creator_name"],
                    "targetCount": r["target_count"],
                    "doneCount": r["done_count"],
                    "overdue": r["overdue_count"] > 0,
                }
            )

        if type:
            result = [r for r in result if r["type"] == type]
        if status == "overdue":
            result = [r for r in result if r["overdue"]]
        elif status == "done":
            result = [r for r in result if r["doneCount"] == r["targetCount"]]
        elif status == "active":
            result = [r for r in result if r["doneCount"] < r["targetCount"]]

        return result

    result = []
    for r in rows:
        r = dict(r)
        overdue = _is_overdue(r["target_status"], r["type"], r["deadline_at"])
        result.append(
            {
                "id": r["id"],
                "title": r["title"],
                "type": r["type"],
                "deadlineAt": r["deadline_at"],
                "createdAt": r["created_at"],
                "orgId": r["org_id"],
                "orgName": r.get("org_name"),
                "orgType": r.get("org_type"),
                "status": r["target_status"],
                "completedAt": r["completed_at"],
                "overdue": overdue,
                "createdByName": r["creator_name"],
            }
        )

    if status:
        result = [r for r in result if (r["overdue"] if status == "overdue" else r["status"] == status)]
    if type:
        result = [r for r in result if r["type"] == type]

    return result


@router.get("/api/tasks/{task_id}")
def get_task(task_id: int, current_user: dict = Depends(get_current_user)):
    db = get_db()
    task = _task_with_targets(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Topshiriq topilmadi")

    if current_user["role"] == "director":
        owns = any(t["org_id"] == current_user["org_id"] for t in task["targets"])
        if not owns:
            raise HTTPException(status_code=403, detail="Ruxsat yo'q")

    return task


@router.post("/api/tasks", status_code=201)
def create_task(body: CreateTaskBody, current_user: dict = Depends(require_roles("department", "admin"))):
    db = get_db()

    if not body.title.strip():
        raise HTTPException(status_code=400, detail="Sarlavha kiritilishi shart")
    if body.type not in ("control", "info"):
        raise HTTPException(status_code=400, detail="Topshiriq turi noto'g'ri")
    if not body.orgIds:
        raise HTTPException(status_code=400, detail="Kamida bitta tashkilot tanlanishi kerak")

    normalized_deadline = normalize_datetime(body.deadlineAt) if body.type == "control" else None
    if body.type == "control" and not normalized_deadline:
        raise HTTPException(status_code=400, detail="Muddat kiritilishi shart va to'g'ri formatda bo'lishi kerak")

    placeholders = ",".join("?" * len(body.orgIds))
    orgs = db.execute(f"SELECT * FROM orgs WHERE id IN ({placeholders})", body.orgIds).fetchall()
    if len(orgs) != len(body.orgIds):
        raise HTTPException(status_code=400, detail="Ba'zi tashkilotlar topilmadi")

    initial_status = "pending" if body.type == "control" else "sent"

    cur = db.execute(
        "INSERT INTO tasks (title, description, type, deadline_at, created_by) VALUES (?, ?, ?, ?, ?)",
        (body.title.strip(), body.description.strip(), body.type, normalized_deadline, current_user["id"]),
    )
    task_id = cur.lastrowid
    for org in orgs:
        db.execute(
            "INSERT INTO task_targets (task_id, org_id, status) VALUES (?, ?, ?)", (task_id, org["id"], initial_status)
        )
    db.commit()

    task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    task = dict(task)

    for org in orgs:
        org = dict(org)
        if org["director_user_id"]:
            director = db.execute("SELECT * FROM users WHERE id = ?", (org["director_user_id"],)).fetchone()
            if director:
                director = dict(director)
                telegram_bot.notify_new_task(director, task, org)
                push.notify_user(
                    director["id"],
                    {
                        "title": "🔴 Yangi ijro topshirig'i" if body.type == "control" else "ℹ️ Yangi ma'lumot",
                        "body": body.title,
                        "url": f"/#/task/{task_id}",
                    },
                )

    return _task_with_targets(db, task_id)


@router.patch("/api/tasks/{task_id}/targets/{org_id}/done")
def mark_done(task_id: int, org_id: int, current_user: dict = Depends(require_roles("director"))):
    if current_user["org_id"] != org_id:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")

    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        raise HTTPException(status_code=404, detail="Topshiriq topilmadi")
    if task["type"] != "info":
        raise HTTPException(status_code=400, detail="Bu topshiriq turi uchun ijro tasdiqlash bo'lim tomonidan amalga oshiriladi")

    target = db.execute("SELECT * FROM task_targets WHERE task_id = ? AND org_id = ?", (task_id, org_id)).fetchone()
    if not target:
        raise HTTPException(status_code=404, detail="Topilmadi")
    if target["status"] == "done":
        return _task_with_targets(db, task_id)

    db.execute(
        "UPDATE task_targets SET status = 'done', completed_at = datetime('now'), completed_by = ? WHERE id = ?",
        (current_user["id"], target["id"]),
    )
    db.commit()
    return _task_with_targets(db, task_id)


@router.patch("/api/tasks/{task_id}/targets/{org_id}/close")
def close_target(task_id: int, org_id: int, current_user: dict = Depends(require_roles("department", "admin"))):
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        raise HTTPException(status_code=404, detail="Topshiriq topilmadi")
    if task["type"] != "control":
        raise HTTPException(status_code=400, detail="Bu topshiriqni yechish shart emas")
    if (
        current_user["role"] != "admin"
        and task["created_by"] != current_user["id"]
        and task["additional_closer_id"] != current_user["id"]
    ):
        raise HTTPException(status_code=403, detail="Faqat shu topshiriqni bergan xodim yoki administrator nazoratdan yechishi mumkin")

    target = db.execute("SELECT * FROM task_targets WHERE task_id = ? AND org_id = ?", (task_id, org_id)).fetchone()
    if not target:
        raise HTTPException(status_code=404, detail="Topilmadi")

    db.execute(
        "UPDATE task_targets SET status = 'closed', completed_at = datetime('now'), completed_by = ? WHERE id = ?",
        (current_user["id"], target["id"]),
    )
    db.commit()
    return _task_with_targets(db, task_id)


@router.patch("/api/tasks/{task_id}/assign-closer")
def assign_closer(task_id: int, body: AssignCloserBody, current_user: dict = Depends(require_roles("admin"))):
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        raise HTTPException(status_code=404, detail="Topshiriq topilmadi")
    if task["type"] != "control":
        raise HTTPException(status_code=400, detail="Bu faqat nazoratdagi topshiriqlar uchun mumkin")

    if body.userId is not None:
        user = db.execute(
            "SELECT * FROM users WHERE id = ? AND role = 'department' AND is_active = 1", (body.userId,)
        ).fetchone()
        if not user:
            raise HTTPException(status_code=400, detail="Bo'lim xodimi topilmadi")

    db.execute("UPDATE tasks SET additional_closer_id = ? WHERE id = ?", (body.userId, task_id))
    db.commit()
    return _task_with_targets(db, task_id)


@router.post("/api/tasks/{task_id}/attachments", status_code=201)
async def upload_attachment(
    task_id: int, files: list[UploadFile] = File(...), current_user: dict = Depends(get_current_user)
):
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        raise HTTPException(status_code=404, detail="Topshiriq topilmadi")

    if current_user["role"] == "director":
        owns = db.execute(
            "SELECT 1 FROM task_targets WHERE task_id = ? AND org_id = ?", (task_id, current_user["org_id"])
        ).fetchone()
        if not owns:
            raise HTTPException(status_code=403, detail="Ruxsat yo'q")

    max_size = 25 * 1024 * 1024
    saved = []
    try:
        for file in files:
            contents = await file.read()
            if len(contents) > max_size:
                raise HTTPException(status_code=400, detail=f"\"{file.filename}\" hajmi 25MB dan katta")

            ext = Path(file.filename or "").suffix
            stored_name = f"{uuid.uuid4()}{ext}"
            (UPLOAD_DIR / stored_name).write_bytes(contents)
            saved.append(stored_name)

            db.execute(
                """INSERT INTO attachments (task_id, original_name, stored_name, mime_type, size, source, uploaded_by)
                   VALUES (?, ?, ?, ?, ?, 'upload', ?)""",
                (task_id, file.filename, stored_name, file.content_type, len(contents), current_user["id"]),
            )
    except HTTPException:
        for stored_name in saved:
            (UPLOAD_DIR / stored_name).unlink(missing_ok=True)
        db.rollback()
        raise

    db.commit()
    return _task_with_targets(db, task_id)


@router.get("/api/tasks/{task_id}/attach-link")
def attach_link(task_id: int, current_user: dict = Depends(get_current_user)):
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        raise HTTPException(status_code=404, detail="Topshiriq topilmadi")

    if current_user["role"] == "director":
        owns = db.execute(
            "SELECT 1 FROM task_targets WHERE task_id = ? AND org_id = ?", (task_id, current_user["org_id"])
        ).fetchone()
        if not owns:
            raise HTTPException(status_code=403, detail="Ruxsat yo'q")

    if not current_user["telegram_chat_id"]:
        raise HTTPException(status_code=400, detail="Avval Telegram hisobingizni ulang")

    return {"deepLink": telegram_bot.attach_deep_link(task_id), "botConfigured": telegram_bot.is_configured()}


@router.get("/api/tasks/attachments/{attachment_id}/download")
def download_attachment(attachment_id: int, current_user: dict = Depends(get_current_user)):
    db = get_db()
    attachment = db.execute("SELECT * FROM attachments WHERE id = ?", (attachment_id,)).fetchone()
    if not attachment:
        raise HTTPException(status_code=404, detail="Topilmadi")
    attachment = dict(attachment)

    task = db.execute("SELECT * FROM tasks WHERE id = ?", (attachment["task_id"],)).fetchone()
    if current_user["role"] == "director":
        owns = db.execute(
            "SELECT 1 FROM task_targets WHERE task_id = ? AND org_id = ?", (task["id"], current_user["org_id"])
        ).fetchone()
        if not owns:
            raise HTTPException(status_code=403, detail="Ruxsat yo'q")

    if attachment["text_content"]:
        return PlainTextResponse(attachment["text_content"])

    if not attachment["stored_name"]:
        raise HTTPException(status_code=404, detail="Fayl mavjud emas")

    file_path = UPLOAD_DIR / attachment["stored_name"]
    return FileResponse(file_path, filename=attachment["original_name"] or attachment["stored_name"])
