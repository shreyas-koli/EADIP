import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.database.base import Base
from app.database.session import get_db
from app.auth.jwt import create_access_token
from app.models.user import User
from app.models.warehouse import Warehouse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()



@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def db_session(client):
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    
    # Create test user
    test_user = User(
        email="test_explorer@example.com",
        hashed_password="fakehash",
        full_name="Explorer User"
    )
    session.add(test_user)
    session.commit()
    
    # Create test warehouse
    test_warehouse = Warehouse(
        name="Test WH",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="test_db",
        username="test_user",
        encrypted_password=b"faketoken",
        owner_id=test_user.id
    )
    session.add(test_warehouse)
    session.commit()
    
    yield session
    
    session.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def auth_headers(db_session):
    user = db_session.query(User).filter_by(email="test_explorer@example.com").first()
    token = create_access_token(data={"sub": user.email})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def warehouse_id(db_session):
    warehouse = db_session.query(Warehouse).first()
    return warehouse.id

@patch('app.api.warehouse.WarehouseConnector.connect')
@patch('app.api.warehouse.ExplorerService.get_schemas')
def test_get_explorer_schemas(mock_get_schemas, mock_connect, client, auth_headers, warehouse_id):
    mock_connect.return_value = MagicMock()
    mock_get_schemas.return_value = [{"name": "public"}, {"name": "eadip"}]
    
    response = client.get(f"/warehouses/{warehouse_id}/explorer/schemas", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[0]["name"] == "public"

@patch('app.api.warehouse.WarehouseConnector.connect')
@patch('app.api.warehouse.ExplorerService.get_tables')
def test_get_explorer_tables(mock_get_tables, mock_connect, client, auth_headers, warehouse_id):
    mock_connect.return_value = MagicMock()
    mock_get_tables.return_value = [
        {"name": "users", "schema_name": "public", "estimated_row_count": 100}
    ]
    
    response = client.get(f"/warehouses/{warehouse_id}/explorer/schemas/public/tables", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "users"

@patch('app.api.warehouse.WarehouseConnector.connect')
@patch('app.api.warehouse.ExplorerService.get_columns')
def test_get_explorer_columns(mock_get_columns, mock_connect, client, auth_headers, warehouse_id):
    mock_connect.return_value = MagicMock()
    mock_get_columns.return_value = [
        {"name": "id", "data_type": "INTEGER", "nullable": False, "position": 1, "is_primary_key": True, "foreign_key": None}
    ]
    
    response = client.get(f"/warehouses/{warehouse_id}/explorer/schemas/public/tables/users/columns", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "id"

def test_get_explorer_unauthorized(client, warehouse_id):
    response = client.get(f"/warehouses/{warehouse_id}/explorer/schemas")
    assert response.status_code == 401

# ─── Row Endpoint Tests ──────────────────────────────────────────────────────

_DEFAULT_ROW_RESPONSE = {
    "columns": ["id", "name", "email"],
    "rows": [[1, "Alice", "alice@example.com"], [2, "Bob", None]],
    "limit": 50,
    "offset": 0,
    "returned_rows": 2,
    "total_rows": 1000,
    "is_estimated_total": True,
}

@patch('app.api.warehouse.WarehouseConnector.connect')
@patch('app.api.warehouse.ExplorerService.get_rows')
def test_get_rows_success(mock_get_rows, mock_connect, client, auth_headers, warehouse_id):
    """Authenticated user can retrieve rows from their own warehouse."""
    mock_connect.return_value = MagicMock()
    mock_get_rows.return_value = _DEFAULT_ROW_RESPONSE

    response = client.get(
        f"/warehouses/{warehouse_id}/explorer/schemas/public/tables/users/rows",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["columns"] == ["id", "name", "email"]
    assert len(data["rows"]) == 2
    assert data["returned_rows"] == 2
    assert data["total_rows"] == 1000
    assert data["is_estimated_total"] is True

@patch('app.api.warehouse.WarehouseConnector.connect')
@patch('app.api.warehouse.ExplorerService.get_rows')
def test_get_rows_null_values(mock_get_rows, mock_connect, client, auth_headers, warehouse_id):
    """NULL values are serialised as JSON null, not the string 'null'."""
    mock_connect.return_value = MagicMock()
    mock_get_rows.return_value = {**_DEFAULT_ROW_RESPONSE, "rows": [[1, None, None]]}

    response = client.get(
        f"/warehouses/{warehouse_id}/explorer/schemas/public/tables/users/rows",
        headers=auth_headers,
    )
    assert response.status_code == 200
    row = response.json()["rows"][0]
    assert row[1] is None   # JSON null, not string
    assert row[2] is None

def test_get_rows_unauthorized(client, warehouse_id):
    """Unauthenticated request returns 401."""
    response = client.get(
        f"/warehouses/{warehouse_id}/explorer/schemas/public/tables/users/rows"
    )
    assert response.status_code == 401

def test_get_rows_wrong_warehouse(client, db_session, auth_headers):
    """User cannot retrieve rows from a non-existent or unowned warehouse."""
    response = client.get(
        "/warehouses/99999/explorer/schemas/public/tables/users/rows",
        headers=auth_headers,
    )
    assert response.status_code == 404

@patch('app.api.warehouse.WarehouseConnector.connect')
@patch('app.api.warehouse.ExplorerService.get_rows')
def test_get_rows_pagination_offset(mock_get_rows, mock_connect, client, auth_headers, warehouse_id):
    """Offset is forwarded to ExplorerService."""
    mock_connect.return_value = MagicMock()
    mock_get_rows.return_value = {**_DEFAULT_ROW_RESPONSE, "offset": 50}

    response = client.get(
        f"/warehouses/{warehouse_id}/explorer/schemas/public/tables/users/rows?limit=50&offset=50",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["offset"] == 50
    # Verify ExplorerService.get_rows was called with correct limit/offset
    call_kwargs = mock_get_rows.call_args
    assert call_kwargs.kwargs.get("limit") == 50 or call_kwargs.args[3] == 50
    assert call_kwargs.kwargs.get("offset") == 50 or call_kwargs.args[4] == 50

def test_get_rows_limit_too_large(client, auth_headers, warehouse_id):
    """limit > 100 returns 422."""
    response = client.get(
        f"/warehouses/{warehouse_id}/explorer/schemas/public/tables/users/rows?limit=999",
        headers=auth_headers,
    )
    assert response.status_code == 422

def test_get_rows_negative_offset(client, auth_headers, warehouse_id):
    """Negative offset returns 422."""
    response = client.get(
        f"/warehouses/{warehouse_id}/explorer/schemas/public/tables/users/rows?offset=-1",
        headers=auth_headers,
    )
    assert response.status_code == 422

@patch('app.api.warehouse.WarehouseConnector.connect')
@patch('app.api.warehouse.ExplorerService.get_rows')
def test_get_rows_empty_table(mock_get_rows, mock_connect, client, auth_headers, warehouse_id):
    """Empty table returns 200 with empty rows list."""
    mock_connect.return_value = MagicMock()
    mock_get_rows.return_value = {
        "columns": ["id", "name"],
        "rows": [],
        "limit": 50,
        "offset": 0,
        "returned_rows": 0,
        "total_rows": 0,
        "is_estimated_total": True,
    }

    response = client.get(
        f"/warehouses/{warehouse_id}/explorer/schemas/public/tables/empty_table/rows",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["rows"] == []
    assert data["returned_rows"] == 0
    assert data["total_rows"] == 0

# ─── _serialize_value unit tests ──────────────────────────────────────────────

from app.warehouse.explorer import _serialize_value
import datetime, decimal, uuid

def test_serialize_none():
    assert _serialize_value(None) is None

def test_serialize_bool():
    assert _serialize_value(True) is True
    assert _serialize_value(False) is False

def test_serialize_int():
    assert _serialize_value(42) == 42

def test_serialize_decimal():
    result = _serialize_value(decimal.Decimal("3.14"))
    assert isinstance(result, float)
    assert abs(result - 3.14) < 0.001

def test_serialize_datetime():
    dt = datetime.datetime(2024, 1, 15, 10, 30, 0)
    result = _serialize_value(dt)
    assert result == "2024-01-15T10:30:00"

def test_serialize_uuid():
    u = uuid.UUID("12345678-1234-5678-1234-567812345678")
    assert _serialize_value(u) == "12345678-1234-5678-1234-567812345678"

def test_serialize_large_string_truncated():
    big = "x" * 10000
    result = _serialize_value(big)
    assert "truncated" in result

# ─── _safe_identifier unit tests ────────────────────────────────────────────

from app.warehouse.explorer import _safe_identifier

def test_safe_identifier_normal():
    assert _safe_identifier("public") == '"public"'

def test_safe_identifier_with_quotes():
    """A name containing double-quotes is escaped correctly."""
    assert _safe_identifier('schema"name') == '"schema""name"'

def test_safe_identifier_injection_attempt():
    """Classic injection attempt is neutralised."""
    attack = 'public"; DROP TABLE users; --'
    result = _safe_identifier(attack)
    assert 'DROP' not in result or result.startswith('"')
    assert result.startswith('"') and result.endswith('"')


# ═══════════════════════════════════════════════════════════════════════════════
# ─── Phase 4: SQL Console Tests ─────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

from app.warehouse.sql_validator import validate_sql, SQLValidationError

# ─── validate_sql unit tests ─────────────────────────────────────────────────

def test_validate_select_allowed():
    """Simple SELECT is allowed."""
    result = validate_sql("SELECT 1")
    assert result == "SELECT 1"

def test_validate_select_trailing_semicolon():
    """Trailing semicolons on a single statement are allowed."""
    result = validate_sql("SELECT * FROM users;")
    assert result == "SELECT * FROM users"

def test_validate_cte_allowed():
    """CTE (WITH) is allowed."""
    result = validate_sql("WITH cte AS (SELECT 1) SELECT * FROM cte")
    assert "WITH" in result.upper()

def test_validate_explain_allowed():
    """EXPLAIN is allowed."""
    result = validate_sql("EXPLAIN SELECT * FROM users")
    assert result == "EXPLAIN SELECT * FROM users"

def test_validate_explain_analyze_allowed():
    """EXPLAIN ANALYZE is allowed."""
    result = validate_sql("EXPLAIN ANALYZE SELECT * FROM users")
    assert result == "EXPLAIN ANALYZE SELECT * FROM users"

def test_validate_explain_options_allowed():
    """EXPLAIN with PostgreSQL options is allowed."""
    result = validate_sql("EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM users")
    assert result == "EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM users"

def test_validate_explain_analyze_update_blocked():
    """EXPLAIN ANALYZE containing an UPDATE is blocked by the keyword scan."""
    with pytest.raises(SQLValidationError, match="UPDATE"):
        validate_sql("EXPLAIN ANALYZE UPDATE users SET name = 'x'")

def test_validate_explain_analyze_insert_blocked():
    """EXPLAIN ANALYZE containing an INSERT is blocked by the keyword scan."""
    with pytest.raises(SQLValidationError, match="INSERT"):
        validate_sql("EXPLAIN ANALYZE INSERT INTO users (name) VALUES ('x')")

def test_validate_explain_analyze_delete_blocked():
    """EXPLAIN ANALYZE containing a DELETE is blocked by the keyword scan."""
    with pytest.raises(SQLValidationError, match="DELETE"):
        validate_sql("EXPLAIN ANALYZE DELETE FROM users")

def test_validate_explain_analyze_drop_blocked():
    """EXPLAIN ANALYZE containing a DROP is blocked by the keyword scan."""
    with pytest.raises(SQLValidationError, match="DROP"):
        validate_sql("EXPLAIN ANALYZE DROP TABLE users")

def test_validate_cte_update_blocked():
    """CTE containing an UPDATE is blocked by the keyword scan."""
    with pytest.raises(SQLValidationError, match="UPDATE"):
        validate_sql("WITH cte AS (UPDATE users SET name = 'x' RETURNING *) SELECT * FROM cte")

def test_validate_cte_delete_blocked():
    """CTE containing a DELETE is blocked by the keyword scan."""
    with pytest.raises(SQLValidationError, match="DELETE"):
        validate_sql("WITH cte AS (DELETE FROM users RETURNING *) SELECT * FROM cte")

def test_validate_arbitrary_unknown_blocked():
    """Arbitrary statements that evaluate to UNKNOWN but are not EXPLAIN are blocked."""
    with pytest.raises(SQLValidationError, match="UNKNOWN"):
        # We need something sqlparse treats as UNKNOWN and isn't caught by keyword lists.
        # "FOO BAR" usually falls into this.
        validate_sql("FOO BAR")
def test_validate_empty_raises():
    """Empty SQL raises SQLValidationError."""
    with pytest.raises(SQLValidationError):
        validate_sql("")

def test_validate_whitespace_only_raises():
    with pytest.raises(SQLValidationError):
        validate_sql("   ")

def test_validate_insert_blocked():
    """INSERT is blocked."""
    with pytest.raises(SQLValidationError, match="INSERT"):
        validate_sql("INSERT INTO users (name) VALUES ('x')")

def test_validate_update_blocked():
    """UPDATE is blocked."""
    with pytest.raises(SQLValidationError, match="UPDATE"):
        validate_sql("UPDATE users SET name='x'")

def test_validate_delete_blocked():
    """DELETE is blocked."""
    with pytest.raises(SQLValidationError, match="DELETE"):
        validate_sql("DELETE FROM users")

def test_validate_drop_blocked():
    """DROP is blocked."""
    with pytest.raises(SQLValidationError, match="DROP"):
        validate_sql("DROP TABLE users")

def test_validate_alter_blocked():
    """ALTER is blocked."""
    with pytest.raises(SQLValidationError, match="ALTER"):
        validate_sql("ALTER TABLE users ADD COLUMN x TEXT")

def test_validate_create_blocked():
    """CREATE is blocked."""
    with pytest.raises(SQLValidationError, match="CREATE"):
        validate_sql("CREATE TABLE foo (id INT)")

def test_validate_truncate_blocked():
    """TRUNCATE is blocked."""
    with pytest.raises(SQLValidationError, match="TRUNCATE"):
        validate_sql("TRUNCATE TABLE users")

def test_validate_grant_blocked():
    """GRANT is blocked."""
    with pytest.raises(SQLValidationError, match="GRANT"):
        validate_sql("GRANT SELECT ON users TO public")

def test_validate_revoke_blocked():
    """REVOKE is blocked."""
    with pytest.raises(SQLValidationError, match="REVOKE"):
        validate_sql("REVOKE SELECT ON users FROM public")

def test_validate_begin_blocked():
    """BEGIN transaction control is blocked."""
    with pytest.raises(SQLValidationError):
        validate_sql("BEGIN")

def test_validate_multi_statement_blocked():
    """Multiple statements separated by semicolon are rejected."""
    with pytest.raises(SQLValidationError, match="single SQL statement"):
        validate_sql("SELECT 1; DROP TABLE users")

def test_validate_multi_statement_with_comment_blocked():
    """Multi-statement with embedded comment is still blocked."""
    with pytest.raises(SQLValidationError, match="single SQL statement"):
        validate_sql("SELECT 1; -- comment\nDROP TABLE users")


# ─── /query endpoint tests ────────────────────────────────────────────────────

_DEFAULT_QUERY_RESPONSE = {
    "columns": ["id", "name"],
    "rows": [[1, "Alice"], [2, "Bob"]],
    "returned_rows": 2,
    "execution_time_ms": 12.5,
    "truncated": False,
}

@patch('app.api.warehouse.WarehouseConnector.connect')
@patch('app.api.warehouse.ExplorerService.execute_query')
def test_query_success(mock_execute, mock_connect, client, auth_headers, warehouse_id):
    """Authenticated user can run a SELECT against their own warehouse."""
    mock_connect.return_value = MagicMock()
    mock_execute.return_value = _DEFAULT_QUERY_RESPONSE

    response = client.post(
        f"/warehouses/{warehouse_id}/explorer/query",
        json={"sql": "SELECT id, name FROM users"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["columns"] == ["id", "name"]
    assert len(data["rows"]) == 2
    assert data["truncated"] is False
    assert "execution_time_ms" in data

def test_query_unauthenticated(client, warehouse_id):
    """Unauthenticated request returns 401."""
    response = client.post(
        f"/warehouses/{warehouse_id}/explorer/query",
        json={"sql": "SELECT 1"},
    )
    assert response.status_code == 401

def test_query_wrong_warehouse(client, auth_headers):
    """User cannot query a warehouse they do not own."""
    response = client.post(
        "/warehouses/99999/explorer/query",
        json={"sql": "SELECT 1"},
        headers=auth_headers,
    )
    assert response.status_code == 404

def test_query_blocked_insert(client, auth_headers, warehouse_id):
    """INSERT is rejected by the validator before reaching the DB."""
    response = client.post(
        f"/warehouses/{warehouse_id}/explorer/query",
        json={"sql": "INSERT INTO users (name) VALUES ('x')"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "INSERT" in response.json()["detail"] or "read-only" in response.json()["detail"].lower()

def test_query_blocked_update(client, auth_headers, warehouse_id):
    response = client.post(
        f"/warehouses/{warehouse_id}/explorer/query",
        json={"sql": "UPDATE users SET name='x'"},
        headers=auth_headers,
    )
    assert response.status_code == 400

def test_query_blocked_delete(client, auth_headers, warehouse_id):
    response = client.post(
        f"/warehouses/{warehouse_id}/explorer/query",
        json={"sql": "DELETE FROM users"},
        headers=auth_headers,
    )
    assert response.status_code == 400

def test_query_blocked_drop(client, auth_headers, warehouse_id):
    response = client.post(
        f"/warehouses/{warehouse_id}/explorer/query",
        json={"sql": "DROP TABLE users"},
        headers=auth_headers,
    )
    assert response.status_code == 400

def test_query_blocked_alter(client, auth_headers, warehouse_id):
    response = client.post(
        f"/warehouses/{warehouse_id}/explorer/query",
        json={"sql": "ALTER TABLE users ADD COLUMN x TEXT"},
        headers=auth_headers,
    )
    assert response.status_code == 400

def test_query_blocked_create(client, auth_headers, warehouse_id):
    response = client.post(
        f"/warehouses/{warehouse_id}/explorer/query",
        json={"sql": "CREATE TABLE foo (id INT)"},
        headers=auth_headers,
    )
    assert response.status_code == 400

def test_query_blocked_truncate(client, auth_headers, warehouse_id):
    response = client.post(
        f"/warehouses/{warehouse_id}/explorer/query",
        json={"sql": "TRUNCATE TABLE users"},
        headers=auth_headers,
    )
    assert response.status_code == 400

def test_query_blocked_grant(client, auth_headers, warehouse_id):
    response = client.post(
        f"/warehouses/{warehouse_id}/explorer/query",
        json={"sql": "GRANT SELECT ON users TO public"},
        headers=auth_headers,
    )
    assert response.status_code == 400

def test_query_blocked_revoke(client, auth_headers, warehouse_id):
    response = client.post(
        f"/warehouses/{warehouse_id}/explorer/query",
        json={"sql": "REVOKE SELECT ON users FROM public"},
        headers=auth_headers,
    )
    assert response.status_code == 400

def test_query_multi_statement_blocked(client, auth_headers, warehouse_id):
    """Multi-statement queries are rejected."""
    response = client.post(
        f"/warehouses/{warehouse_id}/explorer/query",
        json={"sql": "SELECT 1; DROP TABLE users"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "single SQL statement" in response.json()["detail"]

def test_query_empty_sql_rejected(client, auth_headers, warehouse_id):
    """Empty SQL string is rejected."""
    response = client.post(
        f"/warehouses/{warehouse_id}/explorer/query",
        json={"sql": ""},
        headers=auth_headers,
    )
    # Either 400 (validator) or 422 (Pydantic min_length)
    assert response.status_code in (400, 422)

@patch('app.api.warehouse.WarehouseConnector.connect')
@patch('app.api.warehouse.ExplorerService.execute_query')
def test_query_null_values_in_result(mock_execute, mock_connect, client, auth_headers, warehouse_id):
    """NULL values are returned as JSON null."""
    mock_connect.return_value = MagicMock()
    mock_execute.return_value = {
        **_DEFAULT_QUERY_RESPONSE,
        "rows": [[1, None]],
        "returned_rows": 1,
    }
    response = client.post(
        f"/warehouses/{warehouse_id}/explorer/query",
        json={"sql": "SELECT id, name FROM users"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["rows"][0][1] is None

@patch('app.api.warehouse.WarehouseConnector.connect')
@patch('app.api.warehouse.ExplorerService.execute_query')
def test_query_truncated_flag(mock_execute, mock_connect, client, auth_headers, warehouse_id):
    """Truncated flag is returned when result cap is hit."""
    mock_connect.return_value = MagicMock()
    mock_execute.return_value = {**_DEFAULT_QUERY_RESPONSE, "truncated": True, "returned_rows": 1000}
    response = client.post(
        f"/warehouses/{warehouse_id}/explorer/query",
        json={"sql": "SELECT * FROM big_table"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["truncated"] is True
    assert response.json()["returned_rows"] == 1000

@patch('app.api.warehouse.WarehouseConnector.connect')
@patch('app.api.warehouse.ExplorerService.execute_query')
def test_query_no_credentials_in_response(mock_execute, mock_connect, client, auth_headers, warehouse_id):
    """Response never contains password, connection string, or encryption key."""
    mock_connect.return_value = MagicMock()
    mock_execute.return_value = _DEFAULT_QUERY_RESPONSE
    response = client.post(
        f"/warehouses/{warehouse_id}/explorer/query",
        json={"sql": "SELECT 1"},
        headers=auth_headers,
    )
    text = response.text.lower()
    assert "password" not in text
    assert "encrypted_password" not in text
    assert "faketoken" not in text
