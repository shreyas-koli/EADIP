from fastapi import APIRouter, HTTPException, status, Depends
from app.database.session import DBSession
from app.schemas.execution import DiscoveryExecutionRequest, DiscoverySessionResponse
from app.orchestrator.agent_orchestrator import AgentOrchestrator
from app.orchestrator.task_factory import TaskFactory
from app.context.shared_context import SharedContext
from app.services.execution_service import ExecutionService
from app.warehouse.service import get_warehouse_by_id
from app.api.auth import oauth2_scheme
from app.auth.service import get_current_user
import logging
from queue import Queue
import threading
import json
from datetime import datetime, timezone
from fastapi.responses import StreamingResponse
from fastapi.encoders import jsonable_encoder

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/discovery",
    tags=["Discovery"],
)

@router.post(
    "/execute",
    response_model=DiscoverySessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute a discovery session",
)
def execute_discovery(
    request: DiscoveryExecutionRequest, 
    db: DBSession, 
    stream: bool = False,
    token: str = Depends(oauth2_scheme)
):
    """
    Trigger collaborative multi-agent analysis for a specified warehouse.
    Persists the execution summary to PostgreSQL and returns the session details.
    """
    # 1. Authenticate
    user = get_current_user(db, token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Validate warehouse exists
    warehouse = get_warehouse_by_id(db, request.warehouse_id, user)
    if warehouse is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse with id {request.warehouse_id} not found.",
        )
    
    # 4. Validate warehouse is active
    if not getattr(warehouse, "is_active", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot execute discovery on an inactive warehouse.",
        )

    # 5. Determine context strategy
    if not stream:
        context = SharedContext()
    else:
        q: Queue = Queue()
        def event_callback(event_data: dict):
            q.put(event_data)
        context = SharedContext(event_callback=event_callback)
        
    context.set_current_warehouse({
        "id": warehouse.id,
        "name": warehouse.name,
        "db_type": warehouse.db_type,
        "host": warehouse.host,
        "port": warehouse.port,
        "database_name": warehouse.database_name,
    })

    factory = TaskFactory()
    tasks = factory.build_metadata_discovery(warehouse, context)
    orchestrator = AgentOrchestrator(context=context)
    
    logger.info(f"Starting discovery session for warehouse '{warehouse.name}' ({warehouse.id}) with {len(tasks)} tasks.")
    
    if not stream:
        try:
            summary = orchestrator.execute_parallel(tasks)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal orchestration error",
            )

        try:
            logger.info(f"Discovery execution completed. Persisting summary for warehouse '{warehouse.name}' ({warehouse.id}).")
            session_obj = ExecutionService.persist_execution(db, warehouse.id, summary)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistence failed",
            )
        return session_obj

    # Stream execution
    def run_orchestrator():
        try:
            # Tell client we started
            q.put({
                "event": "discovery_started", 
                "warehouse_id": warehouse.id, 
                "tasks": [t.name for t in tasks],
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            # Execute
            summary = orchestrator.execute_parallel(tasks)
            
            # Persist (requires a new DB session since this is a new thread)
            from app.database.session import SessionLocal
            with SessionLocal() as thread_db:
                session_obj = ExecutionService.persist_execution(thread_db, warehouse.id, summary)
                # We need to serialize the pydantic model to jsonable dict
                response_obj = DiscoverySessionResponse.model_validate(session_obj)
                # Include monitoring result for frontend display
                monitoring_result = summary.get("agent_results", {}).get("monitoring")
                q.put({
                    "event": "discovery_completed",
                    "session": response_obj.model_dump(mode="json"),
                    "monitoring": monitoring_result,
                })
                
        except Exception as exc:
            logger.error(f"Background execution failed: {exc}")
            q.put({"event": "error", "message": str(exc)})
        finally:
            q.put(None)  # Sentinel to end stream

    threading.Thread(target=run_orchestrator, daemon=True).start()

    def generate_events():
        while True:
            event = q.get()
            if event is None:
                break
            yield f"data: {json.dumps(jsonable_encoder(event))}\n\n"

    return StreamingResponse(generate_events(), media_type="text/event-stream")
