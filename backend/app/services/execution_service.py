from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models.execution import AgentExecution, DiscoverySession
import logging

logger = logging.getLogger(__name__)


class ExecutionService:
    """
    Service responsible for persisting discovery execution summaries
    into PostgreSQL.
    """

    @staticmethod
    def persist_execution(
        db: Session,
        warehouse_id: int,
        execution_summary: Dict[str, Any],
    ) -> DiscoverySession:
        """
        Persist an execution summary into the database.

        Parameters
        ──────────
        db : Session
            The active database session.
        warehouse_id : int
            The warehouse being analysed.
        execution_summary : Dict[str, Any]
            The output of AgentOrchestrator.execute_parallel(...).

        Returns
        ───────
        DiscoverySession
            The persisted discovery session.
        """
        session_id = execution_summary.get("session_id")
        total_duration_ms = execution_summary.get("total_execution_ms")
        
        completed = set(execution_summary.get("completed", []))
        failed = set(execution_summary.get("failed", []))
        skipped = set(execution_summary.get("skipped", []))
        agent_executions = execution_summary.get("agent_execution", [])

        # Determine overall status.
        # Convention:
        # FAILED -> at least one agent failed
        # COMPLETED -> no agents failed, even if one or more agents were skipped
        status = "FAILED" if failed else "COMPLETED"

        # Derive overall timestamps from agents
        started_at_str = None
        finished_at_str = None

        for metrics in agent_executions:
            a_start = metrics.get("started_at")
            a_finish = metrics.get("finished_at")
            if a_start:
                if started_at_str is None or a_start < started_at_str:
                    started_at_str = a_start
            if a_finish:
                if finished_at_str is None or a_finish > finished_at_str:
                    finished_at_str = a_finish

        if started_at_str:
            started_at = datetime.fromisoformat(started_at_str)
        else:
            started_at = datetime.now(timezone.utc)

        if finished_at_str:
            finished_at = datetime.fromisoformat(finished_at_str)
        else:
            finished_at = datetime.now(timezone.utc)

        # Retrieve recommendations
        agent_results = execution_summary.get("agent_results", {})
        recommendations = agent_results.get("recommendation")

        if recommendations:
            from app.recommendation.formatter import RecommendationFormatter
            formatter = RecommendationFormatter()
            recommendations = formatter.format(recommendations)

        # Create session
        discovery_session = DiscoverySession(
            session_id=session_id,
            warehouse_id=warehouse_id,
            started_at=started_at,
            finished_at=finished_at,
            total_duration_ms=total_duration_ms,
            status=status,
            recommendations=recommendations,
        )

        try:
            db.add(discovery_session)
            db.flush()  # To get the session.id for the relationship

            # Persist agent executions
            for metrics in agent_executions:
                agent_name = metrics.get("agent")
                if not agent_name:
                    raise ValueError("Agent execution is missing agent name")
                
                is_completed = agent_name in completed
                is_failed = agent_name in failed
                is_skipped = agent_name in skipped
                
                match_count = sum([is_completed, is_failed, is_skipped])
                if match_count == 0:
                    raise ValueError(f"Agent '{agent_name}' has no valid execution status")
                elif match_count > 1:
                    raise ValueError(f"Agent '{agent_name}' must have exactly one execution status")

                # Determine agent status
                if is_completed:
                    agent_status = "COMPLETED"
                elif is_failed:
                    agent_status = "FAILED"
                else:
                    agent_status = "SKIPPED"

                a_started_at_str = metrics.get("started_at")
                a_finished_at_str = metrics.get("finished_at")

                a_started_at = datetime.fromisoformat(a_started_at_str) if a_started_at_str else started_at
                a_finished_at = datetime.fromisoformat(a_finished_at_str) if a_finished_at_str else finished_at

                a_exec = AgentExecution(
                    session_id=discovery_session.id,
                    agent_name=agent_name,
                    status=agent_status,
                    started_at=a_started_at,
                    finished_at=a_finished_at,
                    duration_ms=metrics.get("duration_ms"),
                    wave=metrics.get("wave", 0),
                    error=metrics.get("error")
                )
                db.add(a_exec)

            db.commit()
            logger.info(f"Successfully persisted discovery session {session_id} with {len(agent_executions)} agent executions.")
            db.refresh(discovery_session)
            
            return discovery_session

        except Exception as exc:
            db.rollback()
            logger.error(f"Failed to persist execution summary for session {session_id}: {str(exc)}")
            raise

    @staticmethod
    def get_history(
        db: Session,
        warehouse_id: int,
        page: int = 1,
        page_size: int = 10,
        status: str | None = None
    ) -> dict:
        """
        Retrieve discovery history for a given warehouse with pagination.
        Returns a dict containing items, total, page, and page_size.
        """
        query = db.query(DiscoverySession).filter(DiscoverySession.warehouse_id == warehouse_id)
        
        if status:
            query = query.filter(DiscoverySession.status == status)
            
        total = query.count()
        
        offset = (page - 1) * page_size
        items = query.order_by(DiscoverySession.started_at.desc()).offset(offset).limit(page_size).all()
        
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size
        }

    @staticmethod
    def get_execution(
        db: Session,
        warehouse_id: int,
        session_id: str
    ) -> DiscoverySession | None:
        """
        Retrieve a single discovery session with its agent executions
        for a given warehouse.
        """
        from sqlalchemy.orm import selectinload

        return (
            db.query(DiscoverySession)
            .options(selectinload(DiscoverySession.agent_executions))
            .filter(
                DiscoverySession.warehouse_id == warehouse_id,
                DiscoverySession.session_id == session_id
            )
            .first()
        )
