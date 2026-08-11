import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.base import Base
from app.database.session import get_db
from app.auth.jwt import create_access_token
from app.models.user import User
from app.models.warehouse import Warehouse
from app.core.security import decrypt_credential

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

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

client = TestClient(app)

@pytest.fixture(autouse=True)
def db_session():
    app.dependency_overrides[get_db] = override_get_db
    
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    
    # Create a test user
    user = User(
        email="test@example.com",
        full_name="Test User",
        hashed_password="hashedpassword123"
    )
    session.add(user)
    session.commit()
    
    yield session
    
    session.close()
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()

def get_auth_headers():
    token = create_access_token({"sub": "test@example.com"})
    return {"Authorization": f"Bearer {token}"}

def test_delete_nonexistent_warehouse_returns_404():
    response = client.delete("/warehouses/9999", headers=get_auth_headers())
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

def test_unauthenticated_access_returns_401():
    response = client.get("/warehouses/")
    assert response.status_code == 401

def test_authenticated_access_works():
    # Test POST
    create_data = {
        "name": "Test Warehouse",
        "db_type": "postgresql",
        "host": "localhost",
        "port": 5432,
        "database_name": "testdb",
        "username": "user",
        "password": "password"
    }
    response = client.post("/warehouses/", json=create_data, headers=get_auth_headers())
    assert response.status_code == 201
    warehouse_id = response.json()["id"]

    # Verify password is encrypted in database
    db = TestingSessionLocal()
    try:
        wh = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
        assert wh.encrypted_password != "password"
        assert decrypt_credential(wh.encrypted_password) == "password"
    finally:
        db.close()

    # Test GET
    response = client.get("/warehouses/", headers=get_auth_headers())
    assert response.status_code == 200
    assert len(response.json()) == 1

    # Test GET {id}
    response = client.get(f"/warehouses/{warehouse_id}", headers=get_auth_headers())
    assert response.status_code == 200
    assert response.json()["name"] == "Test Warehouse"
    assert "password" not in response.json()
    assert "encrypted_password" not in response.json()

    # Test PUT {id}
    update_data = {"name": "Updated Warehouse", "password": "new-password"}
    response = client.put(f"/warehouses/{warehouse_id}", json=update_data, headers=get_auth_headers())
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Warehouse"
    assert "password" not in response.json()
    assert "encrypted_password" not in response.json()
    
    # Verify updated password is encrypted in database
    db = TestingSessionLocal()
    try:
        wh = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
        assert wh.encrypted_password != "new-password"
        assert wh.encrypted_password != "password"
        assert decrypt_credential(wh.encrypted_password) == "new-password"
    finally:
        db.close()

    # Test DELETE {id}
    response = client.delete(f"/warehouses/{warehouse_id}", headers=get_auth_headers())
    assert response.status_code == 200
    assert response.json()["is_active"] is False

def test_test_connection_unauthenticated_returns_401():
    response = client.post("/warehouses/1/test")
    assert response.status_code == 401

