import time
import threading
from app.orchestrator.agent_orchestrator import AgentOrchestrator, AgentTask

def test_parallel_execution_reduces_total_time():
    """
    Test that execute_parallel schedules independent tasks concurrently.
    """
    orchestrator = AgentOrchestrator()
    
    def slow_task_a():
        time.sleep(1.0)
        return threading.current_thread().name

    def slow_task_b():
        time.sleep(1.0)
        return threading.current_thread().name

    tasks = [
        AgentTask(name="task_a", callable=slow_task_a, args=()),
        AgentTask(name="task_b", callable=slow_task_b, args=()),
    ]
    
    start_time = time.perf_counter()
    result = orchestrator.execute_parallel(tasks)
    end_time = time.perf_counter()
    
    elapsed = end_time - start_time
    
    assert result["parallel"] is True
    assert "task_a" in result["completed"]
    assert "task_b" in result["completed"]
    
    # 2 sequential 1-second tasks take ~2 seconds.
    # Parallel should take ~1 second + overhead.
    assert elapsed < 1.7, f"Tasks did not execute in parallel, elapsed: {elapsed}"

def test_dependency_ordering():
    """
    Test that execute_parallel respects task dependencies.
    """
    orchestrator = AgentOrchestrator()
    
    timeline = []
    
    def task_a():
        timeline.append(("start", "task_a", time.perf_counter_ns()))
        time.sleep(0.2)
        timeline.append(("end", "task_a", time.perf_counter_ns()))
        
    def task_b():
        timeline.append(("start", "task_b", time.perf_counter_ns()))
        time.sleep(0.1)
        timeline.append(("end", "task_b", time.perf_counter_ns()))

    # task_b depends on task_a
    tasks = [
        AgentTask(name="task_a", callable=task_a, args=()),
        AgentTask(name="task_b", callable=task_b, args=(), dependencies=["task_a"]),
    ]
    
    result = orchestrator.execute_parallel(tasks)
    
    assert "task_a" in result["completed"]
    assert "task_b" in result["completed"]
    
    task_a_end = next(t[2] for t in timeline if t[0] == "end" and t[1] == "task_a")
    task_b_start = next(t[2] for t in timeline if t[0] == "start" and t[1] == "task_b")
    
    # Assert task_a finishes before task_b starts
    assert task_a_end <= task_b_start

def test_skipped_status_semantics():
    """
    Verify that when an agent's dependency fails, it is marked as SKIPPED,
    not FAILED, in both SharedContext and the execution summary.
    """
    orchestrator = AgentOrchestrator()
    
    def fail_task():
        raise RuntimeError("I failed")
        
    def skip_task():
        pass
        
    tasks = [
        AgentTask(name="metadata", callable=fail_task, args=()),
        AgentTask(name="security", callable=skip_task, args=(), dependencies=["metadata"]),
    ]
    
    result = orchestrator.execute_parallel(tasks)
    
    assert "metadata" in result["failed"]
    assert "security" in result["skipped"]
    assert "security" not in result["failed"]
    
    # Verify the SharedContext status
    from app.context.shared_context import AgentStatus
    assert orchestrator._context._agent_status["security"] == AgentStatus.SKIPPED
    assert orchestrator._context._agent_status["metadata"] == AgentStatus.FAILED

def test_duplicate_task_names_rejected():
    """
    Verify that execute_parallel raises a ValueError if multiple tasks share the same name.
    """
    from app.context.shared_context import SharedContext
    import pytest
    
    orchestrator = AgentOrchestrator(context=SharedContext())

    tasks = [
        AgentTask(name="metadata", callable=lambda: None),
        AgentTask(name="metadata", callable=lambda: None),
    ]

    with pytest.raises(ValueError, match="Duplicate agent task names are not allowed."):
        orchestrator.execute_parallel(tasks)
