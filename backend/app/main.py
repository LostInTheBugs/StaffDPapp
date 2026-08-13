from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import init_db
from app.routes import auth, organization, meeting, time_entry, minute, vault, email, share

app = FastAPI(
    title="Staff Delegation",
    description="Outil de gestion pour les délégations du personnel au Luxembourg",
    version="2026.08.007",
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth.router)
app.include_router(organization.router)
app.include_router(meeting.router)
app.include_router(time_entry.router)
app.include_router(minute.router)
app.include_router(vault.router)
app.include_router(email.router)
app.include_router(share.router)


@app.on_event("startup")
def on_startup():
    init_db()
    # Rappels de réunion dus (idempotent — ne duplique rien)
    try:
        from app.core.database import SessionLocal
        from app.services.email_service import scan_due_reminders
        import os
        db = SessionLocal()
        try:
            n = scan_due_reminders(db, base_url=os.environ.get("SD_BASE_URL", ""))
            if n:
                print(f"[email] {n} rappel(s) de réunion mis en file")
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        print(f"[email] scan rappels ignoré : {e}")


@app.get("/api/health")
def health():
    return {"status": "ok"}
