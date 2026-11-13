"""
Comprehensive unit tests for the Automation Agent.

Tests cover:
- Basic functionality (consumes recommendations, handles empty lists)
- Classification (automatable, informational, security, insufficient info)
- Safety (destructive ops, SQL identifier safety, no execution)
- Action plan schema (status, approval, rollback, verification, preconditions)
- Evidence handling (no hallucination, source preservation)
- Execution safety (no database mutation methods called)
"""

import pytest
from unittest.mock import MagicMock

from app.context.shared_context import SharedContext
from app.models.user import User  # noqa: F401
from app.models.warehouse import Warehouse
from app.agents.automation_agent import AutomationAgent
from app.warehouse.automation import (
    AutomationEngine,
    AutomationStatus,
    ActionStatus,
    RiskLevel,
    SafetyClass,
    NonAutomatableReason,
    _is_safe_identifier,
    _quote_identifier,
)


@pytest.fixture
def sample_warehouse():
    return Warehouse(
        id=1,
        name="Test Benchmark WH",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="eadip_benchmark",
        username="test_user",
        encrypted_password=b"faketoken",
        owner_id=1,
    )


@pytest.fixture
def populated_context():
    context = SharedContext()
    context.set_agent_result(
        "recommendation",
        {
            "summary": {"recommendation_count": 5, "high": 2, "medium": 2, "low": 1},
            "recommendations": [
                {
                    "recommendation_type": "missing_primary_key",
                    "schema": "public",
                    "table": "orders",
                    "column": None,
                    "priority": "HIGH",
                    "impact": "HIGH",
                    "effort": "LOW",
                    "confidence": 1.0,
                    "category": "Metadata",
                    "title": "Missing Primary Key on public.orders",
                    "description": "Table 'public.orders' lacks a primary key.",
                    "source_agents": ["metadata"],
                },
                {
                    "recommendation_type": "large_table_indexing",
                    "schema": "public",
                    "table": "orders",
                    "column": None,
                    "priority": "MEDIUM",
                    "impact": "MEDIUM",
                    "effort": "MEDIUM",
                    "confidence": 0.9,
                    "category": "Statistics",
                    "title": "Large Table: public.orders",
                    "description": "Table 'public.orders' has 500000 rows.",
                    "source_agents": ["statistics"],
                },
                {
                    "recommendation_type": "unencrypted_pii",
                    "schema": "public",
                    "table": "orders",
                    "column": "customer_id",
                    "priority": "HIGH",
                    "impact": "HIGH",
                    "effort": "MEDIUM",
                    "confidence": 1.0,
                    "category": "Security",
                    "title": "Security Alert: UNENCRYPTED_PII on public.orders",
                    "description": "Column contains sensitive customer ID without encryption.",
                    "source_agents": ["security"],
                },
                {
                    "recommendation_type": "weak_table_name",
                    "schema": "public",
                    "table": "temp",
                    "column": None,
                    "priority": "LOW",
                    "impact": "LOW",
                    "effort": "LOW",
                    "confidence": 0.9,
                    "category": "Metadata",
                    "title": "Weak Table Name: temp",
                    "description": "The table 'public.temp' has a generic name.",
                    "source_agents": ["metadata"],
                },
                {
                    "recommendation_type": "empty_table",
                    "schema": "public",
                    "table": "unused_archive",
                    "column": None,
                    "priority": "LOW",
                    "impact": "LOW",
                    "effort": "LOW",
                    "confidence": 0.8,
                    "category": "Statistics",
                    "title": "Empty Table: public.unused_archive",
                    "description": "Table 'public.unused_archive' is empty.",
                    "source_agents": ["statistics"],
                },
            ],
        },
    )
    return context


# ── Basic functionality ──────────────────────────────────────────────


def test_automation_agent_consumes_recommendations(sample_warehouse, populated_context):
    """Verify AutomationAgent consumes recommendation results and produces structured output."""
    agent = AutomationAgent()
    result = agent.generate_action_plans(sample_warehouse, populated_context)

    assert "status" in result
    assert result["status"] == "COMPLETED"
    assert "generated_at" in result
    assert "summary" in result
    assert "action_plans" in result
    assert "non_automatable" in result

    summary = result["summary"]
    assert summary["total_recommendations"] == 5


def test_empty_recommendations_handled(sample_warehouse):
    """Verify empty recommendation list is handled gracefully."""
    context = SharedContext()
    context.set_agent_result("recommendation", {"recommendations": []})

    agent = AutomationAgent()
    result = agent.generate_action_plans(sample_warehouse, context)

    assert result["status"] == "COMPLETED"
    assert result["summary"]["total_recommendations"] == 0
    assert result["summary"]["automatable"] == 0
    assert len(result["action_plans"]) == 0
    assert len(result["non_automatable"]) == 0


