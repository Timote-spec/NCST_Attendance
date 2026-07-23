# NCST Face Recognition Attendance System — Audit Report (Phase 1)

_Pre-modification analysis performed before any code changes._

## 1. Architecture Overview

| Layer | Technology | Notes |
|-------|-----------|-------|
| Backend API | FastAPI (0.111) + Uvicorn | Served on `0.0.0.0:8000` via `run.py` |
| ORM / DB | Raw `sqlite3` (WAL mode) | File DB `app/attendance.db`, thread-local connections |
| Auth | JWT (PyJWT, HS256) | Single secret, 1440-min expiry |
| Face recognition | InsightFace `buffalo_sc` + ONNXRuntime (CPU) | `FaceService` wraps `FaceAnalysis` |
| Matching | Cosine similarity vs stored float32 BLOB embeddings | Threshold from config (`0.65`) |
| Frontend | Static HTML/CSS/JS served via `StaticFiles` | Hash-router SPA shell in `index.html` |
| Email/OTP | SMTP + sha256-hashed OTP | Dev-mode console fallback |
| Tests | `test_api.py` (requests-based integration) | Assumes running server |

### Module map

```
app/
  main.py            app factory, CORS, route registration, page routes
  config.py          pydantic-settings (DB, JWT, SMTP, enrollment)
  database.py        schema DDL, migrations, admin seeding, audit log
  schemas.py         pydantic request/response models
  utils.py           PST timezone helper
  email_service.py   SMTP send + dev fallback
  otp_service.py     OTP generate/store/verify (rate-gated)
  services/face_service.py   InsightFace wrapper
  routes/
    auth.py          login, register-admin, forgot/reset password, /me
    register.py      registrant enrollment (face + profile)
    attendance.py    /verify (face → attendance)
    admin.py         users, logs, re-enroll, audit, bulk import
    students.py      student self-service (profile, attendance, face)
    staff.py         staff read views (attendance, students, scanner)
    announcements.py list/create/delete
    notifications.py  list/mark-read
    approvals.py      list/decide approval_requests
    reports.py        CSV/JSON export
frontend/
  login.html  register.html  forgot-password.html  scanner.html  index.html
```

## 2. Existing Capabilities (working)

- **Face enrollment** (`/register`) — captures face, computes embedding, stores BLOB.
- **Attendance verification** (`/verify`) — live face → cosine match → time-in/out log with duplicate prevention per day.
- **Admin auth** — login, admin-only registration via OTP approval, OTP password reset.
- **Student/Staff login** — reuses `registrants` table + bcrypt passwords.
- **Public scanner UI** (`scanner.html`) — functional kiosk with camera, auto-scan, results.
- **Auth pages** (`login/register/forgot-password`) — complete and functional.
- **Announcements, notifications, approvals, reports** — backend endpoints present.
- **Audit logging** — admin actions recorded.
- **Bulk import** — CSV-style row import for students.

## 3. Critical Issues (broken / incomplete)

### 3.1 Dashboard SPA is non-functional (HIGHEST PRIORITY)
`frontend/index.html` defines a hash `Router` and `NAV` config for ADMIN/STAFF/STUDENT, but **every page handler it calls is undefined**:
`overviewPanel, studentOverviewPanel, registrantsPanel, attendancePanel, auditPanel, scannerPanel, settingsPanel, approvalsPanel, announcementsPanel, notificationsPanel, profilePanel, facePanel, loadOverview, renderRegistrants, loadAttendance, loadAudit, showAddUserModal`.

Result: clicking any sidebar link renders an empty `#content`. **The entire Admin, Staff, and Student portal UI is missing.** This is the single biggest gap versus the project objective.

### 3.2 Student Portal absent
Backend exposes `/students/me/*` (profile, attendance, face, notifications, profile-update request) but there is **no student-facing UI**. The objective's dedicated Student Portal (dashboard, attendance module, profile, update-request workflow, face status) is unimplemented.

### 3.3 Approval & update workflows never complete
- `/students/me/profile-update-request` inserts into `profile_update_requests` but **no admin endpoint reviews or applies** these requests; `profile_update_requests` is never read or applied.
- No endpoint creates `approval_requests` for **face re-registration** or **account requests** (the table/UI for Approvals exists but is never fed).
- `face_registrations` table is created but **never used** (embeddings live in `registrants.face_embedding`).
- No notifications are generated when a request is submitted or decided.

### 3.4 Password recovery is admin-only
`/auth/forgot-password/*` and the reset backend query only the `admins` table. Students/Staff have no recovery path despite having passwords.

