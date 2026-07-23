from datetime import datetime, timedelta, timezone

import bcrypt as _bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.database import (
    create_notification,
    find_user_by_email,
    get_db_connection,
    get_admin_email,
    log_system_action,
    pst_str,
)
from app.email_service import send_otp_email
from app.services.rate_limit import limiter
from app.otp_service import (
    OTP_PURPOSE_PASSWORD_RESET,
    generate_otp,
    store_password_reset_otp,
    verify_password_reset_otp,
    can_request_password_reset_otp,
)
from app.schemas import (
    GenericResponse,
    LoginRequest,
    RequestOtpRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyOtpRequest,
)

router = APIRouter()
_security = HTTPBearer(auto_error=False)


# ─── JWT helpers ───────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def _verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    return _bcrypt.checkpw(password.encode(), password_hash.encode())


def _create_token(user_id: str, role: str = "ADMIN") -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expiry_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
) -> str:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        admin_id = payload["sub"]
        conn = get_db_connection()
        row = conn.execute("SELECT 1 FROM admins WHERE admin_id = ?", (admin_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin not found")
        return admin_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
):
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = payload["sub"]
        role = payload.get("role", "STUDENT")
        conn = get_db_connection()
        if role == "ADMIN":
            row = conn.execute("SELECT admin_id as user_id, email as name, 'ADMIN' as role FROM admins WHERE admin_id = ?", (user_id,)).fetchone()
        else:
            row = conn.execute(
                "SELECT user_id, (first_name || ' ' || last_name) as name, role FROM registrants WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return {"user_id": row["user_id"], "name": row["name"], "role": row["role"]}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


# ─── Endpoints ─────────────────────────────────────────────────────

def _send_email_or_fail(send_fn, *args) -> None:
    try:
        send_fn(*args)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send email. Check SMTP settings in .env ({exc})",
        ) from exc


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    if not limiter.is_allowed(f"login:{client_ip}", limit=settings.rate_limit_login_per_minute):
        raise HTTPException(
            status_code=429,
            detail=f"Too many login attempts. Try again in {limiter.retry_after(f'login:{client_ip}')}s.",
        )

    email = body.email.strip().lower()
    account = find_user_by_email(email)

    if not account or not _verify_password(body.password, account["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if account["kind"] == "ADMIN" and account.get("status") == "ARCHIVED":
        raise HTTPException(status_code=403, detail="This admin account has been archived.")

    if account["kind"] == "REGISTRANT" and account.get("status") == "ARCHIVED":
        raise HTTPException(status_code=403, detail="This account has been archived.")

    if account["kind"] == "ADMIN":
        role = "ADMIN"
        sub = account["id"]
        name = account["email"]
    else:
        role = account["role"]
        sub = account["id"]
        name = f"{account['first_name']} {account['last_name']}"

    token = _create_token(sub, role=role)
    log_system_action(
        account["email"] if role == "ADMIN" else None,
        "LOGIN",
        f"{role} {sub} ({name}) signed in",
    )
    return TokenResponse(access_token=token, role=role, name=name)


@router.post("/auth/logout", response_model=GenericResponse)
def logout(_user: dict = Depends(get_current_user)):
    email = _user.get("name") if _user.get("role") == "ADMIN" else None
    log_system_action(email, "LOGOUT", f"User {_user['user_id']} signed out")
    return GenericResponse(status="ok", message="Signed out")


@router.post("/auth/change-password", response_model=GenericResponse)
def change_password(body: dict, _user: dict = Depends(get_current_user)):
    old_pw = (body.get("old_password") or "").strip()
    new_pw = (body.get("new_password") or "").strip()
    if len(new_pw) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
    conn = get_db_connection()
    if _user["role"] == "ADMIN":
        row = conn.execute("SELECT password_hash FROM admins WHERE admin_id = ?", (_user["user_id"],)).fetchone()
        if not row or not _verify_password(old_pw, row["password_hash"]):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        conn.execute("UPDATE admins SET password_hash = ? WHERE admin_id = ?", (_hash_password(new_pw), _user["user_id"]))
    else:
        row = conn.execute("SELECT password_hash FROM registrants WHERE user_id = ?", (_user["user_id"],)).fetchone()
        if not row or not _verify_password(old_pw, row["password_hash"]):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        conn.execute("UPDATE registrants SET password_hash = ? WHERE user_id = ?", (_hash_password(new_pw), _user["user_id"]))
    conn.commit()
    if _user["role"] != "ADMIN":
        create_notification(_user["user_id"], "Password changed", "Your password was changed successfully.", "SECURITY")
    log_system_action(None, "PASSWORD_CHANGE", f"User {_user['user_id']} changed password")
    return GenericResponse(status="ok", message="Password updated successfully")


@router.get("/auth/me")
def me(_user: dict = Depends(get_current_user)):
    return _user


@router.get("/admin/me")
def get_admin_profile(_admin: str = Depends(get_current_admin)):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT admin_id, email, first_name, last_name, created_at FROM admins WHERE admin_id = ?",
        (_admin,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Admin not found")
    data = dict(row)
    data["main_admin_email"] = settings.main_admin_email.strip().lower()
    return data


@router.post("/auth/forgot-password/request-otp", response_model=GenericResponse)
def request_password_otp(body: RequestOtpRequest, request: Request):
    email = body.email.strip().lower()
    client_ip = request.client.host if request.client else "unknown"
    if not limiter.is_allowed(f"otp:{client_ip}", limit=settings.rate_limit_login_per_minute):
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")

    account = find_user_by_email(email)
    if not account:
        # Avoid account enumeration: still return success-style message.
        return GenericResponse(
            status="ok",
            message="If an account exists, a verification code has been sent to your email.",
        )

    if not can_request_password_reset_otp(email):
        raise HTTPException(
            status_code=429,
            detail="Please wait a minute before requesting another OTP",
        )

    otp = generate_otp()
    store_password_reset_otp(account["id"], email, otp)
    _send_email_or_fail(send_otp_email, email, otp)

    log_system_action(email if account["kind"] == "ADMIN" else None, "OTP_REQUEST", f"Password reset OTP requested for {email}")

    return GenericResponse(
        status="ok",
        message="A verification code has been sent to your email",
    )


@router.post("/auth/forgot-password/verify-otp", response_model=GenericResponse)
def verify_forgot_password_otp(body: VerifyOtpRequest):
    email = body.email.strip().lower()
    otp = body.otp.strip()

    account = find_user_by_email(email)
    if not account:
        raise HTTPException(status_code=404, detail="No account found with this email")

    if not verify_password_reset_otp(email, otp):
        raise HTTPException(
            status_code=400,
            detail="Invalid, expired, or locked-out verification code"
        )

    return GenericResponse(
        status="ok",
        message="Verification code approved. You may now reset your password."
    )


@router.post("/auth/forgot-password/reset", response_model=GenericResponse)
def reset_password_with_otp(body: ResetPasswordRequest):
    email = body.email.strip().lower()
    otp = body.otp.strip()

    # 1. Enforce password complexity check
    pw = body.new_password
    if len(pw) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if not (any(c.isupper() for c in pw) and any(c.islower() for c in pw) and any(c.isdigit() for c in pw)):
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least one uppercase letter, one lowercase letter, and one number"
        )

    account = find_user_by_email(email)
    if not account:
        raise HTTPException(status_code=404, detail="No account found with this email")

    # 2. Verify that there is a verified OTP in the DB that hasn't expired yet
    conn = get_db_connection()
    now_str = pst_str()
    row = conn.execute(
        """
        SELECT id, user_id FROM password_reset_otps
        WHERE email = ? AND verified = 1 AND expires_at > ?
        ORDER BY created_at DESC LIMIT 1
        """,
        (email, now_str),
    ).fetchone()

    if not row:
        raise HTTPException(
            status_code=400,
            detail="Password reset session expired or OTP not verified. Please verify OTP first."
        )

    # 3. Securely hash password and update
    new_hash = _hash_password(pw)
    if account["kind"] == "ADMIN":
        conn.execute("UPDATE admins SET password_hash = ? WHERE email = ?", (new_hash, email))
    else:
        conn.execute("UPDATE registrants SET password_hash = ? WHERE user_id = ?", (new_hash, account["id"]))

    # 4. Invalidate the OTP (mark verified = 2 for used)
    conn.execute(
        "UPDATE password_reset_otps SET verified = 2, updated_at = ? WHERE id = ?",
        (now_str, row["id"]),
    )
    conn.commit()

    if account["kind"] == "REGISTRANT":
        create_notification(account["id"], "Password changed", "Your account password was reset successfully.", "SECURITY")

    log_system_action(email if account["kind"] == "ADMIN" else None, "PASSWORD_RESET", f"Password reset for {email}")

    return GenericResponse(status="ok", message="Password has been reset successfully")
