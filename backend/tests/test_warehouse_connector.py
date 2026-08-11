import pytest
from unittest.mock import patch, MagicMock
from app.warehouse.connector import WarehouseConnector
from app.models.warehouse import Warehouse
from app.core.security import encrypt_credential

@pytest.fixture
def mock_warehouse():
    wh = Warehouse(
        id=1,
        name="Test Warehouse",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="test_db",
        username="test_user",
        encrypted_password=encrypt_credential("secret_plaintext")
    )
    return wh

@patch("app.warehouse.connector.URL.create")
@patch("app.warehouse.connector.create_engine")
def test_connector_decrypts_credentials_successfully(mock_create_engine, mock_url_create, mock_warehouse):
    # Act
    WarehouseConnector.connect(mock_warehouse)
    
    # Assert
    # 2. SQLAlchemy receives the correct plaintext password internally.
    mock_url_create.assert_called_once_with(
        drivername="postgresql+psycopg2",
        username="test_user",
        password="secret_plaintext",
        host="localhost",
        port=5432,
        database="test_db"
    )
    
    # 3. Verify warehouse object was not mutated to store plaintext
    assert mock_warehouse.encrypted_password != "secret_plaintext"
    
@patch("app.warehouse.connector.URL.create")
def test_connector_fails_on_invalid_ciphertext(mock_url_create):
    wh = Warehouse(
        id=1,
        name="Test Warehouse",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="test_db",
        username="test_user",
        encrypted_password="invalid_ciphertext_not_fernet"
    )
    
    # Act & Assert
    with pytest.raises(ConnectionError, match="Failed to decrypt warehouse credentials"):
        WarehouseConnector.connect(wh)
        
    # 5. Invalid ciphertext does NOT fall back to plaintext.
    mock_url_create.assert_not_called()

@patch("app.warehouse.connector.URL.create")
@patch("app.warehouse.connector.create_engine")
def test_connector_existing_behavior_unsupported_db(mock_create_engine, mock_url_create, mock_warehouse):
    mock_warehouse.db_type = "mysql"
    
    with pytest.raises(ValueError, match="Unsupported database type"):
        WarehouseConnector.connect(mock_warehouse)
        
    mock_url_create.assert_not_called()
