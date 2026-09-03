from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_models_expose_four_distinct_owners():
    response = client.get("/api/models")
    assert response.status_code == 200
    models = response.json()
    assert {item["name"] for item in models} == {"cae", "padim", "patchcore", "stfpm"}
    assert {item["owner"] for item in models} == {"A", "B", "C", "D"}


def test_rejects_unknown_category_before_inference():
    response = client.post(
        "/api/detections",
        data={"model_name": "cae", "category": "unknown"},
        files={"file": ("sample.png", b"not-an-image", "image/png")},
    )
    assert response.status_code == 400

