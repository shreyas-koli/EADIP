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
from app.schemas.execution import DiscoveryHistoryPaginatedResponse, DiscoverySessionResponse

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
from app.schemas.explorer import SchemaResponse, TableResponse, ColumnResponse, RowDataResponse, QueryRequest, QueryResponse
from app.warehouse.explorer import ExplorerService, DEFAULT_ROW_LIMIT, MAX_ROW_LIMIT
from app.warehouse.sql_validator import SQLValidationError, validate_sql
from app.schemas.assistant import AssistantRequest, AssistantResponse, ProvidersResponse
from app.services.assistant_service import process_assistant_chat
from app.services.provider_availability import get_provider_availability

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
def create(warehouse_data: WarehouseCreate, db: DBSession, token: str = Depends(oauth2_scheme)):
    """
    Register a new data-warehouse connection.

    - Validates the payload via ``WarehouseCreate``.
    - Delegates to ``create_warehouse()`` in the service layer.
    - Returns **201** with the created warehouse on success.
    - Returns **400** if the name is already taken.
    """
    user = get_current_user(db, token)
    if user is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        warehouse = create_warehouse(db, warehouse_data, user)
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
def list_warehouses(db: DBSession, token: str = Depends(oauth2_scheme)):
    """
    Return every active warehouse connection.
    """
    user = get_current_user(db, token)
    if user is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return get_all_warehouses(db, user)


# ── GET /{id} ────────────────────────────────────────────────────


@router.get(
    "/{warehouse_id}",
    response_model=WarehouseResponse,
    summary="Get warehouse by ID",
)
def get_warehouse(warehouse_id: int, db: DBSession, token: str = Depends(oauth2_scheme)):
    """
    Return a single warehouse by its primary key.

    Returns **404** if the warehouse does not exist.
    """
    user = get_current_user(db, token)
    if user is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    warehouse = get_warehouse_by_id(db, warehouse_id, user)

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
def update(warehouse_id: int, warehouse_data: WarehouseUpdate, db: DBSession, token: str = Depends(oauth2_scheme)):
    """
    Partially update an existing warehouse connection.

    Only the supplied fields are modified; all others remain
    unchanged.  Returns **404** if the warehouse does not exist.
    """
    user = get_current_user(db, token)
    if user is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    warehouse = update_warehouse(db, warehouse_id, warehouse_data, user)

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
def delete(warehouse_id: int, db: DBSession, token: str = Depends(oauth2_scheme)):
    """
    Deactivate a warehouse (soft-delete via ``is_active = False``).

    Returns **404** if the warehouse does not exist.
    """
    user = get_current_user(db, token)
    if user is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    warehouse = delete_warehouse(db, warehouse_id, user)

    if warehouse is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse with id {warehouse_id} not found.",
        )

    return warehouse


# ── POST /{id}/test ──────────────────────────────────────────────


@router.post(
    "/{warehouse_id}/test",
    summary="Test warehouse connectivity",
)
def test_connection(warehouse_id: int, db: DBSession, token: str = Depends(oauth2_scheme)):
    """
    Execute a lightweight ``SELECT 1`` against the warehouse to
    verify that the connection parameters are valid and the
    database is reachable.

    Returns **404** if the warehouse does not exist.
    """
    user = get_current_user(db, token)
    if user is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    warehouse = get_warehouse_by_id(db, warehouse_id, user)

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
        
    warehouse = get_warehouse_by_id(db, warehouse_id, user)
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
        
    warehouse = get_warehouse_by_id(db, warehouse_id, user)
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

# ── GET /{id}/explorer/schemas ───────────────────────────────────


@router.get(
    "/{warehouse_id}/explorer/schemas",
    response_model=list[SchemaResponse],
    summary="Get database schemas for a warehouse",
)
def get_explorer_schemas(warehouse_id: int, db: DBSession, token: str = Depends(oauth2_scheme)):
    """
    Return all non-system schemas in the warehouse database.
    """
    user = get_current_user(db, token)
    if user is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    warehouse = get_warehouse_by_id(db, warehouse_id, user)
    if warehouse is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse with id {warehouse_id} not found.",
        )
        
    try:
        engine = WarehouseConnector.connect(warehouse)
        schemas = ExplorerService.get_schemas(engine)
        engine.dispose()
        return schemas
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch schemas: {str(e)}",
        )


# ── GET /{id}/explorer/schemas/{schema_name}/tables ──────────────


@router.get(
    "/{warehouse_id}/explorer/schemas/{schema_name}/tables",
    response_model=list[TableResponse],
    summary="Get tables in a schema",
)
def get_explorer_tables(warehouse_id: int, schema_name: str, db: DBSession, token: str = Depends(oauth2_scheme)):
    """
    Return all tables within a specific schema, including estimated row counts.
    """
    user = get_current_user(db, token)
    if user is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    warehouse = get_warehouse_by_id(db, warehouse_id, user)
    if warehouse is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse with id {warehouse_id} not found.",
        )
        
    try:
        engine = WarehouseConnector.connect(warehouse)
        tables = ExplorerService.get_tables(engine, schema_name)
        engine.dispose()
        return tables
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tables: {str(e)}",
        )


# ── GET /{id}/explorer/schemas/{schema_name}/tables/{table_name}/columns 


@router.get(
    "/{warehouse_id}/explorer/schemas/{schema_name}/tables/{table_name}/columns",
    response_model=list[ColumnResponse],
    summary="Get columns in a table",
)
def get_explorer_columns(warehouse_id: int, schema_name: str, table_name: str, db: DBSession, token: str = Depends(oauth2_scheme)):
    """
    Return all columns and metadata for a specific table.
    """
    user = get_current_user(db, token)
    if user is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    warehouse = get_warehouse_by_id(db, warehouse_id, user)
    if warehouse is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse with id {warehouse_id} not found.",
        )
        
    try:
        engine = WarehouseConnector.connect(warehouse)
        columns = ExplorerService.get_columns(engine, schema_name, table_name)
        engine.dispose()
        
        if not columns:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Table {table_name} not found in schema {schema_name}.",
            )
            
        return columns
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch columns: {str(e)}",
        )


