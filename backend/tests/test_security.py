import pytest
from app.core.security import encrypt_credential, decrypt_credential

def test_encrypt_decrypt_roundtrip():
    plaintext = "test-password"
    ciphertext = encrypt_credential(plaintext)
    
    assert ciphertext != plaintext
    
    decrypted = decrypt_credential(ciphertext)
    assert decrypted == plaintext

def test_invalid_ciphertext():
    with pytest.raises(ValueError, match="WAREHOUSE_CREDENTIALS_INVALID_TOKEN"):
        decrypt_credential("invalid_ciphertext")

def test_empty_credential():
    with pytest.raises(ValueError, match="Credential cannot be empty"):
        encrypt_credential("")
        
    with pytest.raises(ValueError, match="WAREHOUSE_CREDENTIALS_MISSING"):
        decrypt_credential("")
