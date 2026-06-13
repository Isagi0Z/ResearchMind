export type ExtractionRoute = "grobid_primary" | "grobid_with_fallback" | "ocr_primary" | "hybrid";
export type ExtractionMethod = "grobid" | "pymupdf_fallback" | "ocr_surya" | "ocr_tesseract" | "llm_repair";
export type CanonicalLabel = "introduction" | "related_work" | "methodology" | "results" | "discussion" | "conclusion" | "limitations" | "future_work" | "acknowledgments" | "appendix" | "other";
export type DocumentType = "research_article" | "review" | "meta_analysis" | "preprint" | "thesis" | "case_study" | "technical_report" | "other";
export type VenueType = "journal" | "conference" | "workshop" | "preprint_server" | "thesis" | "unknown";
export type ResolutionStatus = "resolved" | "unresolved" | "ambiguous";
export type ResolutionSource = "grobid_consolidation" | "crossref_lookup" | "manual" | "none";
export type CitationIntent = "supports" | "contrasts" | "extends" | "uses_method" | "background" | "compares" | "unknown";
export type ClaimType = "statistical" | "causal" | "comparative" | "methodological" | "existence" | "negation";
export type EntityLabel = "method" | "dataset" | "metric" | "tool" | "material" | "disease" | "drug" | "gene_protein" | "organism" | "person" | "organization" | "location" | "other";
export type StageStatus = "success" | "partial" | "failed" | "skipped";

export type EvidenceType = "direct_quote" | "paraphrase" | "statistical" | "derived" | "external" | "llm_generated" | "human_annotated";
export type EvidenceTargetType = "claim" | "entity" | "citation_intent" | "confidence";
export type AggregationMethod = "minimum" | "product" | "weighted_average";
export type UncertaintyType = "measurement_error" | "missing_data" | "contradictory_evidence" | "model_uncertainty" | "ambiguous_source" | "extraction_artifact" | "not_applicable";
export type ConsensusStatus = "consistent" | "contradictory" | "insufficient_evidence";

export type ProvenanceAction = "created" | "updated" | "validated" | "corrected" | "rejected" | "annotated" | "merged";
export type ProvenanceAgentType = "pipeline_stage" | "llm" | "human_reviewer" | "external_service" | "rule_based";
export type DataSource = "grobid" | "pymupdf" | "ocr_surya" | "ocr_tesseract" | "crossref" | "pubmed" | "llm" | "manual_review" | "inferred" | "unknown";

export type RelationType = "cites" | "cited_by" | "contradicts" | "supports" | "extends" | "supersedes" | "reproduces" | "uses_method" | "uses_dataset" | "compares_with" | "reviews" | "meta_analysis_includes" | "unknown";
export type AnnotationType = "human_review" | "human_correction" | "llm_suggestion" | "automated_flag" | "quality_issue" | "manual_override";
export type AnnotationStatus = "open" | "accepted" | "rejected" | "superseded";
export type ValidationSeverity = "error" | "warning" | "info";
