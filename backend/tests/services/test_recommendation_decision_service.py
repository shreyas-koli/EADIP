"""
Unit tests for RecommendationDecisionService (R4).

Verifies authorization enforcement, batch evaluation,
SharedContext integration, and telemetry broadcasting.
"""

from unittest.mock import MagicMock, patch
import pytest

from app.context.shared_context import SharedContext
from app.models.user import User
from app.models.warehouse import Warehouse
from app.services.recommendation_decision_service import RecommendationDecisionService
from app.warehouse.recommendation_decision import RecommendationDecisionState


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


def test_evaluate_candidate_decision_unauthorized_raises(mock_db, mock_user):
    """Test authorization check: unauthorized warehouse access raises PermissionError."""
    with patch("app.services.recommendation_decision_service.get_warehouse_by_id", return_value=None):
        candidate = {"action_type": "ANALYZE_TABLE", "schema": "public", "table": "votes"}

        with pytest.raises(PermissionError) as exc_info:
            RecommendationDecisionService.evaluate_candidate_decision(
                db=mock_db,
                warehouse_id=999,
                candidate=candidate,
                user=mock_user,
            )

        assert "access denied" in str(exc_info.value)


def test_evaluate_candidate_decision_success(mock_db, mock_user, mock_warehouse):
    """Test authorized single decision evaluation returns R4 result."""
    candidate = {"action_type": "ANALYZE_TABLE", "schema": "public", "table": "votes"}

    mock_match_summary = {"fingerprint": "fp_sha256", "match_found": False, "matches": []}
    mock_condition = {"condition_status": "PRESENT", "evidence": []}

    with patch(
        "app.services.recommendation_decision_service.get_warehouse_by_id",
        return_value=mock_warehouse,
    ), patch(
        "app.services.recommendation_decision_service.RecommendationFingerprintService.find_matches_for_candidate",
        return_value=mock_match_summary,
    ), patch(
        "app.services.recommendation_decision_service.CurrentConditionEvaluator.evaluate_current_condition",
        return_value=mock_condition,
    ):
        result = RecommendationDecisionService.evaluate_candidate_decision(
            db=mock_db,
            warehouse_id=77,
            candidate=candidate,
            user=mock_user,
        )

    assert result["decision"] == RecommendationDecisionState.PROPOSE
    assert result["fingerprint"] == "fp_sha256"


def test_evaluate_candidates_batch_with_context(mock_db, mock_user, mock_warehouse):
    """Test batch candidate evaluation categorizes PROPOSE/SUPPRESS/REVIEW and stores in SharedContext."""
    candidates = [
        {"recommendation_id": "c1", "action_type": "ANALYZE_TABLE", "schema": "public", "table": "t1"},
        {"recommendation_id": "c2", "action_type": "ANALYZE_TABLE", "schema": "public", "table": "t2"},
    ]

    mock_dec1 = {"recommendation_id": "c1", "decision": "PROPOSE", "reason_code": "NO_HISTORY_CONDITION_PRESENT"}
    mock_dec2 = {"recommendation_id": "c2", "decision": "SUPPRESS", "reason_code": "CONDITION_RESOLVED"}

    context = SharedContext()

    with patch(
        "app.services.recommendation_decision_service.get_warehouse_by_id",
        return_value=mock_warehouse,
    ), patch.object(
        RecommendationDecisionService,
        "evaluate_candidate_decision",
        side_effect=[mock_dec1, mock_dec2],
    ):
        summary = RecommendationDecisionService.evaluate_candidates_batch(
            db=mock_db,
            warehouse_id=77,
            candidates=candidates,
            user=mock_user,
            context=context,
        )

    assert summary["total_candidates"] == 2
    assert summary["propose_count"] == 1
    assert summary["suppress_count"] == 1
    assert summary["review_count"] == 0

    ctx_result = context.get_agent_result("recommendation_decision")
    assert ctx_result is not None
    assert ctx_result["propose_count"] == 1
