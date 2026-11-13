"""
Unit tests for RecommendationDecisionEngine (R4).

Verifies deterministic decision matrix across all matrix combinations:
1. No history + PRESENT → PROPOSE
2. No history + RESOLVED → SUPPRESS
3. ACHIEVED + PRESENT → PROPOSE
4. ACHIEVED + RESOLVED → SUPPRESS
5. FAILED + PRESENT → REVIEW
6. FAILED + RESOLVED → SUPPRESS
7. UNCERTAIN + PRESENT → REVIEW
8. REJECTED + PRESENT → REVIEW
9. REJECTED + RESOLVED → SUPPRESS
10. Any + UNCERTAIN → REVIEW
11. Any + NOT_MEASURABLE → REVIEW
12. Missing current condition → REVIEW
"""

import pytest
from app.warehouse.recommendation_decision import (
    DecisionReasonCode,
    RecommendationDecisionEngine,
    RecommendationDecisionState,
)


@pytest.fixture
def candidate():
    return {
        "recommendation_id": "rec_001",
        "action_type": "ANALYZE_TABLE",
        "target": {"schema": "public", "table": "votes"},
    }


def test_matrix_case_1_no_history_present(candidate):
    """Case 1: No history match + PRESENT condition → PROPOSE."""
    res = RecommendationDecisionEngine.make_decision(
        candidate=candidate,
        fingerprint="fp123",
        historical_match=None,
        current_condition={"condition_status": "PRESENT", "evidence": []},
    )
    assert res["decision"] == RecommendationDecisionState.PROPOSE
    assert res["reason_code"] == DecisionReasonCode.NO_HISTORY_CONDITION_PRESENT
    assert "No previous equivalent recommendation exists" in res["reason"]


def test_matrix_case_2_no_history_resolved(candidate):
    """Case 2: No history match + RESOLVED condition → SUPPRESS."""
    res = RecommendationDecisionEngine.make_decision(
        candidate=candidate,
        fingerprint="fp123",
        historical_match=None,
        current_condition={"condition_status": "RESOLVED", "evidence": []},
    )
    assert res["decision"] == RecommendationDecisionState.SUPPRESS
    assert res["reason_code"] == DecisionReasonCode.NO_HISTORY_CONDITION_RESOLVED
    assert "currently resolved" in res["reason"]


def test_matrix_case_3_achieved_present(candidate):
    """Case 3: Historical ACHIEVED + PRESENT condition → PROPOSE (Recurring condition)."""
    hist = {"final_outcome": "ACHIEVED", "verification_status": "VERIFIED"}
    res = RecommendationDecisionEngine.make_decision(
        candidate=candidate,
        fingerprint="fp123",
        historical_match=hist,
        current_condition={"condition_status": "PRESENT", "evidence": []},
    )
    assert res["decision"] == RecommendationDecisionState.PROPOSE
    assert res["reason_code"] == DecisionReasonCode.CONDITION_REAPPEARED
    assert "reappeared" in res["reason"]


def test_matrix_case_4_achieved_resolved(candidate):
    """Case 4: Historical ACHIEVED + RESOLVED condition → SUPPRESS."""
    hist = {"final_outcome": "ACHIEVED", "verification_status": "VERIFIED"}
    res = RecommendationDecisionEngine.make_decision(
        candidate=candidate,
        fingerprint="fp123",
        historical_match=hist,
        current_condition={"condition_status": "RESOLVED", "evidence": []},
    )
    assert res["decision"] == RecommendationDecisionState.SUPPRESS
    assert res["reason_code"] == DecisionReasonCode.CONDITION_RESOLVED
    assert "remains resolved" in res["reason"]


def test_matrix_case_5_failed_present(candidate):
    """Case 5: Historical FAILED + PRESENT condition → REVIEW (Safety review required)."""
    hist = {"final_outcome": "FAILED", "execution_status": "FAILED"}
    res = RecommendationDecisionEngine.make_decision(
        candidate=candidate,
        fingerprint="fp123",
        historical_match=hist,
        current_condition={"condition_status": "PRESENT", "evidence": []},
    )
    assert res["decision"] == RecommendationDecisionState.REVIEW
    assert res["reason_code"] == DecisionReasonCode.HISTORICAL_ACTION_FAILED
    assert "previous action failed" in res["reason"]


