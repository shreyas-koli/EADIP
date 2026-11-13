"""
Orchestration tests for the Automation Agent.

Verifies:
1. Automation depends on Recommendation (not Explainability or Reporting).
2. Automation executes in the correct workflow wave (Wave 4).
3. Telemetry is emitted correctly.
4. Failure is isolated — Recommendation, Explainability, and Reporting
   remain intact if Automation fails.
5. Existing orchestration tests remain passing.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.models.user import User  # noqa: F401
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


def test_automation_in_task_factory_wave_4(mock_warehouse):
    """Verify TaskFactory includes automation task with dependency on recommendation."""
    context = SharedContext()
    factory = TaskFactory()
    tasks = factory.build_metadata_discovery(mock_warehouse, context)

    task_names = [t.name for t in tasks]
    assert "automation" in task_names

    auto_task = next(t for t in tasks if t.name == "automation")
    assert auto_task.dependencies == ["recommendation"]


def test_automation_does_not_depend_on_explainability(mock_warehouse):
    """Verify Automation does not unnecessarily depend on Explainability."""
    context = SharedContext()
    factory = TaskFactory()
    tasks = factory.build_metadata_discovery(mock_warehouse, context)

    auto_task = next(t for t in tasks if t.name == "automation")
    assert "explainability" not in auto_task.dependencies


def test_automation_does_not_depend_on_reporting(mock_warehouse):
    """Verify Automation does not unnecessarily depend on Reporting."""
    context = SharedContext()
    factory = TaskFactory()
    tasks = factory.build_metadata_discovery(mock_warehouse, context)

    auto_task = next(t for t in tasks if t.name == "automation")
    assert "reporting" not in auto_task.dependencies


def test_full_orchestration_with_automation(mock_warehouse):
    """Verify end-to-end execution of discovery pipeline including Automation Agent."""
    context = SharedContext()
    factory = TaskFactory()

    # Pre-populate context with upstream results
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

        assert "automation" in summary["completed"]
        assert "automation" in summary["agent_results"]

        auto_result = summary["agent_results"]["automation"]
        assert auto_result["status"] == "COMPLETED"
        assert "action_plans" in auto_result
        assert "summary" in auto_result

        statuses = context.get_all_agent_statuses()
        assert statuses["automation"] == "COMPLETED"


def test_automation_failure_does_not_destroy_other_agents(mock_warehouse):
    """Verify that if Automation Agent fails, Recommendation, Explainability, and Reporting are preserved."""
    context = SharedContext()
    factory = TaskFactory()

    with patch.object(factory._metadata_agent, "discover_metadata", return_value={}), \
         patch.object(factory._statistics_agent, "generate_statistics", return_value={}), \
         patch.object(factory._monitoring_agent, "collect_monitoring_data", return_value={}), \
         patch.object(factory._security_agent, "generate_security_report", return_value={}), \
         patch.object(factory._data_quality_agent, "generate_quality_report", return_value={}), \
         patch.object(factory._recommendation_agent, "generate_recommendations",
                      side_effect=lambda wh, ctx: ctx.set_agent_result("recommendation", {"recommendations": []}) or {"recommendations": []}), \
         patch.object(factory._explainability_agent, "generate_explanations",
                      side_effect=lambda wh, ctx: ctx.set_agent_result("explainability", {"explanations": []}) or {"explanations": []}), \
         patch.object(factory._reporting_agent, "generate_report",
                      side_effect=lambda wh, ctx: ctx.set_agent_result("reporting", {"sections": {}}) or {"sections": {}}), \
         patch.object(factory._automation_agent, "generate_action_plans",
                      side_effect=RuntimeError("Simulated Automation Failure")):

        tasks = factory.build_metadata_discovery(mock_warehouse, context)
        orchestrator = AgentOrchestrator(context=context)
        summary = orchestrator.execute_parallel(tasks)

        # Automation failed
        assert "automation" in summary["failed"]
        assert context.get_agent_status("automation") == AgentStatus.FAILED

        # Recommendation, Explainability, and Reporting all succeeded
        assert "recommendation" in summary["completed"]
        assert "explainability" in summary["completed"]
        assert "reporting" in summary["completed"]
        assert context.has_agent_result("recommendation") is True
        assert context.has_agent_result("explainability") is True
        assert context.has_agent_result("reporting") is True


def test_automation_telemetry_emission(mock_warehouse):
    """Verify Automation Agent emits telemetry events during execution."""
    events_collected = []

    def event_callback(event_data):
        events_collected.append(event_data)

    context = SharedContext(event_callback=event_callback)
    context.set_agent_result("recommendation", {"recommendations": []})

    factory = TaskFactory()

    with patch.object(factory._metadata_agent, "discover_metadata", return_value={}), \
         patch.object(factory._statistics_agent, "generate_statistics", return_value={}), \
         patch.object(factory._monitoring_agent, "collect_monitoring_data", return_value={}), \
         patch.object(factory._security_agent, "generate_security_report", return_value={}), \
         patch.object(factory._data_quality_agent, "generate_quality_report", return_value={}), \
         patch.object(factory._recommendation_agent, "generate_recommendations", return_value={"recommendations": []}):

        tasks = factory.build_metadata_discovery(mock_warehouse, context)
        orchestrator = AgentOrchestrator(context=context)
        orchestrator.execute_parallel(tasks)

    # Check that automation-related events were emitted
    automation_events = [e for e in events_collected if e.get("agent") == "automation"]
    assert len(automation_events) > 0

    # Should have at least started and completed events
    event_types = [e.get("event") for e in automation_events]
    assert "agent_started" in event_types
    assert "agent_completed" in event_types
