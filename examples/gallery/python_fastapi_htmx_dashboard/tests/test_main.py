from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_dashboard_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "Dashboard Financeiro" in response.text

def test_health_check_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
