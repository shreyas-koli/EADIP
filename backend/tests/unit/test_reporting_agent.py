import pytest
from app.context.shared_context import SharedContext
from app.models.warehouse import Warehouse
from app.agents.reporting_agent import ReportingAgent


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
    context.set_current_warehouse({
        "id": 1,
        "name": "Test Benchmark WH",
        "db_type": "postgresql",
    })

    # Metadata
    context.set_agent_result(
        "metadata",
        {
            "schemas": {
                "public": {
                    "tables": {
                        "orders": {
                            "columns": [
                                {"name": "id", "data_type": "INTEGER", "primary_key": False}
                            ]
                        }
                    }
                }
            }
        },
    )

    # Statistics
    context.set_agent_result(
        "statistics",
        {
            "tables": [
                {
                    "schema": "public",
                    "table_name": "orders",
                    "estimated_row_count": 500000,
                    "total_columns": 1,
                }
            ]
        },
    )

    # Security
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
                    "description": "Sensitive column without encryption.",
                }
            ]
        },
    )

    # Data Quality
    context.set_agent_result(
        "data_quality",
        {
            "issues": [
                {
                    "schema": "public",
                    "table": "orders",
                    "column": None,
                    "severity": "MEDIUM",
                    "rule": "MISSING_UNIQUENESS_CONSTRAINTS",
                    "dimension": "uniqueness",
                }
            ]
        },
    )

    # Prediction (projections)
    context.set_agent_result(
        "prediction",
        {
            "insights": [
                "Storage usage is projected to increase by 25% over the next 90 days."
            ]
        },
    )

    # Recommendation
    context.set_agent_result(
        "recommendation",
        {
            "summary": {"recommendation_count": 1, "high": 1, "medium": 0, "low": 0},
            "recommendations": [
                {
                    "recommendation_type": "missing_primary_key",
                    "schema": "public",
                    "table": "orders",
                    "column": None,
                    "priority": "HIGH",
                    "impact": "HIGH",
                    "category": "Metadata",
                    "title": "Missing Primary Key on public.orders",
                    "description": "Table 'public.orders' lacks a primary key.",
                }
            ]
        },
    )

    # Explainability
    context.set_agent_result(
        "explainability",
        {
            "summary": {"explanation_count": 1},
            "explanations": [
                {
                    "recommendation_type": "missing_primary_key",
                    "title": "Missing Primary Key on public.orders",
                    "why": "No primary key constraint was detected during discovery.",
                    "evidence": ["Metadata Agent confirmed 0 primary keys on public.orders."],
                    "supporting_agents": ["Metadata Agent"],
                }
            ]
        },
    )

    return context


def test_reporting_agent_consumes_agent_results(sample_warehouse, populated_context):
    """Verify ReportingAgent consolidates agent results into a structured report."""
    agent = ReportingAgent()
    report = agent.generate_report(sample_warehouse, populated_context)

    assert "warehouse_overview" in report
    assert "executive_summary" in report
    assert "sections" in report

    sections = report["sections"]
    assert "metadata" in sections
    assert "statistics_monitoring" in sections
    assert "security" in sections
    assert "data_quality" in sections
    assert "predictions" in sections
    assert "recommendations" in sections
    assert "explainability" in sections


def test_recommendation_and_explainability_appear_in_report(sample_warehouse, populated_context):
    """Verify recommendation and explainability items appear correctly in report sections."""
    agent = ReportingAgent()
    report = agent.generate_report(sample_warehouse, populated_context)

    rec_sec = report["sections"]["recommendations"]
    assert rec_sec["total_recommendations"] == 1
    assert rec_sec["is_executed"] is False
    assert rec_sec["items"][0]["status"] == "PROPOSED"
    assert rec_sec["items"][0]["recommendation_type"] == "missing_primary_key"

    exp_sec = report["sections"]["explainability"]
    assert exp_sec["explanation_count"] == 1
    assert len(exp_sec["items"]) == 1
    assert exp_sec["items"][0]["why"] == "No primary key constraint was detected during discovery."


def test_predictions_distinguishable_from_observed_facts(sample_warehouse, populated_context):
    """Verify predictions are explicitly marked as projections and separated from facts."""
    agent = ReportingAgent()
    report = agent.generate_report(sample_warehouse, populated_context)

    pred_sec = report["sections"]["predictions"]
    assert pred_sec["is_projection"] is True
    assert len(pred_sec["predictions"]) == 1
    assert "projected" in pred_sec["predictions"][0].lower()


def test_recommendations_not_presented_as_executed(sample_warehouse, populated_context):
    """Verify recommendations are marked as PROPOSED, not executed."""
    agent = ReportingAgent()
    report = agent.generate_report(sample_warehouse, populated_context)

    rec_sec = report["sections"]["recommendations"]
    assert rec_sec["is_executed"] is False
    for item in rec_sec["items"]:
        assert item["status"] == "PROPOSED"
        assert item["status"] != "EXECUTED"


def test_missing_agent_results_handled_gracefully(sample_warehouse):
    """Verify empty/missing context results produce structured 'No findings available' entries without errors."""
    context = SharedContext()
    agent = ReportingAgent()
    report = agent.generate_report(sample_warehouse, context)

    assert report["executive_summary"]["total_recommendations"] == 0
    assert report["sections"]["metadata"]["schemas_count"] == 0
    assert "No metadata findings" in report["sections"]["metadata"]["summary"]
    assert "No predictions" in report["sections"]["predictions"]["summary"]
