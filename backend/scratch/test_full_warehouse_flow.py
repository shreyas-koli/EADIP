import os
import sys
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_full_warehouse_flow():
    print("==================================================")
    print(" FULL WAREHOUSE & EXPLORER FLOW VALIDATION")
    print("==================================================")

    # 1. Register & Login
    rand_id = random.randint(100000, 999999)
    email = f"explorer_user_{rand_id}@example.com"
    password = "TestPassword123!"

    reg_res = client.post("/auth/register", json={
        "email": email,
        "password": password,
        "full_name": f"Explorer User {rand_id}"
    })
    print(f"1. Registration: status={reg_res.status_code}")
    assert reg_res.status_code == 201

    login_res = client.post("/auth/login", json={
        "email": email,
        "password": password
    })
    print(f"2. Login: status={login_res.status_code}")
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Create Warehouse with valid local credentials
    wh_payload = {
        "name": f"Flow Test WH {rand_id}",
        "description": "Warehouse for credential & explorer testing",
        "db_type": "postgresql",
        "host": "localhost",
        "port": 5432,
        "database_name": "eadip",
        "username": "postgres",
        "password": "nfshp2mw"
    }
    create_wh_res = client.post("/warehouses/", json=wh_payload, headers=headers)
    print(f"3. Create Warehouse: status={create_wh_res.status_code}")
    assert create_wh_res.status_code == 201
    wh = create_wh_res.json()
    wh_id = wh["id"]

    # 4. List Warehouses
    list_res = client.get("/warehouses", headers=headers)
    print(f"4. List Warehouses: status={list_res.status_code}, count={len(list_res.json())}")
    assert list_res.status_code == 200

    # 5. Get Warehouse Details
    detail_res = client.get(f"/warehouses/{wh_id}", headers=headers)
    print(f"5. Warehouse Selection / Detail: status={detail_res.status_code}")
    assert detail_res.status_code == 200

    # 6. Warehouse Explorer: Schemas
    schema_res = client.get(f"/warehouses/{wh_id}/explorer/schemas", headers=headers)
    print(f"6. Explorer Schemas: status={schema_res.status_code}, schemas={schema_res.json()}")
    assert schema_res.status_code == 200
    schemas = schema_res.json()
    assert len(schemas) > 0
    target_schema = schemas[0]["name"]

    # 7. Warehouse Explorer: Tables in Schema
    tables_res = client.get(f"/warehouses/{wh_id}/explorer/schemas/{target_schema}/tables", headers=headers)
    print(f"7. Explorer Tables in '{target_schema}': status={tables_res.status_code}, count={len(tables_res.json())}")
    assert tables_res.status_code == 200
    tables = tables_res.json()

    if tables:
        target_table = tables[0]["name"]
        # 8. Data Loading (Rows)
        rows_res = client.get(f"/warehouses/{wh_id}/explorer/schemas/{target_schema}/tables/{target_table}/rows", headers=headers)
        print(f"8. Data Loading ('{target_table}'): status={rows_res.status_code}, total_rows={rows_res.json().get('total_count')}")
        assert rows_res.status_code == 200

    # 9. SQL Console (Query Execution)
    query_res = client.post(f"/warehouses/{wh_id}/explorer/query", json={
        "sql": "SELECT current_database(), current_user;"
    }, headers=headers)
    print(f"9. SQL Console Query: status={query_res.status_code}, rows={len(query_res.json().get('rows', []))}")
    assert query_res.status_code == 200

    # 10. AI Assistant Provider Availability
    providers_res = client.get(f"/warehouses/{wh_id}/explorer/assistant/providers", headers=headers)
    print(f"10. AI Assistant Providers: status={providers_res.status_code}, default={providers_res.json().get('default_provider')}")
    assert providers_res.status_code == 200

    # 11. Discovery Execution
    discovery_res = client.post("/discovery/execute", json={
        "warehouse_id": wh_id
    }, headers=headers)
    print(f"11. Discovery Execute: status={discovery_res.status_code}")
    assert discovery_res.status_code in (200, 201)

    print("\n==================================================")
    print(" ALL 11 WAREHOUSE & EXPLORER TESTS PASSED 100%!")
    print("==================================================")

if __name__ == "__main__":
    test_full_warehouse_flow()
