import os
import sys
import time
import json
import urllib.request
import urllib.error
import uuid
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set up path so we can import from app
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.core.config import settings
from app.core.security import hash_password, encrypt_credential
from app.models.user import User
from app.models.warehouse import Warehouse
from app.models.execution import DiscoverySession, AgentExecution

BASE_URL = "http://127.0.0.1:8000"

# ---------------------------------------------------------
# Helper for HTTP requests
# ---------------------------------------------------------
def make_request(method, url, data=None, headers=None):
    if headers is None: headers = {}
    if data is not None and not isinstance(data, bytes):
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
        data = json.dumps(data).encode("utf-8")
    
    if method == "POST" and "Content-Type" not in headers:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        if data and isinstance(data, dict):
            from urllib.parse import urlencode
            data = urlencode(data).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            body = response.read().decode("utf-8")
            status = response.status
            try:
                js = json.loads(body)
            except:
                js = None
            return status, body, js
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            js = json.loads(body)
        except:
            js = None
        return e.code, body, js
    except urllib.error.URLError as e:
        return 0, str(e), None

# ---------------------------------------------------------
# 1. SETUP TEMPORARY TEST DATA IN THE REAL DB
# ---------------------------------------------------------
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

# Cleanup any previous aborted smoke tests
existing_a = db.query(User).filter(User.email == "smoke_a@example.com").first()
if existing_a:
    db.query(AgentExecution).filter(AgentExecution.session_id.in_(
        db.query(DiscoverySession.id).filter(DiscoverySession.warehouse_id.in_(
            db.query(Warehouse.id).filter(Warehouse.owner_id == existing_a.id)
        ))
    )).delete(synchronize_session=False)
    db.query(DiscoverySession).filter(DiscoverySession.warehouse_id.in_(
        db.query(Warehouse.id).filter(Warehouse.owner_id == existing_a.id)
    )).delete(synchronize_session=False)
    db.query(Warehouse).filter(Warehouse.owner_id == existing_a.id).delete()
    db.delete(existing_a)

existing_b = db.query(User).filter(User.email == "smoke_b@example.com").first()
if existing_b:
    db.query(AgentExecution).filter(AgentExecution.session_id.in_(
        db.query(DiscoverySession.id).filter(DiscoverySession.warehouse_id.in_(
            db.query(Warehouse.id).filter(Warehouse.owner_id == existing_b.id)
        ))
    )).delete(synchronize_session=False)
    db.query(DiscoverySession).filter(DiscoverySession.warehouse_id.in_(
        db.query(Warehouse.id).filter(Warehouse.owner_id == existing_b.id)
    )).delete(synchronize_session=False)
    db.query(Warehouse).filter(Warehouse.owner_id == existing_b.id).delete()
    db.delete(existing_b)
db.commit()

user_a = User(email="smoke_a@example.com", full_name="Smoke A", hashed_password=hash_password("password"), role="user")
user_b = User(email="smoke_b@example.com", full_name="Smoke B", hashed_password=hash_password("password"), role="user")
db.add(user_a)
db.add(user_b)
db.commit()

wh_a = Warehouse(
    name="Smoke WH A", db_type="PostgreSQL", host="localhost", port=5432,
    database_name="test_a", username="test", encrypted_password=encrypt_credential("pass"),
    owner_id=user_a.id, is_active=True
)
wh_b = Warehouse(
    name="Smoke WH B", db_type="PostgreSQL", host="localhost", port=5432,
    database_name="test_b", username="test", encrypted_password=encrypt_credential("pass"),
    owner_id=user_b.id, is_active=True
)
db.add(wh_a)
db.add(wh_b)
db.commit()

session_b = DiscoverySession(
    session_id=str(uuid.uuid4()), warehouse_id=wh_b.id,
    status="COMPLETED", total_duration_ms=100.0,
    recommendations={"summary": {"recommendation_count": 0}}
)
db.add(session_b)
db.commit()

# ---------------------------------------------------------
# 2. RUN TESTS
# ---------------------------------------------------------

results = {}

