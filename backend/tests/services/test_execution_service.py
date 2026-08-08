import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError

from app.database.base import Base
from app.models.warehouse import Warehouse
from app.models.execution import DiscoverySession, AgentExecution
from app.services.execution_service import ExecutionService
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

# Use an in-memory SQLite database for testing
engine = create_engine("sqlite:///:memory:")
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session() -> Session:
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    
    # Create a dummy warehouse for foreign key constraints
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
    session.commit()
    session.refresh(wh)
    
    yield session
    
    session.close()
    Base.metadata.drop_all(bind=engine)


def test_successful_execution_persistence(db_session: Session):
    warehouse = db_session.query(Warehouse).first()
    session_id = str(uuid.uuid4())
    
    execution_summary = {
        "session_id": session_id,
        "total_execution_ms": 500.5,
        "completed": ["metadata", "statistics"],
        "failed": [],
        "skipped": [],
        "agent_execution": [
            {
                "agent": "metadata",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "duration_ms": 250.0,
                "wave": 1
            },
            {
                "agent": "statistics",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "duration_ms": 250.5,
                "wave": 1
            }
        ],
        "agent_results": {
            "recommendation": {
                "summary": {"total": 1},
                "recommendations": [{"title": "Rec 1"}]
            }
        }
    }
    
    result = ExecutionService.persist_execution(db_session, warehouse.id, execution_summary)
    
    assert result.session_id == session_id
    assert result.warehouse_id == warehouse.id
    assert result.status == "COMPLETED"
    assert result.total_duration_ms == 500.5
    assert result.recommendations["summary"]["total"] == 1
    assert len(result.agent_executions) == 2
    
    agents = {a.agent_name: a for a in result.agent_executions}
    assert "metadata" in agents
    assert agents["metadata"].status == "COMPLETED"
    assert agents["metadata"].wave == 1
    assert agents["statistics"].duration_ms == 250.5


def test_failed_execution_persistence(db_session: Session):
    warehouse = db_session.query(Warehouse).first()
    session_id = str(uuid.uuid4())
    
    execution_summary = {
        "session_id": session_id,
        "total_execution_ms": 200,
        "completed": ["metadata"],
        "failed": ["security"],
        "skipped": [],
        "agent_execution": [
            {
                "agent": "metadata",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "duration_ms": 100.0,
                "wave": 1
            },
            {
                "agent": "security",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "duration_ms": 100.0,
                "wave": 2,
                "error": "Connection timeout"
            }
        ]
    }
    
    result = ExecutionService.persist_execution(db_session, warehouse.id, execution_summary)
    
    assert result.status == "FAILED"
    agents = {a.agent_name: a for a in result.agent_executions}
    assert agents["security"].status == "FAILED"
    assert agents["security"].error == "Connection timeout"


def test_skipped_agent_persistence(db_session: Session):
    warehouse = db_session.query(Warehouse).first()
    session_id = str(uuid.uuid4())
    
    execution_summary = {
        "session_id": session_id,
        "completed": ["metadata"],
        "failed": ["security"],
        "skipped": ["recommendation"],
        "agent_execution": [
            {
                "agent": "recommendation",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "wave": 3
            }
        ]
    }
    
    result = ExecutionService.persist_execution(db_session, warehouse.id, execution_summary)
    agents = {a.agent_name: a for a in result.agent_executions}
    assert agents["recommendation"].status == "SKIPPED"


def test_transaction_rollback(db_session: Session):
    warehouse = db_session.query(Warehouse).first()
    session_id = str(uuid.uuid4())
    
    execution_summary = {
        "session_id": session_id,
        "total_execution_ms": 100,
        "completed": ["metadata"],
        "failed": [],
        "skipped": [],
        "agent_execution": [
            {
                "agent": "metadata",
                # Missing required timestamps will cause IntegrityError due to nullable=False
            }
        ]
    }
    
    with pytest.raises(Exception):
        ExecutionService.persist_execution(db_session, None, execution_summary)
        
    # Verify rollback
    count = db_session.query(DiscoverySession).filter_by(session_id=session_id).count()
    assert count == 0


