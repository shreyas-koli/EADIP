import pytest
from unittest.mock import patch, MagicMock

from app.models.warehouse import Warehouse
from app.context.shared_context import SharedContext, AgentStatus
from app.orchestrator.agent_orchestrator import AgentOrchestrator
from app.orchestrator.task_factory import TaskFactory


@pytest.fixture
def mock_warehouse():
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


def test_reporting_in_task_factory_wave_4(mock_warehouse):
    """Verify TaskFactory includes reporting task with dependency on recommendation."""
    context = SharedContext()
    factory = TaskFactory()
    tasks = factory.build_metadata_discovery(mock_warehouse, context)

    task_names = [t.name for t in tasks]
    assert "reporting" in task_names

    rep_task = next(t for t in tasks if t.name == "reporting")
    assert rep_task.dependencies == ["recommendation"]


def test_full_orchestration_with_reporting(mock_warehouse):
    """Verify end-to-end execution of discovery pipeline including Reporting Agent."""
    context = SharedContext()
    factory = TaskFactory()

    context.set_agent_result("metadata", {"schemas": {"public": {"tables": {"orders": {"columns": []}}}}})
    context.set_agent_result("statistics", {"tables": [{"schema": "public", "table_name": "orders", "estimated_row_count": 100}]})
    context.set_agent_result("monitoring", {"active_connections": 2})
    context.set_agent_result("security", {"issues": []})
    context.set_agent_result("data_quality", {"issues": []})

    with patch.object(factory._metadata_agent, "discover_metadata", return_value={}), \
         patch.object(factory._statistics_agent, "generate_statistics", return_value={}), \
         patch.object(factory._monitoring_agent, "collect_monitoring_data", return_value={}), \
         patch.object(factory._security_agent, "generate_security_report", return_value={}), \
         patch.object(factory._data_quality_agent, "generate_quality_report", return_value={}), \
         patch.object(factory._recommendation_agent, "generate_recommendations", return_value={"summary": {}, "recommendations": []}):

        tasks = factory.build_metadata_discovery(mock_warehouse, context)
        orchestrator = AgentOrchestrator(context=context)
        summary = orchestrator.execute_parallel(tasks)

        assert "reporting" in summary["completed"]
        assert "reporting" in summary["agent_results"]

        rep_result = summary["agent_results"]["reporting"]
        assert "warehouse_overview" in rep_result
        assert "executive_summary" in rep_result
        assert "sections" in rep_result

        statuses = context.get_all_agent_statuses()
        assert statuses["reporting"] == "COMPLETED"


def test_reporting_failure_does_not_destroy_recommendation_or_explainability(mock_warehouse):
    """Verify that if Reporting Agent fails, Recommendation and Explainability outputs are preserved."""
    context = SharedContext()
    factory = TaskFactory()

    with patch.object(factory._metadata_agent, "discover_metadata", return_value={}), \
         patch.object(factory._statistics_agent, "generate_statistics", return_value={}), \
         patch.object(factory._monitoring_agent, "collect_monitoring_data", return_value={}), \
         patch.object(factory._security_agent, "generate_security_report", return_value={}), \
         patch.object(factory._data_quality_agent, "generate_quality_report", return_value={}), \
         patch.object(factory._recommendation_agent, "generate_recommendations", side_effect=lambda wh, ctx: ctx.set_agent_result("recommendation", {"recommendations": []}) or {"recommendations": []}), \
         patch.object(factory._explainability_agent, "generate_explanations", side_effect=lambda wh, ctx: ctx.set_agent_result("explainability", {"explanations": []}) or {"explanations": []}), \
         patch.object(factory._reporting_agent, "generate_report", side_effect=RuntimeError("Simulated Reporting Failure")):

        tasks = factory.build_metadata_discovery(mock_warehouse, context)
        orchestrator = AgentOrchestrator(context=context)
        summary = orchestrator.execute_parallel(tasks)

        # Reporting failed
        assert "reporting" in summary["failed"]
        assert context.get_agent_status("reporting") == AgentStatus.FAILED

        # Recommendation & Explainability succeeded and results are preserved
        assert "recommendation" in summary["completed"]
        assert "explainability" in summary["completed"]
        assert context.has_agent_result("recommendation") is True
        assert context.has_agent_result("explainability") is True
