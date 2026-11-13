"""
Unit tests for R6 Recommendation Explanation Engine.
Tests deterministic explanation generation, evidence assembly, decision template matching,
R5 lifecycle explanation, uncertainty handling, determinism, and zero LLM dependency.
"""

import pytest
from app.warehouse.recommendation_explanation import RecommendationExplanationEngine


def test_explain_no_history_condition_present():
    engine = RecommendationExplanationEngine()
    candidate = {
        "action_type": "CREATE_INDEX",
        "schema": "public",
        "table": "orders",
        "column": "customer_id",
        "recommendation_id": "rec-101",
    }
    history_match = {
        "match_found": False,
        "match_count": 0,
        "fingerprint": "abc123def456",
        "most_recent_outcome": None,
    }
    condition_result = {
        "condition_status": "PRESENT",
        "condition_type": "MISSING_INDEX",
        "reason": "Index missing on high-scanned column customer_id",
        "evidence": [
            {
                "source": "pg_stat_user_tables",
                "field": "seq_scan",
                "value": 1500,
                "interpretation": "1500 sequential scans observed on public.orders",
            }
        ],
    }
    decision_result = {
        "decision": "PROPOSE",
        "reason_code": "NO_HISTORY_CONDITION_PRESENT",
        "reason": "No previous recommendation outcome history exists and current condition is PRESENT.",
        "evaluated_at": "2026-09-26T12:00:00Z",
    }
    lifecycle_state = "ACTIVE"

    explanation = RecommendationExplanationEngine.generate_explanation(
        candidate=candidate,
        fingerprint=history_match.get("fingerprint"),
        historical_match=history_match,
        current_condition=condition_result,
        decision_result=decision_result,
        lifecycle_state=lifecycle_state,
    )

    assert explanation["decision"] == "PROPOSE"
    assert explanation["lifecycle_state"] == "ACTIVE"
    assert explanation["reason_code"] == "NO_HISTORY_CONDITION_PRESENT"
    assert explanation["fingerprint"] == "abc123def456"
    assert explanation["historical_context"]["match_found"] is False
    assert explanation["current_condition"]["condition_state"] == "PRESENT"
    assert explanation["uncertainty"] is None
    assert "no prior historical outcome" in explanation["summary"].lower() or "first-time" in explanation["summary"].lower() or "present" in explanation["summary"].lower()


def test_explain_condition_reappeared():
    engine = RecommendationExplanationEngine()
    candidate = {
        "action_type": "ANALYZE_TABLE",
        "schema": "public",
        "table": "users",
        "recommendation_id": "rec-102",
    }
    history_match = {
        "match_found": True,
        "match_count": 1,
        "fingerprint": "fingerprint-789",
        "most_recent_outcome": {
            "final_outcome": "ACHIEVED",
            "execution_status": "COMPLETED",
            "verification_status": "VERIFIED",
            "objective_status": "ACHIEVED",
            "session_id": "session-old",
            "action_id": 42,
        },
    }
    condition_result = {
        "condition_status": "PRESENT",
        "condition_type": "MODIFICATIONS_SINCE_ANALYZE",
        "reason": "150 modifications occurred since last analyze",
        "evidence": [
            {
                "source": "pg_stat_user_tables",
                "field": "n_mod_since_analyze",
                "value": 150,
                "interpretation": "150 modifications since last analyze",
            }
        ],
    }
    decision_result = {
        "decision": "PROPOSE",
        "reason_code": "CONDITION_REAPPEARED",
        "reason": "Matching historical recommendation reached ACHIEVED, but current condition is PRESENT again.",
        "evaluated_at": "2026-09-26T12:00:00Z",
    }
    lifecycle_state = "REOPENED"

    explanation = RecommendationExplanationEngine.generate_explanation(
        candidate=candidate,
        fingerprint=history_match.get("fingerprint"),
        historical_match=history_match,
        current_condition=condition_result,
        decision_result=decision_result,
        lifecycle_state=lifecycle_state,
    )

    assert explanation["decision"] == "PROPOSE"
    assert explanation["lifecycle_state"] == "REOPENED"
    assert explanation["reason_code"] == "CONDITION_REAPPEARED"
    assert explanation["historical_context"]["match_found"] is True
    assert explanation["historical_context"]["previous_final_outcome"] == "ACHIEVED"
    assert explanation["current_condition"]["condition_state"] == "PRESENT"
    assert "reappeared" in explanation["summary"].lower()


