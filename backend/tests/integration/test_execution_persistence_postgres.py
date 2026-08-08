import uuid
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.database.base import Base
from app.models.warehouse import Warehouse
from app.models.execution import DiscoverySession, AgentExecution
from app.services.execution_service import ExecutionService

# Check if PostgreSQL is configured (skip if not)
if not settings.TEST_DATABASE_URL or "postgresql" not in settings.TEST_DATABASE_URL:
    pytest.skip("PostgreSQL integration test requires configured TEST_DATABASE_URL", allow_module_level=True)

try:
    engine = create_engine(settings.TEST_DATABASE_URL)
    engine.connect().close()
except Exception:
    pytest.skip("Could not connect to PostgreSQL test database", allow_module_level=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def postgres_session():
    # Make sure all tables exist
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    
    # Create isolated test warehouse
    wh = Warehouse(
        name=f"test_postgres_wh_{uuid.uuid4()}",
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
    
    yield session, wh
    
    # Clean up records created by the test
    # Delete child executions first (or rely on cascade, but manual delete is safer for testing)
    session.query(AgentExecution).filter(
        AgentExecution.session_id.in_(
            session.query(DiscoverySession.id).filter(DiscoverySession.warehouse_id == wh.id)
        )
    ).delete(synchronize_session=False)
    session.query(DiscoverySession).filter(DiscoverySession.warehouse_id == wh.id).delete(synchronize_session=False)
    session.delete(wh)
    session.commit()
    session.close()


def test_postgresql_execution_persistence(postgres_session):
    session, warehouse = postgres_session
    
    session_id = str(uuid.uuid4())
    
    execution_summary = {
        "session_id": session_id,
        "total_execution_ms": 1000.0,
        "completed": ["metadata", "statistics", "data_quality"],
        "failed": [],
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
                "agent": "statistics",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "duration_ms": 200.0,
                "wave": 1
            },
            {
                "agent": "data_quality",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "duration_ms": 150.0,
                "wave": 2
            }
        ],
        "agent_results": {
            "recommendation": {
                "summary": {
                    "recommendation_count": 1
                },
                "recommendations": [
                    {
                        "recommendation_type": "test",
                        "priority": "LOW",
                        "category": "Test"
                    }
                ],
                "priority": {
                    "high": [],
                    "medium": [],
                    "low": []
                }
            }
        }
    }
    
    # Call persist_execution
    result = ExecutionService.persist_execution(session, warehouse.id, execution_summary)
    
    # Verify DiscoverySession exists in PostgreSQL
    db_session = session.query(DiscoverySession).filter_by(session_id=session_id).first()
    assert db_session is not None
    assert db_session.warehouse_id == warehouse.id
    assert db_session.status == "COMPLETED"
    assert db_session.total_duration_ms == 1000.0
    
    # Verify AgentExecution rows and relationships
    assert len(db_session.agent_executions) == 3
    agents = {a.agent_name: a for a in db_session.agent_executions}
    assert "data_quality" in agents
    assert agents["data_quality"].status == "COMPLETED"
    
    # Verify JSONB recommendation field stored correctly
    recs = db_session.recommendations
    assert recs["summary"]["recommendation_count"] == 1
    assert recs["recommendations"][0]["recommendation_type"] == "test"
    assert recs["recommendations"][0]["priority"] == "LOW"
    assert "high" in recs["priority"]