### 3.5 Announcements / Notifications have no management UI
Admin cannot create/delete announcements from the dashboard (no UI). Students/Staff have no view UI (the backend lists them, but nothing renders them).

## 4. Security Vulnerabilities

| # | Issue | Location | Risk |
|---|-------|----------|------|
| S1 | `jwt_secret_key="change-me"` default | `config.py` | Token forgery if unchanged |
| S2 | `CORSMiddleware(allow_origins=["*"], allow_credentials=True)` | `main.py` | Invalid + permissive CORS |
| S3 | No rate limiting on `/auth/login` or OTP endpoints | `auth.py` | Brute-force / OTP abuse |
| S4 | `open_enrollment=true` → `/register` needs no auth and creates accounts | `register.py` | Unauthorized account creation |
| S5 | Token stored in `localStorage` **and** non-HttpOnly cookie | `login.html` | XSS token theft |
| S6 | No CSRF protection on credential forms | all auth pages | CSRF on login/reset |
| S7 | Raw SQL string built in `update_my_profile` (whitelisted keys — OK) but no server-side field validation beyond whitelist | `students.py` | Low (mitigated) |
| S8 | `attendance.db`, `.env` could be committed (no guard enforced) | repo | Secret/PII leak |

Mitigations present: parameterized queries everywhere (no SQLi), bcrypt hashing, OTP expiry + 60s resend gate.

## 5. Database Issues

- **No indexes** on `attendance_logs(user_id, date)`, `registrants(email)`, `registrants(role,status)` → slow as data grows.
- **No explicit FK constraints** for most tables (only `attendance_logs` references `registrants` inline); `PRAGMA foreign_keys=ON` is set but DDL lacks `REFERENCES` clauses broadly.
- **Soft-delete** only partially modeled (`status ACTIVE/ARCHIVED`); no `deleted_at` and no restore endpoints (toggle only).
- **Redundant/unused** tables: `face_registrations`, `profile_update_requests` (write-only).
- `attendance_status` allows `LATE` in UI copy but never computed server-side.

## 6. UI / UX Inconsistencies

- Color tokens diverge from the prescribed brand: code uses Primary `#1E40AF` (spec `#1E3A8A`), Success `#22C55E` (spec `#16A34A`), and lacks Warning `#D97706` / Danger `#DC2626` tokens consistently. Login/register/forgot use slightly different palettes than the dashboard.
- No empty-state / loading-state / error-state components reused across pages (scanner has some; dashboard has none because it's empty).
- No breadcrumb, no pagination component (logs use raw `LIMIT/OFFSET` with no UI), no consistent card/table styling shared with auth pages.

## 7. Performance / Reliability

- `FaceService()` is instantiated as a **module global in 4 route modules** (`admin`, `attendance`, `register`, `students`) → InsightFace model (`buffalo_sc`) loads **multiple times**, wasting RAM and CPU and risking init races. Should be a single lazy singleton.
- `/verify` loads **all** active embeddings into memory each call (O(n)); acceptable at small scale but should be cached/incremental and add a similarity index note.
- No recognition-event log, camera-health endpoint for the admin view (staff has a basic one), or performance metrics.

## 8. Summary of Findings → Work Items

| Phase | Work |
|-------|------|
| P2 UI/UX | Rebuild `index.html` into a real SPA; enforce brand tokens (#1E3A8A etc.); shared components (cards, tables, modals, empty/loading/error states, pagination, breadcrumbs). |
| P3 Auth | Harden CORS, JWT secret, cookie attrs, rate limiting; extend password reset to Students/Staff; role selection already in login. |
| P4 Student Portal | Build full student SPA: dashboard, attendance module + export, profile, update-request workflow, face status/request. |
| P5 Admin | Build admin dashboard (stats), user/student management, approval center, attendance admin, announcements, audit. |
| P6 Staff | Build staff portal (attendance, students read-only, announcements, profile, scanner status). |
| P7 Face | Singleton service; camera-health + scanner diagnostics; recognition-event log; confidence/duplicate handling preserved. |
| P8 Scanner | Kiosk already functional; add health indicator + diagnostics to admin. |
| P9 DB | Indexes, FKs, notification helper, wire unused tables into workflows, restore endpoints. |
| P10 Security | Items S1–S8 above. |
| P11 QA | Extend `test_api.py`; validate import + server boot. |

_No working feature (face enrollment, verification, public scanner, admin auth) will be removed; all are preserved and wrapped in the new UI._
