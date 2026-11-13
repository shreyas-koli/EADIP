import os
import sys
import base64

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.models.user
import app.models.warehouse
from app.core.config import settings
from app.database.session import SessionLocal
from app.models.warehouse import Warehouse
from app.warehouse.connector import WarehouseConnector
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import text

def run_definitive_diagnostic():
    print("==========================================================================")
    print(" AETHERARCHIVE DEFINITIVE ENCRYPTION & DATABASE DIAGNOSTIC SUITE")
    print("==========================================================================")
    
    # 1. Environment & Config Variables
    env_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    print(f"Active .env Path: {env_file_path}")
    print(f"Active .env Exists: {os.path.exists(env_file_path)}")
    
    enc_var_name = "ENCRYPTION_KEY"
    raw_key = getattr(settings, enc_var_name, None)
    key_loaded = bool(raw_key)
    key_length = len(raw_key) if raw_key else 0
    
    print(f"\n[STEP 1: ENCRYPTION VARIABLE DIAGNOSTICS]")
    print(f"encryption_variable_name = {enc_var_name}")
    print(f"encryption_key_loaded = {key_loaded}")
    print(f"encryption_key_length = {key_length}")
    
    fernet_valid = False
    f_instance = None
    if key_loaded:
        try:
            f_instance = Fernet(raw_key)
            fernet_valid = True
            print("Fernet initialization = SUCCESS (Key is a valid 32-byte base64 Fernet key)")
        except Exception as e:
            print(f"Fernet initialization = FAILED: WAREHOUSE_ENCRYPTION_KEY_INVALID ({e})")
            
    # 2. Database Connection Identity
    db = SessionLocal()
    try:
        db_url = settings.DATABASE_URL
        # Mask password in URL
        from urllib.parse import urlparse
        parsed = urlparse(db_url)
        masked_url = f"{parsed.scheme}://{parsed.username}:*****@{parsed.hostname}:{parsed.port}{parsed.path}"
        
        print(f"\n[STEP 2: APPLICATION DATABASE IDENTITY]")
        print(f"database_host = {parsed.hostname}")
        print(f"database_port = {parsed.port}")
        print(f"database_name = {parsed.path.lstrip('/')}")
        print(f"database_user = {parsed.username}")
        print(f"masked_connection_uri = {masked_url}")
        
        warehouses = db.query(Warehouse).order_by(Warehouse.id).all()
        print(f"warehouse_record_count = {len(warehouses)}")
        
        print(f"\n[STEP 3: PER-WAREHOUSE RECORD DECRYPTION & CONNECTIVITY AUDIT]")
        for wh in warehouses:
            print(f"\n--- Warehouse ID={wh.id} ('{wh.name}') ---")
            print(f"  db_type = {wh.db_type}")
            print(f"  host = {wh.host}")
            print(f"  port = {wh.port}")
            print(f"  database_name = {wh.database_name}")
            print(f"  username = {wh.username}")
            
            ciphertext = wh.encrypted_password
            has_cipher = bool(ciphertext)
            cipher_len = len(ciphertext) if ciphertext else 0
            
            print(f"  encrypted_password_present = {has_cipher}")
            print(f"  encrypted_password_length = {cipher_len}")
            
            decryption_category = "UNKNOWN"
            decrypted_plain = None
            
            if not has_cipher:
                decryption_category = "WAREHOUSE_CREDENTIALS_MISSING"
            elif not fernet_valid or not f_instance:
                decryption_category = "WAREHOUSE_ENCRYPTION_KEY_INVALID"
            else:
                try:
                    decrypted_plain = f_instance.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
                    decryption_category = "SUCCESS"
                except InvalidToken:
                    decryption_category = "WAREHOUSE_CREDENTIALS_INVALID_TOKEN (Key Mismatch)"
                except Exception as ex:
                    decryption_category = f"WAREHOUSE_CREDENTIALS_MALFORMED ({type(ex).__name__})"
                    
            print(f"  decryption_result = {decryption_category}")
            
            conn_result = "SKIPPED (Decryption Failed)"
            if decryption_category == "SUCCESS":
                try:
                    ok = WarehouseConnector.test_connection(wh)
                    conn_result = "SUCCESS" if ok else "WAREHOUSE_CONNECTION_FAILED (Unreachable / Bad Credentials)"
                except Exception as ex:
                    conn_result = f"WAREHOUSE_CONNECTION_FAILED ({ex})"
            print(f"  warehouse_connection_result = {conn_result}")
            
    finally:
        db.close()

if __name__ == "__main__":
    run_definitive_diagnostic()
