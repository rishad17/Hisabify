from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def make_client(**overrides) -> TestClient:
    settings = Settings(_env_file=None, **{"environment": "test", **overrides})
    return TestClient(create_app(settings))


def test_health_ok():
    response = make_client().get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "TakaWise AI"
    assert body["environment"] == "test"


def test_unknown_route_uses_standard_error_shape():
    response = make_client().get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "Not Found", "details": None}
    }


def test_cors_allows_configured_origin_only():
    client = make_client(cors_origins="http://localhost:5173")
    preflight = {"Access-Control-Request-Method": "GET"}

    ok = client.options("/health", headers={"Origin": "http://localhost:5173", **preflight})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"

    blocked = client.options("/health", headers={"Origin": "https://evil.example", **preflight})
    assert "access-control-allow-origin" not in blocked.headers


def test_cors_origin_list_parsing():
    s = Settings(_env_file=None, cors_origins=" http://a.com/ , https://b.com ,, ")
    assert s.cors_origin_list == ["http://a.com", "https://b.com"]


def test_docs_hidden_in_production():
    assert make_client(environment="production").get("/docs").status_code == 404
