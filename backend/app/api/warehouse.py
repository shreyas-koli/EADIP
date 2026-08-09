"""
Warehouse management API router.

Thin HTTP layer that delegates all business logic to the warehouse
service, connector, and orchestrator.  Responsible only for
request / response mapping, status codes, and error translation.
"""

from typing import Literal
from fastapi import APIRouter, HTTPException, status as http_status, Depends, Query
from app.api.auth import oauth2_scheme
from app.auth.service import get_current_user
from app.services.execution_service import ExecutionService
from app.schemas.execution import DiscoveryHistoryPaginatedResponse, DiscoveryHistoryResponse, DiscoverySessionResponse

from app.database.session import DBSession
from app.orchestrator.agent_orchestrator import AgentOrchestrator
from app.orchestrator.task_factory import TaskFactory
from app.context.shared_context import SharedContext
from app.schemas.warehouse import WarehouseCreate, WarehouseResponse, WarehouseUpdate
from app.warehouse.connector import WarehouseConnector
from app.warehouse.service import (
    create_warehouse,
    delete_warehouse,
    get_all_warehouses,
    get_warehouse_by_id,
    update_warehouse,
)

# ── Router ───────────────────────────────────────────────────────
router = APIRouter(
    prefix="/warehouses",
    tags=["Warehouses"],
)


# ── POST / ───────────────────────────────────────────────────────


@router.post(
    "/",
    response_model=WarehouseResponse,
    status_code=http_status.HTTP_201_CREATED,
    summary="Register a new warehouse",
)
def create(warehouse_data: WarehouseCreate, db: DBSession):
    """
    Register a new data-warehouse connection.

    - Validates the payload via ``WarehouseCreate``.
    - Delegates to ``create_warehouse()`` in the service layer.
    - Returns **201** with the created warehouse on success.
    - Returns **400** if the name is already taken.
    """
    try:
        warehouse = create_warehouse(db, warehouse_data)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return warehouse


# ── GET / ────────────────────────────────────────────────────────


@router.get(
    "/",
    response_model=list[WarehouseResponse],
    summary="List all active warehouses",
)
def list_warehouses(db: DBSession):
    """
    Return every active warehouse connection.
    """
    return get_all_warehouses(db)


# ── GET /{id} ────────────────────────────────────────────────────


@router.get(
    "/{warehouse_id}",
    response_model=WarehouseResponse,
    summary="Get warehouse by ID",
)
def get_warehouse(warehouse_id: int, db: DBSession):
    """
    Return a single warehouse by its primary key.

    Returns **404** if the warehouse does not exist.
    """
    warehouse = get_warehouse_by_id(db, warehouse_id)

    if warehouse is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse with id {warehouse_id} not found.",
        )

    return warehouse


# ── PUT /{id} ────────────────────────────────────────────────────


@router.put(
    "/{warehouse_id}",
    response_model=WarehouseResponse,
    summary="Update a warehouse",
)
def update(warehouse_id: int, warehouse_data: WarehouseUpdate, db: DBSession):
    """
    Partially update an existing warehouse connection.

    Only the supplied fields are modified; all others remain
    unchanged.  Returns **404** if the warehouse does not exist.
    """
    warehouse = update_warehouse(db, warehouse_id, warehouse_data)

    if warehouse is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse with id {warehouse_id} not found.",
        )

    return warehouse


# ── DELETE /{id} ─────────────────────────────────────────────────


@router.delete(
    "/{warehouse_id}",
    response_model=WarehouseResponse,
    summary="Soft-delete a warehouse",
)
def delete(warehouse_id: int, db: DBSession):
    """
    Deactivate a warehouse (soft-delete via ``is_active = False``).

    Returns **404** if the warehouse does not exist.
    """
    warehouse = delete_warehouse(db, warehouse_id)

    if warehouse is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse with id {warehouse_id} not found.",
        )

    return warehouse


# ── POST /{id}/test ──────────────────────────────────────────────


@router.post(
    "/{warehouse_id}/test",
    summary="Test warehouse connectivity",
)
def test_connection(warehouse_id: int, db: DBSession):
    """
    Execute a lightweight ``SELECT 1`` against the warehouse to
    verify that the connection parameters are valid and the
    database is reachable.

    Returns **404** if the warehouse does not exist.
    """
    warehouse = get_warehouse_by_id(db, warehouse_id)

    if warehouse is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse with id {warehouse_id} not found.",
        )

    connector = WarehouseConnector()
    is_connected = connector.test_connection(warehouse)

    return {
        "warehouse_id": warehouse.id,
        "warehouse_name": warehouse.name,
        "connected": is_connected,
    }

# ── GET /{id}/history ────────────────────────────────────────────


@router.get(
    "/{warehouse_id}/history",
    response_model=DiscoveryHistoryPaginatedResponse,
    summary="Get discovery history for a warehouse",
)
def get_warehouse_history(
    warehouse_id: int, 
    db: DBSession, 
    token: str = Depends(oauth2_scheme),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    status: Literal["COMPLETED", "FAILED"] | None = Query(None, description="Filter by status")
):
    """
    Return high-level discovery history for a warehouse.
    """
    user = get_current_user(db, token)
    if user is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    warehouse = get_warehouse_by_id(db, warehouse_id)
    if warehouse is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse with id {warehouse_id} not found.",
        )
        
    return ExecutionService.get_history(db, warehouse_id, page=page, page_size=page_size, status=status)


# ── GET /{id}/history/{session_id} ───────────────────────────────


@router.get(
    "/{warehouse_id}/history/{session_id}",
    response_model=DiscoverySessionResponse,
    summary="Get detailed discovery execution for a warehouse",
)
def get_warehouse_execution(warehouse_id: int, session_id: str, db: DBSession, token: str = Depends(oauth2_scheme)):
    """
    Return the complete execution detail for a single discovery session.
    """
    user = get_current_user(db, token)
    if user is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    warehouse = get_warehouse_by_id(db, warehouse_id)
    if warehouse is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse with id {warehouse_id} not found.",
        )
        
    execution = ExecutionService.get_execution(db, warehouse_id, session_id)
    if execution is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Execution session {session_id} not found for warehouse {warehouse_id}.",
        )
        
    return execution
