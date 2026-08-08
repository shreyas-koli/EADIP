import uuid
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database.base import Base
from app.database.session import get_db
from app.models.warehouse import Warehouse
from app.models.execution import DiscoverySession
from app.auth.jwt import create_access_token

from sqlalchemy.pool import StaticPool

# Use an in-memory SQLite database for testing
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

@pytest.fixture(scope="function")
def db_session():
    app.dependency_overrides[get_db] = override_get_db
    
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    
    # Create test user for auth
    from app.models.user import User
    from app.core.security import hash_password
    test_user = User(full_name="Test User", email="test@example.com", hashed_password=hash_password("password"))
    session.add(test_user)
    
    wh = Warehouse(
        name=f"test_wh_{uuid.uuid4()}",
        db_type="PostgreSQL",
        host="localhost",
        port=5432,
        database_name="test_db",
        username="test_user",
        encrypted_password="encrypted",
        is_active=True
    )
    session.add(wh)
    
    wh_inactive = Warehouse(
        name=f"test_wh_inactive_{uuid.uuid4()}",
        db_type="PostgreSQL",
        host="localhost",
        port=5432,
        database_name="test_db",
        username="test_user",
        encrypted_password="encrypted",
        is_active=False
    )
    session.add(wh_inactive)
    
    session.commit()
    session.refresh(wh)
    session.refresh(wh_inactive)
    
    token = create_access_token(data={"sub": test_user.email})
    headers = {"Authorization": f"Bearer {token}"}
    
    yield session, wh, wh_inactive, headers
    
    session.close()
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)

def test_successful_execution(db_session):
    session, wh, _, headers = db_session
    
    with patch("app.api.discovery.AgentOrchestrator") as mock_orchestrator_class:
        mock_instance = MagicMock()
        mock_orchestrator_class.return_value = mock_instance
        mock_instance.execute_parallel.return_value = {
            "session_id": str(uuid.uuid4()),
            "total_execution_ms": 100.0,
            "completed": ["metadata"],
            "failed": [],
            "skipped": [],
            "agent_execution": [
                {
                    "agent": "metadata",
                    "started_at": "2023-01-01T00:00:00+00:00",
                    "finished_at": "2023-01-01T00:00:01+00:00",
                    "duration_ms": 100.0,
                    "wave": 1
                }
            ],
            "agent_results": {}
        }
        
        response = client.post("/discovery/execute", json={"warehouse_id": wh.id}, headers=headers)
        
        assert response.status_code == 201
        data = response.json()
        assert "session_id" in data
        assert data["warehouse_id"] == wh.id
        assert data["status"] == "COMPLETED"
        assert len(data["agent_executions"]) == 1

def test_warehouse_not_found(db_session):
    _, _, _, headers = db_session
    response = client.post("/discovery/execute", json={"warehouse_id": 99999}, headers=headers)
    assert response.status_code == 404

def test_warehouse_inactive(db_session):
    _, _, wh_inactive, headers = db_session
    response = client.post("/discovery/execute", json={"warehouse_id": wh_inactive.id}, headers=headers)
    assert response.status_code == 400
    assert "inactive warehouse" in response.json()["detail"]

def test_invalid_request(db_session):
    _, _, _, headers = db_session
    response = client.post("/discovery/execute", json={"warehouse_id": "not_an_int"}, headers=headers)
    assert response.status_code == 422

def test_execution_with_skipped_agent(db_session):
    session, wh, _, headers = db_session
    
    with patch("app.api.discovery.AgentOrchestrator") as mock_orchestrator_class:
        mock_instance = MagicMock()
        mock_orchestrator_class.return_value = mock_instance
        mock_instance.execute_parallel.return_value = {
            "session_id": str(uuid.uuid4()),
            "total_execution_ms": 100.0,
            "completed": [],
            "failed": [],
            "skipped": ["metadata"],
            "agent_execution": [
                {
                    "agent": "metadata",
                    "started_at": "2023-01-01T00:00:00+00:00",
                    "finished_at": "2023-01-01T00:00:01+00:00"
                }
            ]
        }
        
        response = client.post("/discovery/execute", json={"warehouse_id": wh.id}, headers=headers)
        assert response.status_code == 201
        assert response.json()["status"] == "COMPLETED"

