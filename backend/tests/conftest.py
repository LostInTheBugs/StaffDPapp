import os
import tempfile
import atexit

import pytest
from fastapi.testclient import TestClient


def _login(client, email, password, captcha_id, captcha_answer):
    r = client.post("/api/auth/login", json={
        "email": email, "password": password,
        "captcha_id": captcha_id, "captcha_answer": captcha_answer,
    })
    assert r.status_code == 200, f"Login failed: {r.json()}"
    return r.json()["access_token"]

# ── Set test DB BEFORE importing app ──────────────────────────────
_db_fd, _db_path = tempfile.mkstemp(suffix=".db", prefix="sd_test_")
os.environ["SD_DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["SD_EMAIL_DIR"] = f"{tempfile.gettempdir()}/sd_emails_test"
os.makedirs(os.environ["SD_EMAIL_DIR"], exist_ok=True)

from app.main import app
from app.core.database import SessionLocal, Base, engine
from app.core.ratelimit import reset_rate_limits
from tests.helpers import fetch_captcha


def _cleanup():
    os.close(_db_fd)
    try:
        os.unlink(_db_path)
    except OSError:
        pass


atexit.register(_cleanup)


@pytest.fixture
def org_with_users(client):
    """Create an org with president (sophie), secretary (marc), and member (tom)."""
    from tests.helpers import fetch_captcha, create_invitation
    from app.core.database import SessionLocal
    from app.models.user import User

    # Create org
    cid, ans = fetch_captcha(client)
    r = client.post("/api/organizations", json={
        "organization_name": "TestPV",
        "company_name": "TestPV SA",
        "employee_count": 120,
        "admin_email": "sophie@testpv.lu",
        "admin_password": "test123456",
        "admin_first_name": "Sophie",
        "admin_last_name": "Muller",
        "admin_delegue_status": "titulaire",
        "admin_delegue_role": "president",
        "captcha_id": cid,
        "captcha_answer": ans,
    })
    assert r.status_code == 201, f"Create org failed: {r.json()}"

    # Login as sophie
    cid2, ans2 = fetch_captcha(client)
    sophie_token = _login(client, "sophie@testpv.lu", "test123456", cid2, ans2)
    h = {"Authorization": f"Bearer {sophie_token}"}

    # Get org_id
    r = client.get("/api/dashboard", headers=h)
    org_id = r.json()["organization"]["id"]

    # Get sophie's user_id
    db = SessionLocal()
    sophie = db.query(User).filter(User.email == "sophie@testpv.lu").first()
    sophie_id = sophie.id
    db.close()

    # Invite marc as secretaire
    db2 = SessionLocal()
    create_invitation(db2, "marc@testpv.lu", org_id, sophie_id, "MARC123",
                      delegue_status="titulaire", delegue_role="secretaire")
    db2.close()

    # Marc joins
    cid3, ans3 = fetch_captcha(client)
    client.post("/api/join", json={
        "email": "marc@testpv.lu", "password": "test123456",
        "first_name": "Marc", "last_name": "Weber",
        "invitation_code": "MARC123",
        "captcha_id": cid3, "captcha_answer": ans3,
    })

    # Invite tom as membre
    db3 = SessionLocal()
    create_invitation(db3, "tom@testpv.lu", org_id, sophie_id, "TOM456",
                      delegue_status="titulaire", delegue_role="membre")
    db3.close()

    cid4, ans4 = fetch_captcha(client)
    client.post("/api/join", json={
        "email": "tom@testpv.lu", "password": "test123456",
        "first_name": "Tom", "last_name": "Wagner",
        "invitation_code": "TOM456",
        "captcha_id": cid4, "captcha_answer": ans4,
    })

    # Also create another org for IDOR tests
    cid5, ans5 = fetch_captcha(client)
    r2 = client.post("/api/organizations", json={
        "organization_name": "OtherOrg",
        "company_name": "Other SA",
        "employee_count": 50,
        "admin_email": "other@other.lu",
        "admin_password": "test123456",
        "admin_first_name": "Other",
        "admin_last_name": "User",
        "admin_delegue_status": "titulaire",
        "admin_delegue_role": "president",
        "captcha_id": cid5,
        "captcha_answer": ans5,
    })
    assert r2.status_code == 201

    cid6, ans6 = fetch_captcha(client)
    other_token = _login(client, "other@other.lu", "test123456", cid6, ans6)

    # Authentication tokens for the three users
    cid_s, ans_s = fetch_captcha(client)
    stok = _login(client, "sophie@testpv.lu", "test123456", cid_s, ans_s)
    cid_m, ans_m = fetch_captcha(client)
    mtok = _login(client, "marc@testpv.lu", "test123456", cid_m, ans_m)
    cid_t, ans_t = fetch_captcha(client)
    ttok = _login(client, "tom@testpv.lu", "test123456", cid_t, ans_t)

    return {
        "org_id": org_id,
        "sophie_token": stok,
        "marc_token": mtok,
        "tom_token": ttok,
        "other_token": other_token,
    }



@pytest.fixture(autouse=True)
def setup_db():
    """Recreate tables before each test for isolation."""
    Base.metadata.create_all(bind=engine)
    reset_rate_limits()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
