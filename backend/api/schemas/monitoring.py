from pydantic import BaseModel
from typing import List, Optional

class CorpusStatistic(BaseModel):
    documentCount: int
    authorCount: int
    entityCount: int
    reviewCount: int

class ModuleHealth(BaseModel):
    moduleId: str
    name: str
    status: str
    uptime: str
    activeThreads: int

class QueueJob(BaseModel):
    id: str
    moduleId: str
    type: str
    status: str
    submitTimeStr: str
    durationMs: int

class ErrorEvent(BaseModel):
    id: str
    moduleId: str
    type: str
    severity: str
    message: str
    timeStr: str

class PerformanceMetric(BaseModel):
    label: str
    throughput: float
    latencyMs: float
    successRate: float

class MonitoringSnapshot(BaseModel):
    id: str
    health: List[ModuleHealth]
    metrics: dict
    charts: List[PerformanceMetric]
    queue: List[QueueJob]
    recentErrors: List[ErrorEvent]
    corpus: CorpusStatistic
