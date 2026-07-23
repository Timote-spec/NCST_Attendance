import os
import uuid
import io
from pathlib import Path

import qrcode
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from fastapi.responses import FileResponse, Response

from app.config import settings
from app.database import get_db_connection
from app.routes.auth import get_current_user
from app.schemas import GenericResponse

# NOTE: Images must be served from the persistent filesystem under settings.upload_dir
# and the corresponding URL must be stable across logins, refreshes, and restarts.


router = APIRouter()
UPLOAD_DIR = Path(settings.upload_dir)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png"}


async def _validate_image(file: UploadFile) -> bytes:
    if file.content_type not in settings.allowed_image_types:
        raise HTTPException(status_code=400, detail="Only JPG, JPEG, and PNG images are allowed")
    data = await file.read()
    if len(data) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File size exceeds {settings.max_upload_size_mb}MB limit")
    ext = Path(file.filename or "image.jpg").suffix.lower()
    if ext not in PHOTO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="File extension must be .jpg, .jpeg, or .png")
    return data


def _save_photo(image_bytes: bytes, ext: str) -> str:
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = UPLOAD_DIR / filename
    filepath.write_bytes(image_bytes)
    return str(filepath)


def _delete_photo(filepath: str):
    path = Path(filepath)
    if path.exists():
        path.unlink()


@router.post("/upload/photo", response_model=GenericResponse)
async def upload_photo(image: UploadFile = File(...), _user: dict = Depends(get_current_user)):
    data = await _validate_image(image)
    ext = Path(image.filename or "photo.jpg").suffix.lower()
    photo_path = _save_photo(data, ext)
    conn = get_db_connection()
    old = conn.execute("SELECT photo_path FROM registrants WHERE user_id = ?", (_user["user_id"],)).fetchone()
    if old and old["photo_path"]:
        _delete_photo(old["photo_path"])
    conn.execute("UPDATE registrants SET photo_path = ? WHERE user_id = ?", (photo_path, _user["user_id"]))
    conn.commit()
    return GenericResponse(status="ok", message="Photo uploaded successfully")


@router.get("/images/{user_id}")
def get_photo(user_id: str):
    conn = get_db_connection()
    row = conn.execute("SELECT photo_path FROM registrants WHERE user_id = ?", (user_id,)).fetchone()
    if row and row["photo_path"]:
        path = Path(row["photo_path"])
        if path.exists():
            return FileResponse(str(path), headers={"Cache-Control": "private, max-age=3600"})
    fallback = Path("frontend/images/default-avatar.png")

    if fallback.exists():
        return FileResponse(str(fallback), headers={"Cache-Control": "public, max-age=86400"})
    return Response(status_code=204)


@router.get("/qr/{user_id}")
def get_qr_code(user_id: str):
    conn = get_db_connection()
    row = conn.execute("SELECT qr_image_path FROM registrants WHERE user_id = ?", (user_id,)).fetchone()
    if not row or not row["qr_image_path"]:
        raise HTTPException(status_code=404, detail="QR code not generated for this user")

    path = Path(row["qr_image_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="QR image file not found")

    return FileResponse(str(path), media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})

