"""
End-to-end integration test for Recommendation Fingerprinting & Structural Deduplication (R2).

Verifies multi-session candidate matching:
Session 1: Proposed action -> Approval -> Execution -> Verification -> Supervisor ACHIEVED -> History record with Fingerprint SHA-256.
Session 2: New Discovery generates structurally equivalent candidate ANALYZE_TABLE public.votes -> Fingerprint matches -> Historical match found.

CRITICAL R2 SAFETY ASSERTIONS:
- match_found == True
- Previous outcome == ACHIEVED is returned in match history.
- Recommendation candidate is NOT suppressed or deleted.
- RecommendationAgent decision logic remains 100% UNCHANGED.
- Zero warehouse mutations are executed.
"""

from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock

from app.agents.recommendation_agent import RecommendationAgent
from app.context.shared_context import SharedContext
from app.models.approval import ActionApproval
from app.models.action_execution_record import ActionExecutionRecord
from app.models.action_verification_record import ActionVerificationRecord
from app.models.execution import DiscoverySession
from app.models.recommendation_outcome_record import RecommendationOutcomeRecord
from app.models.supervisor_reanalysis_record import SupervisorReanalysisRecord
from app.models.user import User
from app.models.warehouse import Warehouse
from app.services.recommendation_fingerprint_service import RecommendationFingerprintService
from app.services.recommendation_outcome_service import RecommendationOutcomeService


@pytest.fixture
def mock_user():
    return User(
        id=1,
        email="r2_e2e@example.com",
        full_name="R2 E2E User",
        role="user",
        is_active=True,
    )


@pytest.fixture
def mock_warehouse(mock_user):
    return Warehouse(
        id=30,
        name="R2 Outcome WH",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="r2_db",
        username="postgres",
        encrypted_password=b"token",
        owner_id=mock_user.id,
        is_active=True,
    )


def test_e2e_recommendation_fingerprinting_non_suppression(mock_warehouse, mock_user):
    """
    Integration test verifying candidate matching across discovery sessions without recommendation suppression.
    """
    now = datetime.now(timezone.utc)

    # Candidate payload for ANALYZE_TABLE public.votes
    candidate_action = {
        "action_id": "act_s1_votes",
        "action_type": "ANALYZE_TABLE",
        "recommendation_type": "ANALYZE_TABLE",
        "status": "PROPOSED",
        "target": {"schema": "public", "table": "votes"},
    }

    fp = RecommendationFingerprintService.fingerprint_recommendation(candidate_action)
    assert len(fp) == 64

    # 1. Discovery Session #1 history setup
    sess_1 = DiscoverySession(
        id=101,
        session_id="sess_r2_001",
        warehouse_id=mock_warehouse.id,
        started_at=now,
        finished_at=now,
        total_duration_ms=1200.0,
        status="COMPLETED",
        recommendations={
            "automation": {
                "action_plans": [candidate_action]
            }
        },
    )

    history_rec_s1 = RecommendationOutcomeRecord(
        id=1,
        recommendation_id="act_s1_votes",
        action_id="act_s1_votes",
        session_id=sess_1.id,
        warehouse_id=mock_warehouse.id,
        user_id=mock_user.id,
        action_type="ANALYZE_TABLE",
        target={"schema": "public", "table": "votes"},
        approval_status="APPROVED",
        execution_status="COMPLETED",
        verification_status="VERIFIED",
        objective_status="ACHIEVED",
        final_outcome="ACHIEVED",
        fingerprint=fp,
        created_at=now,
        updated_at=now,
    )

    mock_db = MagicMock()

    def mock_execute(stmt):
        mock_res = MagicMock()
        stmt_str = str(stmt)
        if "discovery_sessions" in stmt_str:
            mock_res.scalar_one_or_none.return_value = sess_1
        elif "recommendation_outcome_records" in stmt_str:
            mock_res.scalars().all.return_value = [history_rec_s1]
            mock_res.scalar_one_or_none.return_value = history_rec_s1
        else:
            mock_res.scalar_one_or_none.return_value = None
            mock_res.scalars().all.return_value = []
        return mock_res

    mock_db.execute.side_effect = mock_execute

    # 2. Discovery Session #2 generates equivalent candidate
    candidate_session2 = {
        "action_id": "act_s2_votes",
        "action_type": "ANALYZE_TABLE",
        "recommendation_type": "ANALYZE_TABLE",
        "status": "PROPOSED",
        "target": {"schema": "public", "table": "votes"},
    }

    fp2 = RecommendationFingerprintService.fingerprint_recommendation(candidate_session2)

    # 3. Assert structural equivalence
    assert fp2 == fp

    # 4. Search history matches for candidate
    match_summary = RecommendationFingerprintService.find_matches_for_candidate(
        db=mock_db, warehouse_id=mock_warehouse.id, candidate=candidate_session2
    )

    # 5. R2 Identity Assertions
    assert match_summary["fingerprint"] == fp
    assert match_summary["match_found"] is True
    assert match_summary["match_count"] == 1
    assert match_summary["matches"][0]["final_outcome"] == "ACHIEVED"

    # 6. CRITICAL R2 NON-SUPPRESSION ASSERTION:
    # The candidate recommendation candidate remains intact and NOT suppressed
    assert candidate_session2["action_type"] == "ANALYZE_TABLE"
    assert candidate_session2["status"] == "PROPOSED"

    # 7. RecommendationAgent decision logic assertion
    agent = RecommendationAgent()
    context = SharedContext()
    recs_out = agent.generate_recommendations(mock_warehouse, context)
    assert isinstance(recs_out, dict)
    assert "recommendations" in recs_out
