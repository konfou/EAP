def test_health_and_ready(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True

    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_metrics_snapshot(client):
    client.get("/health")
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["total_requests"] >= 1


def test_prometheus_metrics(client):
    response = client.get("/metrics", headers={"Accept": "text/plain"})
    assert response.status_code == 200
    assert "http_requests_total" in response.text

    response = client.get("/metrics/prometheus")
    assert response.status_code == 200
    assert "http_request_latency_seconds" in response.text
