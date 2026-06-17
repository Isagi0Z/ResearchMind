export type HealthStatus = 'Healthy' | 'Warning' | 'Error';

export interface ModuleHealth {
  moduleId: string;
  name: string;
  status: HealthStatus;
  uptime: string;
  activeThreads: number;
}

export interface QueueJob {
  id: string;
  moduleId: string;
  type: string;
  status: 'active' | 'pending' | 'completed' | 'failed';
  submitTimeStr: string;
  durationMs: number;
}

export interface ErrorEvent {
  id: string;
  moduleId: string;
  type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  timeStr: string;
}

export interface PerformanceMetric {
  label: string;
  throughput: number;
  latencyMs: number;
  successRate: number;
}

export interface CorpusStatistic {
  documentCount: number;
  authorCount: number;
  entityCount: number;
  reviewCount: number;
}

export interface MonitoringSnapshot {
  id: string;
  health: ModuleHealth[];
  metrics: {
    queriesExecuted: number;
    queriesToday: number;
    querySuccessRate: number;
    reviewsGenerated: number;
    reviewsToday: number;
    registeredUsers: number;
    activeUsers: number;
    refreshTokensActive: number;
    documentsProcessed: number;
  };
  charts: PerformanceMetric[];
  queue: QueueJob[];
  recentErrors: ErrorEvent[];
  corpus: CorpusStatistic;
}
