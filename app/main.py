import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import init_db
from app.routes.admin import router as admin_router
from app.routes.attendance import router as attendance_router
from app.routes.auth import router as auth_router
from app.routes.register import router as register_router
from app.routes.students import router as students_router
from app.routes.staff import router as staff_router
from app.routes.announcements import router as announcements_router
from app.routes.notifications import router as notifications_router
from app.routes.approvals import router as approvals_router
from app.routes.reports import router as reports_router
from app.routes.images import router as images_router
from app.routes.dashboard import router as dashboard_router
from app.services.face_service import face_service
from app.services.rate_limit import limiter

app = FastAPI(title="NCST Face Recognition Attendance System")

# CORS: never combine wildcard origin with credentials. If a wildcard is
# configured we drop credentials to keep the policy valid and safe.
allow_credentials = settings.cors_origins != ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def global_rate_limit(request: Request, call_next):
    # Protect unauthenticated, high-risk endpoints.
    path = request.url.path
    if path.startswith("/api/v1/auth") or path.startswith("/api/v1/verify") or path.startswith("/api/v1/attendance/rfid") or path == "/api/v1/rfid":
        client = request.client.host if request.client else "unknown"
        key = f"global:{client}"
        if not limiter.is_allowed(key, limit=settings.rate_limit_per_minute):
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down and try again."},
            )
    return await call_next(request)


@app.on_event("startup")
def startup():
    init_db()


app.include_router(auth_router, prefix="/api/v1", tags=["Auth"])
app.include_router(register_router, prefix="/api/v1", tags=["Registration"])
app.include_router(attendance_router, prefix="/api/v1", tags=["Attendance"])
app.include_router(admin_router, prefix="/api/v1", tags=["Admin"])
app.include_router(students_router, prefix="/api/v1", tags=["Students"])
app.include_router(staff_router, prefix="/api/v1", tags=["Staff"])
app.include_router(announcements_router, prefix="/api/v1", tags=["Announcements"])
app.include_router(notifications_router, prefix="/api/v1", tags=["Notifications"])
app.include_router(approvals_router, prefix="/api/v1", tags=["Approvals"])
app.include_router(reports_router, prefix="/api/v1", tags=["Reports"])
app.include_router(images_router, prefix="/api/v1", tags=["Images"])
app.include_router(dashboard_router, prefix="/api/v1", tags=["Dashboard"])

app.mount("/static", StaticFiles(directory="frontend"), name="static")


# ─── Professional HTML error pages (SPA) ──────────────────────────────
_ERROR_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NCST — {title}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/static/assets/css/styles.css">
  <style>
    .err-wrap {{ min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 1.5rem;
      background: linear-gradient(135deg, var(--surface-1) 0%, var(--surface-2) 100%); }}
    .err-card {{ width: 100%; max-width: 460px; background: var(--surface); border: 1px solid var(--border);
      border-radius: 18px; box-shadow: 0 20px 50px rgba(15, 23, 42, .12); padding: 2.25rem; text-align: center; }}
    .err-brand {{ display: flex; align-items: center; justify-content: center; gap: .6rem; margin-bottom: 1.25rem; font-weight: 700; color: var(--text); }}
    .err-brand img {{ width: 34px; height: 34px; border-radius: 8px; }}
    .err-code {{ font-size: 3.5rem; font-weight: 800; line-height: 1; letter-spacing: -1px;
      background: linear-gradient(135deg, var(--primary), var(--accent)); -webkit-background-clip: text; background-clip: text; color: transparent; }}
    .err-card h1 {{ font-size: 1.4rem; margin: .5rem 0 .4rem; color: var(--text); }}
    .err-card p {{ color: var(--muted); margin: 0 0 1.5rem; line-height: 1.5; }}
    .err-actions {{ display: flex; gap: .75rem; justify-content: center; flex-wrap: wrap; }}
    .err-links {{ margin-top: 1.5rem; font-size: .85rem; color: var(--muted); }}
    .err-links a {{ color: var(--accent); text-decoration: none; font-weight: 500; }}
    .err-links a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <div class="err-wrap">
    <div class="err-card">
      <div class="err-brand"><img src="/static/images/ncst-logo.png" alt="NCST"> <span>NCST Face Recognition</span></div>
      <div class="err-code">{code}</div>
      <h1>{title}</h1>
      <p>{message}</p>
      <div class="err-actions">
        <a class="btn btn-primary" href="/">Return to Dashboard</a>
        <a class="btn btn-secondary" href="/login">Sign In</a>
      </div>
      <div class="err-links">Quick links: <a href="/">Dashboard</a> · <a href="/login">Login</a> · <a href="/scanner">Scanner</a></div>
    </div>
  </div>
</body>
</html>"""


def _is_api_request(request: Request) -> bool:
    return request.url.path.startswith("/api/") or request.url.path.startswith("/static/")


def _error_html(status_code: int, title: str, message: str) -> HTMLResponse:
    html = _ERROR_PAGE.format(code=status_code, title=title, message=message)
    return HTMLResponse(content=html, status_code=status_code)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    # API and static asset requests keep the JSON contract.
    if _is_api_request(request):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    if exc.status_code == 404:
        return _error_html(404, "Page Not Found", "The page you are looking for does not exist or may have been moved.")
    if exc.status_code == 403:
        return _error_html(403, "Forbidden", "You do not have permission to access this resource.")
    if exc.status_code == 401:
        return _error_html(401, "Unauthorized", "Your session is missing or invalid. Please sign in to continue.")
    return _error_html(exc.status_code, "Error", str(exc.detail) or "An unexpected error occurred.")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    traceback.print_exc()
    if _is_api_request(request):
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
    return _error_html(500, "Internal Server Error", "Something went wrong on our end. Our team has been notified.")


@app.get("/api/v1/health/face")
def face_health():
    return face_service.health()


@app.get("/", response_class=FileResponse)
async def read_index():
    return FileResponse("frontend/index.html")


@app.get("/login", response_class=FileResponse)
async def read_login():
    return FileResponse("frontend/login.html")


@app.get("/forgot-password", response_class=FileResponse)
async def read_forgot_password():
    return FileResponse("frontend/forgot-password.html")


@app.get("/scanner", response_class=FileResponse)
async def read_scanner():
    return FileResponse("frontend/scanner.html")


@app.get("/rfid-scanner", response_class=FileResponse)
async def read_rfid_scanner():
    return FileResponse("frontend/rfid-scanner.html")


@app.get("/gate-scanner", response_class=FileResponse)
async def read_gate_scanner():
    return FileResponse("frontend/gate-scanner.html")


@app.get("/dashboard/{path:path}", response_class=FileResponse)
async def read_dashboard_spa(path: str):
    """Serve the SPA shell for bookmarked dashboard paths (hash router takes over)."""
    return FileResponse("frontend/index.html")


@app.get("/health")
def health_check():
    return {"status": "ok"}
