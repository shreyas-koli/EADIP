import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import uuid

from app.main import app
from app.database.base import Base
from app.database.session import get_db
from app.auth.jwt import create_access_token
from app.models.user import User
from app.models.warehouse import Warehouse
from app.core.security import hash_password, encrypt_credential

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

client = TestClient(app)

@pytest.fixture(autouse=True)
def auth_db_session():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    
    # 1. Setup User A
    user_a = User(
        email="usera@example.com",
        full_name="User A",
        hashed_password=hash_password("password"),
        role="user"
    )
    session.add(user_a)
    
    # 2. Setup User B
    user_b = User(
        email="userb@example.com",
        full_name="User B",
        hashed_password=hash_password("password"),
        role="user"
    )
    session.add(user_b)
    
    # 3. Setup Admin User
    user_admin = User(
        email="admin@example.com",
        full_name="Admin User",
        hashed_password=hash_password("password"),
        role="admin"
    )
    session.add(user_admin)
    session.commit()
    
    # 4. Create Warehouse A (Owned by User A)
    wh_a = Warehouse(
        name="Warehouse A",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="db_a",
        username="user_a",
        encrypted_password=encrypt_credential("pass"),
        owner_id=user_a.id,
        is_active=True
    )
    session.add(wh_a)
    
    # 5. Create Warehouse B (Owned by User B)
    wh_b = Warehouse(
        name="Warehouse B",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="db_b",
        username="user_b",
        encrypted_password=encrypt_credential("pass"),
        owner_id=user_b.id,
        is_active=True
    )
    session.add(wh_b)
    session.commit()
    
    session.refresh(user_a)
    session.refresh(user_b)
    session.refresh(user_admin)
    session.refresh(wh_a)
    session.refresh(wh_b)
    
    # Generate Tokens
    token_a = create_access_token({"sub": user_a.email})
    token_b = create_access_token({"sub": user_b.email})
    token_admin = create_access_token({"sub": user_admin.email})
    
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    headers_admin = {"Authorization": f"Bearer {token_admin}"}
    
    yield {
        "session": session,
        "user_a": user_a,
        "user_b": user_b,
        "wh_a": wh_a,
        "wh_b": wh_b,
        "headers_a": headers_a,
        "headers_b": headers_b,
        "headers_admin": headers_admin
    }
    
    session.close()
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_cross_user_get_warehouse(auth_db_session):
    headers_b = auth_db_session["headers_b"]
    wh_a = auth_db_session["wh_a"]
    
    response = client.get(f"/warehouses/{wh_a.id}", headers=headers_b)
    assert response.status_code == 404


def test_cross_user_update_warehouse(auth_db_session):
    headers_b = auth_db_session["headers_b"]
    wh_a = auth_db_session["wh_a"]
    
    response = client.put(f"/warehouses/{wh_a.id}", json={"name": "Hacked"}, headers=headers_b)
    assert response.status_code == 404


def test_cross_user_delete_warehouse(auth_db_session):
    headers_b = auth_db_session["headers_b"]
    wh_a = auth_db_session["wh_a"]
    
    response = client.delete(f"/warehouses/{wh_a.id}", headers=headers_b)
    assert response.status_code == 404


def test_cross_user_test_connection(auth_db_session):
    headers_b = auth_db_session["headers_b"]
    wh_a = auth_db_session["wh_a"]
    
    response = client.post(f"/warehouses/{wh_a.id}/test", headers=headers_b)
    assert response.status_code == 404


def test_cross_user_execute_discovery(auth_db_session):
    headers_b = auth_db_session["headers_b"]
    wh_a = auth_db_session["wh_a"]
    
    response = client.post("/discovery/execute", json={"warehouse_id": wh_a.id}, headers=headers_b)
    assert response.status_code == 404


def test_cross_user_get_history(auth_db_session):
    headers_b = auth_db_session["headers_b"]
    wh_a = auth_db_session["wh_a"]
    
    response = client.get(f"/warehouses/{wh_a.id}/history", headers=headers_b)
    assert response.status_code == 404


def test_cross_user_get_execution(auth_db_session):
    headers_b = auth_db_session["headers_b"]
    wh_a = auth_db_session["wh_a"]
    fake_session_id = str(uuid.uuid4())
    
    response = client.get(f"/warehouses/{wh_a.id}/history/{fake_session_id}", headers=headers_b)
    assert response.status_code == 404


def test_real_session_cross_user_idor(auth_db_session):
    session = auth_db_session["session"]
    headers_a = auth_db_session["headers_a"]
    wh_b = auth_db_session["wh_b"]
    
    # 1. Create a real persisted execution in User B's warehouse
    from app.services.execution_service import ExecutionService
    real_session_id = str(uuid.uuid4())
    ExecutionService.persist_execution(session, wh_b.id, {
        "session_id": real_session_id,
        "completed": ["metadata"],
        "agent_execution": [{"agent": "metadata", "wave": 1}]
    })
    
    # 2. User A attempts to access User B's warehouse with User B's real session ID
    response = client.get(f"/warehouses/{wh_b.id}/history/{real_session_id}", headers=headers_a)
    
    # 3. Must return 404, not leak the session
    assert response.status_code == 404


def test_list_warehouses_isolation(auth_db_session):
    headers_a = auth_db_session["headers_a"]
    headers_b = auth_db_session["headers_b"]
    wh_a = auth_db_session["wh_a"]
    wh_b = auth_db_session["wh_b"]
    
    res_a = client.get("/warehouses/", headers=headers_a)
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert len(data_a) == 1
    assert data_a[0]["id"] == wh_a.id
    
    res_b = client.get("/warehouses/", headers=headers_b)
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert len(data_b) == 1
    assert data_b[0]["id"] == wh_b.id


def test_admin_global_access(auth_db_session):
    headers_admin = auth_db_session["headers_admin"]
    wh_a = auth_db_session["wh_a"]
    wh_b = auth_db_session["wh_b"]
    
    # Admin list all
    res_list = client.get("/warehouses/", headers=headers_admin)
    assert res_list.status_code == 200
    data = res_list.json()
    assert len(data) == 2
    
    # Admin gets specific
    res_get = client.get(f"/warehouses/{wh_a.id}", headers=headers_admin)
    assert res_get.status_code == 200
    
    res_get2 = client.get(f"/warehouses/{wh_b.id}", headers=headers_admin)
    assert res_get2.status_code == 200

def test_unauthenticated_access_is_blocked():
    response = client.get("/warehouses/")
    assert response.status_code == 401
    
    response = client.get("/warehouses/1")
    assert response.status_code == 401
    
    response = client.post("/discovery/execute", json={"warehouse_id": 1})
    assert response.status_code == 401

def test_nonexistent_warehouse(auth_db_session):
    headers_a = auth_db_session["headers_a"]
    response = client.get("/warehouses/9999", headers=headers_a)
    assert response.status_code == 404
