def test_root_returns_healthy(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["version"] == "1.0.0"
    assert "EcoFlood" in body["message"]


def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
