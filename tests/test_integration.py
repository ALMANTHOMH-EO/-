import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_db = tempfile.NamedTemporaryFile(prefix="esko-v2-test-", suffix=".db", delete=False)
_db.close()
os.environ["DATABASE_URL"] = "sqlite:///" + _db.name
os.environ["COOKIE_SECURE"] = "false"
os.environ["ADMIN_BOOTSTRAP_KEY"] = "test-bootstrap-secret-key"

from fastapi.testclient import TestClient
from app.main import app, Base, engine, init_db, SessionLocal, DailyUsage, local_today


def test_registration_slots_pairing_and_admin():
    Base.metadata.drop_all(bind=engine)
    init_db()
    with TestClient(app) as client:
        csrf_response = client.get("/api/auth/csrf")
        assert csrf_response.status_code == 200
        csrf = csrf_response.json()["csrfToken"]
        headers = {"X-CSRF-Token": csrf}
        health = client.get("/api/health")
        assert health.status_code == 200 and health.json()["ok"] is True
        register = client.post("/api/auth/register", headers=headers, json={
            "username": "test_user", "display_name": "Tester", "age_band": "under18",
            "password": "correct-horse-battery-12"
        })
        assert register.status_code == 201, register.text
        login = client.post("/api/auth/login", headers=headers, json={
            "username": "test_user", "password": "correct-horse-battery-12"
        })
        assert login.status_code == 200, login.text
        me = client.get("/api/me")
        assert me.status_code == 200 and me.json()["username"] == "test_user"
        slots = client.get("/api/slots?group=1")
        assert slots.status_code == 200 and len(slots.json()["slots"]) == 50
        reserve = client.post("/api/slots/1/reserve", headers=headers, json={})
        assert reserve.status_code == 200, reserve.text
        with TestClient(app) as other:
            other_csrf = other.get("/api/auth/csrf").json()["csrfToken"]
            other_headers = {"X-CSRF-Token": other_csrf}
            other_register = other.post("/api/auth/register", headers=other_headers, json={
                "username": "second_user", "display_name": "Second", "age_band": "under18",
                "password": "second-user-password-strong-12"
            })
            assert other_register.status_code == 201
            other_login = other.post("/api/auth/login", headers=other_headers, json={
                "username": "second_user", "password": "second-user-password-strong-12"
            })
            assert other_login.status_code == 200
            collision = other.post("/api/slots/1/reserve", headers=other_headers, json={})
            assert collision.status_code == 409
            second_reserve = other.post("/api/slots/2/reserve", headers=other_headers, json={})
            assert second_reserve.status_code == 200

        pairing = client.post("/api/pairings?slot_id=1", headers=headers, json={})
        assert pairing.status_code == 200, pairing.text
        code = pairing.json()["code"]
        redeem = client.post("/api/pairings/redeem", headers=headers, json={"code": code, "device_label": "My phone"})
        assert redeem.status_code == 201, redeem.text
        redeem_again = client.post("/api/pairings/redeem", headers=headers, json={"code": code, "device_label": "Second try"})
        assert redeem_again.status_code == 400
        release = client.delete("/api/slots/1/reserve", headers=headers)
        assert release.status_code == 200, release.text
        with SessionLocal() as db:
            db.add(DailyUsage(user_id=1, usage_day=local_today(), seconds=6 * 60 * 60))
            db.commit()
        limited = client.get("/api/slots")
        assert limited.status_code == 429
        logout = client.post("/api/auth/logout", headers=headers)
        assert logout.status_code == 200, logout.text

        admin_bootstrap = client.post("/api/admin/bootstrap", headers={**headers, "X-Bootstrap-Key": "test-bootstrap-secret-key"}, json={
            "username": "eo_admin", "display_name": "EO Admin", "age_band": "under18",
            "password": "another-very-strong-password-2026"
        })
        assert admin_bootstrap.status_code == 201, admin_bootstrap.text
        admin_login = client.post("/api/auth/login", headers=headers, json={
            "username": "eo_admin", "password": "another-very-strong-password-2026"
        })
        assert admin_login.status_code == 200, admin_login.text
        overview = client.get("/api/admin/overview")
        assert overview.status_code == 200 and overview.json()["users"] == 3
        search = client.get("/api/admin/users?q=test_user")
        assert search.status_code == 200 and len(search.json()["users"]) == 1
        blocked = client.post("/api/admin/users/1/status", headers=headers, json={"status": "blocked"})
        assert blocked.status_code == 200 and blocked.json()["status"] == "blocked"
        blocked_login = client.post("/api/auth/login", headers=headers, json={
            "username": "test_user", "password": "correct-horse-battery-12"
        })
        assert blocked_login.status_code == 401
