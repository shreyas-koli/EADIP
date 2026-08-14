from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_cors_preflight_auth_register():
    """
    Test that the CORS preflight request (OPTIONS) for /auth/register
    returns a successful response for an allowed origin.
    """
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type",
    }
    response = client.options("/auth/register", headers=headers)
    
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "POST" in response.headers.get("access-control-allow-methods", "")
    assert "Content-Type" in response.headers.get("access-control-allow-headers", "")

def test_cors_preflight_warehouses():
    """
    Test that the CORS preflight request (OPTIONS) for /warehouses/
    returns a successful response for an allowed origin.
    """
    headers = {
        "Origin": "http://127.0.0.1:3000",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Authorization",
    }
    response = client.options("/warehouses/", headers=headers)
    
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:3000"
    assert "GET" in response.headers.get("access-control-allow-methods", "")
    assert "Authorization" in response.headers.get("access-control-allow-headers", "")

def test_cors_preflight_disallowed_origin():
    """
    Test that the CORS preflight request (OPTIONS) for a disallowed origin
    does not return the origin in the access-control-allow-origin header.
    """
    headers = {
        "Origin": "http://evil-domain.com",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type",
    }
    response = client.options("/auth/register", headers=headers)
    
    # In FastAPI's CORSMiddleware, if an origin is not allowed, 
    # it typically responds with 400 or just omits the allow-origin header.
    assert response.headers.get("access-control-allow-origin") is None
