"""
End-to-end integration tests for Persistent Recommendation Explanation & Auditability Records (R6.1).

Mandatory multi-session lifecycle test verifying durable, historically immutable explanations:
- Session 1: No history + condition PRESENT -> PROPOSE -> ACTIVE (Persisted Record A)
- Session 2: Historical ACHIEVED + condition RESOLVED -> SUPPRESS -> SUPPRESSED (Persisted Record B)
- Session 3: Historical ACHIEVED + condition PRESENT again -> PROPOSE (CONDITION_REAPPEARED) -> REOPENED (Persisted Record C)

Verifies:
1. Historical retrieval for Session 1 returns Record A (PROPOSE/ACTIVE/PRESENT) without re-evaluating live state.
2. Historical retrieval for Session 2 returns Record B (SUPPRESS/SUPPRESSED/RESOLVED).
3. Historical retrieval for Session 3 returns Record C (PROPOSE/REOPENED/PRESENT).
4. SharedContext reset does NOT lose historical explanations.
5. Live warehouse condition mutations do NOT alter historical decision-time evidence.
"""

from unittest.mock import MagicMock, patch
import pytest

from app.context.shared_context import SharedContext
from app.models.recommendation_explanation_record import RecommendationExplanationRecord
from app.models.warehouse import Warehouse
from app.services.recommendation_explanation_service import RecommendationExplanationService


