# NCST Face Recognition Attendance System

Face recognition + QR code attendance system with FastAPI backend and vanilla JS frontend.

---

## How to Run

```bash
git clone <repo-url>
cd ncst-face-detection-system
python -m venv .venv
.venv\Scripts\activate            # Linux: source .venv/bin/activate
pip install -r requirements.txt
python run.py                     # http://localhost:8000
```

No database setup needed — SQLite database (`app/attendance.db`) is auto-created and seeded on first boot.

---

## Default Test Accounts

| Role | Email | Password |
|------|-------|----------|
| Administrator | `admin@ncst.edu` | `admin123` |
| Staff | `staff@ncst.edu` | `staff123` |
| Student | `student@ncst.edu` | `student123` |

---

## Tech Stack

- **Backend:** FastAPI + Uvicorn
- **Database:** SQLite (auto-created, no setup)
- **Face Recognition:** InsightFace (`buffalo_sc` model)
- **Frontend:** Vanilla HTML/CSS/JS (no framework)

---

## Project Structure

```
app/           — FastAPI backend (routes, services, config, seeders)
frontend/      — HTML pages, CSS, JS, images
uploads/       — Student photo uploads
run.py         — Entry point (uvicorn)
```

## Key Endpoints

| Path | Description |
|------|-------------|
| `/` | Login page |
| `/scanner` | Kiosk scanner (face + QR) |
| `/dashboard/overview` | Portal (role-based) |
| `/api/v1/health` | Health check |
| `/api/v1/auth/login` | Login API |
| `/api/v1/verify` | Face recognition attendance |
| `/api/v1/verify/qr` | QR code attendance |

---

## Environment Config (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `MIN_ATTENDANCE_INTERVAL_MINUTES` | 120 | Min time between IN and OUT |
| `LATE_CUTOFF_TIME` | 08:00 | Scans after this = LATE |
| `SCAN_COOLDOWN_SECONDS` | 30 | Per-person scan cooldown |
| `MATCHING_THRESHOLD` | 0.65 | Face similarity cutoff |
| `JWT_SECRET_KEY` | (auto) | JWT signing secret |
