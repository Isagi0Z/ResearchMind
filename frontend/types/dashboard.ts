export interface CorpusSummary {
  totalDocuments: number;
  entityClusters: number;
  graphNodes: number;
  graphEdges: number;
  activeJobs: number;
  failedJobs: number;
  completedJobs: number;
}

export interface SystemStatus {
  extraction: "healthy" | "warning" | "error";
  resolution: "healthy" | "warning" | "error";
  graph: "healthy" | "warning" | "error";
  reasoning: "healthy" | "warning" | "error";
  synthesis: "healthy" | "warning" | "error";
}

export interface RecentReview {
  id: string;
  title: string;
  type: string;
  confidence: number;
  createdAt: string;
}