def test_mandatory_multi_session_r6_explanation_lifecycle():
    """
    Mandatory R6.1 E2E multi-session lifecycle test:
    Session 1 (session_id=101): PRESENT -> PROPOSE -> ACTIVE -> Persisted Record A
    Session 2 (session_id=102): RESOLVED -> SUPPRESS -> SUPPRESSED -> Persisted Record B
    Session 3 (session_id=103): PRESENT again -> PROPOSE -> REOPENED -> Persisted Record C

    Verifies distinct, immutable retrieval for each session from DB.
    """
    mock_wh = MagicMock(spec=Warehouse)
    mock_wh.id = 55
    mock_wh.owner_id = 1
    mock_wh.db_type = "postgresql"

    candidate = {
        "recommendation_id": "rec_votes_analyze",
        "action_type": "ANALYZE_TABLE",
        "target": {"schema": "public", "table": "votes"},
    }

    fingerprint = "5f9b4c2e8a1d7f305f9b4c2e8a1d7f305f9b4c2e8a1d7f305f9b4c2e8a1d7f30"
    mock_user = MagicMock()
    mock_user.id = 1

    # In-memory dictionary store simulating SQLAlchemy session query/commit for tests
    stored_records = {}

    def mock_query(model):
        query_mock = MagicMock()

        def filter_impl(*args):
            filtered_query = MagicMock()

            def first_impl():
                # Simple lookup matching session_id if provided
                for rec in stored_records.values():
                    if rec.recommendation_id == "rec_votes_analyze":
                        return rec
                return None

            filtered_query.first = first_impl
            filtered_query.order_by = lambda *a: filtered_query
            return filtered_query

        query_mock.filter = filter_impl
        return query_mock

    # SESSION 1: No history, current condition PRESENT (session_id=101)
    history_session1 = {"fingerprint": fingerprint, "match_found": False, "matches": []}
    condition_session1 = {
        "condition_status": "PRESENT",
        "condition_type": "MODIFICATIONS_SINCE_ANALYZE",
        "evidence": [{"source": "pg_stat_user_tables", "field": "n_mod_since_analyze", "value": 2000}],
        "reason": "2000 modifications have occurred on table 'public.votes' since last analyze.",
    }

    db_session1 = MagicMock()

    def add_impl1(rec):
        rec.id = 1
        rec.created_at = MagicMock()
        rec.created_at.isoformat.return_value = "2026-09-26T12:00:00Z"
        stored_records[(101, rec.recommendation_id)] = rec

    db_session1.add.side_effect = add_impl1
    db_session1.query.side_effect = lambda model: mock_query_for_session(101)

    def mock_query_for_session(target_sess):
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.first.side_effect = lambda: stored_records.get((target_sess, "rec_votes_analyze"))
        return q

    with patch("app.services.recommendation_explanation_service.get_warehouse_by_id", return_value=mock_wh), patch(
        "app.services.recommendation_explanation_service.RecommendationFingerprintService.find_matches_for_candidate",
        return_value=history_session1,
    ), patch(
        "app.services.recommendation_explanation_service.CurrentConditionEvaluator.evaluate_current_condition",
        return_value=condition_session1,
    ):
        exp_session1 = RecommendationExplanationService.get_candidate_explanation(
            db=db_session1, warehouse_id=55, candidate=candidate, user=mock_user, session_id=101
        )

    assert exp_session1["decision"] == "PROPOSE"
    assert exp_session1["lifecycle_state"] == "ACTIVE"
    assert exp_session1["reason_code"] == "NO_HISTORY_CONDITION_PRESENT"

    # SESSION 2: Execution occurred (ACHIEVED), condition now RESOLVED (0 modifications, session_id=102)
    achieved_match = {
        "id": 1,
        "recommendation_id": "rec_votes_analyze",
        "final_outcome": "ACHIEVED",
        "verification_status": "VERIFIED",
    }
    history_session2 = {"fingerprint": fingerprint, "match_found": True, "matches": [achieved_match]}
    condition_session2 = {
        "condition_status": "RESOLVED",
        "condition_type": "MODIFICATIONS_SINCE_ANALYZE",
        "evidence": [{"source": "pg_stat_user_tables", "field": "n_mod_since_analyze", "value": 0}],
        "reason": "No modifications recorded since latest analyze.",
    }

    db_session2 = MagicMock()

    def add_impl2(rec):
        rec.id = 2
        rec.created_at = MagicMock()
        rec.created_at.isoformat.return_value = "2026-09-26T13:00:00Z"
        stored_records[(102, rec.recommendation_id)] = rec

    db_session2.add.side_effect = add_impl2
    db_session2.query.side_effect = lambda model: mock_query_for_session(102)

    with patch("app.services.recommendation_explanation_service.get_warehouse_by_id", return_value=mock_wh), patch(
        "app.services.recommendation_explanation_service.RecommendationFingerprintService.find_matches_for_candidate",
        return_value=history_session2,
    ), patch(
        "app.services.recommendation_explanation_service.CurrentConditionEvaluator.evaluate_current_condition",
        return_value=condition_session2,
    ):
        exp_session2 = RecommendationExplanationService.get_candidate_explanation(
            db=db_session2, warehouse_id=55, candidate=candidate, user=mock_user, session_id=102
        )

    assert exp_session2["decision"] == "SUPPRESS"
    assert exp_session2["lifecycle_state"] == "SUPPRESSED"

    # SESSION 3: Later modifications occur (session_id=103)
    condition_session3 = {
        "condition_status": "PRESENT",
        "condition_type": "MODIFICATIONS_SINCE_ANALYZE",
        "evidence": [{"source": "pg_stat_user_tables", "field": "n_mod_since_analyze", "value": 1500}],
        "reason": "1500 modifications occurred since last analyze.",
    }

    db_session3 = MagicMock()

    def add_impl3(rec):
        rec.id = 3
        rec.created_at = MagicMock()
        rec.created_at.isoformat.return_value = "2026-09-26T14:00:00Z"
        stored_records[(103, rec.recommendation_id)] = rec

    db_session3.add.side_effect = add_impl3
    db_session3.query.side_effect = lambda model: mock_query_for_session(103)

    with patch("app.services.recommendation_explanation_service.get_warehouse_by_id", return_value=mock_wh), patch(
        "app.services.recommendation_explanation_service.RecommendationFingerprintService.find_matches_for_candidate",
        return_value=history_session2,
    ), patch(
        "app.services.recommendation_explanation_service.CurrentConditionEvaluator.evaluate_current_condition",
        return_value=condition_session3,
    ):
        exp_session3 = RecommendationExplanationService.get_candidate_explanation(
            db=db_session3, warehouse_id=55, candidate=candidate, user=mock_user, session_id=103
        )

    assert exp_session3["decision"] == "PROPOSE"
    assert exp_session3["lifecycle_state"] == "REOPENED"

    # VERIFY INDEPENDENT HISTORICAL RETRIEVAL
    with patch("app.services.recommendation_explanation_service.get_warehouse_by_id", return_value=mock_wh):
        h1 = RecommendationExplanationService.get_historical_explanation(
            db=db_session1, warehouse_id=55, recommendation_id="rec_votes_analyze", user=mock_user, session_id=101
        )
        h2 = RecommendationExplanationService.get_historical_explanation(
            db=db_session2, warehouse_id=55, recommendation_id="rec_votes_analyze", user=mock_user, session_id=102
        )
        h3 = RecommendationExplanationService.get_historical_explanation(
            db=db_session3, warehouse_id=55, recommendation_id="rec_votes_analyze", user=mock_user, session_id=103
        )

    assert h1["decision"] == "PROPOSE"
    assert h1["lifecycle_state"] == "ACTIVE"
    assert h1["current_condition"]["condition_status"] == "PRESENT"

    assert h2["decision"] == "SUPPRESS"
    assert h2["lifecycle_state"] == "SUPPRESSED"
    assert h2["current_condition"]["condition_status"] == "RESOLVED"

    assert h3["decision"] == "PROPOSE"
    assert h3["lifecycle_state"] == "REOPENED"
    assert h3["current_condition"]["condition_status"] == "PRESENT"


