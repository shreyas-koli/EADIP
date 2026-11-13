import pytest
from unittest.mock import MagicMock, patch

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


def test_explainability_in_task_factory_wave_4(mock_warehouse):
    """Verify TaskFactory includes explainability task with dependency on recommendation."""
    context = SharedContext()
    factory = TaskFactory()
    tasks = factory.build_metadata_discovery(mock_warehouse, context)

    task_names = [t.name for t in tasks]
    assert "explainability" in task_names

    exp_task = next(t for t in tasks if t.name == "explainability")
    assert exp_task.dependencies == ["recommendation"]


def test_full_orchestration_with_explainability(mock_warehouse):
    """Verify end-to-end execution of discovery pipeline including Explainability Agent."""
    context = SharedContext()
    factory = TaskFactory()

    # Pre-populate upstream agent results in shared context so agents complete cleanly
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

        assert "explainability" in summary["completed"]
        assert "explainability" in summary["agent_results"]

        exp_result = summary["agent_results"]["explainability"]
        assert "summary" in exp_result
        assert "explanations" in exp_result

        # Check telemetry tracking
        statuses = context.get_all_agent_statuses()
        assert statuses["explainability"] == "COMPLETED"


def test_explainability_failure_does_not_destroy_recommendation_output(mock_warehouse):
    """Verify that if Explainability Agent fails, Recommendation output is preserved in SharedContext."""
    context = SharedContext()
    factory = TaskFactory()

    with patch.object(factory._metadata_agent, "discover_metadata", return_value={}), \
         patch.object(factory._statistics_agent, "generate_statistics", return_value={}), \
         patch.object(factory._monitoring_agent, "collect_monitoring_data", return_value={}), \
         patch.object(factory._security_agent, "generate_security_report", return_value={}), \
         patch.object(factory._data_quality_agent, "generate_quality_report", return_value={}), \
         patch.object(factory._recommendation_agent, "generate_recommendations", side_effect=lambda wh, ctx: ctx.set_agent_result("recommendation", {"recommendations": []}) or {"recommendations": []}), \
         patch.object(factory._explainability_agent, "generate_explanations", side_effect=RuntimeError("Simulated Explainability Failure")):

        tasks = factory.build_metadata_discovery(mock_warehouse, context)
        orchestrator = AgentOrchestrator(context=context)
        summary = orchestrator.execute_parallel(tasks)

        # Explainability failed
        assert "explainability" in summary["failed"]
        assert context.get_agent_status("explainability") == AgentStatus.FAILED

        # Recommendation succeeded and result is preserved
        assert "recommendation" in summary["completed"]
        assert context.has_agent_result("recommendation") is True
        assert context.get_agent_result("recommendation") is not None
