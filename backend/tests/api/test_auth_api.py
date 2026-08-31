import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.base import Base
from app.database.session import get_db
from app.models.user import User
from app.core.security import hash_password

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
def db_session():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    
    # Create a test user
    user = User(
        email="test@example.com",
        full_name="Test User",
        hashed_password=hash_password("password123")
    )
    session.add(user)
    session.commit()
    
    yield session
    
    session.close()
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()

def test_json_login_works():
    response = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "password123"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

def test_form_login_works():
    response = client.post(
        "/auth/token",
        data={"username": "test@example.com", "password": "password123"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

def test_form_login_fails_invalid_credentials():
    response = client.post(
        "/auth/token",
        data={"username": "test@example.com", "password": "wrongpassword"}
    )
    assert response.status_code == 401

def test_register_normal_password_succeeds():
    response = client.post(
        "/auth/register",
        json={"full_name": "New User", "email": "newuser@example.com", "password": "Password123!"}
    )
    assert response.status_code == 201
    
    # Verify login works
    login_response = client.post(
        "/auth/login",
        json={"email": "newuser@example.com", "password": "Password123!"}
    )
    assert login_response.status_code == 200

def test_register_password_exactly_72_bytes_succeeds():
    password = "a" * 72
    response = client.post(
        "/auth/register",
        json={"full_name": "New User 2", "email": "newuser2@example.com", "password": password}
    )
    assert response.status_code == 201

def test_register_password_over_72_bytes_fails():
    password = "a" * 73
    response = client.post(
        "/auth/register",
        json={"full_name": "New User 3", "email": "newuser3@example.com", "password": password}
    )
    assert response.status_code == 422
    assert "Password cannot exceed 72 bytes" in response.text

def test_register_multibyte_unicode_password_calculated_correctly():
    # '🔥' is 4 bytes in UTF-8. 
    # 18 of them = 72 bytes. 
    # 19 of them = 76 bytes, which should fail even though it's only 19 characters.
    password = "🔥" * 19
    response = client.post(
        "/auth/register",
        json={"full_name": "New User 4", "email": "newuser4@example.com", "password": password}
    )
    assert response.status_code == 422
    assert "Password cannot exceed 72 bytes" in response.text
