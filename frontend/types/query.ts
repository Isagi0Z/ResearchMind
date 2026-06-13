export type QueryType = 
  | 'FACTUAL'
  | 'EXPLANATION'
  | 'COMPARISON'
  | 'CONSENSUS'
  | 'CONTRADICTION'
  | 'RESEARCH_GAP'
  | 'MULTI_HOP'
  | 'EXPLORATION';

export type ExecutionState = 'idle' | 'parsing' | 'planning' | 'reasoning' | 'synthesis' | 'completed' | 'failed';

export interface ParsedQuery {
  id: string; // CRC32 deterministic
  text: string;
  type: QueryType;
}

export interface ReasoningStep {
  id: string;
  order: number;
  description: string;
  confidence: number;
  pathId: string;
}

export interface AggregatedEvidence {
  id: string;
  sourceDocId: string;
  sourceTitle: string;
  excerpt: string;
  confidence: number;
}

export interface ExecutionPlan {
  stepsCount: number;
  estimatedTimeMs: number;
}

export interface QueryMetrics {
  executionTimeMs: number;
  evidenceCount: number;
  reasoningSteps: number;
  overallConfidence: number;
}

export interface ResearchAnswer {
  queryId: string;
  text: string;
  confidence: number;
  evidence: AggregatedEvidence[];
  traces: ReasoningStep[];
  metrics: QueryMetrics;
}
