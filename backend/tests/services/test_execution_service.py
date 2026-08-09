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

# --- Retrieval Tests ---

def test_get_history_ordering(db_session: Session):
    warehouse = db_session.query(Warehouse).first()
    
    # Create multiple sessions
    for i in range(3):
        execution_summary = {
            "session_id": f"sess_{i}",
            "total_execution_ms": 100,
            "completed": ["metadata"],
            "failed": [],
            "skipped": [],
            "agent_execution": [
                {
                    "agent": "metadata",
                    "started_at": datetime.fromtimestamp(1600000000 + i * 1000, tz=timezone.utc).isoformat(),
                    "finished_at": datetime.fromtimestamp(1600000010 + i * 1000, tz=timezone.utc).isoformat()
                }
            ]
        }
        ExecutionService.persist_execution(db_session, warehouse.id, execution_summary)
        
    history = ExecutionService.get_history(db_session, warehouse.id)
    
    items = history["items"]
    assert len(items) == 3
    assert history["total"] == 3
    # Should be ordered by newest first (sess_2, sess_1, sess_0)
    assert items[0].session_id == "sess_2"
    assert items[1].session_id == "sess_1"
    assert items[2].session_id == "sess_0"

def test_get_history_empty(db_session: Session):
    warehouse = db_session.query(Warehouse).first()
    history = ExecutionService.get_history(db_session, warehouse.id)
    assert isinstance(history, dict)
    assert len(history["items"]) == 0
    assert history["total"] == 0

def test_get_execution_detail(db_session: Session):
    warehouse = db_session.query(Warehouse).first()
    session_id = str(uuid.uuid4())
    
    execution_summary = {
        "session_id": session_id,
        "total_execution_ms": 500,
        "completed": ["metadata"],
        "failed": [],
        "skipped": [],
        "agent_execution": [
            {
                "agent": "metadata",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "duration_ms": 100.0,
                "wave": 1
            }
        ],
        "agent_results": {
            "recommendation": {"key": "value"}
        }
    }
    
    ExecutionService.persist_execution(db_session, warehouse.id, execution_summary)
    
    # Retrieve
    session = ExecutionService.get_execution(db_session, warehouse.id, session_id)
    assert session is not None
    assert session.session_id == session_id
    assert session.warehouse_id == warehouse.id
    
    # Agent executions retrieved
    assert len(session.agent_executions) == 1
    assert session.agent_executions[0].agent_name == "metadata"
    assert session.agent_executions[0].duration_ms == 100.0
    
    # JSONB recommendation retrieved
    assert session.recommendations == {"key": "value"}

def test_get_execution_cross_warehouse_isolation(db_session: Session):
    # Setup a second warehouse
    wh2 = Warehouse(
        name=f"test_wh_{uuid.uuid4()}",
        db_type="PostgreSQL",
        host="localhost",
        port=5432,
        database_name="test_db2",
        username="test_user",
        encrypted_password="encrypted",
        is_active=True
    )
    db_session.add(wh2)
    db_session.commit()
    db_session.refresh(wh2)
    
    warehouse1 = db_session.query(Warehouse).first()
    
    # Create session A in warehouse 1
    sess_a_id = "sess_a"
    ExecutionService.persist_execution(db_session, warehouse1.id, {
        "session_id": sess_a_id,
        "completed": ["metadata"],
        "agent_execution": [{"agent": "metadata"}]
    })
    
    # Create session B in warehouse 2
    sess_b_id = "sess_b"
    ExecutionService.persist_execution(db_session, wh2.id, {
        "session_id": sess_b_id,
        "completed": ["metadata"],
        "agent_execution": [{"agent": "metadata"}]
    })
    
    # Try to access session B through warehouse 1
    result = ExecutionService.get_execution(db_session, warehouse1.id, sess_b_id)
    assert result is None

def test_get_execution_unknown_session(db_session: Session):
    warehouse = db_session.query(Warehouse).first()
    result = ExecutionService.get_execution(db_session, warehouse.id, "nonexistent")
    assert result is None

def test_retrieval_is_read_only(db_session: Session):
    warehouse = db_session.query(Warehouse).first()
    
    initial_count = db_session.query(DiscoverySession).count()
    
    ExecutionService.get_history(db_session, warehouse.id)
    ExecutionService.get_execution(db_session, warehouse.id, "fake")
    
    final_count = db_session.query(DiscoverySession).count()
    assert initial_count == final_count

# --- Pagination & Filtering Tests ---

