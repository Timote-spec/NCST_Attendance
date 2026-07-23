from datetime import datetime
from typing import Optional, List

import re
from pydantic import BaseModel, field_validator


# ─── Registrants ───────────────────────────────────────────────────

class RegisterRegistrantRequest(BaseModel):
    user_id: str
    first_name: str
    last_name: str
    role: str
    department_section: str
    email: str
    course: Optional[str] = None
    year_level: Optional[str] = None
    section: Optional[str] = None
    contact_number: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    rfid_uid: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("Email is required")
        if not re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("Invalid email format")
        return v


def _photo_url(user_id: str) -> str:
    return f"/api/v1/images/{user_id}"


class RegistrantResponse(BaseModel):
    user_id: str
    first_name: str
    last_name: str
    role: str
    department_section: str
    status: str
    email: str
    course: Optional[str] = None
    year_level: Optional[str] = None
    section: Optional[str] = None
    contact_number: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    photo_url: Optional[str] = None
    rfid_uid: Optional[str] = None
    created_at: Optional[datetime] = None
    temporary_password: Optional[str] = None

    class Config:
        from_attributes = True


class RegistrantListRow(BaseModel):
    user_id: str
    first_name: str
    last_name: str
    role: str
    department_section: str
    status: str
    email: Optional[str] = None
    contact_number: Optional[str] = None
    emergency_contact: Optional[str] = None
    rfid_uid: Optional[str] = None
    qr_token: Optional[str] = None
    section: Optional[str] = None
    photo_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MarkAttendanceRequest(BaseModel):
    device_id: str


class RfidAttendanceRequest(BaseModel):
    rfid_uid: str


class AttendanceLogResponse(BaseModel):
    user_id: str
    user_name: str
    logged_at: datetime
    device_id: str
    time_in: Optional[str] = None
    time_out: Optional[str] = None
    attendance_status: Optional[str] = None
    date: Optional[str] = None
    photo_url: Optional[str] = None
    section: Optional[str] = None
    course: Optional[str] = None
    year_level: Optional[str] = None
    department_section: Optional[str] = None
    scan_action: Optional[str] = None  # "in" | "out"; used by frontend scanner
    scan_method: Optional[str] = None

    class Config:
        from_attributes = True


# ─── Auth / Admin ──────────────────────────────────────────────────

class CreateAdminRequest(BaseModel):
    email: str
    first_name: str
    last_name: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("Email is required")
        if not re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("Invalid email format")
        return v

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("First name is required")
        if not re.match(r"^[a-zA-Z\s'-]+$", v):
            raise ValueError("First name must contain only letters")
        return v

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Last name is required")
        if not re.match(r"^[a-zA-Z\s'-]+$", v):
            raise ValueError("Last name must contain only letters")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str


class AdminResponse(BaseModel):
    admin_id: str
    email: str
    first_name: str
    last_name: str
    created_at: datetime

    class Config:
        from_attributes = True


class AdminListRow(BaseModel):
    admin_id: str
    email: str
    first_name: str
    last_name: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class UpdateAdminRequest(BaseModel):
    first_name: str
    last_name: str

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("First name is required")
        if not re.match(r"^[a-zA-Z\s'-]+$", v):
            raise ValueError("First name must contain only letters")
        return v

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Last name is required")
        if not re.match(r"^[a-zA-Z\s'-]+$", v):
            raise ValueError("Last name must contain only letters")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Optional[str] = None
    name: Optional[str] = None


class RequestOtpRequest(BaseModel):
    email: str


class VerifyOtpRequest(BaseModel):
    email: str
    otp: str


class ResetPasswordRequest(BaseModel):
    email: str
    otp: str
    new_password: str


class GenericResponse(BaseModel):
    status: str
    message: str


class LogRow(BaseModel):
    log_id: int
    user_id: str
    first_name: str
    last_name: str
    role: str
    department_section: str
    logged_at: datetime
    device_id: str
    time_in: Optional[str] = None
    time_out: Optional[str] = None
    attendance_status: Optional[str] = None
    date: Optional[str] = None
    photo_url: Optional[str] = None
    scan_method: Optional[str] = None

    class Config:
        from_attributes = True


class UpdateRegistrantRequest(BaseModel):
    first_name: str
    last_name: str
    role: str
    department_section: str
    email: Optional[str] = None
    course: Optional[str] = None
    year_level: Optional[str] = None
    section: Optional[str] = None
    contact_number: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    rfid_uid: Optional[str] = None


class AuditLogRow(BaseModel):
    log_id: int
    admin_email: str | None
    action: str
    details: str | None
    logged_at: datetime

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list


# ─── Student / Profile ─────────────────────────────────────────────

class StudentProfileResponse(BaseModel):
    user_id: str
    first_name: str
    last_name: str
    role: str
    department_section: str
    status: str
    email: Optional[str] = None
    course: Optional[str] = None
    year_level: Optional[str] = None
    section: Optional[str] = None
    contact_number: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    rfid_uid: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProfileUpdateRequest(BaseModel):
    field_name: str
    new_value: str


class ProfileUpdateResponse(BaseModel):
    id: int
    user_id: str
    field_name: str
    old_value: Optional[str]
    new_value: str
    status: str
    requested_at: datetime
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None

    class Config:
        from_attributes = True


class FaceRegistrationResponse(BaseModel):
    id: int
    user_id: str
    status: str
    captured_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ─── Announcements ─────────────────────────────────────────────────

class AnnouncementCreate(BaseModel):
    title: str
    content: str
    target_role: str = "ALL"
    is_pinned: bool = False


class AnnouncementResponse(BaseModel):
    id: int
    title: str
    content: str
    target_role: str
    created_by: str
    created_at: datetime
    is_pinned: int

    class Config:
        from_attributes = True


# ─── Notifications ─────────────────────────────────────────────────

class NotificationResponse(BaseModel):
    id: int
    user_id: str
    title: str
    message: str
    notification_type: str
    is_read: int
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Approvals ─────────────────────────────────────────────────────

class ApprovalRequestResponse(BaseModel):
    id: int
    user_id: str
    request_type: str
    details: Optional[str]
    status: str
    requested_at: datetime
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None

    class Config:
        from_attributes = True


class ApprovalDecision(BaseModel):
    decision: str
    notes: Optional[str] = None


# ─── Reports ───────────────────────────────────────────────────────

class ReportExportRequest(BaseModel):
    report_type: str
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    role: Optional[str] = None
    user_id: Optional[str] = None
    format: str = "csv"
