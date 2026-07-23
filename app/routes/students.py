import csv
import io
import json
import logging
import numpy as np
from datetime import datetime
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import Response

from app.database import (
    create_notification,
    get_db_connection,
    log_system_action,
    pst_now,
    pst_str,
)
from app.routes.auth import get_current_user
from app.schemas import (
    AttendanceLogResponse,
    FaceRegistrationResponse,
    GenericResponse,
    ProfileUpdateRequest,
    ProfileUpdateResponse,
    RegistrantResponse,
)
from app.services.face_service import face_service

router = APIRouter()
logger = logging.getLogger(__name__)


def _safe_attendance_response(r) -> AttendanceLogResponse:
    """Build an AttendanceLogResponse from a DB row with null-safe field access."""
    logged_at_raw = r["logged_at"]
    if isinstance(logged_at_raw, str):
        try:
            logged_at_val = datetime.strptime(logged_at_raw[:19], "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            logged_at_val = datetime.now()
    elif logged_at_raw is None:
        logged_at_val = datetime.now()
    else:
        logged_at_val = logged_at_raw
    return AttendanceLogResponse(
        user_id=r["user_id"],
        user_name=r["user_name"],
        logged_at=logged_at_val,
        device_id=r["device_id"] or "unknown",
        time_in=r["time_in"],
        time_out=r["time_out"],
        attendance_status=r["attendance_status"],
        date=r["date"],
        scan_method=r["scan_method"],
    )

ALLOWED_PROFILE_FIELDS = {
    "first_name", "last_name", "email", "contact_number",
    "address", "emergency_contact", "course", "year_level", "section",
}


# ─── Student Profile (read-only by default) ──────────────────────────

@router.get("/students/me", response_model=RegistrantResponse)
def get_my_profile(_user: dict = Depends(get_current_user)):
    if _user["role"] == "ADMIN":
        raise HTTPException(status_code=403, detail="Admins should use admin endpoints")
    conn = get_db_connection()
    row = conn.execute(
        """SELECT user_id, first_name, last_name, role, department_section, status, email, course, year_level, section, contact_number, address, emergency_contact, rfid_uid, created_at
              FROM registrants
             WHERE user_id = ?""",
        (_user["user_id"],),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")
    return RegistrantResponse(
        user_id=row["user_id"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        role=row["role"],
        department_section=row["department_section"],
        status=row["status"],
        email=row["email"],
        course=row["course"],
        year_level=row["year_level"],
        section=row["section"],
        contact_number=row["contact_number"],
        address=row["address"],
        emergency_contact=row["emergency_contact"],
        rfid_uid=row["rfid_uid"],
        photo_url=f"/api/v1/images/{row['user_id']}",
        created_at=row["created_at"],
    )


@router.put("/students/me", response_model=GenericResponse)
def update_my_profile(body: dict, _user: dict = Depends(get_current_user)):
    """Submit a profile change request. Changes take effect only after admin approval."""
    if _user["role"] == "ADMIN":
        raise HTTPException(status_code=403, detail="Admins should use admin endpoints")

    updates = {k: v for k, v in body.items() if k in ALLOWED_PROFILE_FIELDS and v not in (None, "")}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    conn = get_db_connection()
    now = pst_str()
    changes = {}
    for field, new_value in updates.items():
        old_row = conn.execute("SELECT * FROM registrants WHERE user_id = ?", (_user["user_id"],)).fetchone()
        old_value = old_row[field] if old_row else None
        conn.execute(
            """INSERT INTO profile_update_requests (user_id, field_name, old_value, new_value, status, requested_at)
               VALUES (?, ?, ?, ?, 'PENDING', ?)""",
            (_user["user_id"], field, old_value, str(new_value), now),
        )
        changes[field] = str(new_value)

    conn.execute(
        """INSERT INTO approval_requests (user_id, request_type, details, status, requested_at)
           VALUES (?, 'PROFILE_UPDATE', ?, 'PENDING', ?)""",
        (_user["user_id"], json.dumps({"changes": changes}), now),
    )
    conn.commit()
    log_system_action(None, "PROFILE_UPDATE_REQUEST", f"User {_user['user_id']} requested profile changes: {changes}")
    return GenericResponse(status="ok", message="Profile update request submitted for approval")


# ─── Student Dashboard ─────────────────────────────────────────────

@router.get("/students/me/dashboard")
def get_my_dashboard(_user: dict = Depends(get_current_user)):
    if _user["role"] == "ADMIN":
        raise HTTPException(status_code=403, detail="Admins should use admin endpoints")
    try:
        conn = get_db_connection()
        uid = _user["user_id"]
        now = pst_now()
        today = now.strftime("%Y-%m-%d")
        month_start = now.strftime("%Y-%m-01")

        total = conn.execute("SELECT COUNT(*) FROM attendance_logs WHERE user_id = ?", (uid,)).fetchone()[0]
        present = conn.execute("SELECT COUNT(*) FROM attendance_logs WHERE user_id = ? AND attendance_status = 'PRESENT'", (uid,)).fetchone()[0]
        late = conn.execute("SELECT COUNT(*) FROM attendance_logs WHERE user_id = ? AND attendance_status = 'LATE'", (uid,)).fetchone()[0]
        this_month = conn.execute("SELECT COUNT(*) FROM attendance_logs WHERE user_id = ? AND date >= ?", (uid, month_start)).fetchone()[0]
        this_week = conn.execute(
            "SELECT COUNT(*) FROM attendance_logs WHERE user_id = ? AND date >= date(?, '-6 days')",
            (uid, today),
        ).fetchone()[0]
        unread = conn.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0", (uid,)).fetchone()[0]
        announcements = conn.execute("SELECT COUNT(*) FROM announcements").fetchone()[0]

        rate = round((present / total) * 100, 1) if total else 0.0

        recent = conn.execute(
            """SELECT a.log_id, a.user_id, r.first_name || ' ' || r.last_name AS user_name,
                      a.logged_at, a.device_id, a.time_in, a.time_out, a.attendance_status, a.date
                 FROM attendance_logs a JOIN registrants r ON r.user_id = a.user_id
                WHERE a.user_id = ? ORDER BY a.date DESC, a.logged_at DESC LIMIT 5""",
            (uid,),
        ).fetchall()

        # Last 30 days series for the chart
        series_rows = conn.execute(
            """SELECT date, COUNT(*) AS cnt FROM attendance_logs
                 WHERE user_id = ? AND date >= date(?, '-29 days')
                 GROUP BY date ORDER BY date ASC""",
            (uid, today),
        ).fetchall()
        series = [{"date": r["date"], "count": r["cnt"]} for r in series_rows]

        face_row = conn.execute("SELECT face_embedding FROM registrants WHERE user_id = ?", (uid,)).fetchone()
        face_status = "REGISTERED" if face_row and face_row["face_embedding"] else "NOT_REGISTERED"

        return {
            "attendance_rate": rate,
            "total": total,
            "present": present,
            "late": late,
            "month_count": this_month,
            "week_count": this_week,
            "unread_notifications": unread,
            "announcements": announcements,
            "face_status": face_status,
            "recent": [dict(r) for r in recent],
            "series": series,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error fetching dashboard for student %s", _user.get("user_id"))
        raise HTTPException(status_code=500, detail="Failed to load dashboard data. Please try again.") from exc


# ─── Student Attendance ────────────────────────────────────────────

# FIX: response_model was list[AttendanceLogResponse] but the handler returns a
# paginated dict {total, page, page_size, items}.  Pydantic validation was
# raising a 500 Internal Validation Error on every request.  Removed the
# incorrect response_model and wrapped all DB calls in try/except.
@router.get("/students/me/attendance")
def get_my_attendance(
    _user: dict = Depends(get_current_user),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> Any:
    if _user["role"] == "ADMIN":
        raise HTTPException(status_code=403, detail="Admins should use admin endpoints")
    try:
        conn = get_db_connection()
        sql = """SELECT a.log_id, a.user_id,
                        r.first_name || ' ' || r.last_name AS user_name,
                        a.logged_at, a.device_id,
                        a.time_in, a.time_out, a.attendance_status, a.date, a.scan_method
                   FROM attendance_logs a
                   JOIN registrants r ON r.user_id = a.user_id
                  WHERE a.user_id = ?"""
        params: list = [_user["user_id"]]
        if date_from:
            sql += " AND a.date >= ?"
            params.append(date_from)
        if date_to:
            sql += " AND a.date <= ?"
            params.append(date_to)
        sql += " ORDER BY a.date DESC, a.logged_at DESC LIMIT ? OFFSET ?"
        params.extend([page_size, (page - 1) * page_size])
        rows = conn.execute(sql, params).fetchall()

        count_sql = (
            "SELECT COUNT(*) FROM attendance_logs a"
            " JOIN registrants r ON r.user_id = a.user_id"
            " WHERE a.user_id = ?"
        )
        count_params: list = [_user["user_id"]]
        if date_from:
            count_sql += " AND a.date >= ?"
            count_params.append(date_from)
        if date_to:
            count_sql += " AND a.date <= ?"
            count_params.append(date_to)
        total = conn.execute(count_sql, count_params).fetchone()[0]

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_safe_attendance_response(r) for r in rows],
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error fetching student attendance for %s", _user.get("user_id"))
        raise HTTPException(status_code=500, detail="Failed to load attendance records. Please try again.") from exc


@router.get("/students/me/attendance/export")
def export_my_attendance(
    _user: dict = Depends(get_current_user),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    conn = get_db_connection()
    sql = """SELECT a.log_id, r.first_name || ' ' || r.last_name AS user_name, a.date, a.time_in, a.time_out, a.attendance_status, a.logged_at, a.device_id, a.scan_method
                FROM attendance_logs a JOIN registrants r ON r.user_id = a.user_id
               WHERE a.user_id = ?"""
    params = [_user["user_id"]]
    if date_from:
        sql += " AND a.date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND a.date <= ?"
        params.append(date_to)
    sql += " ORDER BY a.date DESC, a.logged_at DESC"
    rows = conn.execute(sql, params).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Log ID", "Name", "Date", "Time In", "Time Out", "Status", "Logged At", "Device", "Method"])
    for r in rows:
        writer.writerow([r["log_id"], r["user_name"], r["date"], r["time_in"], r["time_out"], r["attendance_status"], r["logged_at"], r["device_id"], r["scan_method"]])
    headers = {"Content-Disposition": f"attachment; filename=my-attendance-{_user['user_id']}.csv"}
    return Response(content=output.getvalue(), media_type="text/csv", headers=headers)


@router.get("/students/me/attendance/summary")
def get_my_attendance_summary(_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    total = conn.execute("SELECT COUNT(*) FROM attendance_logs WHERE user_id = ?", (_user["user_id"],)).fetchone()[0]
    present = conn.execute("SELECT COUNT(*) FROM attendance_logs WHERE user_id = ? AND attendance_status = 'PRESENT'", (_user["user_id"],)).fetchone()[0]
    absent = conn.execute("SELECT COUNT(*) FROM attendance_logs WHERE user_id = ? AND attendance_status = 'ABSENT'", (_user["user_id"],)).fetchone()[0]
    late = conn.execute("SELECT COUNT(*) FROM attendance_logs WHERE user_id = ? AND attendance_status = 'LATE'", (_user["user_id"],)).fetchone()[0]
    return {"total": total, "present": present, "absent": absent, "late": late}


# ─── Face Registration ─────────────────────────────────────────────

@router.get("/students/me/face", response_model=FaceRegistrationResponse)
def get_my_face_status(_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    row = conn.execute("SELECT face_embedding FROM registrants WHERE user_id = ?", (_user["user_id"],)).fetchone()
    has_face = bool(row and row["face_embedding"])
    return FaceRegistrationResponse(id=0, user_id=_user["user_id"], status="REGISTERED" if has_face else "NOT_REGISTERED")


@router.post("/students/me/face", response_model=GenericResponse)
async def update_my_face(image: UploadFile = File(...), _user: dict = Depends(get_current_user)):
    image_bytes = await image.read()
    try:
        embedding = await face_service.extract_embedding(image_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
    conn = get_db_connection()
    conn.execute("UPDATE registrants SET face_embedding = ? WHERE user_id = ?", (embedding_blob, _user["user_id"]))
    conn.commit()
    return GenericResponse(status="ok", message="Face updated successfully")


@router.post("/students/me/face-reregister-request", response_model=GenericResponse)
def request_face_reregister(_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    conn.execute(
        """INSERT INTO approval_requests (user_id, request_type, details, status, requested_at)
           VALUES (?, 'FACE_REREGISTER', ?, 'PENDING', ?)""",
        (_user["user_id"], json.dumps({"note": "Student requested face re-registration."}), pst_str()),
    )
    conn.commit()
    log_system_action(None, "FACE_REREGISTER_REQUEST", f"User {_user['user_id']} requested face re-registration")
    return GenericResponse(status="ok", message="Face re-registration request submitted for approval")


# ─── QR Code ─────────────────────────────────────────────────────

@router.get("/students/me/qr", response_model=GenericResponse)
def get_my_qr(_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    row = conn.execute("SELECT qr_token, qr_payload_enc, qr_image_path FROM registrants WHERE user_id = ?", (_user["user_id"],)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    if not row["qr_token"] or not row["qr_payload_enc"] or not row["qr_image_path"]:
        try:
            from app.services.qr_service import ensure_qr_for_user
            ensure_qr_for_user(conn, _user["user_id"], force_regen=False)
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to generate QR code. Check server logs.")
    row = conn.execute("SELECT qr_token FROM registrants WHERE user_id = ?", (_user["user_id"],)).fetchone()
    if not row or not row["qr_token"]:
        raise HTTPException(status_code=500, detail="QR code not available")
    return GenericResponse(status="ok", message=row["qr_token"])


# ─── Profile update / approval requests (student view) ────────────

@router.get("/students/me/requests")
def get_my_requests(_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    approvals = conn.execute(
        """SELECT id, request_type, details, status, requested_at, reviewed_at, reviewed_by
              FROM approval_requests WHERE user_id = ? ORDER BY requested_at DESC""",
        (_user["user_id"],),
    ).fetchall()
    profile = conn.execute(
        """SELECT id, field_name, old_value, new_value, status, requested_at, reviewed_at, reviewed_by
              FROM profile_update_requests WHERE user_id = ? ORDER BY requested_at DESC""",
        (_user["user_id"],),
    ).fetchall()
    return {
        "approvals": [dict(r) for r in approvals],
        "profile_updates": [dict(r) for r in profile],
    }


@router.post("/students/me/profile-update-request", response_model=ProfileUpdateResponse)
def request_profile_update(body: ProfileUpdateRequest, _user: dict = Depends(get_current_user)):
    if body.field_name not in ALLOWED_PROFILE_FIELDS:
        raise HTTPException(status_code=400, detail="Field not editable")
    conn = get_db_connection()
    old_row = conn.execute("SELECT * FROM registrants WHERE user_id = ?", (_user["user_id"],)).fetchone()
    old_value = old_row[body.field_name] if old_row else None
    now = pst_str()
    cur = conn.execute(
        """INSERT INTO profile_update_requests (user_id, field_name, old_value, new_value, status, requested_at)
           VALUES (?, ?, ?, ?, 'PENDING', ?)""",
        (_user["user_id"], body.field_name, old_value, body.new_value, now),
    )
    conn.execute(
        """INSERT INTO approval_requests (user_id, request_type, details, status, requested_at)
           VALUES (?, 'PROFILE_UPDATE', ?, 'PENDING', ?)""",
        (_user["user_id"], json.dumps({"changes": {body.field_name: body.new_value}}), now),
    )
    conn.commit()
    return ProfileUpdateResponse(
        id=cur.lastrowid,
        user_id=_user["user_id"],
        field_name=body.field_name,
        old_value=old_value,
        new_value=body.new_value,
        status="PENDING",
        requested_at=now,
    )


# ─── Notifications ────────────────────────────────────────────────

@router.get("/students/me/notifications", response_model=list[dict])
def get_my_notifications(_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    rows = conn.execute(
        """SELECT id, title, message, notification_type, is_read, created_at
                FROM notifications
               WHERE user_id = ?
            ORDER BY created_at DESC""",
        (_user["user_id"],),
    ).fetchall()
    return [dict(r) for r in rows]


@router.post("/students/me/notifications/{notification_id}/read", response_model=GenericResponse)
def mark_notification_read(notification_id: int, _user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?", (notification_id, _user["user_id"]))
    conn.commit()
    return GenericResponse(status="ok", message="Marked as read")
