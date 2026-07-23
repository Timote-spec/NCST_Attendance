import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.database import get_db_connection, pst_now
from app.routes.auth import get_current_user
from app.schemas import GenericResponse

router = APIRouter()


def _require_admin_or_staff(_user: dict = Depends(get_current_user)):
    if _user["role"] not in ("ADMIN", "STAFF", "FACULTY"):
        raise HTTPException(status_code=403, detail="Access denied")
    return _user


@router.get("/staff/dashboard/stats")
def staff_dashboard_stats(_user: dict = Depends(_require_admin_or_staff)):
    conn = get_db_connection()
    now = pst_now()
    today = now.strftime("%Y-%m-%d")
    month_start = now.strftime("%Y-%m-01")
    uid = _user["user_id"]

    attendance_today = conn.execute("SELECT COUNT(*) FROM attendance_logs WHERE user_id = ? AND date = ?", (uid, today)).fetchone()[0]
    total_attendance = conn.execute("SELECT COUNT(*) FROM attendance_logs WHERE user_id = ?", (uid,)).fetchone()[0]
    month_attendance = conn.execute("SELECT COUNT(*) FROM attendance_logs WHERE user_id = ? AND date >= ?", (uid, month_start)).fetchone()[0]
    announcements = conn.execute("SELECT COUNT(*) FROM announcements").fetchone()[0]

    recent = conn.execute(
        """SELECT a.log_id, a.user_id, r.first_name || ' ' || r.last_name AS user_name, a.date, a.time_in, a.attendance_status
              FROM attendance_logs a JOIN registrants r ON r.user_id = a.user_id
             WHERE a.user_id = ?
             ORDER BY a.date DESC, a.logged_at DESC LIMIT 10""",
        (uid,),
    ).fetchall()
    series = conn.execute(
        """SELECT date, COUNT(*) AS cnt FROM attendance_logs
             WHERE user_id = ? AND date >= date(?, '-13 days') GROUP BY date ORDER BY date ASC""",
        (uid, today),
    ).fetchall()

    return {
        "attendance_today": attendance_today,
        "total_attendance": total_attendance,
        "month_attendance": month_attendance,
        "announcements": announcements,
        "recent": [dict(r) for r in recent],
        "series": [{"date": r["date"], "count": r["cnt"]} for r in series],
    }


# ─── Attendance Records ─────────────────────────────────────────────

@router.get("/staff/attendance")
def get_staff_attendance(
    _user: dict = Depends(_require_admin_or_staff),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    conn = get_db_connection()
    sql = """SELECT a.log_id, a.user_id, r.first_name || ' ' || r.last_name AS user_name, r.role, r.department_section, a.logged_at, a.device_id, a.time_in, a.time_out, a.attendance_status, a.date, a.scan_method
               FROM attendance_logs a
               JOIN registrants r ON r.user_id = a.user_id
              WHERE a.user_id = ?"""
    params = [_user["user_id"]]
    if date_from:
        sql += " AND a.date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND a.date <= ?"
        params.append(date_to)
    total = conn.execute(f"SELECT COUNT(*) FROM ({sql})", params).fetchone()[0]
    offset = (page - 1) * page_size
    sql += " ORDER BY a.date DESC, a.logged_at DESC LIMIT ? OFFSET ?"
    params.extend([page_size, offset])
    rows = conn.execute(sql, params).fetchall()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [dict(r) for r in rows],
    }


@router.get("/staff/attendance/export")
def export_staff_attendance(
    _user: dict = Depends(_require_admin_or_staff),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    conn = get_db_connection()
    sql = """SELECT a.log_id, a.user_id, r.first_name || ' ' || r.last_name AS user_name, r.role, r.department_section, a.logged_at, a.device_id, a.time_in, a.time_out, a.attendance_status, a.date, a.scan_method
               FROM attendance_logs a
               JOIN registrants r ON r.user_id = a.user_id
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
    writer.writerow(["Log ID", "Name", "Role", "Department", "Date", "Time In", "Time Out", "Status", "Logged At", "Device", "Method"])
    for r in rows:
        writer.writerow([
            r["log_id"], r["user_name"], r["role"], r["department_section"],
            r["date"], r["time_in"], r["time_out"], r["attendance_status"], r["logged_at"], r["device_id"], r["scan_method"]
        ])
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=my_attendance.csv"})


# ─── Student Directory (Read-only for Staff) ───────────────────────

@router.get("/staff/students")
def get_staff_students(
    _user: dict = Depends(_require_admin_or_staff),
    search: str | None = Query(None),
    role: str | None = Query(None, pattern="^(STUDENT|STAFF|FACULTY)$"),
    status: str | None = Query(None, pattern="^(ACTIVE|ARCHIVED)$"),
):
    conn = get_db_connection()
    sql = "SELECT user_id, first_name, last_name, role, department_section, status, photo_path, created_at FROM registrants WHERE 1=1"
    params = []
    if role:
        sql += " AND role = ?"
        params.append(role)
    if status:
        sql += " AND status = ?"
        params.append(status)
    if search:
        sql += " AND (first_name LIKE ? OR last_name LIKE ? OR user_id LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like])
    sql += " ORDER BY created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@router.get("/staff/students/{user_id}")
def get_staff_student_detail(user_id: str, _user: dict = Depends(_require_admin_or_staff)):
    conn = get_db_connection()
    row = conn.execute(
        """SELECT user_id, first_name, last_name, role, department_section, status, photo_path, email, course, year_level, section, contact_number, address, emergency_contact, created_at
               FROM registrants
              WHERE user_id = ?""",
        (user_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Student not found")
    return dict(row)


# ─── Scanner Status ────────────────────────────────────────────────

@router.get("/staff/scanner-status")
def get_scanner_status(_user: dict = Depends(_require_admin_or_staff)):
    try:
        import cv2
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW if hasattr(cv2, 'CAP_DSHOW') else 0)
        is_open = cap.isOpened()
        if is_open:
            cap.release()
        return {"camera": "available" if is_open else "unavailable"}
    except Exception:
        return {"camera": "unavailable"}


# ─── Announcements (Read for Staff) ────────────────────────────────

@router.get("/staff/announcements")
def get_staff_announcements(_user: dict = Depends(_require_admin_or_staff)):
    conn = get_db_connection()
    role = _user["role"]
    rows = conn.execute(
        """SELECT id, title, content, target_role, created_by, created_at, is_pinned
               FROM announcements
              WHERE target_role IN (?, 'ALL')
           ORDER BY is_pinned DESC, created_at DESC""",
        (role,),
    ).fetchall()
    return [dict(r) for r in rows]


# ─── Profile (Staff) ───────────────────────────────────────────────

@router.get("/staff/me")
def get_staff_profile(_user: dict = Depends(get_current_user)):
    if _user["role"] not in ("STAFF", "FACULTY"):
        raise HTTPException(status_code=403, detail="Staff access only")
    conn = get_db_connection()
    row = conn.execute(
        """SELECT user_id, first_name, last_name, role, department_section, status, email,
                  course, year_level, section, contact_number, address, emergency_contact, created_at
             FROM registrants WHERE user_id = ?""",
        (_user["user_id"],),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")
    result = dict(row)
    result["photo_url"] = f"/api/v1/images/{row['user_id']}"
    return result
