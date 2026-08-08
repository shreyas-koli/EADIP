from app.orchestrator.task_factory import TaskFactory
from app.models.warehouse import Warehouse
from app.orchestrator.agent_orchestrator import AgentOrchestrator

def test_metadata_discovery_graph():
    """
    Verify the actual AgentTask dependency definitions returned by TaskFactory.
    """
    factory = TaskFactory()
    warehouse = Warehouse(name="test")
    tasks = factory.build_metadata_discovery(warehouse)
    
    task_map = {t.name: t for t in tasks}
    
    assert task_map["metadata"].dependencies == []
    assert task_map["statistics"].dependencies == []
    assert task_map["security"].dependencies == ["metadata"]
    assert task_map["data_quality"].dependencies == ["metadata"]
    assert set(task_map["recommendation"].dependencies) == {
        "metadata",
        "statistics",
        "security",
        "data_quality",
    }

def test_no_circular_dependencies():
    """
    Verify that the current graph does not produce a circular dependency.
    """
    factory = TaskFactory()
    warehouse = Warehouse(name="test")
    tasks = factory.build_metadata_discovery(warehouse)
    
    task_map = {t.name: t for t in tasks}
    
    # The orchestrator's built-in graph validation throws ValueError if there are cycles.
    try:
        AgentOrchestrator._validate_graph(task_map)
    except ValueError as e:
        assert False, f"Circular dependency or missing dependency detected in TaskFactory graph: {e}"
