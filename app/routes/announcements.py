from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_db_connection, log_system_action, pst_str
from app.routes.auth import get_current_admin, get_current_user
from app.schemas import AnnouncementCreate, AnnouncementResponse, GenericResponse

router = APIRouter()


@router.get("/announcements", response_model=list[AnnouncementResponse])
def list_announcements(_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    role = _user["role"]
    rows = conn.execute(
        """SELECT id, title, content, target_role, created_by, created_at, is_pinned
               FROM announcements
              WHERE target_role IN (?, 'ALL')
           ORDER BY is_pinned DESC, created_at DESC""",
        (role,),
    ).fetchall()
    return [
        AnnouncementResponse(
            id=r["id"],
            title=r["title"],
            content=r["content"],
            target_role=r["target_role"],
            created_by=r["created_by"],
            created_at=r["created_at"],
            is_pinned=r["is_pinned"],
        )
        for r in rows
    ]


@router.post("/announcements", response_model=AnnouncementResponse)
def create_announcement(body: AnnouncementCreate, _admin: str = Depends(get_current_admin)):
    conn = get_db_connection()
    now = pst_str()
    cur = conn.execute(
        """INSERT INTO announcements (title, content, target_role, created_by, created_at, is_pinned)
               VALUES (?, ?, ?, ?, ?, ?)""",
        (body.title, body.content, body.target_role, _admin, now, 1 if body.is_pinned else 0),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM announcements WHERE id = ?", (cur.lastrowid,)).fetchone()
    return AnnouncementResponse(
        id=row["id"],
        title=row["title"],
        content=row["content"],
        target_role=row["target_role"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        is_pinned=row["is_pinned"],
    )


@router.delete("/announcements/{announcement_id}", response_model=GenericResponse)
def delete_announcement(announcement_id: int, _admin: str = Depends(get_current_admin)):
    conn = get_db_connection()
    row = conn.execute("SELECT id FROM announcements WHERE id = ?", (announcement_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Announcement not found")
    conn.execute("DELETE FROM announcements WHERE id = ?", (announcement_id,))
    conn.commit()
    log_system_action(_admin, "DELETE_ANNOUNCEMENT", f"Deleted announcement {announcement_id}")
    return GenericResponse(status="ok", message="Announcement deleted")
