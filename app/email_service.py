import asyncio
import logging
import os
import subprocess
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)


def is_email_configured() -> bool:
    return bool(
        settings.smtp_host.strip()
        and settings.smtp_user.strip()
        and settings.smtp_password.strip()
    )


def _build_html_body(template: str, **kwargs) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {{ margin:0; padding:0; background:#F4F7FC; font-family:'Segoe UI',Arial,sans-serif; }}
    .wrap {{ max-width:560px; margin:0 auto; padding:32px 16px; }}
    .card {{ background:#fff; border-radius:10px; padding:32px; box-shadow:0 2px 12px rgba(0,0,0,0.06); }}
    .logo {{ text-align:center; margin-bottom:20px; }}
    .logo img {{ width:100px; height:auto; }}
    h1 {{ font-size:20px; color:#1E3A8A; margin:0 0 8px; text-align:center; }}
    p {{ font-size:15px; color:#374151; line-height:1.6; margin:0 0 16px; }}
    .otp {{ display:inline-block; background:#EEF2FF; color:#1E40AF; font-size:28px; font-weight:700;
            letter-spacing:6px; padding:12px 24px; border-radius:8px; margin:8px 0 16px; font-family:monospace; }}
    .footer {{ font-size:12px; color:#9CA3AF; text-align:center; margin-top:20px; }}
    hr {{ border:none; border-top:1px solid #E5E7EB; margin:20px 0; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <div class="logo"><img src="https://i.imgur.com/hq6JAHj.png" alt="NCST Logo"></div>
      {template.format(**kwargs)}
      <hr>
      <p style="font-size:13px;color:#6B7280;">NCST Face Recognition System &bull; OTP expires in {settings.otp_expiry_minutes} minutes</p>
    </div>
    <div class="footer">&copy; {datetime.now().year} NCST. All rights reserved.</div>
  </div>
</body>
</html>"""


_OTP_HTML_TPL = """
<h1>Password Reset Request</h1>
<p>Hello,</p>
<p>We received a request to reset the password for your NCST Face Recognition account.</p>
<p style="text-align:center;"><span class="otp">{otp}</span></p>
<p>Enter this code on the password reset page. If you did not request this, please ignore this email.</p>
"""


def _otp_text(otp: str) -> str:
    return (
        f"Hello,\n\n"
        f"You requested a password reset for your NCST Face Recognition account.\n\n"
        f"Your one-time password (OTP) is: {otp}\n\n"
        f"This code expires in {settings.otp_expiry_minutes} minutes. "
        f"If you did not request this, you can ignore this email.\n\n"
        f"\u2014 NCST Face Recognition System"
    )


_REGISTRATION_HTML_TPL = """
<h1>New Admin Registration Approval</h1>
<p>Hello Administrator,</p>
<p>Someone is attempting to create a new NCST Face Recognition admin account.</p>
<p><strong>Registering email:</strong> {registering_email}</p>
<p style="text-align:center;"><span class="otp">{otp}</span></p>
<p>Share this code with the person registering only if you approve this account.<br>
If you did not expect this request, ignore this email and do not share the code.</p>
"""


_WELCOME_HTML_TPL = """
<h1>Welcome to NCST Attendance</h1>
<p>Hello {first_name},</p>
<p>Your account has been created on the NCST Face Recognition Attendance System.</p>
<p><strong>User ID:</strong> {user_id}</p>
<p><strong>Email:</strong> {email}</p>
<p style="text-align:center;"><span class="otp">{password}</span></p>
<p>Please log in with the temporary password above and change it immediately from your profile settings.</p>
<p>If you did not expect this account, please contact your administrator.</p>
"""


def _welcome_text(first_name: str, user_id: str, email: str, password: str) -> str:
    return (
        f"Hello {first_name},\n\n"
        f"Your account has been created on the NCST Face Recognition Attendance System.\n\n"
        f"User ID: {user_id}\n"
        f"Email: {email}\n"
        f"Temporary Password: {password}\n\n"
        f"Please log in with the temporary password above and change it immediately "
        f"from your profile settings.\n\n"
        f"If you did not expect this account, please contact your administrator.\n\n"
        f"\u2014 NCST Face Recognition System"
    )


def _registration_text(otp: str, registering_email: str) -> str:
    return (
        f"Hello Administrator,\n\n"
        f"Someone is attempting to create a new NCST Face Recognition admin account.\n\n"
        f"Registering email: {registering_email}\n\n"
        f"Approval verification code: {otp}\n\n"
        f"Share this code with the person registering only if you approve this account.\n"
        f"This code expires in {settings.otp_expiry_minutes} minutes.\n\n"
        f"If you did not expect this request, ignore this email and do not share the code.\n\n"
        f"\u2014 NCST Face Recognition System"
    )


def _send_email(to_email: str, subject: str, body_text: str, body_html: str | None = None) -> None:
    if not is_email_configured():
        logger.warning(
            "SMTP not fully configured — email to %s not sent. "
            "Set SMTP_HOST, SMTP_USER, and SMTP_PASSWORD in .env. Subject: %s",
            to_email,
            subject,
        )
        print(f"[DEV-PHP] Email to {to_email}\nSubject: {subject}\n\n{body_text}")
        return

    # Build environment variables for the PHP process
    php_env = os.environ.copy()
    php_env["SMTP_HOST"] = settings.smtp_host
    php_env["SMTP_PORT"] = str(settings.smtp_port)
    php_env["SMTP_USER"] = settings.smtp_user
    php_env["SMTP_PASSWORD"] = settings.smtp_password
    php_env["SMTP_FROM_EMAIL"] = settings.smtp_from_email or settings.smtp_user
    php_env["SMTP_USE_TLS"] = str(settings.smtp_use_tls)
    php_env["SMTP_USE_SSL"] = str(settings.smtp_use_ssl)

    # Paths relative to working directory (root of project)
    php_bin = os.path.join("php_runtime", "php.exe")
    php_script = os.path.join("php_mailer", "send_email.php")

    if not os.path.isfile(php_bin) or not os.path.isfile(php_script):
        logger.warning(
            "PHP mailer not found (%s or %s missing). "
            "Falling back to print — email to %s not sent.",
            php_bin, php_script, to_email,
        )
        print(f"[EMAIL] To: {to_email}\nSubject: {subject}\n\n{body_text}")
        return

    cmd = [
        php_bin,
        php_script,
        to_email,
        subject,
        body_html or "",
        body_text
    ]

    try:
        logger.info("Executing PHPMailer script to send email to %s...", to_email)
        result = subprocess.run(
            cmd,
            env=php_env,
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )
        logger.info("PHPMailer subprocess stdout: %s", result.stdout)
    except subprocess.CalledProcessError as e:
        logger.error(
            "PHPMailer subprocess failed with exit code %d. Stdout: %s. Stderr: %s",
            e.returncode,
            e.stdout,
            e.stderr
        )
        raise RuntimeError(f"PHPMailer error: {e.stderr or e.stdout}") from e
    except subprocess.TimeoutExpired as e:
        logger.error("PHPMailer subprocess timed out after 30 seconds.")
        raise RuntimeError("PHPMailer timed out.") from e
    except Exception as e:
        logger.error("Unexpected error running PHPMailer: %s", e)
        raise RuntimeError(f"Unexpected mailer error: {e}") from e


def send_otp_email(to_email: str, otp: str) -> None:
    subject = "NCST Face Recognition \u2014 Password Reset OTP"
    body_text = _otp_text(otp)
    body_html = _build_html_body(_OTP_HTML_TPL, otp=otp)
    _send_email(to_email, subject, body_text, body_html)


def send_registration_verification_email(
    admin_email: str,
    otp: str,
    *,
    registering_email: str,
) -> None:
    subject = "NCST Face Recognition \u2014 New Admin Registration Approval"
    body_text = _registration_text(otp, registering_email)
    body_html = _build_html_body(_REGISTRATION_HTML_TPL, otp=otp, registering_email=registering_email)
    _send_email(admin_email, subject, body_text, body_html)


async def send_otp_email_async(to_email: str, otp: str) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, send_otp_email, to_email, otp)


async def send_registration_verification_email_async(
    admin_email: str,
    otp: str,
    *,
    registering_email: str,
) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        send_registration_verification_email,
        admin_email,
        otp,
        registering_email=registering_email,
    )


def send_welcome_email(to_email: str, first_name: str, user_id: str) -> None:
    password = "Default123!"
    subject = "NCST Face Recognition \u2014 Welcome &amp; Account Created"
    body_text = _welcome_text(first_name, user_id, to_email, password)
    body_html = _build_html_body(_WELCOME_HTML_TPL, first_name=first_name, user_id=user_id, email=to_email, password=password)
    _send_email(to_email, subject, body_text, body_html)


async def send_welcome_email_async(to_email: str, first_name: str, user_id: str) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, send_welcome_email, to_email, first_name, user_id)
