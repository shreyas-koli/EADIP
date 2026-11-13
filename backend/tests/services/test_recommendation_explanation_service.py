"""
Unit tests for RecommendationExplanationService (R6).
Verifies tenant authorization checks, single candidate explanation, batch explanation,
and SharedContext integration.
"""

from unittest.mock import MagicMock, patch
import pytest

from app.context.shared_context import SharedContext
from app.models.user import User
from app.models.warehouse import Warehouse
from app.services.recommendation_explanation_service import RecommendationExplanationService


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_user():
    u = MagicMock(spec=User)
    u.id = 10
    return u


@pytest.fixture
def mock_warehouse():
    w = MagicMock(spec=Warehouse)
    w.id = 77
    w.owner_id = 10
    w.db_type = "postgresql"
    return w


def test_explain_candidate_unauthorized_raises(mock_db, mock_user):
    """Test authorization check: unauthorized warehouse access raises PermissionError."""
    with patch("app.services.recommendation_explanation_service.get_warehouse_by_id", return_value=None):
        candidate = {"action_type": "ANALYZE_TABLE", "schema": "public", "table": "votes"}

        with pytest.raises(PermissionError) as exc_info:
            RecommendationExplanationService.get_candidate_explanation(
                db=mock_db,
                warehouse_id=999,
                candidate=candidate,
                user=mock_user,
            )

        assert "access denied" in str(exc_info.value)


def test_explain_candidate_success(mock_db, mock_user, mock_warehouse):
    """Test authorized single candidate explanation synthesis."""
    candidate = {"action_type": "ANALYZE_TABLE", "schema": "public", "table": "votes"}

    mock_match_summary = {"fingerprint": "fp_sha256", "match_found": False, "matches": []}
    mock_condition = {"condition_status": "PRESENT", "evidence": []}

    with patch(
        "app.services.recommendation_explanation_service.get_warehouse_by_id",
        return_value=mock_warehouse,
    ), patch(
        "app.services.recommendation_explanation_service.RecommendationFingerprintService.find_matches_for_candidate",
        return_value=mock_match_summary,
    ), patch(
        "app.services.recommendation_explanation_service.CurrentConditionEvaluator.evaluate_current_condition",
        return_value=mock_condition,
    ):
        result = RecommendationExplanationService.get_candidate_explanation(
            db=mock_db,
            warehouse_id=77,
            candidate=candidate,
            user=mock_user,
        )

    assert result["decision"] == "PROPOSE"
    assert result["lifecycle_state"] == "ACTIVE"
    assert result["reason_code"] == "NO_HISTORY_CONDITION_PRESENT"
    assert result["fingerprint"] == "fp_sha256"
    assert result["summary"] is not None


def test_explain_candidates_batch_with_context(mock_db, mock_user, mock_warehouse):
    """Test batch explanation synthesis and SharedContext storage."""
    candidates = [
        {"recommendation_id": "c1", "action_type": "ANALYZE_TABLE", "schema": "public", "table": "t1"},
        {"recommendation_id": "c2", "action_type": "ANALYZE_TABLE", "schema": "public", "table": "t2"},
    ]

    mock_exp1 = {"recommendation_id": "c1", "decision": "PROPOSE", "lifecycle_state": "ACTIVE"}
    mock_exp2 = {"recommendation_id": "c2", "decision": "SUPPRESS", "lifecycle_state": "SUPPRESSED"}

    context = SharedContext()

    with patch(
        "app.services.recommendation_explanation_service.get_warehouse_by_id",
        return_value=mock_warehouse,
    ), patch.object(
        RecommendationExplanationService,
        "get_candidate_explanation",
        side_effect=[mock_exp1, mock_exp2],
    ):
        summary = RecommendationExplanationService.generate_explanations_batch(
            db=mock_db,
            warehouse_id=77,
            candidates=candidates,
            user=mock_user,
            context=context,
        )

    assert summary["total_explanations"] == 2
    assert len(summary["explanations"]) == 2

    ctx_result = context.get_agent_result("recommendation_explanation")
    assert ctx_result is not None
    assert ctx_result["total_explanations"] == 2
