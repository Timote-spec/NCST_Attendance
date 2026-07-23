import datetime

import bcrypt
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File

DEFAULT_PASSWORD = "Default123!"

from app.database import (
    create_notification,
    get_admin_email,
    get_db_connection,
    log_system_action,
    pst_now,
    pst_str,
)
from app.routes.auth import get_current_admin
from app.config import settings
from app.schemas import AdminListRow, AuditLogRow, CreateAdminRequest, GenericResponse, LogRow, RegistrantListRow, UpdateAdminRequest, UpdateRegistrantRequest
from app.services.face_service import face_service

router = APIRouter()


@router.get("/admin/users")
def list_users(
    role: str | None = Query(None, pattern="^(STUDENT|STAFF|FACULTY)$"),
    status: str | None = Query(None, pattern="^(ACTIVE|ARCHIVED)$"),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    _admin: str = Depends(get_current_admin),
):
    conn = get_db_connection()
    base_sql = "FROM registrants WHERE 1=1"
    params = []
    if role:
        base_sql += " AND role = ?"
        params.append(role)
    if status:
        base_sql += " AND status = ?"
        params.append(status)
    if search:
        base_sql += " AND (first_name LIKE ? OR last_name LIKE ? OR user_id LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like])
    total = conn.execute(f"SELECT COUNT(*) {base_sql}", params).fetchone()[0]
    offset = (page - 1) * page_size
    rows = conn.execute(
        f"SELECT user_id, first_name, last_name, role, department_section, status, email, contact_number, emergency_contact, rfid_uid, qr_token, section, photo_path, created_at {base_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [page_size, offset],
    ).fetchall()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            RegistrantListRow(
                user_id=r["user_id"],
                first_name=r["first_name"],
                last_name=r["last_name"],
                role=r["role"],
                department_section=r["department_section"],
                status=r["status"],
                email=r["email"],
                contact_number=r["contact_number"],
                emergency_contact=r["emergency_contact"],
                rfid_uid=r["rfid_uid"],
                qr_token=r["qr_token"],
                section=r["section"],
                photo_url=f"/api/v1/images/{r['user_id']}",
                created_at=r["created_at"],
            )
            for r in rows
        ],
    }


