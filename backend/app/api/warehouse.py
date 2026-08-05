"""
Warehouse management API router.

Thin HTTP layer that delegates all business logic to the warehouse
service, connector, and orchestrator.  Responsible only for
request / response mapping, status codes, and error translation.
"""

from fastapi import APIRouter, HTTPException, status

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
    status_code=status.HTTP_201_CREATED,
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
            status_code=status.HTTP_400_BAD_REQUEST,
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
            status_code=status.HTTP_404_NOT_FOUND,
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
            status_code=status.HTTP_404_NOT_FOUND,
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
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse with id {warehouse_id} not found.",
        )

    connector = WarehouseConnector()
    is_connected = connector.test_connection(warehouse)

    return {
        "warehouse_id": warehouse.id,
        "warehouse_name": warehouse.name,
        "connected": is_connected,
    }


# ── POST /{id}/discover ─────────────────────────────────────────


@router.post(
    "/{warehouse_id}/discover",
    summary="Discover warehouse metadata",
)
def discover_metadata(warehouse_id: int, db: DBSession):
    """
    Trigger metadata discovery for the specified warehouse.

    Delegates to the ``AgentOrchestrator`` which orchestrates
    agent tasks in parallel based on their dependency graph.

    Returns **404** if the warehouse does not exist.
    """
    warehouse = get_warehouse_by_id(db, warehouse_id)

    if warehouse is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse with id {warehouse_id} not found.",
        )

    # ── Orchestration setup ────────────────────────────────────
    context = SharedContext()
    context.set_current_warehouse({
        "id": warehouse.id,
        "name": warehouse.name,
        "db_type": warehouse.db_type,
        "host": warehouse.host,
        "port": warehouse.port,
        "database_name": warehouse.database_name,
    })

    # ── Build execution plan and run ───────────────────────────
    factory = TaskFactory()
    tasks = factory.build_metadata_discovery(warehouse)

    orchestrator = AgentOrchestrator()
    try:
        summary = orchestrator.execute_parallel(tasks)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    # ── Read results from Shared Memory Bus ────────────────────
    agent_results = context.get_all_agent_results()

    return {
        **agent_results,
        "execution": summary,
    }

