"""
Unit tests for ControlledReanalysisEngine (Phase 7).

Verifies deterministic assessment logic, objective status evaluation,
explicit handling of unmeasured performance metrics (no fabricated causality),
and safe follow-up recommendation generation (PROPOSED state requiring human approval).
"""

import pytest

from app.models.warehouse import Warehouse
from app.warehouse.reanalysis_engine import ControlledReanalysisEngine


@pytest.fixture
def mock_warehouse():
    return Warehouse(
        id=77,
        name="Reanalysis WH",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="eadip_re",
        username="postgres",
        encrypted_password=b"token",
        owner_id=1,
    )


@pytest.fixture
def sample_action_plan():
    return {
        "action_id": "act_re_001",
        "action_type": "CREATE_INDEX",
        "target": {"schema": "public", "table": "orders", "column": "created_at"},
        "statement": 'CREATE INDEX "idx_orders_created_at" ON "public"."orders" ("created_at")',
        "risk_level": "LOW",
        "safety_class": "REVERSIBLE_WRITE",
    }


def test_reanalyze_completed_and_verified(mock_warehouse, sample_action_plan):
    """Verify COMPLETED + VERIFIED yields SUCCESSFUL_OUTCOME and ACHIEVED objective status."""
    exec_data = {"status": "COMPLETED", "duration_ms": 20.0, "statement_fingerprint": sample_action_plan["statement"]}
    ver_data = {"status": "VERIFIED", "verified": True, "checks": [{"status": "PASS"}]}

    res = ControlledReanalysisEngine.reanalyze(mock_warehouse, sample_action_plan, exec_data, ver_data)

    assert res["status"] == "SUCCESSFUL_OUTCOME"
    assert res["objective_status"] == "ACHIEVED"
    assert res["follow_up_required"] is False
    assert res["follow_up_type"] == "NONE"
    assert res["follow_up_details"] is None
    # Check no fake latency metric claim
    latency_comp = [c for c in res["comparisons"] if c["metric"] == "query_latency_impact"][0]
    assert latency_comp["status"] == "NOT_MEASURED"
    assert "No comparable post-execution latency benchmark" in latency_comp["reason"]


def test_reanalyze_completed_and_verification_failed(mock_warehouse, sample_action_plan):
    """Verify COMPLETED + VERIFICATION_FAILED yields UNSUCCESSFUL_OUTCOME and NOT_ACHIEVED."""
    exec_data = {"status": "COMPLETED", "duration_ms": 20.0, "statement_fingerprint": sample_action_plan["statement"]}
    ver_data = {"status": "VERIFICATION_FAILED", "verified": False, "checks": [{"status": "FAIL"}]}

    res = ControlledReanalysisEngine.reanalyze(mock_warehouse, sample_action_plan, exec_data, ver_data)

    assert res["status"] == "UNSUCCESSFUL_OUTCOME"
    assert res["objective_status"] == "NOT_ACHIEVED"
    assert res["follow_up_required"] is True
    assert res["follow_up_type"] == "ANALYSIS"
    assert res["follow_up_details"] is not None
    # Follow-up must be PROPOSED and require approval
    assert res["follow_up_details"]["status"] == "PROPOSED"
    assert res["follow_up_details"]["requires_approval"] is True


def test_reanalyze_inconclusive_verification(mock_warehouse, sample_action_plan):
    """Verify COMPLETED + INCONCLUSIVE yields UNCERTAIN_OUTCOME and UNCERTAIN objective."""
    exec_data = {"status": "COMPLETED", "duration_ms": 20.0}
    ver_data = {"status": "INCONCLUSIVE", "verified": None}

    res = ControlledReanalysisEngine.reanalyze(mock_warehouse, sample_action_plan, exec_data, ver_data)

    assert res["status"] == "UNCERTAIN_OUTCOME"
    assert res["objective_status"] == "UNCERTAIN"
    assert res["follow_up_required"] is True
    assert res["follow_up_type"] == "OBSERVATION"


def test_reanalyze_execution_failed(mock_warehouse, sample_action_plan):
    """Verify FAILED execution yields UNSUCCESSFUL_OUTCOME and NOT_ACHIEVED objective."""
    exec_data = {"status": "FAILED", "duration_ms": 5.0, "error_message": "Connection timeout"}

    res = ControlledReanalysisEngine.reanalyze(mock_warehouse, sample_action_plan, exec_data, None)

    assert res["status"] == "UNSUCCESSFUL_OUTCOME"
    assert res["objective_status"] == "NOT_ACHIEVED"
    assert res["follow_up_required"] is True
    assert "failed during target execution" in res["conclusion"].lower()
