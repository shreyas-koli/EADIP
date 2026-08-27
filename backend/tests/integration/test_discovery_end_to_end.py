import uuid
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.config import settings
from app.database.base import Base
from app.database.session import get_db
from app.models.warehouse import Warehouse
from app.models.execution import DiscoverySession, AgentExecution
from app.auth.jwt import create_access_token
from app.core.security import encrypt_credential

client = TestClient(app)

@pytest.fixture(scope="function")
def e2e_session(tmp_path):
    db_path = tmp_path / "test_e2e.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 15},
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    def override_get_db():
        try:
            db = SessionLocal()
            yield db
        finally:
            db.close()
            
    app.dependency_overrides[get_db] = override_get_db
    
    # Make sure all tables exist
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    
    # Create test user for auth
    from app.models.user import User
    from app.core.security import hash_password
    test_email = f"test_{uuid.uuid4()}@example.com"
    test_user = User(full_name="Test User", email=test_email, hashed_password=hash_password("password"))
    session.add(test_user)
    
    # Create isolated test warehouse
    wh = Warehouse(
        name=f"test_postgres_wh_{uuid.uuid4()}",
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
    
    yield session, wh, headers
    
    # Clean up records created by the test
    session.query(AgentExecution).filter(
        AgentExecution.session_id.in_(
            session.query(DiscoverySession.id).filter(DiscoverySession.warehouse_id == wh.id)
        )
    ).delete(synchronize_session=False)
    session.query(DiscoverySession).filter(DiscoverySession.warehouse_id == wh.id).delete(synchronize_session=False)
    session.delete(wh)
    session.delete(test_user)
    session.commit()
    session.close()
    
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()

@pytest.fixture
def mock_external_infrastructure():
    """
    Mock only external infrastructure (MetadataInspector and StatisticsAnalyzer)
    that connect to a real remote database. The rest of the pipeline executes for real.
    """
    with patch("app.agents.metadata_agent.MetadataInspector") as mock_metadata_inspector, \
         patch("app.agents.statistics_agent.StatisticsAnalyzer") as mock_statistics_analyzer, \
         patch("app.agents.monitoring_agent.MonitoringAnalyzer") as mock_monitoring_analyzer:
         
        mock_inspector_instance = MagicMock()
        mock_metadata_inspector.return_value = mock_inspector_instance
        mock_inspector_instance.inspect_database.return_value = {
            "schemas": {
                "public": {
                    "tables": {
                        "users": {
                            "columns": [
                                {"name": "id", "type": "INTEGER", "primary_key": True, "nullable": False},
                                {"name": "password", "type": "VARCHAR", "primary_key": False, "nullable": True},
                            ]
                        }
                    }
                }
            }
        }
        
        mock_stats_instance = MagicMock()
        mock_statistics_analyzer.return_value = mock_stats_instance
        mock_stats_instance.analyse.return_value = {
            "tables": [
                {
                    "schema": "public",
                    "table_name": "users",
                    "estimated_row_count": 100,
                    "total_columns": 2
                }
            ]
        }
        
        mock_monitoring_instance = MagicMock()
        mock_monitoring_analyzer.return_value = mock_monitoring_instance
        mock_monitoring_instance.analyse.return_value = {
            "summary": {"partial_failure": False},
            "findings": [],
            "errors": []
        }
        
        yield mock_inspector_instance, mock_stats_instance, mock_monitoring_instance

def test_end_to_end_successful_execution(e2e_session, mock_external_infrastructure):
    """
    Test a full successful end-to-end execution of the discovery pipeline.
    """
    session, wh, headers = e2e_session
    mock_inspector, mock_stats, mock_monitoring = mock_external_infrastructure
    
    # 1. Execute the HTTP request
    response = client.post("/discovery/execute", json={"warehouse_id": wh.id}, headers=headers)
    
    # A. Verify HTTP layer
    assert response.status_code == 201
    
    # B. Verify Response
    data = response.json()
    assert "session_id" in data
    assert data["warehouse_id"] == wh.id
    assert data["status"] == "COMPLETED"
    assert "agent_executions" in data
    assert len(data["agent_executions"]) == 6
    
    session_id = data["session_id"]
    
    # Verify execution order / dependencies (wave numbers should reflect the graph)
    agents = {a["agent_name"]: a for a in data["agent_executions"]}
    assert "metadata" in agents and "statistics" in agents and "monitoring" in agents
    assert "security" in agents and "data_quality" in agents
    assert "recommendation" in agents
    
    # Wave 1: metadata, statistics, monitoring
    assert agents["metadata"]["wave"] == 1
    assert agents["statistics"]["wave"] == 1
    assert agents["monitoring"]["wave"] == 1
    
    # Wave 2: security, data_quality
    assert agents["security"]["wave"] == 2
    assert agents["data_quality"]["wave"] == 2
    
    # Wave 3: recommendation
    assert agents["recommendation"]["wave"] == 3
    
    # C. Orchestration / Execution Summary is validated inherently by the response matching
    
    # D. Verify Persistence
    db_session = session.query(DiscoverySession).filter_by(session_id=session_id).first()
    assert db_session is not None
    assert db_session.session_id == session_id
    assert db_session.warehouse_id == wh.id
    assert db_session.status == "COMPLETED"
    
    assert len(db_session.agent_executions) == 6
    db_agents = {a.agent_name: a for a in db_session.agent_executions}
    assert db_agents["metadata"].status == "COMPLETED"
    assert db_agents["statistics"].status == "COMPLETED"
    assert db_agents["monitoring"].status == "COMPLETED"
    assert db_agents["security"].status == "COMPLETED"
    assert db_agents["data_quality"].status == "COMPLETED"
    assert db_agents["recommendation"].status == "COMPLETED"
    
    # E. Verify Recommendation persistence and structure
    recs = db_session.recommendations
    assert recs is not None
    assert "summary" in recs
    assert "recommendations" in recs
    assert "priority" in recs
    
    # We expect some rules to trigger based on our mock data (e.g. nullable sensitive column 'password')
    # Just verify the structure survives the database round trip
    assert isinstance(recs["summary"]["recommendation_count"], int)
    
    # F. Response/database consistency
    assert response.json()["session_id"] == db_session.session_id
    assert response.json()["status"] == db_session.status

def test_end_to_end_skipped_agent_semantics(e2e_session, mock_external_infrastructure):
    """
    Test skipped agent semantics end-to-end where an upstream dependency fails.
    """
    session, wh, headers = e2e_session
    mock_inspector, mock_stats, mock_monitoring = mock_external_infrastructure
    
    # Make the upstream metadata dependency fail
    mock_inspector.inspect_database.side_effect = Exception("Failed to connect to database")
    
    response = client.post("/discovery/execute", json={"warehouse_id": wh.id}, headers=headers)
    
    assert response.status_code == 201
    data = response.json()
    
    # Since metadata failed, security, data_quality, and recommendation should be skipped.
    assert data["status"] == "FAILED" # Session should be FAILED since at least one failed
    
    agents = {a["agent_name"]: a for a in data["agent_executions"]}
    
    # metadata should have failed
    assert agents["metadata"]["status"] == "FAILED"
    
    # downstream agents should be skipped
    assert agents["security"]["status"] == "SKIPPED"
    assert agents["data_quality"]["status"] == "SKIPPED"
    assert agents["recommendation"]["status"] == "SKIPPED"
    
    # statistics and monitoring should still complete (independent)
    assert agents["statistics"]["status"] == "COMPLETED"
    assert agents["monitoring"]["status"] == "COMPLETED"
    
    # Verify persistence preserves the distinction
    session_id = data["session_id"]
    db_session = session.query(DiscoverySession).filter_by(session_id=session_id).first()
    assert db_session.status == "FAILED"
    
    db_agents = {a.agent_name: a for a in db_session.agent_executions}
    assert db_agents["metadata"].status == "FAILED"
    assert db_agents["security"].status == "SKIPPED"
    assert db_agents["data_quality"].status == "SKIPPED"
    assert db_agents["recommendation"].status == "SKIPPED"
    assert db_agents["statistics"].status == "COMPLETED"
    assert db_agents["monitoring"].status == "COMPLETED"

def test_end_to_end_skipped_without_failure_semantics(e2e_session, mock_external_infrastructure):
    """
    Verify the existing contract: failed = [], skipped != [] must produce session.status == COMPLETED.
    We simulate this by patching the orchestrator to forcibly skip an agent without failure.
    (This tests the session-level status aggregation logic).
    """
    session, wh, headers = e2e_session
    mock_inspector, mock_stats, mock_monitoring = mock_external_infrastructure
    
    with patch("app.orchestrator.agent_orchestrator.AgentOrchestrator.execute_parallel") as mock_exec:
        mock_exec.return_value = {
            "session_id": str(uuid.uuid4()),
            "total_execution_ms": 100.0,
            "completed": ["metadata", "statistics", "monitoring"],
            "failed": [],
            "skipped": ["security", "data_quality", "recommendation"],
            "agent_execution": [
                {"agent": "metadata", "status": "COMPLETED", "started_at": "2023-01-01T00:00:00+00:00", "finished_at": "2023-01-01T00:00:01+00:00", "duration_ms": 100, "wave": 1},
                {"agent": "statistics", "status": "COMPLETED", "started_at": "2023-01-01T00:00:00+00:00", "finished_at": "2023-01-01T00:00:01+00:00", "duration_ms": 100, "wave": 1},
                {"agent": "monitoring", "status": "COMPLETED", "started_at": "2023-01-01T00:00:00+00:00", "finished_at": "2023-01-01T00:00:01+00:00", "duration_ms": 100, "wave": 1},
                {"agent": "security", "status": "SKIPPED", "started_at": "2023-01-01T00:00:00+00:00", "finished_at": "2023-01-01T00:00:01+00:00", "duration_ms": 0, "wave": 2},
                {"agent": "data_quality", "status": "SKIPPED", "started_at": "2023-01-01T00:00:00+00:00", "finished_at": "2023-01-01T00:00:01+00:00", "duration_ms": 0, "wave": 2},
                {"agent": "recommendation", "status": "SKIPPED", "started_at": "2023-01-01T00:00:00+00:00", "finished_at": "2023-01-01T00:00:01+00:00", "duration_ms": 0, "wave": 3}
            ],
            "agent_results": {}
        }
        
        response = client.post("/discovery/execute", json={"warehouse_id": wh.id}, headers=headers)
        
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "COMPLETED"

def test_end_to_end_persistence_failure_rollback(e2e_session, mock_external_infrastructure):
    """
    Verify that if persistence fails after execution starts, no partial DiscoverySession remains.
    """
    session, wh, headers = e2e_session
    mock_inspector, mock_stats, mock_monitoring = mock_external_infrastructure
    
    # We will patch ExecutionService to raise an error during persistence
    with patch("app.services.execution_service.ExecutionService.persist_execution", side_effect=ValueError("Database error during persistence")):
        response = client.post("/discovery/execute", json={"warehouse_id": wh.id}, headers=headers)
        
        assert response.status_code == 422
        assert "Database error during persistence" in response.json()["detail"]
        
    # Verify no records were persisted for this warehouse in this test
    assert session.query(DiscoverySession).filter_by(warehouse_id=wh.id).count() == 0

def test_request_isolation_concurrency(e2e_session, mock_external_infrastructure):
    """
    Test request isolation / concurrency.
    Verify that two independent API requests receive independent SharedContext instances
    and do not leak state.
    """
    session, wh, headers = e2e_session
    mock_inspector, mock_stats, mock_monitoring = mock_external_infrastructure
    
    import concurrent.futures
    
    def make_request():
        return client.post("/discovery/execute", json={"warehouse_id": wh.id}, headers=headers)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future1 = executor.submit(make_request)
        future2 = executor.submit(make_request)
        
        response1 = future1.result()
        response2 = future2.result()
    
    if response1.status_code != 201:
        print(f"Response 1 error: {response1.json()}")
    if response2.status_code != 201:
        print(f"Response 2 error: {response2.json()}")
        
    assert response1.status_code == 201
    assert response2.status_code == 201
    
    data1 = response1.json()
    data2 = response2.json()
    
    assert data1["session_id"] != data2["session_id"], "Context/Session ID should be isolated per request"
    
    # Verify both sessions were independently persisted
    assert session.query(DiscoverySession).filter_by(session_id=data1["session_id"]).count() == 1
    assert session.query(DiscoverySession).filter_by(session_id=data2["session_id"]).count() == 1
