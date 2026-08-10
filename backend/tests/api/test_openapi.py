import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_openapi_schema():
    response = client.get("/openapi.json")
    assert response.status_code == 200, "Failed to get openapi.json"
    schema = response.json()
    
    paths = schema.get("paths", {})
    
    # 2. Required endpoints
    assert "/discovery/execute" in paths, "POST /discovery/execute missing"
    assert "/warehouses/{warehouse_id}/history" in paths, "GET history missing"
    assert "/warehouses/{warehouse_id}/history/{session_id}" in paths, "GET execution detail missing"
    
    # 3. History Endpoint Parameters
    history_get = paths["/warehouses/{warehouse_id}/history"]["get"]
    parameters = history_get.get("parameters", [])
    
    param_names = [p["name"] for p in parameters]
    assert "warehouse_id" in param_names
    assert "page" in param_names
    assert "page_size" in param_names
    assert "status" in param_names
    
    for p in parameters:
        name = p["name"]
        schema_info = p.get("schema", {})
        
        if name == "warehouse_id":
            assert p["in"] == "path"
            assert schema_info.get("type") == "integer"
            
        if name == "page":
            assert p["in"] == "query"
            assert schema_info.get("type") == "integer"
            assert schema_info.get("minimum") == 1
            assert schema_info.get("default") == 1
            
        if name == "page_size":
            assert p["in"] == "query"
            assert schema_info.get("type") == "integer"
            assert schema_info.get("minimum") == 1
            assert schema_info.get("maximum") == 100
            assert schema_info.get("default") == 10
            
        if name == "status":
            assert p["in"] == "query"
            assert "anyOf" in schema_info or schema_info.get("type") == "string", "Status should be string or anyOf(null/str)"
            
            # Extract enum values if present
            enum_values = None
            if "enum" in schema_info:
                enum_values = schema_info["enum"]
            elif "anyOf" in schema_info:
                for option in schema_info["anyOf"]:
                    if "enum" in option:
                        enum_values = option["enum"]
                        break
            
            assert enum_values is not None, "Status parameter should have enum choices"
            assert "COMPLETED" in enum_values
            assert "FAILED" in enum_values
            assert "UNKNOWN" not in enum_values
            assert "RUNNING" not in enum_values

    # 4 & 5. Response Schemas References
    # Check 200 response for History
    history_responses = history_get.get("responses", {})
    assert "200" in history_responses
    content_schema = history_responses["200"].get("content", {}).get("application/json", {}).get("schema", {})
    assert "$ref" in content_schema
    assert "DiscoveryHistoryPaginatedResponse" in content_schema["$ref"]
    
    # Check 200 response for Detail
    detail_get = paths["/warehouses/{warehouse_id}/history/{session_id}"]["get"]
    detail_responses = detail_get.get("responses", {})
    assert "200" in detail_responses
    detail_content_schema = detail_responses["200"].get("content", {}).get("application/json", {}).get("schema", {})
    assert "$ref" in detail_content_schema
    assert "DiscoverySessionResponse" in detail_content_schema["$ref"]
    
    # 7. Authentication / Security scheme
    assert "security" in history_get, "GET history missing security requirements"
    assert "security" in detail_get, "GET detail missing security requirements"
    
    security_schemes = schema.get("components", {}).get("securitySchemes", {})
    assert "OAuth2PasswordBearer" in security_schemes
    assert security_schemes["OAuth2PasswordBearer"]["flows"]["password"]["tokenUrl"] == "/auth/token"
    
    # 9. HTTP Responses
    assert "401" in history_responses or "422" in history_responses, "Should document standard error codes"
    assert "404" in detail_responses or "422" in detail_responses, "Should document standard error codes"
    
    # Analyze Schema Components directly for 4, 5, 6
    components = schema.get("components", {}).get("schemas", {})
    
    # Paginated Response Check
    assert "DiscoveryHistoryPaginatedResponse" in components
    paginated_props = components["DiscoveryHistoryPaginatedResponse"]["properties"]
    assert "items" in paginated_props
    assert "total" in paginated_props
    assert "page" in paginated_props
    assert "page_size" in paginated_props
    
    # History Item Check
    assert "DiscoveryHistoryResponse" in components
    history_props = components["DiscoveryHistoryResponse"]["properties"]
    assert "session_id" in history_props
    assert "warehouse_id" in history_props
    assert "started_at" in history_props
    assert "finished_at" in history_props
    assert "status" in history_props
    assert "total_duration_ms" in history_props
    assert "agent_executions" not in history_props
    assert "recommendations" not in history_props
    
    # Detail Item Check
    assert "DiscoverySessionResponse" in components
    detail_props = components["DiscoverySessionResponse"]["properties"]
    assert "session_id" in detail_props
    assert "agent_executions" in detail_props
    assert "recommendations" in detail_props
    
    assert "AgentExecutionResponse" in components
    agent_exec_props = components["AgentExecutionResponse"]["properties"]
    assert "agent_name" in agent_exec_props
    assert "status" in agent_exec_props
    assert "started_at" in agent_exec_props
    assert "finished_at" in agent_exec_props
    assert "duration_ms" in agent_exec_props
    
    # Nullability Check
    # finished_at in DiscoveryHistoryResponse allows null (anyOf with type "null")
    finished_at_prop = history_props["finished_at"]
    assert "anyOf" in finished_at_prop, "finished_at should allow null"
    has_null = any(x.get("type") == "null" for x in finished_at_prop["anyOf"])
    assert has_null, "finished_at should allow null"
    
    agent_duration_prop = agent_exec_props["duration_ms"]
    assert "anyOf" in agent_duration_prop
    assert any(x.get("type") == "null" for x in agent_duration_prop["anyOf"])