def test_execution_with_failed_agent(db_session):
    session, wh, _, headers = db_session
    
    with patch("app.api.discovery.AgentOrchestrator") as mock_orchestrator_class:
        mock_instance = MagicMock()
        mock_orchestrator_class.return_value = mock_instance
        mock_instance.execute_parallel.return_value = {
            "session_id": str(uuid.uuid4()),
            "total_execution_ms": 100.0,
            "completed": [],
            "failed": ["metadata"],
            "skipped": [],
            "agent_execution": [
                {
                    "agent": "metadata",
                    "started_at": "2023-01-01T00:00:00+00:00",
                    "finished_at": "2023-01-01T00:00:01+00:00"
                }
            ]
        }
        
        response = client.post("/discovery/execute", json={"warehouse_id": wh.id}, headers=headers)
        assert response.status_code == 201
        assert response.json()["status"] == "FAILED"

def test_persistence_validation_error(db_session):
    session, wh, _, headers = db_session
    
    with patch("app.api.discovery.AgentOrchestrator") as mock_orchestrator_class:
        mock_instance = MagicMock()
        mock_orchestrator_class.return_value = mock_instance
        session_id = str(uuid.uuid4())
        mock_instance.execute_parallel.return_value = {
            "session_id": session_id,
            "total_execution_ms": 100.0,
            "completed": ["metadata"],
            "failed": [],
            "skipped": [],
            "agent_execution": [
                {
                    # Missing agent name
                    "started_at": "2023-01-01T00:00:00+00:00",
                    "finished_at": "2023-01-01T00:00:01+00:00"
                }
            ]
        }
        
        response = client.post("/discovery/execute", json={"warehouse_id": wh.id}, headers=headers)
        assert response.status_code == 422
        assert "missing agent name" in response.json()["detail"].lower()
        
        # Verify nothing was persisted
        count = session.query(DiscoverySession).filter_by(session_id=session_id).count()
        assert count == 0

def test_unauthenticated_request(db_session):
    session, wh, _, _ = db_session
    response = client.post("/discovery/execute", json={"warehouse_id": wh.id})
    assert response.status_code == 401

def test_explicit_context_api_propagation(db_session):
    """
    Verify the discovery API creates one context and passes it through to TaskFactory and AgentOrchestrator.
    """
    session, wh, _, headers = db_session
    
    with patch("app.api.discovery.TaskFactory") as mock_task_factory_class, \
         patch("app.api.discovery.AgentOrchestrator") as mock_orchestrator_class:
         
        mock_factory_instance = MagicMock()
        mock_task_factory_class.return_value = mock_factory_instance
        mock_factory_instance.build_metadata_discovery.return_value = []
        
        mock_orchestrator_instance = MagicMock()
        mock_orchestrator_class.return_value = mock_orchestrator_instance
        mock_orchestrator_instance.execute_parallel.return_value = {
            "session_id": str(uuid.uuid4()),
            "total_execution_ms": 10.0,
            "completed": [],
            "failed": [],
            "skipped": [],
            "agent_execution": [],
            "agent_results": {}
        }
        
        response = client.post("/discovery/execute", json={"warehouse_id": wh.id}, headers=headers)
        
        assert response.status_code == 201
        
        # Verify TaskFactory was called with context
        mock_factory_instance.build_metadata_discovery.assert_called_once()
        args, kwargs = mock_factory_instance.build_metadata_discovery.call_args
        assert len(args) == 2, "Expected warehouse and context"
        context = args[1]
        from app.context.shared_context import SharedContext
        assert isinstance(context, SharedContext), "Expected context to be a SharedContext"
        
        # Verify AgentOrchestrator was instantiated with the EXACT SAME context
        mock_orchestrator_class.assert_called_once_with(context=context)