@router.get("/admin/users/{user_id}", response_model=RegistrantListRow)
def get_user(user_id: str, _admin: str = Depends(get_current_admin)):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT user_id, first_name, last_name, role, department_section, status, email, contact_number, emergency_contact, rfid_uid, photo_path, created_at FROM registrants WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return RegistrantListRow(
        user_id=row["user_id"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        role=row["role"],
        department_section=row["department_section"],
        status=row["status"],
        email=row["email"],
        contact_number=row["contact_number"],
        emergency_contact=row["emergency_contact"],
        rfid_uid=row["rfid_uid"],
        photo_url=f"/api/v1/images/{row['user_id']}",
        created_at=row["created_at"],
    )


@router.get("/admin/profile-update-requests")
def list_profile_update_requests(_admin: str = Depends(get_current_admin)):
    conn = get_db_connection()
    rows = conn.execute(
        """SELECT p.id, p.user_id, r.first_name || ' ' || r.last_name AS user_name, p.field_name, p.old_value, p.new_value, p.status, p.requested_at, p.reviewed_at, p.reviewed_by
              FROM profile_update_requests p
              LEFT JOIN registrants r ON r.user_id = p.user_id
             ORDER BY p.requested_at DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


@router.put("/admin/users/{user_id}/status", response_model=RegistrantListRow)
def toggle_user_status(
    user_id: str,
    _admin: str = Depends(get_current_admin),
):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT user_id, first_name, last_name, role, department_section, status, email, contact_number, emergency_contact, photo_path, created_at FROM registrants WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    new_status = "ARCHIVED" if row["status"] == "ACTIVE" else "ACTIVE"
    conn.execute("UPDATE registrants SET status = ? WHERE user_id = ?", (new_status, user_id))
    conn.commit()
    admin_email = get_admin_email(_admin)
    log_system_action(admin_email, "TOGGLE_STATUS", f"Changed user {user_id} status from {row['status']} to {new_status}")
    updated = conn.execute(
        "SELECT user_id, first_name, last_name, role, department_section, status, email, contact_number, emergency_contact, photo_path, created_at FROM registrants WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    return RegistrantListRow(
        user_id=updated["user_id"],
        first_name=updated["first_name"],
        last_name=updated["last_name"],
        role=updated["role"],
        department_section=updated["department_section"],
        status=updated["status"],
        email=updated["email"],
        contact_number=updated["contact_number"],
        emergency_contact=updated["emergency_contact"],
        photo_url=f"/api/v1/images/{updated['user_id']}",
        created_at=updated["created_at"],
    )


@router.get("/admin/logs")
def list_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    search: str | None = Query(None),
    _admin: str = Depends(get_current_admin),
):
    conn = get_db_connection()
    base_sql = """FROM attendance_logs a
                   JOIN registrants r ON r.user_id = a.user_id
                  WHERE 1=1"""
    params = []
    if date_from:
        base_sql += " AND a.date >= ?"
        params.append(date_from)
    if date_to:
        base_sql += " AND a.date <= ?"
        params.append(date_to)
    if search:
        base_sql += " AND (r.first_name LIKE ? OR r.last_name LIKE ? OR r.user_id LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like])
    total = conn.execute(f"SELECT COUNT(*) {base_sql}", params).fetchone()[0]
    offset = (page - 1) * page_size
    rows = conn.execute(
        f"""SELECT a.log_id, a.user_id, r.first_name, r.last_name, r.role, r.department_section, r.photo_path, a.logged_at, a.device_id, a.time_in, a.time_out, a.attendance_status, a.date, a.scan_method
               {base_sql}
            ORDER BY a.date DESC, a.logged_at DESC
            LIMIT ? OFFSET ?""",
        params + [page_size, offset],
    ).fetchall()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            LogRow(
                log_id=r["log_id"],
                user_id=r["user_id"],
                first_name=r["first_name"],
                last_name=r["last_name"],
                role=r["role"],
                department_section=r["department_section"],
                logged_at=r["logged_at"],
                device_id=r["device_id"],
                time_in=r["time_in"],
                time_out=r["time_out"],
                attendance_status=r["attendance_status"],
                date=r["date"],
                photo_url=f"/api/v1/images/{r['user_id']}",
                scan_method=r["scan_method"],
            )
            for r in rows
        ],
    }


@router.put("/admin/users/{user_id}", response_model=RegistrantListRow)
def update_registrant(
    user_id: str,
    body: UpdateRegistrantRequest,
    _admin: str = Depends(get_current_admin),
):
    if body.role not in ("STUDENT", "STAFF", "FACULTY"):
        raise HTTPException(status_code=400, detail="Role must be STUDENT, STAFF, or FACULTY")
    conn = get_db_connection()
    row = conn.execute(
        "SELECT user_id, first_name, last_name, role, department_section, status, email, contact_number, emergency_contact, photo_path, created_at FROM registrants WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    rfid_val = body.rfid_uid.strip() if body.rfid_uid else None
    if rfid_val:
        existing = conn.execute(
            "SELECT user_id FROM registrants WHERE rfid_uid = ? AND user_id != ?",
            (rfid_val, user_id),
        ).fetchone()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"RFID UID '{rfid_val}' is already assigned to another user.",
            )
    conn.execute(
        """UPDATE registrants
              SET first_name = ?, last_name = ?, role = ?, department_section = ?, email = ?, course = ?, year_level = ?, section = ?, contact_number = ?, address = ?, emergency_contact = ?, rfid_uid = ?
            WHERE user_id = ?""",
        (
            body.first_name, body.last_name, body.role, body.department_section,
            body.email, body.course, body.year_level, body.section,
            body.contact_number, body.address, body.emergency_contact,
            rfid_val,
            user_id,
        ),
    )
    conn.commit()
    admin_email = get_admin_email(_admin)
    log_system_action(admin_email, "UPDATE_REGISTRANT", f"Updated user {user_id}")
    updated = conn.execute(
        "SELECT user_id, first_name, last_name, role, department_section, status, email, contact_number, emergency_contact, rfid_uid, photo_path, created_at FROM registrants WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    return RegistrantListRow(
        user_id=updated["user_id"],
        first_name=updated["first_name"],
        last_name=updated["last_name"],
        role=updated["role"],
        department_section=updated["department_section"],
        status=updated["status"],
        email=updated["email"],
        contact_number=updated["contact_number"],
        emergency_contact=updated["emergency_contact"],
        rfid_uid=updated["rfid_uid"],
        photo_url=f"/api/v1/images/{updated['user_id']}",
        created_at=updated["created_at"],
    )


@router.post("/admin/users/{user_id}/re-enroll", response_model=GenericResponse)
async def reenroll_registrant(
    user_id: str,
    image: UploadFile = File(...),
    _admin: str = Depends(get_current_admin),
):
    conn = get_db_connection()
    row = conn.execute("SELECT user_id FROM registrants WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    image_bytes = await image.read()
    try:
        embedding = await face_service.extract_embedding(image_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
    conn.execute("UPDATE registrants SET face_embedding = ? WHERE user_id = ?", (embedding_blob, user_id))
    conn.commit()
    admin_email = get_admin_email(_admin)
    log_system_action(admin_email, "RE_ENROLL", f"Re-enrolled face embedding for user {user_id}")
    return GenericResponse(status="ok", message=f"Face re-enrolled for {user_id}")


@router.post("/admin/users/{user_id}/generate-qr", response_model=GenericResponse)
def generate_user_qr(user_id: str, _admin: str = Depends(get_current_admin)):
    from app.services.qr_service import ensure_qr_for_user
    conn = get_db_connection()
    row = conn.execute("SELECT user_id FROM registrants WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    ensure_qr_for_user(conn, user_id, force_regen=True)
    log_system_action(get_admin_email(_admin), "GENERATE_QR", f"Generated QR code for user {user_id}")
    return GenericResponse(status="ok", message="QR code regenerated")


@router.post("/admin/generate-all-qr", response_model=GenericResponse)
def generate_all_qr(_admin: str = Depends(get_current_admin)):
    from app.services.qr_service import ensure_qr_for_user
    conn = get_db_connection()
    rows = conn.execute("SELECT user_id FROM registrants WHERE qr_token IS NULL OR qr_payload_enc IS NULL OR qr_image_path IS NULL").fetchall()
    count = 0
    for row in rows:
        ensure_qr_for_user(conn, row["user_id"], force_regen=False)
        count += 1
    conn.commit()
    log_system_action(get_admin_email(_admin), "GENERATE_ALL_QR", f"Generated QR codes for {count} users")
    return GenericResponse(status="ok", message=f"Generated QR codes for {count} users")


@router.get("/admin/audit-logs")
def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    search: str | None = Query(None),
    _admin: str = Depends(get_current_admin),
):
    conn = get_db_connection()
    base_sql = "FROM audit_logs WHERE 1=1"
    params = []
    if search:
        base_sql += " AND (action LIKE ? OR admin_email LIKE ? OR details LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like])
    total = conn.execute(f"SELECT COUNT(*) {base_sql}", params).fetchone()[0]
    offset = (page - 1) * page_size
    rows = conn.execute(
        f"SELECT log_id, admin_email, action, details, logged_at {base_sql} ORDER BY logged_at DESC LIMIT ? OFFSET ?",
        params + [page_size, offset],
    ).fetchall()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            AuditLogRow(
                log_id=r["log_id"],
                admin_email=r["admin_email"],
                action=r["action"],
                details=r["details"],
                logged_at=r["logged_at"],
            )
            for r in rows
        ],
    }


@router.get("/admin/students/bulk-template")
def get_bulk_template(_admin: str = Depends(get_current_admin)):
    return {
        "headers": ["user_id", "first_name", "last_name", "role", "department_section", "email", "course", "year_level", "section", "contact_number", "address", "emergency_contact"],
        "sample": ["STU001", "Juan", "Dela Cruz", "STUDENT", "BSCS-3A", "juan@example.com", "BSCS", "3", "A", "09123456789", "123 Main St", "Parent: 09987654321"]
    }


@router.post("/admin/students/bulk-import", response_model=GenericResponse)
def bulk_import_students(payload: dict, _admin: str = Depends(get_current_admin)):
    rows = payload.get("rows", [])
    if not rows:
        raise HTTPException(status_code=400, detail="No rows provided")
    conn = get_db_connection()
    inserted = 0
    errors = []
    for i, row in enumerate(rows):
        try:
            user_id = str(row.get("user_id", "")).strip()
            first_name = str(row.get("first_name", "")).strip()
            last_name = str(row.get("last_name", "")).strip()
            role = str(row.get("role", "STUDENT")).strip().upper()
            department_section = str(row.get("department_section", "")).strip()
            if not all([user_id, first_name, last_name, role, department_section]):
                errors.append(f"Row {i+1}: missing required fields")
                continue
            if role not in ("STUDENT", "STAFF", "FACULTY"):
                role = "STUDENT"
            now = pst_str()
            pw_hash = bcrypt.hashpw(DEFAULT_PASSWORD.encode(), bcrypt.gensalt()).decode()
            conn.execute(
                """INSERT OR IGNORE INTO registrants (user_id, first_name, last_name, role, department_section, status, created_at, email, password_hash, course, year_level, section, contact_number, address, emergency_contact)
                       VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id, first_name, last_name, role, department_section, now,
                    row.get("email"), pw_hash, row.get("course"), row.get("year_level"),
                    row.get("section"), row.get("contact_number"), row.get("address"), row.get("emergency_contact"),
                ),
            )
            inserted += 1
        except Exception as e:
            errors.append(f"Row {i+1}: {e}")
    conn.commit()

    # Backfill QR for inserted users (best-effort).
    try:
        from app.services.qr_service import ensure_qr_for_user
        # generate for any user missing qr_image_path or payload after this import
        rows = conn.execute(
            """SELECT user_id FROM registrants WHERE qr_image_path IS NULL OR qr_payload_enc IS NULL"""
        ).fetchall()
        for r in rows:
            ensure_qr_for_user(conn, r["user_id"], force_regen=False)
        conn.commit()
    except Exception:
        pass

    log_system_action(get_admin_email(_admin), "BULK_IMPORT", f"Imported {inserted} users, {len(errors)} errors")

    msg = f"Imported {inserted} users successfully"
    if errors:
        msg += f". Errors: {len(errors)}"
    return GenericResponse(status="ok", message=msg)