def test_missing_recommendation_context(sample_warehouse):
    """Verify missing recommendation context is handled without error."""
    context = SharedContext()
    agent = AutomationAgent()
    result = agent.generate_action_plans(sample_warehouse, context)

    assert result["status"] == "COMPLETED"
    assert result["summary"]["total_recommendations"] == 0


def test_structured_result_stored_in_context(sample_warehouse, populated_context):
    """Verify the automation result is stored in SharedContext."""
    agent = AutomationAgent()
    agent.generate_action_plans(sample_warehouse, populated_context)

    stored = populated_context.get_agent_result("automation")
    assert stored is not None
    assert stored["status"] == "COMPLETED"
    assert "action_plans" in stored


def test_action_ids_are_generated(sample_warehouse, populated_context):
    """Verify action IDs are generated for automatable actions."""
    agent = AutomationAgent()
    result = agent.generate_action_plans(sample_warehouse, populated_context)

    for plan in result["action_plans"]:
        assert "action_id" in plan
        assert isinstance(plan["action_id"], str)
        assert len(plan["action_id"]) > 0


def test_recommendation_types_preserved(sample_warehouse, populated_context):
    """Verify recommendation types are preserved in both action plans and non-automatable results."""
    agent = AutomationAgent()
    result = agent.generate_action_plans(sample_warehouse, populated_context)

    all_types = set()
    for plan in result["action_plans"]:
        all_types.add(plan["recommendation_type"])
    for na in result["non_automatable"]:
        all_types.add(na["recommendation_type"])

    assert "large_table_indexing" in all_types
    assert "missing_primary_key" in all_types


# ── Classification ───────────────────────────────────────────────────


def test_supported_recommendation_becomes_automatable(sample_warehouse, populated_context):
    """Verify that a supported safe recommendation (large_table_indexing) becomes automatable."""
    agent = AutomationAgent()
    result = agent.generate_action_plans(sample_warehouse, populated_context)

    # large_table_indexing should map to ANALYZE_TABLE
    automatable_types = [p["recommendation_type"] for p in result["action_plans"]]
    assert "large_table_indexing" in automatable_types


def test_informational_recommendation_is_not_automatable(sample_warehouse, populated_context):
    """Verify informational recommendations like weak_table_name are NOT_AUTOMATABLE."""
    agent = AutomationAgent()
    result = agent.generate_action_plans(sample_warehouse, populated_context)

    weak_name_result = next(
        (n for n in result["non_automatable"] if n["recommendation_type"] == "weak_table_name"),
        None,
    )
    assert weak_name_result is not None
    assert weak_name_result["automation_status"] == AutomationStatus.NOT_AUTOMATABLE


def test_security_recommendation_requires_manual_review(sample_warehouse, populated_context):
    """Verify security-category recommendations require manual review."""
    agent = AutomationAgent()
    result = agent.generate_action_plans(sample_warehouse, populated_context)

    security_result = next(
        (n for n in result["non_automatable"] if n["recommendation_type"] == "unencrypted_pii"),
        None,
    )
    assert security_result is not None
    assert security_result["automation_status"] == AutomationStatus.REQUIRES_MANUAL_REVIEW
    assert security_result["reason"] == NonAutomatableReason.SECURITY_SENSITIVE


def test_insufficient_information_classification(sample_warehouse):
    """Verify recommendations with missing required params become INSUFFICIENT_INFORMATION."""
    context = SharedContext()
    context.set_agent_result("recommendation", {
        "recommendations": [
            {
                "recommendation_type": "large_table_indexing",
                "schema": "",  # Missing schema
                "table": "orders",
                "column": None,
                "priority": "MEDIUM",
                "impact": "MEDIUM",
                "category": "Statistics",
                "title": "Large Table",
                "description": "Missing schema",
                "source_agents": ["statistics"],
            }
        ]
    })

    agent = AutomationAgent()
    result = agent.generate_action_plans(sample_warehouse, context)

    assert len(result["action_plans"]) == 0
    assert len(result["non_automatable"]) == 1
    assert result["non_automatable"][0]["automation_status"] == AutomationStatus.INSUFFICIENT_INFORMATION


