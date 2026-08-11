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
from app.core.security import encrypt_credential

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
        encrypted_password=encrypt_credential("encrypted"),
        is_active=True,
        owner=test_user
    )
    session.add(wh)
    
    wh_inactive = Warehouse(
        name=f"test_wh_inactive_{uuid.uuid4()}",
        db_type="PostgreSQL",
        host="localhost",
        port=5432,
        database_name="test_db",
        username="test_user",
        encrypted_password=encrypt_credential("encrypted"),
        is_active=False,
        owner=test_user
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

# --- HISTORY API TESTS ---

def test_get_history_empty(db_session):
    session, wh, _, headers = db_session
    response = client.get(f"/warehouses/{wh.id}/history", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["page_size"] == 10

def test_pagination_default(db_session):
    session, wh, _, headers = db_session
    from app.services.execution_service import ExecutionService
    # Create 12 records
    for i in range(12):
        ExecutionService.persist_execution(session, wh.id, {
            "session_id": f"api_test_sess_{i}",
            "completed": ["metadata"],
            "agent_execution": [{"agent": "metadata", "wave": 1}]
        })
        
    response = client.get(f"/warehouses/{wh.id}/history", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 10
    assert data["total"] == 12
    assert data["page"] == 1
    assert data["page_size"] == 10

def test_pagination_second_page(db_session):
    session, wh, _, headers = db_session
    from app.services.execution_service import ExecutionService
    for i in range(12):
        ExecutionService.persist_execution(session, wh.id, {
            "session_id": f"api_test_sess_{i}",
            "completed": ["metadata"],
            "agent_execution": [{"agent": "metadata", "wave": 1}]
        })
    response = client.get(f"/warehouses/{wh.id}/history?page=2&page_size=10", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["page"] == 2
    assert data["total"] == 12

def test_pagination_custom_size(db_session):
    session, wh, _, headers = db_session
    from app.services.execution_service import ExecutionService
    for i in range(12):
        ExecutionService.persist_execution(session, wh.id, {
            "session_id": f"api_test_sess_{i}",
            "completed": ["metadata"],
            "agent_execution": [{"agent": "metadata", "wave": 1}]
        })
    response = client.get(f"/warehouses/{wh.id}/history?page=1&page_size=5", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 5
    assert data["page_size"] == 5
    assert data["total"] == 12

def test_pagination_beyond_available(db_session):
    session, wh, _, headers = db_session
    from app.services.execution_service import ExecutionService
    for i in range(12):
        ExecutionService.persist_execution(session, wh.id, {
            "session_id": f"api_test_sess_{i}",
            "completed": ["metadata"],
            "agent_execution": [{"agent": "metadata", "wave": 1}]
        })
    response = client.get(f"/warehouses/{wh.id}/history?page=10&page_size=10", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 12

def test_filter_completed(db_session):
    session, wh, _, headers = db_session
    from app.services.execution_service import ExecutionService
    # Add a failed session
    ExecutionService.persist_execution(session, wh.id, {
        "session_id": f"api_test_sess_fail",
        "failed": ["metadata"],
        "agent_execution": [{"agent": "metadata", "status": "FAILED", "wave": 1}]
    })
    
    response = client.get(f"/warehouses/{wh.id}/history?status=COMPLETED", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert all(item["status"] == "COMPLETED" for item in data["items"])

def test_filter_failed(db_session):
    session, wh, _, headers = db_session
    from app.services.execution_service import ExecutionService
    # Add a failed session
    ExecutionService.persist_execution(session, wh.id, {
        "session_id": f"api_test_sess_fail",
        "failed": ["metadata"],
        "agent_execution": [{"agent": "metadata", "status": "FAILED", "wave": 1}]
    })
    response = client.get(f"/warehouses/{wh.id}/history?status=FAILED", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["status"] == "FAILED"

def test_invalid_status(db_session):
    session, wh, _, headers = db_session
    response = client.get(f"/warehouses/{wh.id}/history?status=INVALID", headers=headers)
    assert response.status_code == 422

def test_invalid_page(db_session):
    session, wh, _, headers = db_session
    response = client.get(f"/warehouses/{wh.id}/history?page=0", headers=headers)
    assert response.status_code == 422

def test_invalid_page_size(db_session):
    session, wh, _, headers = db_session
    response = client.get(f"/warehouses/{wh.id}/history?page_size=101", headers=headers)
    assert response.status_code == 422
    
def test_get_execution_detail(db_session):
    session, wh, _, headers = db_session
    from app.services.execution_service import ExecutionService
    session_id = "api_test_sess_detail"
    ExecutionService.persist_execution(session, wh.id, {
        "session_id": session_id,
        "completed": ["metadata"],
        "agent_execution": [{"agent": "metadata", "wave": 1, "duration_ms": 100.0}],
        "agent_results": {"recommendation": {"rec1": "val1"}}
    })
    
    response = client.get(f"/warehouses/{wh.id}/history/{session_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert len(data["agent_executions"]) == 1
    assert data["agent_executions"][0]["agent_name"] == "metadata"
    assert data["recommendations"] == {"rec1": "val1"}

def test_get_history_invalid_warehouse(db_session):
    session, wh, _, headers = db_session
    response = client.get("/warehouses/9999/history", headers=headers)
    assert response.status_code == 404

def test_get_execution_invalid_session(db_session):
    session, wh, _, headers = db_session
    response = client.get(f"/warehouses/{wh.id}/history/nonexistent", headers=headers)
    assert response.status_code == 404

def test_cross_warehouse_isolation(db_session):
    session, wh1, _, headers = db_session
    
    # Create second warehouse
    wh2 = Warehouse(
        name=f"test_wh_api_{uuid.uuid4()}",
        db_type="PostgreSQL",
        host="localhost",
        port=5432,
        database_name="test_db2",
        username="test_user",
        encrypted_password=encrypt_credential("encrypted"),
        is_active=True
    )
    session.add(wh2)
    session.commit()
    session.refresh(wh2)
    
    # Create session in warehouse 2
    from app.services.execution_service import ExecutionService
    sess_id = "api_test_cross"
    ExecutionService.persist_execution(session, wh2.id, {
        "session_id": sess_id,
        "completed": ["metadata"],
        "agent_execution": [{"agent": "metadata", "wave": 1}]
    })
    
    # Try to access it from warehouse 1
    response = client.get(f"/warehouses/{wh1.id}/history/{sess_id}", headers=headers)
    assert response.status_code == 404

# --- SECURITY API TESTS ---

def test_missing_authentication_history(db_session):
    session, wh, _, _ = db_session
    response = client.get(f"/warehouses/{wh.id}/history")
    assert response.status_code == 401
    
def test_invalid_authentication_history(db_session):
    session, wh, _, _ = db_session
    response = client.get(f"/warehouses/{wh.id}/history", headers={"Authorization": "Bearer invalid_token"})
    assert response.status_code == 401
    
def test_missing_authentication_execution(db_session):
    session, wh, _, _ = db_session
    response = client.get(f"/warehouses/{wh.id}/history/dummy_session")
    assert response.status_code == 401

def test_history_isolation(db_session):
    session, wh1, _, headers = db_session
    
    wh2 = Warehouse(
        name=f"test_wh_api_{uuid.uuid4()}",
        db_type="PostgreSQL",
        host="localhost",
        port=5432,
        database_name="test_db2",
        username="test_user",
        encrypted_password=encrypt_credential("encrypted"),
        is_active=True
    )
    session.add(wh2)
    session.commit()
    session.refresh(wh2)
    
    from app.services.execution_service import ExecutionService
    ExecutionService.persist_execution(session, wh1.id, {
        "session_id": "api_test_wh1",
        "completed": ["metadata"],
        "agent_execution": [{"agent": "metadata", "wave": 1}]
    })
    
    ExecutionService.persist_execution(session, wh2.id, {
        "session_id": "api_test_wh2",
        "completed": ["metadata"],
        "agent_execution": [{"agent": "metadata", "wave": 1}]
    })
    
    response = client.get(f"/warehouses/{wh1.id}/history", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["session_id"] == "api_test_wh1"

def test_history_response_contract(db_session):
    session, wh, _, headers = db_session
    from app.services.execution_service import ExecutionService
    ExecutionService.persist_execution(session, wh.id, {
        "session_id": "api_test_contract",
        "completed": ["metadata"],
        "agent_execution": [{"agent": "metadata", "wave": 1}]
    })
    
    response = client.get(f"/warehouses/{wh.id}/history", headers=headers)
    assert response.status_code == 200
    data = response.json()
    item = data["items"][0]
    
    # Allowed fields in history
    allowed_keys = {"session_id", "warehouse_id", "started_at", "finished_at", "status", "total_duration_ms"}
    assert set(item.keys()) == allowed_keys
    
    # Explicitly verify sensitive/unwanted fields are missing
    assert "agent_executions" not in item
    assert "recommendations" not in item
    assert "encrypted_password" not in item
    assert "username" not in item

def test_detail_response_contract(db_session):
    session, wh, _, headers = db_session
    from app.services.execution_service import ExecutionService
    ExecutionService.persist_execution(session, wh.id, {
        "session_id": "api_test_detail_contract",
        "completed": ["metadata"],
        "agent_execution": [{"agent": "metadata", "wave": 1, "duration_ms": 100.0, "status": "COMPLETED"}],
        "agent_results": {"recommendation": {"rec1": "val1"}}
    })
    
    response = client.get(f"/warehouses/{wh.id}/history/api_test_detail_contract", headers=headers)
    assert response.status_code == 200
    data = response.json()
    
    # Detail fields
    allowed_keys = {"session_id", "warehouse_id", "started_at", "finished_at", "status", "total_duration_ms", "agent_executions", "recommendations"}
    assert set(data.keys()) == allowed_keys
    
    # Agent execution fields
    agent_exec = data["agent_executions"][0]
    agent_allowed_keys = {"agent_name", "status", "started_at", "finished_at", "duration_ms", "wave", "error"}
    assert set(agent_exec.keys()) == agent_allowed_keys
    
    # Ensure recommendations are returned unchanged
    assert data["recommendations"] == {"rec1": "val1"}

def test_null_field_handling(db_session):
    session, wh, _, headers = db_session
    from app.services.execution_service import ExecutionService
    # Seed an execution with missing optional fields
    ExecutionService.persist_execution(session, wh.id, {
        "session_id": "api_test_nulls",
        # no completed or failed, simulating a crash or immediate cancellation
        "failed": ["metadata"], # Make it FAILED status
        "agent_execution": [{
            "agent": "metadata", 
            "status": "FAILED", 
            "wave": 1,
            # Explicitly omitting duration_ms and finished_at
        }]
    })
    
    # Manually nullify finished_at on the session itself if persist_execution set it
    from app.models.execution import DiscoverySession, AgentExecution
    sess_obj = session.query(DiscoverySession).filter_by(session_id="api_test_nulls").first()
    sess_obj.finished_at = None
    sess_obj.total_duration_ms = None
    
    agent_obj = session.query(AgentExecution).filter_by(session_id=sess_obj.id).first()
    agent_obj.finished_at = None
    agent_obj.duration_ms = None
    agent_obj.error = None
    session.commit()
    
    response = client.get(f"/warehouses/{wh.id}/history/api_test_nulls", headers=headers)
    assert response.status_code == 200
    data = response.json()
    
    assert data["finished_at"] is None
    assert data["total_duration_ms"] is None
    
    agent_exec = data["agent_executions"][0]
    assert agent_exec["finished_at"] is None
    assert agent_exec["duration_ms"] is None
    assert agent_exec["error"] is None

def test_api_filter_and_pagination(db_session):
    session, wh, _, headers = db_session
    from app.services.execution_service import ExecutionService
    for i in range(8):
        ExecutionService.persist_execution(session, wh.id, {
            "session_id": f"api_test_comp_{i}",
            "completed": ["metadata"],
            "agent_execution": [{"agent": "metadata", "wave": 1}]
        })
    for i in range(5):
        ExecutionService.persist_execution(session, wh.id, {
            "session_id": f"api_test_fail_{i}",
            "failed": ["metadata"],
            "agent_execution": [{"agent": "metadata", "status": "FAILED", "wave": 1}]
        })
        
    response = client.get(f"/warehouses/{wh.id}/history?status=COMPLETED&page=2&page_size=5", headers=headers)
    assert response.status_code == 200
    data = response.json()
    
    assert len(data["items"]) == 3
    assert data["total"] == 8
    assert data["page"] == 2
    assert data["page_size"] == 5
    assert all(item["status"] == "COMPLETED" for item in data["items"])
