from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.db import get_db
from app.deps import get_current_user, require_roles

router = APIRouter(prefix="/api/orgs", tags=["orgs"])


class CreateOrgBody(BaseModel):
    name: str
    type: str
    address: str = ""


class UpdateOrgBody(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None


def _org_summary(db, org: dict) -> dict:
    control_pending = db.execute(
        """SELECT COUNT(*) c FROM task_targets tt JOIN tasks t ON t.id = tt.task_id
           WHERE tt.org_id = ? AND t.type = 'control' AND tt.status = 'pending'""",
        (org["id"],),
    ).fetchone()["c"]
    overdue = db.execute(
        """SELECT COUNT(*) c FROM task_targets tt JOIN tasks t ON t.id = tt.task_id
           WHERE tt.org_id = ? AND t.type = 'control' AND tt.status = 'pending' AND t.deadline_at < datetime('now','localtime')""",
        (org["id"],),
    ).fetchone()["c"]
    info_pending = db.execute(
        """SELECT COUNT(*) c FROM task_targets tt JOIN tasks t ON t.id = tt.task_id
           WHERE tt.org_id = ? AND t.type = 'info' AND tt.status = 'sent'""",
        (org["id"],),
    ).fetchone()["c"]

    director = None
    if org["director_user_id"]:
        d = db.execute(
            "SELECT id, full_name, telegram_chat_id FROM users WHERE id = ?", (org["director_user_id"],)
        ).fetchone()
        if d:
            director = {"id": d["id"], "fullName": d["full_name"], "telegramLinked": bool(d["telegram_chat_id"])}

    return {
        "id": org["id"],
        "name": org["name"],
        "type": org["type"],
        "address": org["address"],
        "director": director,
        "controlPending": control_pending,
        "overdue": overdue,
        "infoPending": info_pending,
    }


@router.get("")
def list_orgs(type: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    db = get_db()
    if current_user["role"] == "director":
        org = db.execute("SELECT * FROM orgs WHERE id = ?", (current_user["org_id"],)).fetchone()
        return [_org_summary(db, dict(org))] if org else []

    if type:
        rows = db.execute("SELECT * FROM orgs WHERE type = ? ORDER BY name", (type,)).fetchall()
    else:
        rows = db.execute("SELECT * FROM orgs ORDER BY name").fetchall()
    return [_org_summary(db, dict(r)) for r in rows]


@router.post("", status_code=201)
def create_org(body: CreateOrgBody, current_user: dict = Depends(require_roles("admin"))):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Nomi kiritilishi shart")
    if body.type not in ("school", "kindergarten"):
        raise HTTPException(status_code=400, detail="Turi noto'g'ri")

    db = get_db()
    cur = db.execute("INSERT INTO orgs (name, type, address) VALUES (?, ?, ?)", (body.name.strip(), body.type, body.address.strip()))
    db.commit()
    org = db.execute("SELECT * FROM orgs WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _org_summary(db, dict(org))


@router.patch("/{org_id}")
def update_org(org_id: int, body: UpdateOrgBody, current_user: dict = Depends(require_roles("admin"))):
    db = get_db()
    org = db.execute("SELECT * FROM orgs WHERE id = ?", (org_id,)).fetchone()
    if not org:
        raise HTTPException(status_code=404, detail="Topilmadi")

    db.execute(
        "UPDATE orgs SET name = COALESCE(?, name), address = COALESCE(?, address) WHERE id = ?",
        (body.name.strip() if body.name is not None else None, body.address.strip() if body.address is not None else None, org_id),
    )
    db.commit()
    org = db.execute("SELECT * FROM orgs WHERE id = ?", (org_id,)).fetchone()
    return _org_summary(db, dict(org))


@router.delete("/{org_id}")
def delete_org(org_id: int, current_user: dict = Depends(require_roles("admin"))):
    db = get_db()
    org = db.execute("SELECT * FROM orgs WHERE id = ?", (org_id,)).fetchone()
    if not org:
        raise HTTPException(status_code=404, detail="Topilmadi")

    has_tasks = db.execute("SELECT 1 FROM task_targets WHERE org_id = ? LIMIT 1", (org_id,)).fetchone()
    if has_tasks:
        raise HTTPException(status_code=400, detail="Tashkilotga topshiriqlar biriktirilgan, o'chirib bo'lmaydi")

    db.execute("DELETE FROM orgs WHERE id = ?", (org_id,))
    db.commit()
    return {"ok": True}