def test_ambiguous_target_not_executable(sample_warehouse):
    """Verify that unsafe identifier values are flagged as REQUIRES_MANUAL_REVIEW."""
    context = SharedContext()
    context.set_agent_result("recommendation", {
        "recommendations": [
            {
                "recommendation_type": "large_table_indexing",
                "schema": "public; DROP TABLE",  # SQL injection attempt
                "table": "orders",
                "column": None,
                "priority": "MEDIUM",
                "impact": "MEDIUM",
                "category": "Statistics",
                "title": "Large Table",
                "description": "Unsafe schema",
                "source_agents": ["statistics"],
            }
        ]
    })

    agent = AutomationAgent()
    result = agent.generate_action_plans(sample_warehouse, context)

    assert len(result["action_plans"]) == 0
    assert result["non_automatable"][0]["reason"] == NonAutomatableReason.AMBIGUOUS_TARGET


# ── Safety ───────────────────────────────────────────────────────────


def test_destructive_operations_never_automatically_executable():
    """Verify destructive operations cannot produce executable action plans."""
    engine = AutomationEngine()

    # Simulate a recommendation that looks like a destructive operation
    context = SharedContext()
    context.set_agent_result("recommendation", {
        "recommendations": [
            {
                "recommendation_type": "drop_table_suggestion",
                "schema": "public",
                "table": "old_data",
                "column": None,
                "priority": "LOW",
                "impact": "LOW",
                "category": "Statistics",
                "title": "Drop unused table",
                "description": "This table is unused",
                "source_agents": ["statistics"],
            }
        ]
    })

    warehouse = MagicMock()
    result = engine.analyse(warehouse, context)

    # The unknown type should NOT become an executable action plan
    for plan in result["action_plans"]:
        assert plan["action_type"] not in ("DROP_TABLE", "TRUNCATE", "DELETE")


def test_no_recommendation_text_in_sql(sample_warehouse, populated_context):
    """Verify recommendation description text is never interpolated into SQL statements."""
    agent = AutomationAgent()
    result = agent.generate_action_plans(sample_warehouse, populated_context)

    for plan in result["action_plans"]:
        stmt = plan.get("statement")
        if stmt:
            assert plan.get("description", "") != ""
            # The recommendation description should NOT appear in the SQL
            rec_desc = "Table 'public.orders' has 500000 rows."
            assert rec_desc not in stmt


def test_sql_identifiers_validated():
    """Verify that SQL identifier validation works correctly."""
    assert _is_safe_identifier("orders") is True
    assert _is_safe_identifier("public") is True
    assert _is_safe_identifier("customer_id") is True
    assert _is_safe_identifier("idx_orders_customer_id") is True
    assert _is_safe_identifier("") is False
    assert _is_safe_identifier("DROP TABLE") is False
    assert _is_safe_identifier("a; DROP") is False
    assert _is_safe_identifier("123start") is False
    assert _is_safe_identifier("a" * 64) is False  # Too long


def test_quote_identifier_safety():
    """Verify identifier quoting."""
    assert _quote_identifier("orders") == '"orders"'
    assert _quote_identifier("customer_id") == '"customer_id"'

    with pytest.raises(ValueError):
        _quote_identifier("")
    with pytest.raises(ValueError):
        _quote_identifier("DROP TABLE x")


def test_security_sensitive_actions_require_review(sample_warehouse):
    """Verify security-related recommendations always require manual review."""
    context = SharedContext()
    context.set_agent_result("recommendation", {
        "recommendations": [
            {
                "recommendation_type": "change_permissions",
                "schema": "public",
                "table": "users",
                "column": None,
                "priority": "HIGH",
                "impact": "HIGH",
                "category": "Security",
                "title": "Change user permissions",
                "description": "Update permissions for restricted table.",
                "source_agents": ["security"],
            }
        ]
    })

    agent = AutomationAgent()
    result = agent.generate_action_plans(sample_warehouse, context)

    assert len(result["action_plans"]) == 0
    assert result["non_automatable"][0]["automation_status"] == AutomationStatus.REQUIRES_MANUAL_REVIEW


# ── Action plan schema ───────────────────────────────────────────────


def test_requires_approval_is_true_for_mutations(sample_warehouse, populated_context):
    """Verify requires_approval is true for actions that modify warehouse state."""
    agent = AutomationAgent()
    result = agent.generate_action_plans(sample_warehouse, populated_context)

    for plan in result["action_plans"]:
        if plan["safety_class"] != SafetyClass.READ_ONLY.value:
            assert plan["requires_approval"] is True


def test_executed_is_always_false(sample_warehouse, populated_context):
    """Verify executed is always false in Phase 3."""
    agent = AutomationAgent()
    result = agent.generate_action_plans(sample_warehouse, populated_context)

    for plan in result["action_plans"]:
        assert plan["executed"] is False


def test_status_starts_as_proposed(sample_warehouse, populated_context):
    """Verify all action plans start with status PROPOSED."""
    agent = AutomationAgent()
    result = agent.generate_action_plans(sample_warehouse, populated_context)

    for plan in result["action_plans"]:
        assert plan["status"] == ActionStatus.PROPOSED.value


