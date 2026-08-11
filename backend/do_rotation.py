import os
import sys
from dotenv import dotenv_values, set_key
from cryptography.fernet import Fernet
import pytest
import subprocess

def run_rotation():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    
    # 2. Read CURRENT ENCRYPTION_KEY
    env_vars = dotenv_values(env_path)
    old_key = env_vars.get("ENCRYPTION_KEY")
    if not old_key:
        print("ERROR: ENCRYPTION_KEY not found in .env")
        sys.exit(1)
        
    # 3. Generate NEW cryptographically secure Fernet key
    new_key = Fernet.generate_key().decode("utf-8")
    
    # 4. Set environment variables
    os.environ["OLD_ENCRYPTION_KEY"] = old_key
    os.environ["NEW_ENCRYPTION_KEY"] = new_key
    os.environ["DATABASE_URL"] = env_vars.get("DATABASE_URL")
    
    # 5. Run the migration utility in DRY-RUN mode
    from migrate_encryption_keys import migrate_keys
    
    try:
        print("--- RUNNING DRY RUN ---")
        migrate_keys(dry_run=True)
    except SystemExit as e:
        if e.code != 0:
            print("ERROR: DRY RUN failed.")
            sys.exit(e.code)
            
    # 6. Run with --execute
    try:
        print("--- RUNNING EXECUTE ---")
        migrate_keys(dry_run=False)
    except SystemExit as e:
        if e.code != 0:
            print("ERROR: EXECUTE failed.")
            sys.exit(e.code)
            
    # 7. Verification is handled by POST-COMMIT VERIFICATION in migrate_keys.py
    print("Migration successful! Updating .env")
    
    # 8. Update backend/.env
    set_key(env_path, "ENCRYPTION_KEY", new_key)
    print("ENCRYPTION_KEY updated in .env successfully.")

if __name__ == "__main__":
    run_rotation()
