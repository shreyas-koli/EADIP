import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.database.base import Base
from app.database.session import get_db
from app.auth.jwt import create_access_token
from app.models.user import User
from app.models.warehouse import Warehouse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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



@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def db_session(client):
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    
    # Create test user
    test_user = User(
        email="test_explorer@example.com",
        hashed_password="fakehash",
        full_name="Explorer User"
    )
    session.add(test_user)
    session.commit()
    
    # Create test warehouse
    test_warehouse = Warehouse(
        name="Test WH",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="test_db",
        username="test_user",
        encrypted_password=b"faketoken",
        owner_id=test_user.id
    )
    session.add(test_warehouse)
    session.commit()
    
    yield session
    
    session.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def auth_headers(db_session):
    user = db_session.query(User).filter_by(email="test_explorer@example.com").first()
    token = create_access_token(data={"sub": user.email})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def warehouse_id(db_session):
    warehouse = db_session.query(Warehouse).first()
    return warehouse.id

@patch('app.api.warehouse.WarehouseConnector.connect')
@patch('app.api.warehouse.ExplorerService.get_schemas')
def test_get_explorer_schemas(mock_get_schemas, mock_connect, client, auth_headers, warehouse_id):
    mock_connect.return_value = MagicMock()
    mock_get_schemas.return_value = [{"name": "public"}, {"name": "eadip"}]
    
    response = client.get(f"/warehouses/{warehouse_id}/explorer/schemas", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[0]["name"] == "public"

@patch('app.api.warehouse.WarehouseConnector.connect')
@patch('app.api.warehouse.ExplorerService.get_tables')
def test_get_explorer_tables(mock_get_tables, mock_connect, client, auth_headers, warehouse_id):
    mock_connect.return_value = MagicMock()
    mock_get_tables.return_value = [
        {"name": "users", "schema_name": "public", "estimated_row_count": 100}
    ]
    
    response = client.get(f"/warehouses/{warehouse_id}/explorer/schemas/public/tables", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "users"

@patch('app.api.warehouse.WarehouseConnector.connect')
@patch('app.api.warehouse.ExplorerService.get_columns')
def test_get_explorer_columns(mock_get_columns, mock_connect, client, auth_headers, warehouse_id):
    mock_connect.return_value = MagicMock()
    mock_get_columns.return_value = [
        {"name": "id", "data_type": "INTEGER", "nullable": False, "position": 1, "is_primary_key": True, "foreign_key": None}
    ]
    
    response = client.get(f"/warehouses/{warehouse_id}/explorer/schemas/public/tables/users/columns", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "id"

def test_get_explorer_unauthorized(client, warehouse_id):
    response = client.get(f"/warehouses/{warehouse_id}/explorer/schemas")
    assert response.status_code == 401
