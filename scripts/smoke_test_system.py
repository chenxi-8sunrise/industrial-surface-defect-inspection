from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from backend.app.main import app


def main() -> None:
    client = TestClient(app)
    sample = ROOT / "data" / "raw" / "mvtec_ad" / "bottle" / "test" / "broken_large" / "000.png"
    if not sample.exists():
        raise FileNotFoundError(sample)

    health = client.get("/api/health")
    health.raise_for_status()
    models = client.get("/api/models")
    models.raise_for_status()
    ready = {item["name"]: item["ready"] for item in models.json()}
    if not all(ready.values()):
        raise RuntimeError(f"unavailable model: {ready}")

    detections = []
    for model_name in ("cae", "padim", "patchcore", "stfpm"):
        with sample.open("rb") as stream:
            response = client.post(
                "/api/detections",
                data={"model_name": model_name, "category": "bottle"},
                files={"file": (sample.name, stream, "image/png")},
            )
        response.raise_for_status()
        result = response.json()
        heatmap = client.get(result["heatmap_url"])
        heatmap.raise_for_status()
        if not heatmap.headers.get("content-type", "").startswith("image/"):
            raise RuntimeError(f"invalid heatmap response: {model_name}")
        detections.append({
            "model": model_name,
            "record_id": result["id"],
            "anomaly_score": result["anomaly_score"],
            "is_anomaly": result["is_anomaly"],
            "inference_ms": result["inference_ms"],
            "heatmap_url": result["heatmap_url"],
        })

    history = client.get("/api/detections", params={"limit": 20})
    history.raise_for_status()
    statistics = client.get("/api/statistics")
    statistics.raise_for_status()
    report = {
        "status": "passed",
        "health": health.json(),
        "models_ready": ready,
        "sample": str(sample.relative_to(ROOT)),
        "detections": detections,
        "history_records": len(history.json()),
        "statistics": statistics.json(),
    }
    output = ROOT / "artifacts" / "system_acceptance.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
