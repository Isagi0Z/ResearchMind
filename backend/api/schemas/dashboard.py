from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal, Tuple

class CorpusSummary(BaseModel):
    totalDocuments: int
    entityClusters: int
    graphNodes: int
    graphEdges: int
    activeJobs: int = 0
    failedJobs: int = 0
    completedJobs: int = 0

class SystemStatus(BaseModel):
    extraction: Literal["healthy", "warning", "error"]
    resolution: Literal["healthy", "warning", "error"]
    graph: Literal["healthy", "warning", "error"]
    reasoning: Literal["healthy", "warning", "error"]
    synthesis: Literal["healthy", "warning", "error"]

class RecentReview(BaseModel):
    id: str
    title: str
    type: str
    confidence: float
    createdAt: str
