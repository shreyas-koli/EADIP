import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.database.session import get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database.base import Base
from app.models.warehouse import Warehouse
from app.auth.jwt import create_access_token
from app.core.security import encrypt_credential, hash_password
from app.models.user import User
import json

def test_stream():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
            
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    
    test_user = User(full_name="Test User", email="test@example.com", hashed_password=hash_password("password"))
    session.add(test_user)
    
    wh = Warehouse(
        name="test_wh_stream",
        db_type="PostgreSQL",
        host="localhost",
        port=5432,
        database_name="test_db",
        username="test_user",
        encrypted_password=encrypt_credential("encrypted"),
        is_active=True,
        owner=test_user
    )
    session.add(wh)
    session.commit()
    session.refresh(wh)
    
    token = create_access_token(data={"sub": test_user.email})
    headers = {"Authorization": f"Bearer {token}"}
    
    client = TestClient(app)
    
    print("Sending POST request to /discovery/execute?stream=true")
    with client.stream("POST", "/discovery/execute?stream=true", json={"warehouse_id": wh.id}, headers=headers) as response:
        print("Response Content-Type:", response.headers.get("Content-Type"))
        for line in response.iter_lines():
            if line:
                print("Event:", line)
                
    session.close()

if __name__ == "__main__":
    test_stream()