def test_explain_condition_resolved_suppress():
    candidate = {
        "action_type": "VACUUM_TABLE",
        "schema": "public",
        "table": "orders",
        "recommendation_id": "rec-103",
    }
    history_match = {
        "match_found": True,
        "match_count": 1,
        "fingerprint": "vac-fingerprint",
        "most_recent_outcome": {
            "final_outcome": "ACHIEVED",
            "execution_status": "COMPLETED",
            "verification_status": "VERIFIED",
            "objective_status": "ACHIEVED",
        },
    }
    condition_result = {
        "condition_status": "RESOLVED",
        "condition_type": "DEAD_TUPLES",
        "reason": "Dead tuples within normal threshold",
        "evidence": [],
    }
    decision_result = {
        "decision": "SUPPRESS",
        "reason_code": "CONDITION_RESOLVED",
        "reason": "Current condition is RESOLVED.",
        "evaluated_at": "2026-09-26T12:00:00Z",
    }
    lifecycle_state = "SUPPRESSED"

    explanation = RecommendationExplanationEngine.generate_explanation(
        candidate=candidate,
        fingerprint=history_match.get("fingerprint"),
        historical_match=history_match,
        current_condition=condition_result,
        decision_result=decision_result,
        lifecycle_state=lifecycle_state,
    )

    assert explanation["decision"] == "SUPPRESS"
    assert explanation["lifecycle_state"] == "SUPPRESSED"
    assert explanation["reason_code"] == "CONDITION_RESOLVED"
    assert "resolved" in explanation["summary"].lower()


def test_explain_historical_action_failed_review():
    candidate = {
        "action_type": "CREATE_INDEX",
        "schema": "public",
        "table": "events",
        "column": "created_at",
        "recommendation_id": "rec-104",
    }
    history_match = {
        "match_found": True,
        "match_count": 1,
        "fingerprint": "fail-fp",
        "most_recent_outcome": {
            "final_outcome": "NOT_ACHIEVED",
            "execution_status": "FAILED",
            "verification_status": "FAILED",
            "objective_status": "FAILED",
        },
    }
    condition_result = {
        "condition_status": "PRESENT",
        "condition_type": "MISSING_INDEX",
        "reason": "Index missing",
        "evidence": [],
    }
    decision_result = {
        "decision": "REVIEW",
        "reason_code": "HISTORICAL_ACTION_FAILED",
        "reason": "Historical action failed.",
        "evaluated_at": "2026-09-26T12:00:00Z",
    }
    lifecycle_state = "REVIEW"

    explanation = RecommendationExplanationEngine.generate_explanation(
        candidate=candidate,
        fingerprint=history_match.get("fingerprint"),
        historical_match=history_match,
        current_condition=condition_result,
        decision_result=decision_result,
        lifecycle_state=lifecycle_state,
    )

    assert explanation["decision"] == "REVIEW"
    assert explanation["lifecycle_state"] == "REVIEW"
    assert explanation["reason_code"] == "HISTORICAL_ACTION_FAILED"
    assert explanation["uncertainty"] is not None
    assert "review" in explanation["summary"].lower()


def test_determinism_identical_inputs():
    candidate = {
        "action_type": "ANALYZE_TABLE",
        "schema": "public",
        "table": "products",
        "recommendation_id": "rec-det",
    }
    history_match = {"match_found": False}
    condition_result = {"condition_status": "PRESENT", "evidence": []}
    decision_result = {"decision": "PROPOSE", "reason_code": "NO_HISTORY_CONDITION_PRESENT", "evaluated_at": "2026-09-26T12:00:00Z"}
    lifecycle_state = "ACTIVE"

    exp1 = RecommendationExplanationEngine.generate_explanation(
        candidate=candidate,
        fingerprint=history_match.get("fingerprint"),
        historical_match=history_match,
        current_condition=condition_result,
        decision_result=decision_result,
        lifecycle_state=lifecycle_state,
    )
    exp2 = RecommendationExplanationEngine.generate_explanation(
        candidate=candidate,
        fingerprint=history_match.get("fingerprint"),
        historical_match=history_match,
        current_condition=condition_result,
        decision_result=decision_result,
        lifecycle_state=lifecycle_state,
    )

    assert exp1["summary"] == exp2["summary"]
    assert exp1["decision"] == exp2["decision"]
    assert exp1["decision_evidence"] == exp2["decision_evidence"]
