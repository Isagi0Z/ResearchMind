export type ReviewType = 
  | 'GENERAL'
  | 'METHOD'
  | 'DATASET'
  | 'CONSENSUS'
  | 'CONTRADICTION'
  | 'RESEARCH_GAP'
  | 'COMPARATIVE'
  | 'LANDSCAPE';

export type GenerationStage = 
  | 'idle'
  | 'theme_detection'
  | 'evidence_collection'
  | 'finding_generation'
  | 'section_building'
  | 'traceability_verification'
  | 'confidence_computation'
  | 'final_assembly'
  | 'completed'
  | 'failed';

export interface ReviewRequest {
  id: string; // CRC32
  topic: string;
  type: ReviewType;
  targetEntities: string[];
  documentScope: 'all' | 'recent' | 'high_confidence';
}

export interface EvidenceBundle {
  id: string;
  sourceDocId: string;
  sourceTitle: string;
  excerpt: string;
  confidence: number;
}

export interface ReviewFinding {
  id: string;
  type: string;
  statement: string;
  confidence: number;
  evidence: EvidenceBundle[];
}

export interface ReviewSection {
  id: string;
  order: number;
  title: string;
  content: string;
  findings: string[]; // Finding IDs referenced in this section
}

export interface ReviewMetadata {
  confidence: number;
  findingsCount: number;
  evidenceCount: number;
  sectionsCount: number;
  generationTimeMs: number;
}

export interface ReviewResult {
  id: string;
  request: ReviewRequest;
  abstract: string;
  sections: ReviewSection[];
  findings: ReviewFinding[];
  metadata: ReviewMetadata;
}
