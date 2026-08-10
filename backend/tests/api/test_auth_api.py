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