def test_matrix_case_6_failed_resolved(candidate):
    """Case 6: Historical FAILED + RESOLVED condition → SUPPRESS."""
    hist = {"final_outcome": "FAILED"}
    res = RecommendationDecisionEngine.make_decision(
        candidate=candidate,
        fingerprint="fp123",
        historical_match=hist,
        current_condition={"condition_status": "RESOLVED", "evidence": []},
    )
    assert res["decision"] == RecommendationDecisionState.SUPPRESS
    assert res["reason_code"] == DecisionReasonCode.HISTORICAL_FAILED_CONDITION_RESOLVED


def test_matrix_case_7_uncertain_present(candidate):
    """Case 7: Historical UNCERTAIN + PRESENT condition → REVIEW."""
    hist = {"final_outcome": "UNCERTAIN"}
    res = RecommendationDecisionEngine.make_decision(
        candidate=candidate,
        fingerprint="fp123",
        historical_match=hist,
        current_condition={"condition_status": "PRESENT", "evidence": []},
    )
    assert res["decision"] == RecommendationDecisionState.REVIEW
    assert res["reason_code"] == DecisionReasonCode.HISTORICAL_OUTCOME_UNCERTAIN


def test_matrix_case_8_rejected_present(candidate):
    """Case 8: Historical REJECTED + PRESENT condition → REVIEW."""
    hist = {"final_outcome": "REJECTED", "approval_status": "REJECTED"}
    res = RecommendationDecisionEngine.make_decision(
        candidate=candidate,
        fingerprint="fp123",
        historical_match=hist,
        current_condition={"condition_status": "PRESENT", "evidence": []},
    )
    assert res["decision"] == RecommendationDecisionState.REVIEW
    assert res["reason_code"] == DecisionReasonCode.HISTORICAL_RECOMMENDATION_REJECTED
    assert "previously rejected" in res["reason"]


def test_matrix_case_9_rejected_resolved(candidate):
    """Case 9: Historical REJECTED + RESOLVED condition → SUPPRESS."""
    hist = {"final_outcome": "REJECTED"}
    res = RecommendationDecisionEngine.make_decision(
        candidate=candidate,
        fingerprint="fp123",
        historical_match=hist,
        current_condition={"condition_status": "RESOLVED", "evidence": []},
    )
    assert res["decision"] == RecommendationDecisionState.SUPPRESS
    assert res["reason_code"] == DecisionReasonCode.CONDITION_RESOLVED


def test_matrix_case_10_any_uncertain_condition(candidate):
    """Case 10: Any history + UNCERTAIN condition → REVIEW."""
    hist = {"final_outcome": "ACHIEVED"}
    res = RecommendationDecisionEngine.make_decision(
        candidate=candidate,
        fingerprint="fp123",
        historical_match=hist,
        current_condition={"condition_status": "UNCERTAIN", "evidence": []},
    )
    assert res["decision"] == RecommendationDecisionState.REVIEW
    assert res["reason_code"] == DecisionReasonCode.CONDITION_UNCERTAIN


def test_matrix_case_11_any_not_measurable_condition(candidate):
    """Case 11: Any history + NOT_MEASURABLE condition → REVIEW."""
    res = RecommendationDecisionEngine.make_decision(
        candidate=candidate,
        fingerprint="fp123",
        historical_match=None,
        current_condition={"condition_status": "NOT_MEASURABLE", "evidence": []},
    )
    assert res["decision"] == RecommendationDecisionState.REVIEW
    assert res["reason_code"] == DecisionReasonCode.CONDITION_NOT_MEASURABLE


def test_matrix_case_12_missing_current_condition(candidate):
    """Case 12: Missing current condition → REVIEW."""
    res = RecommendationDecisionEngine.make_decision(
        candidate=candidate,
        fingerprint="fp123",
        historical_match={"final_outcome": "ACHIEVED"},
        current_condition=None,
    )
    assert res["decision"] == RecommendationDecisionState.REVIEW
    assert res["reason_code"] == DecisionReasonCode.CURRENT_CONDITION_UNAVAILABLE


def test_decision_engine_determinism(candidate):
    """Verify identical inputs yield identical R4 decision outputs."""
    hist = {"final_outcome": "ACHIEVED"}
    cond = {"condition_status": "PRESENT", "evidence": []}

    res1 = RecommendationDecisionEngine.make_decision(candidate, "fp1", hist, cond)
    res2 = RecommendationDecisionEngine.make_decision(candidate, "fp1", hist, cond)

    assert res1["decision"] == res2["decision"] == RecommendationDecisionState.PROPOSE
    assert res1["reason_code"] == res2["reason_code"] == DecisionReasonCode.CONDITION_REAPPEARED
    assert res1["reason"] == res2["reason"]
