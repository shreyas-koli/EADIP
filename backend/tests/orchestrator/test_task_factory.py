from app.orchestrator.task_factory import TaskFactory
from app.models.warehouse import Warehouse
from app.orchestrator.agent_orchestrator import AgentOrchestrator
from app.context.shared_context import SharedContext

def test_metadata_discovery_graph():
    """
    Verify the actual AgentTask dependency definitions returned by TaskFactory.
    """
    factory = TaskFactory()
    warehouse = Warehouse(name="test")
    context = SharedContext()
    tasks = factory.build_metadata_discovery(warehouse, context)
    
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
    context = SharedContext()
    tasks = factory.build_metadata_discovery(warehouse, context)
    
    task_map = {t.name: t for t in tasks}
    
    # The orchestrator's built-in graph validation throws ValueError if there are cycles.
    try:
        AgentOrchestrator._validate_graph(task_map)
    except ValueError as e:
        assert False, f"Circular dependency or missing dependency detected in TaskFactory graph: {e}"

def test_explicit_context_propagation():
    """
    Verify that every AgentTask receives the exact same SharedContext instance.
    """
    factory = TaskFactory()
    warehouse = Warehouse(name="test")
    context = SharedContext()
    tasks = factory.build_metadata_discovery(warehouse, context)
    
    task_names = {"metadata", "statistics", "security", "data_quality", "recommendation"}
    
    for task in tasks:
        assert task.name in task_names
        # args[0] is warehouse, args[1] is context
        assert len(task.args) == 2
        assert task.args[1] is context, f"Task {task.name} did not receive the exact SharedContext instance"
