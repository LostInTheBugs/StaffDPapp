from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import assert_secret_key_is_set
from app.core.database import init_db
from app.routes import auth, organization, meeting, time_entry, minute, vault, email, share, consultation, workforce_stat, annual_report, delegate_activity, notice, compliance, election, legal

# Garde de sécurité : refuse le démarrage si SD_SECRET_KEY est absente,
# trop courte ou égale à une valeur d'exemple (jetons JWT forgeables).
assert_secret_key_is_set()

app = FastAPI(
    title="Staff Delegation",
    description="Outil de gestion pour les délégations du personnel au Luxembourg",
    version="2026.08.030",
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
app.include_router(consultation.router)
app.include_router(workforce_stat.router)
app.include_router(annual_report.router)
app.include_router(delegate_activity.router)
app.include_router(notice.router)
app.include_router(compliance.router)
app.include_router(election.router)
app.include_router(legal.router)


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
    # Rappels de consultation L.414-3 dus (idempotent — au plus 1/jour par consultation)
    try:
        import os
        from app.core.database import SessionLocal
        from app.services.email_service import scan_consultation_reminders
        db = SessionLocal()
        try:
            n = scan_consultation_reminders(db, base_url=os.environ.get("SD_BASE_URL", ""))
            if n:
                print(f"[email] {n} rappel(s) de consultation mis en file")
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        print(f"[email] scan consultations ignoré : {e}")

    # Rappels légaux (chantier D) — scan au démarrage + thread quotidien (1er/15 du mois)
    try:
        import os
        import threading
        import time
        from app.core.database import SessionLocal
        from app.services.email_service import scan_compliance_reminders

        def _run_compliance_scan() -> int:
            db = SessionLocal()
            try:
                return scan_compliance_reminders(db, base_url=os.environ.get("SD_BASE_URL", ""))
            finally:
                db.close()

        n = _run_compliance_scan()
        if n:
            print(f"[compliance-scan] {n} rappel(s) légal/aux mis en file")

        def _daily_compliance_loop() -> None:
            while True:
                time.sleep(24 * 3600)
                try:
                    n = _run_compliance_scan()
                    if n:
                        print(f"[compliance-scan] {n} rappel(s) légal/aux mis en file")
                except Exception as e:  # noqa: BLE001
                    print(f"[compliance-scan] échec : {e}")

        threading.Thread(target=_daily_compliance_loop, daemon=True, name="compliance-scan").start()
    except Exception as e:  # noqa: BLE001
        print(f"[compliance-scan] démarrage ignoré : {e}")


@app.get("/api/health")
def health():
    return {"status": "ok"}
