from fastapi import APIRouter, Depends

from app.db import get_db
from app.deps import require_roles

router = APIRouter(prefix="/api/stats", tags=["stats"])


def _org_stat_counts(db, org_id: int) -> dict:
    def count(extra_where: str) -> int:
        row = db.execute(
            f"SELECT COUNT(*) c FROM task_targets tt JOIN tasks t ON t.id = tt.task_id WHERE tt.org_id = ? {extra_where}",
            (org_id,),
        ).fetchone()
        return row["c"]

    return {
        "total": count(""),
        "controlPending": count("AND t.type = 'control' AND tt.status = 'pending'"),
        "controlClosed": count("AND t.type = 'control' AND tt.status = 'closed'"),
        "overdue": count("AND t.type = 'control' AND tt.status = 'pending' AND t.deadline_at < datetime('now','localtime')"),
        "infoPending": count("AND t.type = 'info' AND tt.status = 'sent'"),
        "infoDone": count("AND t.type = 'info' AND tt.status = 'done'"),
    }


@router.get("/me")
def my_stats(current_user: dict = Depends(require_roles("director"))):
    db = get_db()
    return _org_stat_counts(db, current_user["org_id"])


@router.get("/overview")
def overview(current_user: dict = Depends(require_roles("department", "admin"))):
    db = get_db()
    orgs = [dict(o) for o in db.execute("SELECT * FROM orgs ORDER BY name").fetchall()]

    per_org = []
    for o in orgs:
        director = None
        if o["director_user_id"]:
            d = db.execute(
                "SELECT id, full_name, telegram_chat_id FROM users WHERE id = ?", (o["director_user_id"],)
            ).fetchone()
            if d:
                director = {"id": d["id"], "fullName": d["full_name"], "telegramLinked": bool(d["telegram_chat_id"])}
        per_org.append({"id": o["id"], "name": o["name"], "type": o["type"], "director": director, **_org_stat_counts(db, o["id"])})

    totals = {"total": 0, "controlPending": 0, "controlClosed": 0, "overdue": 0, "infoPending": 0, "infoDone": 0}
    for o in per_org:
        for key in totals:
            totals[key] += o[key]

    return {
        "schoolCount": sum(1 for o in orgs if o["type"] == "school"),
        "kindergartenCount": sum(1 for o in orgs if o["type"] == "kindergarten"),
        "totals": totals,
        "perOrg": per_org,
    }
