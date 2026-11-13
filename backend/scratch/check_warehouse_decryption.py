import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.models.user  # import User model for relationship mapping
import app.models.warehouse
from app.core.config import settings
from app.database.session import SessionLocal
from app.models.warehouse import Warehouse
from cryptography.fernet import Fernet, InvalidToken

def check_local_warehouses():
    print(f"Loaded ENCRYPTION_KEY from settings (len={len(settings.ENCRYPTION_KEY) if settings.ENCRYPTION_KEY else 0})")
    
    try:
        f = Fernet(settings.ENCRYPTION_KEY)
        print("Fernet initialized successfully with active ENCRYPTION_KEY.")
    except Exception as e:
        print(f"CRITICAL: Failed to initialize Fernet with ENCRYPTION_KEY: {e}")
        return

    db = SessionLocal()
    try:
        warehouses = db.query(Warehouse).all()
        print(f"Total warehouse records in local database: {len(warehouses)}")
        
        for wh in warehouses:
            has_cipher = bool(wh.encrypted_password)
            can_decrypt = False
            error_reason = None
            
            if has_cipher:
                try:
                    plaintext = f.decrypt(wh.encrypted_password.encode("utf-8")).decode("utf-8")
                    can_decrypt = True
                except InvalidToken:
                    can_decrypt = False
                    error_reason = "InvalidToken (ciphertext was encrypted with a different key)"
                except Exception as ex:
                    can_decrypt = False
                    error_reason = str(ex)
            else:
                error_reason = "No encrypted_password present"
                
            print(f"Warehouse ID={wh.id}, Name='{wh.name}', DB Type='{wh.db_type}', Host='{wh.host}':")
            print(f"  encrypted_password present = {has_cipher}")
            print(f"  decryptable = {can_decrypt}")
            if error_reason:
                print(f"  diagnostic_info = '{error_reason}'")

    finally:
        db.close()

if __name__ == "__main__":
    check_local_warehouses()
