from pydantic_settings import BaseSettings, SettingsConfigDict
import secrets


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_path: str = "app/attendance.db"
    matching_threshold: float = 0.65
    cors_origins: list[str] = ["*"]

    # ── Security ────────────────────────────────────────────────
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 1440
    # HttpOnly cookie used only when "Remember me" is selected; the SPA
    # still reads the token via the Authorization header after login.
    cookie_secure: bool = False
    cookie_samesite: str = "Lax"

    # In-memory rate limiting (requests per window)
    rate_limit_per_minute: int = 60
    rate_limit_login_per_minute: int = 10

    # ── Uploads ────────────────────────────────────────────────
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 5
    allowed_image_types: list[str] = ["image/jpeg", "image/png"]

    # ── Attendance ─────────────────────────────────────────────
    scan_cooldown_seconds: int = 30
    min_attendance_interval_minutes: int = 120  # Min minutes between IN and OUT
    late_cutoff_time: str = "08:00"  # Scans after this HH:MM are marked LATE

    # ── Enrollment ─────────────────────────────────────────────
    open_enrollment: bool = True
    allowed_registration_email: str = "paullacuesta732@gmail.com"
    main_admin_email: str = "admin@ncst.edu.ph"

    # ── QR Crypto ───────────────────────────────────────────────
    # Must be a valid Fernet key (urlsafe base64 32-byte key). Example: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    qr_crypto_key: str = ""

    # ── SMTP ───────────────────────────────────────────────────
    smtp_host: str = ""

    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    otp_expiry_minutes: int = 10

    @property
    def is_default_secret(self) -> bool:
        return not self.jwt_secret_key or self.jwt_secret_key in (
            "change-me", "change-me-to-a-random-secret", ""
        )


settings = Settings()

if settings.is_default_secret:
    # Runtime warning only; do not fail boot so local dev still works.
    import warnings
    warnings.warn(
        "JWT_SECRET_KEY is using the insecure default ('change-me'). "
        "Set a strong random secret in .env before deploying.",
        stacklevel=2,
    )
