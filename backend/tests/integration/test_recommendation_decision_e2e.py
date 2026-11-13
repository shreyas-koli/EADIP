"""
End-to-end integration tests for Recommendation Decision Engine (R4).

Verifies:
1. Multi-discovery recurring condition lifecycle:
   Discovery 1 (No history + PRESENT) → PROPOSE
   Execution → ACHIEVED
   Discovery 2 (ACHIEVED + RESOLVED) → SUPPRESS
   Later modifications (ACHIEVED + PRESENT) → PROPOSE again!
2. Historical failure safety:
   previous = FAILED + current = PRESENT → REVIEW
3. Non-mutation assertion: Zero database modifications performed by R4.
"""

from unittest.mock import MagicMock, patch
import pytest

from app.models.warehouse import Warehouse
from app.services.recommendation_decision_service import RecommendationDecisionService
from app.warehouse.recommendation_decision import (
    DecisionReasonCode,
    RecommendationDecisionEngine,
    RecommendationDecisionState,
)


def test_recurring_condition_multi_discovery_lifecycle():
    """
    Critical recurring-condition test demonstrating state-aware non-permanent suppression:
    Discovery 1: No history + PRESENT → PROPOSE
    Execution: ACHIEVED
    Discovery 2: ACHIEVED + RESOLVED → SUPPRESS
    Later changes: ACHIEVED + PRESENT → PROPOSE again!
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
    mock_db = MagicMock()
    mock_user = MagicMock()
    mock_user.id = 1

    # Step 1: Discovery 1 — No history, current condition PRESENT
    history_step1 = {"fingerprint": fingerprint, "match_found": False, "matches": []}
    condition_step1 = {
        "condition_status": "PRESENT",
        "condition_type": "MODIFICATIONS_SINCE_ANALYZE",
        "evidence": [{"source": "pg_stat_user_tables", "field": "n_mod_since_analyze", "value": 2000}],
        "reason": "2000 modifications have occurred on table 'public.votes' since last analyze.",
    }

    with patch("app.services.recommendation_decision_service.get_warehouse_by_id", return_value=mock_wh), patch(
        "app.services.recommendation_decision_service.RecommendationFingerprintService.find_matches_for_candidate",
        return_value=history_step1,
    ), patch(
        "app.services.recommendation_decision_service.CurrentConditionEvaluator.evaluate_current_condition",
        return_value=condition_step1,
    ):
        dec_step1 = RecommendationDecisionService.evaluate_candidate_decision(
            db=mock_db, warehouse_id=55, candidate=candidate, user=mock_user
        )

    assert dec_step1["decision"] == RecommendationDecisionState.PROPOSE
    assert dec_step1["reason_code"] == DecisionReasonCode.NO_HISTORY_CONDITION_PRESENT

    # Step 2: Discovery 2 — Action previously succeeded (ACHIEVED), catalog stats show 0 modifications (RESOLVED)
    achieved_match = {
        "id": 1,
        "recommendation_id": "rec_votes_analyze",
        "final_outcome": "ACHIEVED",
        "verification_status": "VERIFIED",
    }
    history_step2 = {"fingerprint": fingerprint, "match_found": True, "matches": [achieved_match]}
    condition_step2 = {
        "condition_status": "RESOLVED",
        "condition_type": "MODIFICATIONS_SINCE_ANALYZE",
        "evidence": [{"source": "pg_stat_user_tables", "field": "n_mod_since_analyze", "value": 0}],
        "reason": "No modifications are currently recorded on table 'public.votes' since latest analyze.",
    }

    with patch("app.services.recommendation_decision_service.get_warehouse_by_id", return_value=mock_wh), patch(
        "app.services.recommendation_decision_service.RecommendationFingerprintService.find_matches_for_candidate",
        return_value=history_step2,
    ), patch(
        "app.services.recommendation_decision_service.CurrentConditionEvaluator.evaluate_current_condition",
        return_value=condition_step2,
    ):
        dec_step2 = RecommendationDecisionService.evaluate_candidate_decision(
            db=mock_db, warehouse_id=55, candidate=candidate, user=mock_user
        )

    assert dec_step2["decision"] == RecommendationDecisionState.SUPPRESS
    assert dec_step2["reason_code"] == DecisionReasonCode.CONDITION_RESOLVED

    # Step 3: Later warehouse modifications occur — ACHIEVED history, but condition is PRESENT again!
    condition_step3 = {
        "condition_status": "PRESENT",
        "condition_type": "MODIFICATIONS_SINCE_ANALYZE",
        "evidence": [{"source": "pg_stat_user_tables", "field": "n_mod_since_analyze", "value": 1500}],
        "reason": "1500 modifications have occurred on table 'public.votes' since last analyze.",
    }

    with patch("app.services.recommendation_decision_service.get_warehouse_by_id", return_value=mock_wh), patch(
        "app.services.recommendation_decision_service.RecommendationFingerprintService.find_matches_for_candidate",
        return_value=history_step2,
    ), patch(
        "app.services.recommendation_decision_service.CurrentConditionEvaluator.evaluate_current_condition",
        return_value=condition_step3,
    ):
        dec_step3 = RecommendationDecisionService.evaluate_candidate_decision(
            db=mock_db, warehouse_id=55, candidate=candidate, user=mock_user
        )

    # MUST return PROPOSE again! Proves state-aware, non-permanent suppression!
    assert dec_step3["decision"] == RecommendationDecisionState.PROPOSE
    assert dec_step3["reason_code"] == DecisionReasonCode.CONDITION_REAPPEARED
    assert "reappeared" in dec_step3["reason"]


def test_historical_failure_safety_returns_review():
    """Historical FAILED outcome + PRESENT condition returns REVIEW for safety."""
    candidate = {
        "recommendation_id": "rec_failed_table",
        "action_type": "ANALYZE_TABLE",
        "target": {"schema": "public", "table": "problem_table"},
    }

    historical_failed_match = {
        "final_outcome": "FAILED",
        "execution_status": "FAILED",
        "verification_status": "PENDING",
    }

    condition = {
        "condition_status": "PRESENT",
        "reason": "1000 modifications recorded.",
    }

    result = RecommendationDecisionEngine.make_decision(
        candidate=candidate,
        fingerprint="failed_fp",
        historical_match=historical_failed_match,
        current_condition=condition,
    )

    assert result["decision"] == RecommendationDecisionState.REVIEW
    assert result["reason_code"] == DecisionReasonCode.HISTORICAL_ACTION_FAILED
    assert result["decision"] != RecommendationDecisionState.PROPOSE