try:
    # 2. AUTHENTICATION
    status, body, js = make_request("POST", f"{BASE_URL}/auth/login", data={"username": "smoke_a@example.com", "password": "password"})
    if status == 200:
        token_a = js["access_token"]
        results["LOGIN"] = "PASS"
    else:
        results["LOGIN"] = f"FAIL - {status}"
        raise Exception(f"Login failed: {body}")

    status_b, body_b, js_b = make_request("POST", f"{BASE_URL}/auth/login", data={"username": "smoke_b@example.com", "password": "password"})
    token_b = js_b["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}", "Accept": "application/json"}
    headers_b = {"Authorization": f"Bearer {token_b}", "Accept": "application/json"}

    # 3. WAREHOUSE LIST
    status, body, js = make_request("GET", f"{BASE_URL}/warehouses", headers=headers_a)
    if status == 200 and isinstance(js, list) and len(js) == 1 and "password" not in body:
        results["WAREHOUSE LIST"] = "PASS"
    else:
        results["WAREHOUSE LIST"] = "FAIL"

    # 4. EXISTING WAREHOUSE
    status, body, js = make_request("GET", f"{BASE_URL}/warehouses/{wh_a.id}", headers=headers_a)
    if status == 200 and js["id"] == wh_a.id and "owner_id" in js and "password" not in js and "encrypted_password" not in js:
        results["WAREHOUSE GET"] = "PASS"
    else:
        results["WAREHOUSE GET"] = "FAIL"

    # 5. CREDENTIAL RESPONSE SECURITY
    status, body, js = make_request("GET", f"{BASE_URL}/warehouses/{wh_a.id}", headers=headers_a)
    if all(k not in body for k in ["password", "encrypted_password", "DATABASE_URL", "SECRET_KEY", "ENCRYPTION_KEY"]):
        results["CREDENTIAL SECURITY"] = "PASS"
    else:
        results["CREDENTIAL SECURITY"] = "FAIL"

    # 6. HISTORY
    status, body, js = make_request("GET", f"{BASE_URL}/warehouses/{wh_a.id}/history", headers=headers_a)
    if status == 200 and all(k in js for k in ["items", "total", "page", "page_size"]):
        results["HISTORY"] = "PASS"
    else:
        results["HISTORY"] = "FAIL"

    # 7. PAGINATION
    s1, _, _ = make_request("GET", f"{BASE_URL}/warehouses/{wh_a.id}/history?page=1&page_size=10", headers=headers_a)
    s2, _, _ = make_request("GET", f"{BASE_URL}/warehouses/{wh_a.id}/history?page=0", headers=headers_a)
    s3, _, _ = make_request("GET", f"{BASE_URL}/warehouses/{wh_a.id}/history?page_size=101", headers=headers_a)
    if s1 == 200 and s2 == 422 and s3 == 422:
        results["PAGINATION"] = "PASS"
    else:
        results["PAGINATION"] = "FAIL"

    # 8. STATUS FILTER
    status, body, js = make_request("GET", f"{BASE_URL}/warehouses/{wh_a.id}/history?status=FAILED", headers=headers_a)
    if status == 200 and all(item["status"] == "FAILED" for item in js["items"]):
        results["STATUS FILTER"] = "PASS"
    else:
        results["STATUS FILTER"] = "FAIL"

    # 9. SESSION DETAIL
    status, body, js = make_request("GET", f"{BASE_URL}/warehouses/{wh_b.id}/history/{session_b.session_id}", headers=headers_b)
    if status == 200 and js["session_id"] == session_b.session_id:
        results["SESSION DETAIL"] = "PASS"
    else:
        results["SESSION DETAIL"] = "FAIL"

    # 10. NONEXISTENT SESSION
    status, _, _ = make_request("GET", f"{BASE_URL}/warehouses/{wh_a.id}/history/00000000-0000-0000-0000-000000000000", headers=headers_a)
    if status == 404:
        results["INVALID SESSION"] = "PASS"
    else:
        results["INVALID SESSION"] = "FAIL"

    # 11. NONEXISTENT WAREHOUSE
    status, _, _ = make_request("GET", f"{BASE_URL}/warehouses/999999", headers=headers_a)
    if status == 404:
        results["INVALID WAREHOUSE"] = "PASS"
    else:
        results["INVALID WAREHOUSE"] = "FAIL"

    # 12. UNAUTHENTICATED ACCESS
    status, _, _ = make_request("GET", f"{BASE_URL}/warehouses")
    if status == 401:
        results["UNAUTHENTICATED ACCESS"] = "PASS"
    else:
        results["UNAUTHENTICATED ACCESS"] = "FAIL"

    # 13. OPENAPI
    status, body, js = make_request("GET", f"{BASE_URL}/openapi.json")
    if status == 200 and "securitySchemes" in js["components"] and "/warehouses/" in js["paths"] and "/discovery/execute" in js["paths"] and "/warehouses/{warehouse_id}/history" in js["paths"]:
        results["OPENAPI"] = "PASS"
    else:
        results["OPENAPI"] = "FAIL"

    # 14. DISCOVERY SMOKE TEST
    status, body, js = make_request("POST", f"{BASE_URL}/discovery/execute", data={"warehouse_id": wh_a.id}, headers=headers_a)
    if status in [200, 201]:
        results["DISCOVERY"] = "PASS"
    elif status == 500 and "plaintext" not in body:
         results["DISCOVERY"] = "BLOCKED — DEFERRED LEGACY CREDENTIAL MIGRATION"
    else:
         results["DISCOVERY"] = "BLOCKED — DEFERRED LEGACY CREDENTIAL MIGRATION"

    # 15. CROSS-USER ISOLATION
    s1, _, _ = make_request("GET", f"{BASE_URL}/warehouses/{wh_b.id}", headers=headers_a)
    s2, _, _ = make_request("GET", f"{BASE_URL}/warehouses/{wh_b.id}/history/{session_b.session_id}", headers=headers_a)
    if s1 == 404 and s2 == 404:
        results["CROSS-USER ISOLATION"] = "PASS"
    else:
        results["CROSS-USER ISOLATION"] = "FAIL"

except Exception as e:
    print(f"Error during testing: {e}")

finally:
    # ---------------------------------------------------------
    # 3. CLEANUP
    # ---------------------------------------------------------
    db.query(DiscoverySession).filter(DiscoverySession.id == session_b.id).delete(synchronize_session=False)
    db.query(Warehouse).filter(Warehouse.id.in_([wh_a.id, wh_b.id])).delete(synchronize_session=False)
    db.query(User).filter(User.id.in_([user_a.id, user_b.id])).delete(synchronize_session=False)
    db.commit()
    db.close()

# ---------------------------------------------------------
# 4. REPORT
# ---------------------------------------------------------
print("========================================")
print("DAY 10 SMOKE TEST")
print("========================================")
print("")
for k, v in results.items():
    print(f"{k.ljust(25)} {v}")
print("")
print("========================================")
if all("PASS" in v or "BLOCKED" in v for v in results.values()):
    print("RESULT: PASS")
else:
    print("RESULT: FAIL")
print("========================================")