def test_service_pagination(db_session: Session):
    warehouse = db_session.query(Warehouse).first()
    
    # Create 12 sessions
    for i in range(12):
        ExecutionService.persist_execution(db_session, warehouse.id, {
            "session_id": f"service_sess_{i}",
            "completed": ["metadata"],
            "agent_execution": [{"agent": "metadata", "wave": 1}]
        })
        
    result = ExecutionService.get_history(db_session, warehouse.id, page=1, page_size=10)
    assert len(result["items"]) == 10
    assert result["total"] == 12
    assert result["page"] == 1
    assert result["page_size"] == 10
    
    result_page2 = ExecutionService.get_history(db_session, warehouse.id, page=2, page_size=10)
    assert len(result_page2["items"]) == 2
    assert result_page2["total"] == 12
    assert result_page2["page"] == 2
    assert result_page2["page_size"] == 10
    
    # Verify no duplicates
    ids_page1 = {item.session_id for item in result["items"]}
    ids_page2 = {item.session_id for item in result_page2["items"]}
    assert ids_page1.isdisjoint(ids_page2)

def test_service_custom_page_size(db_session: Session):
    warehouse = db_session.query(Warehouse).first()
    for i in range(12):
        ExecutionService.persist_execution(db_session, warehouse.id, {
            "session_id": f"service_sess_{i}",
            "completed": ["metadata"],
            "agent_execution": [{"agent": "metadata", "wave": 1}]
        })
        
    result = ExecutionService.get_history(db_session, warehouse.id, page=1, page_size=5)
    assert len(result["items"]) == 5
    assert result["total"] == 12
    assert result["page"] == 1
    assert result["page_size"] == 5

def test_service_page_beyond_available(db_session: Session):
    warehouse = db_session.query(Warehouse).first()
    for i in range(12):
        ExecutionService.persist_execution(db_session, warehouse.id, {
            "session_id": f"service_sess_{i}",
            "completed": ["metadata"],
            "agent_execution": [{"agent": "metadata", "wave": 1}]
        })
        
    result = ExecutionService.get_history(db_session, warehouse.id, page=10, page_size=10)
    assert len(result["items"]) == 0
    assert result["total"] == 12
    assert result["page"] == 10
    assert result["page_size"] == 10

def test_service_completed_filter(db_session: Session):
    warehouse = db_session.query(Warehouse).first()
    
    # Create 1 COMPLETED and 1 FAILED
    ExecutionService.persist_execution(db_session, warehouse.id, {
        "session_id": "service_sess_comp",
        "completed": ["metadata"],
        "agent_execution": [{"agent": "metadata", "wave": 1}]
    })
    ExecutionService.persist_execution(db_session, warehouse.id, {
        "session_id": "service_sess_fail",
        "failed": ["metadata"],
        "agent_execution": [{"agent": "metadata", "status": "FAILED", "wave": 1}]
    })
    
    result = ExecutionService.get_history(db_session, warehouse.id, status="COMPLETED")
    assert len(result["items"]) == 1
    assert result["items"][0].status == "COMPLETED"
    assert result["total"] == 1

def test_service_failed_filter(db_session: Session):
    warehouse = db_session.query(Warehouse).first()
    
    ExecutionService.persist_execution(db_session, warehouse.id, {
        "session_id": "service_sess_comp",
        "completed": ["metadata"],
        "agent_execution": [{"agent": "metadata", "wave": 1}]
    })
    ExecutionService.persist_execution(db_session, warehouse.id, {
        "session_id": "service_sess_fail",
        "failed": ["metadata"],
        "agent_execution": [{"agent": "metadata", "status": "FAILED", "wave": 1}]
    })
    
    result = ExecutionService.get_history(db_session, warehouse.id, status="FAILED")
    assert len(result["items"]) == 1
    assert result["items"][0].status == "FAILED"
    assert result["total"] == 1

def test_service_filter_and_pagination_together(db_session: Session):
    warehouse = db_session.query(Warehouse).first()
    
    # 8 COMPLETED
    for i in range(8):
        ExecutionService.persist_execution(db_session, warehouse.id, {
            "session_id": f"service_sess_comp_{i}",
            "completed": ["metadata"],
            "agent_execution": [{"agent": "metadata", "wave": 1}]
        })
        
    # 5 FAILED
    for i in range(5):
        ExecutionService.persist_execution(db_session, warehouse.id, {
            "session_id": f"service_sess_fail_{i}",
            "failed": ["metadata"],
            "agent_execution": [{"agent": "metadata", "status": "FAILED", "wave": 1}]
        })
        
    result_p1 = ExecutionService.get_history(db_session, warehouse.id, status="COMPLETED", page=1, page_size=5)
    assert len(result_p1["items"]) == 5
    assert all(item.status == "COMPLETED" for item in result_p1["items"])
    assert result_p1["total"] == 8
    
    result_p2 = ExecutionService.get_history(db_session, warehouse.id, status="COMPLETED", page=2, page_size=5)
    assert len(result_p2["items"]) == 3
    assert all(item.status == "COMPLETED" for item in result_p2["items"])
    assert result_p2["total"] == 8