def test_shared_context_reset_preserves_historical_explanation():
    """Verify that resetting or clearing SharedContext does NOT lose DB-persisted explanations."""
    mock_wh = MagicMock(spec=Warehouse)
    mock_wh.id = 55
    mock_wh.owner_id = 1

    stored_rec = MagicMock(spec=RecommendationExplanationRecord)
    stored_rec.recommendation_id = "rec_reset_test"
    stored_rec.session_id = 201
    stored_rec.warehouse_id = 55
    stored_rec.action_id = "act_201"
    stored_rec.fingerprint = "fp_201"
    stored_rec.action_type = "ANALYZE_TABLE"
    stored_rec.target = {"schema": "public", "table": "votes"}
    stored_rec.decision = "PROPOSE"
    stored_rec.decision_reason_code = "NO_HISTORY_CONDITION_PRESENT"
    stored_rec.decision_reason = "Condition PRESENT."
    stored_rec.lifecycle_state = "ACTIVE"
    stored_rec.summary = "Proposed because condition is PRESENT."
    stored_rec.historical_context = {"match_found": False}
    stored_rec.current_condition = {"condition_status": "PRESENT"}
    stored_rec.decision_evidence = []
    stored_rec.lifecycle_evidence = []
    stored_rec.uncertainty = None
    stored_rec.created_at = MagicMock()
    stored_rec.created_at.isoformat.return_value = "2026-09-26T12:00:00Z"

    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.first.return_value = stored_rec
    mock_db.query.return_value = mock_query

    mock_user = MagicMock()
    mock_user.id = 1

    # Simulate SharedContext creation, usage, and explicit reset
    ctx = SharedContext()
    ctx.set_agent_result("recommendation_explanation", {"total_explanations": 1})
    assert ctx.get_agent_result("recommendation_explanation") is not None

    # Reset SharedContext
    ctx = SharedContext()
    assert ctx.get_agent_result("recommendation_explanation") is None

    # Retrieve from DB via get_historical_explanation
    with patch("app.services.recommendation_explanation_service.get_warehouse_by_id", return_value=mock_wh):
        h = RecommendationExplanationService.get_historical_explanation(
            db=mock_db, warehouse_id=55, recommendation_id="rec_reset_test", user=mock_user, session_id=201
        )

    assert h is not None
    assert h["decision"] == "PROPOSE"
    assert h["lifecycle_state"] == "ACTIVE"


def test_live_warehouse_change_does_not_alter_historical_explanation():
    """Verify that live warehouse catalog changes do NOT alter decision-time evidence in historical GET lookup."""
    mock_wh = MagicMock(spec=Warehouse)
    mock_wh.id = 55
    mock_wh.owner_id = 1

    stored_rec = MagicMock(spec=RecommendationExplanationRecord)
    stored_rec.recommendation_id = "rec_immutable_test"
    stored_rec.session_id = 301
    stored_rec.warehouse_id = 55
    stored_rec.action_id = "act_301"
    stored_rec.fingerprint = "fp_301"
    stored_rec.action_type = "ANALYZE_TABLE"
    stored_rec.target = {"schema": "public", "table": "votes"}
    stored_rec.decision = "PROPOSE"
    stored_rec.decision_reason_code = "NO_HISTORY_CONDITION_PRESENT"
    stored_rec.decision_reason = "Condition PRESENT."
    stored_rec.lifecycle_state = "ACTIVE"
    stored_rec.summary = "Proposed because condition is PRESENT."
    stored_rec.historical_context = {"match_found": False}
    stored_rec.current_condition = {
        "condition_status": "PRESENT",
        "evidence": [{"source": "pg_stat_user_tables", "field": "n_mod_since_analyze", "value": 5000}],
    }
    stored_rec.decision_evidence = []
    stored_rec.lifecycle_evidence = []
    stored_rec.uncertainty = None
    stored_rec.created_at = MagicMock()
    stored_rec.created_at.isoformat.return_value = "2026-09-26T12:00:00Z"

    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.first.return_value = stored_rec
    mock_db.query.return_value = mock_query

    mock_user = MagicMock()
    mock_user.id = 1

    # Patch CurrentConditionEvaluator to return RESOLVED (simulating live warehouse state change)
    with patch("app.services.recommendation_explanation_service.get_warehouse_by_id", return_value=mock_wh), patch(
        "app.warehouse.current_condition.CurrentConditionEvaluator.evaluate_current_condition",
        side_effect=Exception("Live catalog query must NOT be called during historical retrieval!"),
    ):
        h = RecommendationExplanationService.get_historical_explanation(
            db=mock_db, warehouse_id=55, recommendation_id="rec_immutable_test", user=mock_user, session_id=301
        )

    # Asserts historical evidence remains PRESERVED from decision time without calling live catalog evaluator
    assert h["decision"] == "PROPOSE"
    assert h["current_condition"]["condition_status"] == "PRESENT"
    assert h["current_condition"]["evidence"][0]["value"] == 5000
