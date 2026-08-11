import os
import pytest
from cryptography.fernet import Fernet
from unittest.mock import patch, MagicMock
from app.models.warehouse import Warehouse
from migrate_encryption_keys import migrate_keys

@pytest.fixture
def old_key():
    return Fernet.generate_key().decode("utf-8")

@pytest.fixture
def new_key():
    return Fernet.generate_key().decode("utf-8")

@pytest.fixture
def mock_db_session():
    with patch("migrate_encryption_keys.SessionLocal") as mock_session_local:
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        yield mock_session

def test_migration_success(old_key, new_key, mock_db_session):
    # Setup mock warehouses
    old_f = Fernet(old_key)
    plaintext = "my_secret_password"
    old_ciphertext = old_f.encrypt(plaintext.encode("utf-8")).decode("utf-8")
    
    wh1 = Warehouse(id=1, encrypted_password=old_ciphertext)
    mock_db_session.query.return_value.all.return_value = [wh1]

    # Run migration with execute
    with patch.dict(os.environ, {"OLD_ENCRYPTION_KEY": old_key, "NEW_ENCRYPTION_KEY": new_key}):
        migrate_keys(dry_run=False)

    # Verify session methods were called
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(wh1)

    # Verify re-encryption
    assert wh1.encrypted_password != old_ciphertext
    
    # Verify new key decrypts to same plaintext
    new_f = Fernet(new_key)
    decrypted_with_new = new_f.decrypt(wh1.encrypted_password.encode("utf-8")).decode("utf-8")
    assert decrypted_with_new == plaintext

    # Verify old key cannot decrypt new ciphertext
    with pytest.raises(Exception):
        old_f.decrypt(wh1.encrypted_password.encode("utf-8"))

def test_migration_abort_on_invalid_credential(old_key, new_key, mock_db_session):
    # Setup one valid and one invalid warehouse
    old_f = Fernet(old_key)
    original_wh1_ciphertext = old_f.encrypt(b"valid").decode("utf-8")
    wh1 = Warehouse(id=1, encrypted_password=original_wh1_ciphertext)
    
    # Invalid ciphertext (cannot be decrypted with old_key)
    wrong_key = Fernet.generate_key()
    wrong_f = Fernet(wrong_key)
    original_wh2_ciphertext = wrong_f.encrypt(b"invalid").decode("utf-8")
    wh2 = Warehouse(id=2, encrypted_password=original_wh2_ciphertext)
    
    mock_db_session.query.return_value.all.return_value = [wh1, wh2]

    # Run migration
    with patch.dict(os.environ, {"OLD_ENCRYPTION_KEY": old_key, "NEW_ENCRYPTION_KEY": new_key}):
        with pytest.raises(SystemExit) as exc_info:
            migrate_keys(dry_run=False)

    # Verify failure exit code
    assert exc_info.value.code == 1

    # Verify no commit was made (rollback instead)
    mock_db_session.commit.assert_not_called()
    mock_db_session.rollback.assert_called_once()

    # Verify neither warehouse was modified (no partial updates occurred)
    assert wh1.encrypted_password == original_wh1_ciphertext
    assert wh2.encrypted_password == original_wh2_ciphertext