@router.put("/admin/logs/{log_id}", response_model=GenericResponse)
def update_log(
    log_id: int,
    body: dict,
    _admin: str = Depends(get_current_admin),
):
    conn = get_db_connection()
    row = conn.execute("SELECT log_id FROM attendance_logs WHERE log_id = ?", (log_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Log not found")
    time_out = body.get("time_out")
    status = body.get("attendance_status")
    sets, params = [], []
    if time_out is not None:
        sets.append("time_out = ?")
        params.append(time_out or None)
    if status:
        sets.append("attendance_status = ?")
        params.append(status)
    if not sets:
        raise HTTPException(status_code=400, detail="No fields to update")
    params.append(log_id)
    conn.execute(f"UPDATE attendance_logs SET {', '.join(sets)} WHERE log_id = ?", params)
    conn.commit()
    log_system_action(get_admin_email(_admin), "EDIT_LOG", f"Edited attendance log {log_id}")
    return GenericResponse(status="ok", message="Record updated")


@router.get("/admin/dashboard/stats")
def dashboard_stats(_admin: str = Depends(get_current_admin)):
    conn = get_db_connection()
    now = pst_now()
    today = now.strftime("%Y-%m-%d")
    month_start = now.strftime("%Y-%m-01")

    total_students = conn.execute("SELECT COUNT(*) FROM registrants WHERE role = 'STUDENT' AND status = 'ACTIVE'").fetchone()[0]
    total_staff = conn.execute("SELECT COUNT(*) FROM registrants WHERE role IN ('STAFF','FACULTY') AND status = 'ACTIVE'").fetchone()[0]
    attendance_today = conn.execute("SELECT COUNT(DISTINCT user_id) FROM attendance_logs WHERE date = ?", (today,)).fetchone()[0]
    pending_approvals = conn.execute("SELECT COUNT(*) FROM approval_requests WHERE status = 'PENDING'").fetchone()[0]
    pending_profile = conn.execute("SELECT COUNT(*) FROM profile_update_requests WHERE status = 'PENDING'").fetchone()[0]
    month_attendance = conn.execute("SELECT COUNT(*) FROM attendance_logs WHERE date >= ?", (month_start,)).fetchone()[0]

    total_today = conn.execute("SELECT COUNT(*) FROM attendance_logs WHERE date = ?", (today,)).fetchone()[0]
    present_today = conn.execute("SELECT COUNT(*) FROM attendance_logs WHERE date = ? AND attendance_status = 'PRESENT'", (today,)).fetchone()[0]
    success_rate = round((present_today / total_today) * 100, 1) if total_today else 0.0

    # Scan method breakdown for today
    rfid_today = conn.execute("SELECT COUNT(*) FROM attendance_logs WHERE date = ? AND scan_method = 'RFID'", (today,)).fetchone()[0]
    face_today = conn.execute("SELECT COUNT(*) FROM attendance_logs WHERE date = ? AND scan_method = 'Face'", (today,)).fetchone()[0]
    qr_today = conn.execute("SELECT COUNT(*) FROM attendance_logs WHERE date = ? AND scan_method = 'QR'", (today,)).fetchone()[0]

    # Recent activity (last 10) with scan_method
    recent = conn.execute(
        """SELECT a.log_id, a.user_id, r.first_name || ' ' || r.last_name AS user_name, a.date, a.time_in, a.attendance_status, a.device_id, a.scan_method
              FROM attendance_logs a JOIN registrants r ON r.user_id = a.user_id
             ORDER BY a.date DESC, a.logged_at DESC LIMIT 10"""
    ).fetchall()

    # Last 14 days attendance series
    series = conn.execute(
        """SELECT date, COUNT(*) AS cnt FROM attendance_logs
             WHERE date >= date(?, '-13 days') GROUP BY date ORDER BY date ASC""",
        (today,),
    ).fetchall()

    # RFID statistics (requested dashboard widgets)
    weekly_start = (now - datetime.timedelta(days=6)).strftime("%Y-%m-%d")
    monthly_start = now.replace(day=1).strftime("%Y-%m-%d")

    rfid_week = conn.execute(
        """SELECT COUNT(*) AS cnt FROM attendance_logs
             WHERE date >= ? AND scan_method = 'RFID'""",
        (weekly_start,),
    ).fetchone()["cnt"]

    rfid_month = conn.execute(
        """SELECT COUNT(*) AS cnt FROM attendance_logs
             WHERE date >= ? AND scan_method = 'RFID'""",
        (monthly_start,),
    ).fetchone()["cnt"]

    rfid_series = conn.execute(
        """SELECT date, COUNT(*) AS cnt FROM attendance_logs
             WHERE date >= date(?, '-13 days') AND scan_method = 'RFID'
             GROUP BY date ORDER BY date ASC""",
        (today,),
    ).fetchall()

    # Role distribution
    role_dist = conn.execute(
        "SELECT role, COUNT(*) AS cnt FROM registrants WHERE status = 'ACTIVE' GROUP BY role"
    ).fetchall()

    return {
        "total_students": total_students,
        "total_staff": total_staff,
        "attendance_today": attendance_today,
        "active_cameras": 1 if face_service.ready else 0,
        "recognition_success_rate": success_rate,
        "pending_approvals": pending_approvals + pending_profile,
        "month_attendance": month_attendance,
        "rfid_today": rfid_today,
        "face_today": face_today,
        "qr_today": qr_today,
        "recent": [dict(r) for r in recent],
        "series": [{"date": r["date"], "count": r["cnt"]} for r in series],
        "rfid_weekly_scans": rfid_week or 0,
        "rfid_monthly_scans": rfid_month or 0,
        "rfid_series": [{"date": r["date"], "count": r["cnt"]} for r in rfid_series],
        "role_distribution": [{"role": r["role"], "count": r["cnt"]} for r in role_dist],
        "face_model_status": face_service.health(),
    }


@router.post("/admin/users/{user_id}/reset-password", response_model=GenericResponse)
def admin_reset_password(
    user_id: str,
    body: dict,
    _admin: str = Depends(get_current_admin),
):
    new_password = (body.get("new_password") or "").strip()
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    conn = get_db_connection()
    row = conn.execute("SELECT user_id, first_name, last_name FROM registrants WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    conn.execute("UPDATE registrants SET password_hash = ? WHERE user_id = ?", (new_hash, user_id))
    conn.commit()
    create_notification(user_id, "Password reset by administrator", "Your password was reset by an administrator. Please use the new credentials.", "SECURITY")
    admin_email = get_admin_email(_admin)
    log_system_action(admin_email, "RESET_PASSWORD", f"Admin reset password for {user_id}")
    return GenericResponse(status="ok", message=f"Password reset for {user_id}")


@router.post("/admin/create-admin", response_model=GenericResponse)
def create_admin_account(body: CreateAdminRequest, _admin: str = Depends(get_current_admin)):
    main_admin = settings.main_admin_email.strip().lower()
    conn = get_db_connection()
    caller = conn.execute("SELECT email FROM admins WHERE admin_id = ?", (_admin,)).fetchone()
    if not caller or caller["email"].strip().lower() != main_admin:
        raise HTTPException(status_code=403, detail="Only the main administrator can create admin accounts")

    email = body.email
    existing = conn.execute("SELECT 1 FROM admins WHERE email = ?", (email,)).fetchone()
    if existing:
        raise HTTPException(status_code=409, detail="An admin with this email already exists")

    password_hash = bcrypt.hashpw(DEFAULT_PASSWORD.encode(), bcrypt.gensalt()).decode()
    admin_id = email.split("@")[0]
    now_str = pst_str()
    try:
        conn.execute(
            "INSERT INTO admins (admin_id, email, password_hash, first_name, last_name, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (admin_id, email, password_hash, body.first_name, body.last_name, now_str),
        )
        conn.commit()
    except Exception as e:
        raise HTTPException(status_code=409, detail=str(e))

    log_system_action(main_admin, "CREATE_ADMIN", f"Admin account created for {email} by main admin")
    return GenericResponse(status="ok", message=f"Admin account created. Email: {email}, Temporary Password: {DEFAULT_PASSWORD}")


def _require_main_admin(_admin: str):
    main_admin = settings.main_admin_email.strip().lower()
    conn = get_db_connection()
    caller = conn.execute("SELECT email FROM admins WHERE admin_id = ?", (_admin,)).fetchone()
    if not caller or caller["email"].strip().lower() != main_admin:
        raise HTTPException(status_code=403, detail="Only the main administrator can perform this action")
    return main_admin


@router.get("/admin/list-admins", response_model=list[AdminListRow])
def list_admins(_admin: str = Depends(get_current_admin)):
    _require_main_admin(_admin)
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT admin_id, email, first_name, last_name, COALESCE(status, 'ACTIVE') AS status, created_at FROM admins ORDER BY created_at DESC"
    ).fetchall()
    return [
        AdminListRow(
            admin_id=r["admin_id"],
            email=r["email"],
            first_name=r["first_name"],
            last_name=r["last_name"],
            status=r["status"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


@router.put("/admin/{admin_id}", response_model=GenericResponse)
def update_admin(admin_id: str, body: UpdateAdminRequest, _admin: str = Depends(get_current_admin)):
    _require_main_admin(_admin)
    conn = get_db_connection()
    row = conn.execute("SELECT admin_id FROM admins WHERE admin_id = ?", (admin_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Admin not found")
    conn.execute(
        "UPDATE admins SET first_name = ?, last_name = ? WHERE admin_id = ?",
        (body.first_name, body.last_name, admin_id),
    )
    conn.commit()
    log_system_action(settings.main_admin_email.strip().lower(), "UPDATE_ADMIN", f"Updated admin {admin_id}")
    return GenericResponse(status="ok", message=f"Admin {admin_id} updated")


@router.put("/admin/{admin_id}/status", response_model=GenericResponse)
def toggle_admin_status(admin_id: str, _admin: str = Depends(get_current_admin)):
    main_admin = _require_main_admin(_admin)
    conn = get_db_connection()
    row = conn.execute(
        "SELECT admin_id, COALESCE(status, 'ACTIVE') AS status FROM admins WHERE admin_id = ?", (admin_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Admin not found")
    if row["admin_id"] == _admin:
        raise HTTPException(status_code=400, detail="Cannot archive your own account")
    new_status = "ARCHIVED" if row["status"] == "ACTIVE" else "ACTIVE"
    conn.execute("UPDATE admins SET status = ? WHERE admin_id = ?", (new_status, admin_id))
    conn.commit()
    log_system_action(main_admin, "TOGGLE_ADMIN_STATUS", f"Changed admin {admin_id} status from {row['status']} to {new_status}")
    return GenericResponse(status="ok", message=f"Admin {admin_id} is now {new_status}")
