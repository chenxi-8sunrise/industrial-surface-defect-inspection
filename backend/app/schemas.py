from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ModelInfo(BaseModel):
    name: str
    owner: str
    title: str
    requires_training: bool
    ready: bool


class DetectionResponse(BaseModel):
    id: int
    filename: str
    category: str
    model_name: str
    anomaly_score: float = Field(ge=0.0, le=1.0)
    is_anomaly: bool
    inference_ms: float
    original_url: str
    heatmap_url: str
    created_at: datetime

    class Config:
        orm_mode = True


class StatisticsResponse(BaseModel):
    total: int
    anomaly_count: int
    normal_count: int
    anomaly_rate: float
    by_model: dict[str, int]
    by_category: dict[str, int]

