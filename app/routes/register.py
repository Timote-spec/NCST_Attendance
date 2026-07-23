import bcrypt
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form

from app.config import settings
from app.database import get_db_connection, get_admin_email, log_system_action, pst_str
from app.email_service import send_welcome_email_async
from app.routes.auth import get_current_admin
from app.schemas import RegistrantResponse
from app.services.face_service import face_service

DEFAULT_PASSWORD = "Default123!"

router = APIRouter()


@router.post("/register", response_model=RegistrantResponse)
async def register_registrant(
    user_id: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    role: str = Form(...),
    department_section: str = Form(...),
    email: str = Form(...),
    password: str = Form(DEFAULT_PASSWORD),
    course: str = Form(""),
    year_level: str = Form(""),
    section: str = Form(""),
    contact_number: str = Form(""),
    address: str = Form(""),
    emergency_contact: str = Form(""),
    rfid_uid: str = Form(""),
    image: UploadFile = File(...),
    _admin: str | None = Depends(get_current_admin if not settings.open_enrollment else (lambda: None)),
):
    if role not in ("STUDENT", "STAFF", "FACULTY"):
        raise HTTPException(status_code=400, detail="Role must be STUDENT, STAFF, or FACULTY")

    image_bytes = await image.read()
    try:
        embedding = await face_service.extract_embedding(image_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    embedding_blob = np.array(embedding, dtype=np.float32).tobytes()

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    conn = get_db_connection()
    now_str = pst_str()
    try:
        conn.execute(
            """INSERT INTO registrants (user_id, first_name, last_name, role, department_section, face_embedding, status, created_at, email, password_hash, course, year_level, section, contact_number, address, emergency_contact, rfid_uid)
                   VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id, first_name, last_name, role, department_section, embedding_blob, now_str,
                email, password_hash, course or None, year_level or None,
                section or None, contact_number or None, address or None, emergency_contact or None,
                rfid_uid or None,
            ),
        )
        conn.commit()
    except Exception as e:
        raise HTTPException(status_code=409, detail=f"Registrant already exists: {e}")

    # Automatic QR generation for newly created registrants (token + encrypted payload + PNG).
    try:
        from app.services.qr_service import ensure_qr_for_user
        ensure_qr_for_user(conn, user_id, force_regen=False)
    except Exception:
        # Keep account creation unchanged even if QR crypto not configured.
        pass


    admin_email = get_admin_email(_admin) if _admin else None
    log_system_action(
        admin_email,
        "REGISTER_USER",
        f"Registered user {user_id} ({first_name} {last_name}) as {role}",
    )

    try:
        await send_welcome_email_async(email, first_name, user_id)
    except Exception:
        pass

    return RegistrantResponse(
        user_id=user_id,
        first_name=first_name,
        last_name=last_name,
        role=role,
        department_section=department_section,
        status="ACTIVE",
        email=email,
        course=course or None,
        year_level=year_level or None,
        section=section or None,
        contact_number=contact_number or None,
        address=address or None,
        emergency_contact=emergency_contact or None,
        rfid_uid=rfid_uid or None,
        photo_url=f"/api/v1/images/{user_id}",
        temporary_password=DEFAULT_PASSWORD,
    )
