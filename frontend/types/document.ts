import {
  DocumentType,
  ExtractionRoute,
  StageStatus,
  VenueType,
  CanonicalLabel,
  ExtractionMethod,
  ResolutionStatus,
  ResolutionSource,
  CitationIntent,
  EntityLabel,
  ClaimType,
} from "./enums";

export interface RUOMeta {
  ruo_id: string;
  sro_id?: string;
  corpus_ids: string[];
  schema_version: string;
  created_at: string;
  updated_at: string;
  pipeline_version: string;
  source_file: {
    filename: string;
    sha256: string;
    page_count: number;
    has_text_layer: boolean;
    is_scanned: boolean;
    size_bytes?: number;
  };
  extraction_route: ExtractionRoute;
  document_type: DocumentType;
  language: string;
  arxiv_categories: string[];
  research_fields: string[];
  processing_time_ms?: number;
  pipeline_stages: StageStatus[];
}

export interface RUOAuthor {
  full_name: string;
  given_name?: string;
  surname?: string;
  affiliations: string[];
  email?: string;
  orcid?: string;
  is_corresponding?: boolean;
  evidence_ids: string[];
}

export interface ComponentConfidence {
  component: string;
  score: number;
  subscores: Array<{
    name: string;
    value: number;
    weight: number;
    explanation?: string;
    evidence_ids: string[];
  }>;
  uncertainty?: any;
  evidence_chain_id?: string;
}

export interface RUOHeader {
  title: string;
  authors: RUOAuthor[];
  document_type: DocumentType;
  doi?: string;
  arxiv_id?: string;
  pmid?: string;
  publication_date?: string;
  venue?: string;
  venue_type?: VenueType;
  volume?: string;
  issue?: string;
  pages?: string;
  keywords: string[];
  confidence: ComponentConfidence;
  evidence_ids: string[];
}

export interface RUOEntity {
  entity_id: string;
  text: string;
  label: EntityLabel;
  chunk_id: string;
  sentence: string;
  confidence: number;
  source: string;
  normalized_id?: string;
  normalized_label?: string;
  kb_source?: string;
  evidence_ids: string[];
  embedding?: number[];
  embedding_model?: string;
}

export interface RUOClaim {
  claim_id: string;
  sentence: string;
  chunk_id: string;
  section_id: string;
  canonical_label: CanonicalLabel;
  claim_type: ClaimType;
  matched_patterns: string[];
  confidence: number;
  page: number;
  evidence_chain_id: string;
  is_contradicted: boolean;
  contradiction_detected_at?: string;
  is_supported_by: string[];
  is_replicated?: boolean;
  normalized_statement?: string;
  embedding?: number[];
  embedding_model?: string;
}

export interface RUOQuality {
  confidence: {
    components: ComponentConfidence[];
    overall: number;
    overall_uncertainty?: any;
    overall_evidence_chain_id?: string;
    component_weights: Record<string, number>;
  };
  evidence_coverage: any;
  validation?: any;
  pipeline_log: any[];
  llm_calls: any[];
  requires_manual_review: boolean;
  manual_review_reasons: string[];
  overall_confidence: number;
}

export interface RUODocument {
  meta: RUOMeta;
  header: RUOHeader;
  abstract?: any;
  body: any;
  references: any[];
  citations: any[];
  entities: RUOEntity[];
  claims: RUOClaim[];
  triples: any[];
  quality: RUOQuality;
  annotations: any[];
  schema_version: string;
  lineage: string[];
}
