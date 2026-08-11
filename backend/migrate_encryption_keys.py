import os
import sys
from cryptography.fernet import Fernet, InvalidToken

# Adjust sys.path so we can import app modules when running this script directly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database.session import SessionLocal
from app.models.warehouse import Warehouse

def migrate_keys(dry_run: bool = True):
    """
    Migrate encrypted warehouse credentials from OLD_ENCRYPTION_KEY to NEW_ENCRYPTION_KEY.
    """
    old_key = os.environ.get("OLD_ENCRYPTION_KEY")
    new_key = os.environ.get("NEW_ENCRYPTION_KEY")

    if not old_key:
        print("ERROR: OLD_ENCRYPTION_KEY environment variable is missing.")
        sys.exit(1)
    if not new_key:
        print("ERROR: NEW_ENCRYPTION_KEY environment variable is missing.")
        sys.exit(1)

    try:
        old_f = Fernet(old_key)
    except Exception as e:
        print("ERROR: OLD_ENCRYPTION_KEY is invalid.")
        sys.exit(1)

    try:
        new_f = Fernet(new_key)
    except Exception as e:
        print("ERROR: NEW_ENCRYPTION_KEY is invalid.")
        sys.exit(1)

    db = SessionLocal()
    try:
        warehouses = db.query(Warehouse).all()
        print(f"Found {len(warehouses)} warehouses.")

        decrypted_passwords = {}

        # 1. VERIFICATION PHASE: Try to decrypt all existing passwords
        for wh in warehouses:
            if not wh.encrypted_password:
                continue

            try:
                # Decrypt using old key
                plaintext = old_f.decrypt(wh.encrypted_password.encode("utf-8")).decode("utf-8")
                decrypted_passwords[wh.id] = plaintext
            except InvalidToken:
                print(f"ERROR: Failed to decrypt warehouse ID {wh.id} using OLD_ENCRYPTION_KEY. Aborting.")
                db.rollback()
                sys.exit(1)
            except Exception as e:
                print(f"ERROR: Unexpected error decrypting warehouse ID {wh.id}. Aborting.")
                db.rollback()
                sys.exit(1)

        print("Verification phase complete. All credentials successfully decrypted with OLD_ENCRYPTION_KEY.")

        if dry_run:
            print("DRY RUN: Verification succeeded. No database changes will be made.")
            return

        # 2. UPDATE PHASE: Re-encrypt and update
        for wh in warehouses:
            if wh.id in decrypted_passwords:
                plaintext = decrypted_passwords[wh.id]
                new_ciphertext = new_f.encrypt(plaintext.encode("utf-8")).decode("utf-8")
                wh.encrypted_password = new_ciphertext
                # Safely delete plaintext from memory dict as we go
                del decrypted_passwords[wh.id]

        db.commit()
        print("MIGRATION COMPLETE. All credentials have been re-encrypted with NEW_ENCRYPTION_KEY.")

        # 3. POST-COMMIT VERIFICATION PHASE
        # Refresh to ensure what is actually saved is what we think it is
        for wh in warehouses:
            db.refresh(wh)
            if not wh.encrypted_password:
                continue
            try:
                new_f.decrypt(wh.encrypted_password.encode("utf-8")).decode("utf-8")
            except Exception:
                print(f"CRITICAL ERROR: Failed to decrypt warehouse ID {wh.id} using NEW_ENCRYPTION_KEY after migration!")
                sys.exit(1)

        print("Post-commit verification succeeded.")
        
    except Exception as e:
        print("ERROR: Unexpected error occurred during migration. Rolling back.")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    is_dry_run = "--execute" not in sys.argv
    if is_dry_run:
        print("Running in DRY-RUN mode. Pass --execute to apply changes.")
    migrate_keys(dry_run=is_dry_run)
