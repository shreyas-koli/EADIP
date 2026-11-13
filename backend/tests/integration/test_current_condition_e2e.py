"""
Integration test for R3 Current Condition Awareness.

Verifies end-to-end integration:
Candidate -> R2 Fingerprint -> Historical Match (ACHIEVED) -> R3 Current Condition Awareness.
Ensures current catalog state determines status and that candidate generation remains unaffected.
"""

from unittest.mock import MagicMock, patch
import pytest

from app.models.warehouse import Warehouse
from app.services.current_condition_service import CurrentConditionService
from app.warehouse.current_condition import ConditionStatus
from app.warehouse.recommendation import RecommendationEngine
from app.context.shared_context import SharedContext


def test_current_condition_integration_lifecycle():
    """
    Integration test demonstrating:
    1. Candidate fingerprint is calculated via R2.
    2. Historical match context (outcome = ACHIEVED) is retrieved via R1/R2.
    3. R3 current condition is evaluated against current catalog stats (n_mod_since_analyze > 0).
    4. R3 returns status PRESENT despite historical ACHIEVED outcome.
    5. RecommendationEngine generates candidate without suppression.
    """
    mock_wh = MagicMock(spec=Warehouse)
    mock_wh.id = 55
    mock_wh.owner_id = 1
    mock_wh.db_type = "postgresql"
    mock_wh.username = "db_user"

    candidate = {
        "recommendation_id": "rec_multi_discovery_001",
        "action_type": "ANALYZE_TABLE",
        "target": {"schema": "public", "table": "orders"},
    }

    mock_db = MagicMock()

    historical_match_summary = {
        "fingerprint": "a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f67890",
        "match_found": True,
        "match_count": 1,
        "matches": [
            {
                "id": 10,
                "recommendation_id": "rec_multi_discovery_000",
                "action_id": "act_prev",
                "session_id": 1,
                "action_type": "ANALYZE_TABLE",
                "approval_status": "APPROVED",
                "execution_status": "COMPLETED",
                "verification_status": "VERIFIED",
                "objective_status": "VERIFIED",
                "final_outcome": "ACHIEVED",
            }
        ],
    }

    catalog_stats_row = {
        "schemaname": "public",
        "relname": "orders",
        "last_analyze": None,
        "last_autoanalyze": None,
        "n_mod_since_analyze": 2500,
        "n_live_tup": 50000,
        "n_dead_tup": 300,
    }

    mock_mappings = MagicMock()
    mock_mappings.first.return_value = catalog_stats_row
    mock_conn = MagicMock()
    mock_conn.execution_options.return_value = mock_conn
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.mappings.return_value = mock_mappings
    mock_engine = MagicMock()
    mock_engine.connect.return_value = mock_conn

    mock_user = MagicMock()
    mock_user.id = 1

    with patch(
        "app.services.current_condition_service.get_warehouse_by_id",
        return_value=mock_wh,
    ), patch(
        "app.services.current_condition_service.RecommendationFingerprintService.find_matches_for_candidate",
        return_value=historical_match_summary,
    ), patch(
        "app.warehouse.current_condition.WarehouseConnector.connect",
        return_value=mock_engine,
    ):
        result = CurrentConditionService.evaluate_candidate_condition(
            db=mock_db,
            warehouse_id=55,
            candidate=candidate,
            user=mock_user,
        )

    # Assert R3 output
    assert result["condition_status"] == ConditionStatus.PRESENT
    assert result["condition_type"] == "MODIFICATIONS_SINCE_ANALYZE"
    assert result["historical_match"]["final_outcome"] == "ACHIEVED"
    assert len(result["evidence"]) == 5
    assert result["evidence"][2]["value"] == 2500

    # Assert RecommendationEngine is uninhibited
    ctx = SharedContext()
    ctx.set_agent_result(
        "statistics",
        {
            "tables": [
                {
                    "schema": "public",
                    "table_name": "orders",
                    "estimated_row_count": 500000,
                    "total_columns": 10,
                }
            ]
        },
    )

    rec_engine = RecommendationEngine()
    rec_result = rec_engine.analyse(mock_wh, ctx)
    assert len(rec_result["recommendations"]) == 1
