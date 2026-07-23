import base64
import io
import json
import uuid
from dataclasses import dataclass
from pathlib import Path

import qrcode
from cryptography.fernet import Fernet



from app.config import settings
from app.database import get_db_connection


@dataclass(frozen=True)
class QrPayload:
    user_id: str
    full_name: str
    role: str
    qr_token: str


_cached_key: bytes | None = None

def _require_crypto_key() -> bytes:
    global _cached_key
    if _cached_key is not None:
        return _cached_key

    key = getattr(settings, "qr_crypto_key", "")
    if not key:
        key = Fernet.generate_key().decode()
        _cached_key = key.encode()
        return _cached_key

    # Expect Fernet-compatible key (urlsafe base64). If user provides raw bytes/base64, accept as-is.
    # If it's hex, convert.
    if isinstance(key, str):
        k = key.strip()
        # Common case: Fernet key already.
        try:
            # Fernet will raise if invalid
            Fernet(k)
            _cached_key = k.encode()
            return _cached_key
        except Exception:
            pass
        # Try hex -> bytes -> base64 urlsafe.
        try:
            raw = bytes.fromhex(k)
            _cached_key = base64.urlsafe_b64encode(raw)
            return _cached_key
        except Exception as exc:
            raise RuntimeError("Invalid QR_CRYPTO_KEY format") from exc
    raise RuntimeError("Invalid QR crypto key")


def _fernet() -> Fernet:
    key_bytes = _require_crypto_key()
    return Fernet(key_bytes)


def build_payload(user_id: str, full_name: str, role: str, qr_token: str) -> QrPayload:
    return QrPayload(user_id=user_id, full_name=full_name, role=role, qr_token=qr_token)


def encrypt_payload(payload: QrPayload) -> str:
    body = json.dumps(payload.__dict__, separators=(",", ":"), sort_keys=True).encode("utf-8")
    token = _fernet().encrypt(body)
    return token.decode("utf-8")


def decrypt_payload(enc: str) -> QrPayload:
    raw = _fernet().decrypt(enc.encode("utf-8"))
    data = json.loads(raw.decode("utf-8"))
    return QrPayload(
        user_id=str(data["user_id"]),
        full_name=str(data["full_name"]),
        role=str(data["role"]),
        qr_token=str(data["qr_token"]),
    )


def generate_qr_png_bytes(qr_value: str) -> bytes:
    img = qrcode.make(qr_value)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


def ensure_qr_for_user(
    conn,
    user_id: str,
    *,
    force_regen: bool = False,
) -> None:
    """Idempotently ensure qr_token + encrypted payload + stored PNG image for a registrant."""

    row = conn.execute(
        """SELECT first_name, last_name, role, status, qr_token, qr_payload_enc, qr_image_path
           FROM registrants WHERE user_id = ?""",
        (user_id,),
    ).fetchone()
    if not row:
        raise RuntimeError(f"User not found: {user_id}")
    if row["status"] != "ACTIVE":
        # Still allow QR generation for archived? requirement focuses on new accounts; keep active-only.
        raise RuntimeError(f"User is not ACTIVE: {user_id}")

    qr_token = row["qr_token"]
    if force_regen or not qr_token:
        qr_token = uuid.uuid4().hex
        conn.execute("UPDATE registrants SET qr_token = ? WHERE user_id = ?", (qr_token, user_id))

    # If image/payload missing, we (re)create them.
    qr_payload_enc = row["qr_payload_enc"]
    qr_image_path = row["qr_image_path"]

    if force_regen or not qr_payload_enc or not qr_image_path:
        full_name = f"{row['first_name']} {row['last_name']}".strip()
        payload = build_payload(user_id=user_id, full_name=full_name, role=row["role"], qr_token=qr_token)
        enc = encrypt_payload(payload)

        # Store PNG
        uploads_base = Path(settings.upload_dir) / "qr"
        uploads_base.mkdir(parents=True, exist_ok=True)
        image_path = uploads_base / f"{user_id}.png"
        png_bytes = generate_qr_png_bytes(enc)

        # Overwrite
        image_path.write_bytes(png_bytes)
        new_path_str = str(image_path)

        conn.execute(
            """UPDATE registrants
               SET qr_payload_enc = ?, qr_image_path = ?, qr_token = ?
             WHERE user_id = ?""",
            (enc, new_path_str, qr_token, user_id),
        )

    conn.commit()


def download_path_for_user(conn, user_id: str) -> str | None:
    row = conn.execute("SELECT qr_image_path FROM registrants WHERE user_id = ?", (user_id,)).fetchone()
    if row and row["qr_image_path"]:
        return str(row["qr_image_path"])
    return None

