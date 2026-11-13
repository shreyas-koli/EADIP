import sys
from app.database.init_db import init_db
from app.database.session import SessionLocal
from sqlalchemy import inspect, text

print("Initializing database tables...")
init_db()
print("init_db completed successfully!")

session = SessionLocal()
try:
    inspector = inspect(session.bind)
    tables = inspector.get_table_names()
    print(f"Existing tables in 'eadip' database: {tables}")
finally:
    session.close()