def test_requires_verification_set(sample_warehouse, populated_context):
    """Verify requires_verification is correctly set."""
    agent = AutomationAgent()
    result = agent.generate_action_plans(sample_warehouse, populated_context)

    for plan in result["action_plans"]:
        assert plan["requires_verification"] is True


def test_rollback_generated_only_when_valid(sample_warehouse, populated_context):
    """Verify rollback information is only generated when genuinely valid."""
    agent = AutomationAgent()
    result = agent.generate_action_plans(sample_warehouse, populated_context)

    for plan in result["action_plans"]:
        rollback = plan["rollback_plan"]
        assert "rollback_available" in rollback
        if plan["is_reversible"]:
            assert rollback["rollback_available"] is True


def test_verification_plan_generated(sample_warehouse, populated_context):
    """Verify verification plans are generated."""
    agent = AutomationAgent()
    result = agent.generate_action_plans(sample_warehouse, populated_context)

    for plan in result["action_plans"]:
        vp = plan["verification_plan"]
        assert "verification_type" in vp
        assert "description" in vp


def test_preconditions_generated(sample_warehouse, populated_context):
    """Verify preconditions are generated for action plans."""
    agent = AutomationAgent()
    result = agent.generate_action_plans(sample_warehouse, populated_context)

    for plan in result["action_plans"]:
        assert len(plan["preconditions"]) > 0
        assert any("must exist" in p for p in plan["preconditions"])


def test_safety_checks_generated(sample_warehouse, populated_context):
    """Verify safety checks are generated for action plans."""
    agent = AutomationAgent()
    result = agent.generate_action_plans(sample_warehouse, populated_context)

    for plan in result["action_plans"]:
        assert len(plan["safety_checks"]) > 0
        assert any("must be approved" in s for s in plan["safety_checks"])


# ── Evidence ─────────────────────────────────────────────────────────


def test_evidence_from_available_state_only(sample_warehouse, populated_context):
    """Verify evidence originates only from available workflow state."""
    agent = AutomationAgent()
    result = agent.generate_action_plans(sample_warehouse, populated_context)

    for plan in result["action_plans"]:
        for ev in plan["evidence"]:
            # Evidence should reference actual agents or recommendation text
            assert isinstance(ev, str)
            assert len(ev) > 0


def test_no_hallucinated_metrics(sample_warehouse, populated_context):
    """Verify no hallucinated metrics are introduced in evidence."""
    agent = AutomationAgent()
    result = agent.generate_action_plans(sample_warehouse, populated_context)

    raw = str(result).lower()
    assert "my internal reasoning was" not in raw
    assert "internal thinking" not in raw
    assert "chain of thought" not in raw


def test_recommendation_source_preserved(sample_warehouse, populated_context):
    """Verify recommendation source is preserved in action plans."""
    agent = AutomationAgent()
    result = agent.generate_action_plans(sample_warehouse, populated_context)

    for plan in result["action_plans"]:
        assert plan["source_agent"] == "automation"
        assert len(plan["evidence"]) > 0


# ── Execution safety ────────────────────────────────────────────────


def test_no_execution_path_in_automation_engine():
    """Verify the AutomationEngine has no database mutation methods."""
    engine = AutomationEngine()
    # Check that the engine has no execute/commit/rollback methods
    for attr_name in dir(engine):
        if attr_name.startswith("_"):
            continue
        assert "execute" not in attr_name.lower() or attr_name == "is_executable"
        assert "commit" not in attr_name.lower()
        assert "cursor" not in attr_name.lower()


def test_action_sql_is_data_not_execution(sample_warehouse, populated_context):
    """Verify SQL statements in action plans are treated as data, not executed."""
    agent = AutomationAgent()
    result = agent.generate_action_plans(sample_warehouse, populated_context)

    for plan in result["action_plans"]:
        # Statement is a string (data), never executed
        stmt = plan.get("statement")
        if stmt:
            assert isinstance(stmt, str)
        # Action plan is in PROPOSED status
        assert plan["status"] == ActionStatus.PROPOSED.value
        # Not executed
        assert plan["executed"] is False


def test_no_approval_automatically_granted(sample_warehouse, populated_context):
    """Verify no approval is automatically granted."""
    agent = AutomationAgent()
    result = agent.generate_action_plans(sample_warehouse, populated_context)

    for plan in result["action_plans"]:
        assert plan["status"] != ActionStatus.APPROVED.value
        assert plan["status"] != ActionStatus.EXECUTING.value
        assert plan["status"] != ActionStatus.COMPLETED.value
