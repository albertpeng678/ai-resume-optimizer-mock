from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Optional

class AnalysisResponse(BaseModel):
    id: UUID
    filename: str
    uploaded_at: datetime
    dimensions: list

class AnalysisListItem(BaseModel):
    id: UUID
    filename: str
    uploaded_at: datetime
    avg_score: float

class MetricsResponse(BaseModel):
    total: int
    events: list[dict]
