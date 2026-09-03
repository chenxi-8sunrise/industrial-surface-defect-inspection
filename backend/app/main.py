from __future__ import annotations

from collections import Counter
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from ml.models import list_models

from . import db_models
from .database import Base, engine, get_db
from .schemas import DetectionResponse, ModelInfo, StatisticsResponse
from .services.inference import heatmap_overlay, manager


ROOT = Path(__file__).resolve().parents[2]
STORAGE = ROOT / "backend" / "storage"
UPLOADS = STORAGE / "uploads"
HEATMAPS = STORAGE / "heatmaps"
for directory in (UPLOADS, HEATMAPS):
    directory.mkdir(parents=True, exist_ok=True)

Base.metadata.create_all(bind=engine)
app = FastAPI(title="工业表面缺陷检测API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.mount("/storage", StaticFiles(directory=STORAGE), name="storage")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "surface-defect-api"}


@app.get("/api/models", response_model=list[ModelInfo])
def models() -> list[ModelInfo]:
    return [ModelInfo(**spec.__dict__, ready=manager.ready(spec.name)) for spec in list_models()]


@app.post("/api/detections", response_model=DetectionResponse)
async def detect(
    file: UploadFile = File(...),
    model_name: str = Form(...),
    category: str = Form(...),
    db: Session = Depends(get_db),
) -> DetectionResponse:
    if model_name not in {spec.name for spec in list_models()}:
        raise HTTPException(400, "不支持的模型")
    if category not in {"bottle", "tile", "transistor"}:
        raise HTTPException(400, "不支持的产品类别")
    contents = await file.read()
    image = cv2.imdecode(np.frombuffer(contents, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(400, "无法读取上传图片")
    if not manager.ready(model_name, category):
        raise HTTPException(503, f"{model_name}/{category}模型尚未训练")

    token = uuid4().hex
    extension = Path(file.filename or "image.png").suffix.lower() or ".png"
    original_path = UPLOADS / f"{token}{extension}"
    heatmap_path = HEATMAPS / f"{token}.jpg"
    original_path.write_bytes(contents)
    prediction = manager.predict(model_name, category, cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    encoded, buffer = cv2.imencode(".jpg", heatmap_overlay(image, prediction.heatmap))
    if not encoded:
        raise HTTPException(500, "热力图生成失败")
    buffer.tofile(heatmap_path)

    record = db_models.DetectionRecord(
        filename=file.filename or original_path.name,
        category=category,
        model_name=model_name,
        anomaly_score=prediction.anomaly_score,
        is_anomaly=prediction.is_anomaly,
        inference_ms=prediction.inference_ms,
        original_path=f"/storage/uploads/{original_path.name}",
        heatmap_path=f"/storage/heatmaps/{heatmap_path.name}",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return DetectionResponse(
        id=record.id, filename=record.filename, category=category, model_name=model_name,
        anomaly_score=record.anomaly_score, is_anomaly=record.is_anomaly,
        inference_ms=record.inference_ms, original_url=record.original_path,
        heatmap_url=record.heatmap_path, created_at=record.created_at,
    )


@app.get("/api/detections", response_model=list[DetectionResponse])
def history(limit: int = 50, db: Session = Depends(get_db)) -> list[DetectionResponse]:
    rows = db.query(db_models.DetectionRecord).order_by(db_models.DetectionRecord.created_at.desc()).limit(min(limit, 200)).all()
    return [DetectionResponse(
        id=row.id, filename=row.filename, category=row.category, model_name=row.model_name,
        anomaly_score=row.anomaly_score, is_anomaly=row.is_anomaly, inference_ms=row.inference_ms,
        original_url=row.original_path, heatmap_url=row.heatmap_path, created_at=row.created_at,
    ) for row in rows]


@app.delete("/api/detections/{record_id}")
def delete_record(record_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    record = db.get(db_models.DetectionRecord, record_id)
    if record is None:
        raise HTTPException(404, "记录不存在")
    db.delete(record)
    db.commit()
    return {"deleted": True}


@app.get("/api/statistics", response_model=StatisticsResponse)
def statistics(db: Session = Depends(get_db)) -> StatisticsResponse:
    rows = db.query(db_models.DetectionRecord).all()
    anomaly_count = sum(row.is_anomaly for row in rows)
    total = len(rows)
    return StatisticsResponse(
        total=total,
        anomaly_count=anomaly_count,
        normal_count=total - anomaly_count,
        anomaly_rate=(anomaly_count / total if total else 0.0),
        by_model=dict(Counter(row.model_name for row in rows)),
        by_category=dict(Counter(row.category for row in rows)),
    )


FRONTEND_DIST = ROOT / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
