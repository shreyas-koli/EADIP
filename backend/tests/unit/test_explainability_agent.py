import pytest
from unittest.mock import MagicMock

from app.context.shared_context import SharedContext, AgentStatus
from app.models.warehouse import Warehouse
from app.agents.explainability_agent import ExplainabilityAgent
from app.warehouse.explainability import ExplainabilityEngine


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
    # Metadata finding
    context.set_agent_result(
        "metadata",
        {
            "schemas": {
                "public": {
                    "tables": {
                        "orders": {
                            "columns": [
                                {"name": "id", "data_type": "INTEGER", "primary_key": False},
                                {"name": "customer_id", "data_type": "INTEGER", "primary_key": False},
                                {"name": "amount", "data_type": "NUMERIC", "primary_key": False},
                            ]
                        }
                    }
                }
            }
        },
    )
    # Statistics finding
    context.set_agent_result(
        "statistics",
        {
            "tables": [
                {
                    "schema": "public",
                    "table_name": "orders",
                    "estimated_row_count": 500000,
                    "total_columns": 3,
                }
            ]
        },
    )
    # Security finding
    context.set_agent_result(
        "security",
        {
            "issues": [
                {
                    "schema": "public",
                    "table": "orders",
                    "column": "customer_id",
                    "severity": "HIGH",
                    "rule": "UNENCRYPTED_PII",
                    "description": "Column contains sensitive customer ID without encryption.",
                }
            ]
        },
    )
    # Recommendation finding
    context.set_agent_result(
        "recommendation",
        {
            "summary": {"recommendation_count": 3, "high": 2, "medium": 1, "low": 0},
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
            ],
            "priority": {"high": [], "medium": [], "low": []},
        },
    )
    return context


def test_explainability_agent_consumes_recommendation_and_findings(sample_warehouse, populated_context):
    """Verify ExplainabilityAgent consumes recommendations & prior findings to produce structured output."""
    agent = ExplainabilityAgent()
    result = agent.generate_explanations(sample_warehouse, populated_context)

    assert "summary" in result
    assert "explanations" in result
    assert result["summary"]["explanation_count"] == 3
    assert result["summary"]["supported_recommendations"] == 3
    assert result["summary"]["missing_evidence_count"] == 0

    explanations = result["explanations"]
    assert len(explanations) == 3

    # Test structured fields format
    for exp in explanations:
        assert "recommendation_type" in exp
        assert "title" in exp
        assert "recommendation" in exp
        assert "why" in exp
        assert "evidence" in exp
        assert "affected_objects" in exp
        assert "expected_impact" in exp
        assert "confidence" in exp
        assert "supporting_agents" in exp
        assert "severity" in exp
        assert "evidence_available" in exp
        assert exp["evidence_available"] is True


def test_evidence_is_taken_only_from_available_state(sample_warehouse, populated_context):
    """Verify evidence lists contain actual metrics and observable facts from prior agent results."""
    agent = ExplainabilityAgent()
    result = agent.generate_explanations(sample_warehouse, populated_context)

    # Check large table indexing explanation evidence
    idx_exp = next(e for e in result["explanations"] if e["recommendation_type"] == "large_table_indexing")
    assert "public.orders" in idx_exp["affected_objects"]
    assert any("500,000" in ev for ev in idx_exp["evidence"])
    assert "Statistics Agent" in idx_exp["supporting_agents"]

    # Check security issue explanation evidence
    sec_exp = next(e for e in result["explanations"] if e["recommendation_type"] == "unencrypted_pii")
    assert "public.orders.customer_id" in sec_exp["affected_objects"]
    assert any("UNENCRYPTED_PII" in ev for ev in sec_exp["evidence"])
    assert "Security Agent" in sec_exp["supporting_agents"]


def test_missing_evidence_handled_gracefully(sample_warehouse):
    """Verify that when context lacks detailed evidence for an agent, missing evidence is handled gracefully."""
    context = SharedContext()
    # Provide recommendation without backing metadata/statistics results in context
    context.set_agent_result(
        "recommendation",
        {
            "recommendations": [
                {
                    "recommendation_type": "missing_primary_key",
                    "schema": "public",
                    "table": "unknown_table",
                    "column": None,
                    "priority": "HIGH",
                    "impact": "HIGH",
                    "effort": "LOW",
                    "confidence": 1.0,
                    "category": "Metadata",
                    "title": "Missing Primary Key on public.unknown_table",
                    "description": "Table 'public.unknown_table' lacks a primary key.",
                    "source_agents": ["metadata"],
                }
            ]
        },
    )

    agent = ExplainabilityAgent()
    result = agent.generate_explanations(sample_warehouse, context)

    assert result["summary"]["explanation_count"] == 1
    assert result["summary"]["missing_evidence_count"] == 1
    exp = result["explanations"][0]
    assert exp["evidence_available"] is False
    assert any("Evidence unavailable" in ev for ev in exp["evidence"])


def test_no_hidden_chain_of_thought_returned(sample_warehouse, populated_context):
    """Verify output contains no internal chain-of-thought keywords like 'My internal reasoning was...'."""
    agent = ExplainabilityAgent()
    result = agent.generate_explanations(sample_warehouse, populated_context)

    raw_text = str(result).lower()
    assert "my internal reasoning was" not in raw_text
    assert "internal thinking" not in raw_text
    assert "chain of thought" not in raw_text


def test_empty_recommendations_handling(sample_warehouse):
    """Verify ExplainabilityAgent handles empty recommendation lists cleanly."""
    context = SharedContext()
    context.set_agent_result("recommendation", {"recommendations": []})

    agent = ExplainabilityAgent()
    result = agent.generate_explanations(sample_warehouse, context)

    assert result["summary"]["explanation_count"] == 0
    assert result["explanations"] == []