# ── GET /{id}/explorer/schemas/{schema_name}/tables/{table_name}/rows ──


@router.get(
    "/{warehouse_id}/explorer/schemas/{schema_name}/tables/{table_name}/rows",
    response_model=RowDataResponse,
    summary="Get paginated row data from a table",
)
def get_explorer_rows(
    warehouse_id: int,
    schema_name: str,
    table_name: str,
    db: DBSession,
    token: str = Depends(oauth2_scheme),
    limit: int = DEFAULT_ROW_LIMIT,
    offset: int = 0,
):
    """
    Return a paginated page of rows from the specified table.

    - limit is clamped server-side to MAX_ROW_LIMIT (100).
    - offset must be >= 0.
    - Schema and table names are double-quoted to prevent SQL injection.
    - A 30-second statement timeout is applied per query.
    - No credentials are included in the response.
    """
    user = get_current_user(db, token)
    if user is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    warehouse = get_warehouse_by_id(db, warehouse_id, user)
    if warehouse is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse with id {warehouse_id} not found.",
        )

    # Validate limit/offset
    if limit < 1 or limit > MAX_ROW_LIMIT:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"limit must be between 1 and {MAX_ROW_LIMIT}.",
        )
    if offset < 0:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="offset must be >= 0.",
        )

    try:
        engine = WarehouseConnector.connect(warehouse)
        data = ExplorerService.get_rows(engine, schema_name, table_name, limit=limit, offset=offset)
        engine.dispose()
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch rows: {str(e)}",
        )


# ── POST /{id}/explorer/query ─────────────────────────────────────────────────


@router.post(
    "/{warehouse_id}/explorer/query",
    response_model=QueryResponse,
    summary="Execute a read-only SQL query against a warehouse",
)
def execute_explorer_query(
    warehouse_id: int,
    body: QueryRequest,
    db: DBSession,
    token: str = Depends(oauth2_scheme),
):
    """
    Execute a single, read-only SQL statement against the specified warehouse.

    Security:
    - Requires valid JWT token (authenticated user).
    - Warehouse must be owned by the authenticated user.
    - SQL is validated by sql_validator (blocks INSERT/UPDATE/DELETE/DDL/TCL).
    - Query runs inside a READ ONLY PostgreSQL transaction (defence-in-depth).
    - A 30-second server-side statement timeout is applied.
    - Results are capped at 1,000 rows; 'truncated' indicates overflow.
    - No credentials are included in any response.
    """
    user = get_current_user(db, token)
    if user is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    warehouse = get_warehouse_by_id(db, warehouse_id, user)
    if warehouse is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse with id {warehouse_id} not found.",
        )

    # ── SQL Validation (Layer 1) ────────────────────────────────────────────
    try:
        validated_sql = validate_sql(body.sql)
    except SQLValidationError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # ── Execute (Layers 2-4 inside execute_query) ───────────────────────────
    try:
        engine = WarehouseConnector.connect(warehouse)
        result = ExplorerService.execute_query(engine, validated_sql)
        engine.dispose()
        return result
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        # Surface useful PostgreSQL errors without leaking credentials
        if "statement timeout" in error_msg.lower() or "canceling statement" in error_msg.lower():
            raise HTTPException(
                status_code=http_status.HTTP_408_REQUEST_TIMEOUT,
                detail="Query exceeded the 30-second time limit and was cancelled.",
            )
        if "read-only transaction" in error_msg.lower():
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Only read-only SQL queries are allowed.",
            )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {error_msg}",
        )


import logging
logger = logging.getLogger(__name__)

# ── GET /{id}/explorer/assistant/providers ────────────────────────────────────

@router.get(
    "/{warehouse_id}/explorer/assistant/providers",
    response_model=ProvidersResponse,
    summary="Get AI provider availability status",
)
def get_assistant_providers(
    warehouse_id: int,
    db: DBSession,
    token: str = Depends(oauth2_scheme),
):
    """
    Return the availability status of all configured AI providers.

    Requires authentication and warehouse ownership validation.
    Never exposes API keys, secrets, or credentials in the response.
    """
    user = get_current_user(db, token)
    if user is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    warehouse = get_warehouse_by_id(db, warehouse_id, user)
    if warehouse is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse with id {warehouse_id} not found.",
        )

    try:
        return get_provider_availability()
    except Exception as e:
        logger.error(f"Provider availability check failed: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve provider status.",
        )


# ── POST /{id}/explorer/assistant/chat ────────────────────────────────────────

@router.post(
    "/{warehouse_id}/explorer/assistant/chat",
    response_model=AssistantResponse,
    summary="Chat with the AI assistant about the warehouse",
)
def assistant_chat(
    warehouse_id: int,
    body: AssistantRequest,
    db: DBSession,
    token: str = Depends(oauth2_scheme),
):
    """
    Interact with the Warehouse AI Assistant.
    """
    user = get_current_user(db, token)
    if user is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    warehouse = get_warehouse_by_id(db, warehouse_id, user)
    if warehouse is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse with id {warehouse_id} not found.",
        )

    try:
        engine = WarehouseConnector.connect(warehouse)
        result = process_assistant_chat(engine, body)
        engine.dispose()
        return result
    except HTTPException:
        raise
    except Exception as e:
        # Issue 3: Prevent Raw Exception Leak
        logger.error(f"AI Assistant Error for warehouse {warehouse_id}: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process AI request.",
        )