def test_duplicate_session_id_behavior(db_session: Session):
    warehouse = db_session.query(Warehouse).first()
    session_id = str(uuid.uuid4())
    
    execution_summary = {
        "session_id": session_id,
        "total_execution_ms": 100,
        "completed": [],
        "failed": [],
        "skipped": [],
        "agent_execution": []
    }
    
    # First persistence should succeed
    ExecutionService.persist_execution(db_session, warehouse.id, execution_summary)
    
    # Second persistence should fail due to unique constraint on session_id
    with pytest.raises(IntegrityError):
        ExecutionService.persist_execution(db_session, warehouse.id, execution_summary)

def test_invalid_agent_status_raises_valueerror(db_session: Session):
    warehouse = db_session.query(Warehouse).first()
    session_id = str(uuid.uuid4())
    
    execution_summary = {
        "session_id": session_id,
        "total_execution_ms": 100,
        "completed": ["metadata"],
        "failed": [],
        "skipped": [],
        "agent_execution": [
            {
                "agent": "metadata",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat()
            },
            {
                "agent": "security", # Not in completed/failed/skipped
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat()
            }
        ]
    }
    
    with pytest.raises(ValueError, match="Agent 'security' has no valid execution status"):
        ExecutionService.persist_execution(db_session, warehouse.id, execution_summary)
        
    # Verify rollback
    count = db_session.query(DiscoverySession).filter_by(session_id=session_id).count()
    assert count == 0

def test_session_status_semantics(db_session: Session):
    # failed = [], skipped = ["recommendation"] -> COMPLETED
    warehouse = db_session.query(Warehouse).first()
    session_id = str(uuid.uuid4())
    
    execution_summary = {
        "session_id": session_id,
        "total_execution_ms": 100,
        "completed": ["metadata"],
        "failed": [],
        "skipped": ["recommendation"],
        "agent_execution": [
            {
                "agent": "metadata",
                "started_at": datetime.now(timezone.utc).isoformat()
            },
            {
                "agent": "recommendation",
                "started_at": datetime.now(timezone.utc).isoformat()
            }
        ]
    }
    
    result = ExecutionService.persist_execution(db_session, warehouse.id, execution_summary)
    assert result.status == "COMPLETED"

def test_conflicting_agent_status_raises_valueerror(db_session: Session):
    warehouse = db_session.query(Warehouse).first()
    session_id = str(uuid.uuid4())
    
    execution_summary = {
        "session_id": session_id,
        "total_execution_ms": 100,
        "completed": ["metadata"],
        "failed": ["metadata"], # Conflict: metadata is in both completed and failed
        "skipped": [],
        "agent_execution": [
            {
                "agent": "metadata",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat()
            }
        ]
    }
    
    with pytest.raises(ValueError, match="Agent 'metadata' must have exactly one execution status"):
        ExecutionService.persist_execution(db_session, warehouse.id, execution_summary)
        
    # Verify rollback
    count = db_session.query(DiscoverySession).filter_by(session_id=session_id).count()
    assert count == 0

def test_missing_agent_name_raises_valueerror(db_session: Session):
    warehouse = db_session.query(Warehouse).first()
    session_id = str(uuid.uuid4())
    
    execution_summary = {
        "session_id": session_id,
        "total_execution_ms": 100,
        "completed": ["metadata"],
        "failed": [],
        "skipped": [],
        "agent_execution": [
            {
                # Missing 'agent'
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat()
            }
        ]
    }
    
    with pytest.raises(ValueError, match="Agent execution is missing agent name"):
        ExecutionService.persist_execution(db_session, warehouse.id, execution_summary)
        
    # Verify rollback
    count = db_session.query(DiscoverySession).filter_by(session_id=session_id).count()
    assert count == 0
