import { RUODocument } from "@/types/document";
import { DocumentType, ExtractionRoute, StageStatus } from "@/types/enums";
import { RecentReview, SystemStatus, CorpusSummary } from "@/types/dashboard";

// Deterministic random number generator (LCG)
let seed = 12345;
function random() {
  seed = (seed * 9301 + 49297) % 233280;
  return seed / 233280;
}

function randomInt(min: number, max: number) {
  return Math.floor(random() * (max - min + 1)) + min;
}

function randomChoice<T>(arr: T[]): T {
  return arr[Math.floor(random() * arr.length)];
}

const AUTHORS = [
  "Alice Smith", "Bob Jones", "Charlie Brown", "Diana Prince", 
  "Evan Wright", "Fiona Gallagher", "George Clark", "Hannah Abbott"
];
const VENUES = ["Nature", "Science", "Cell", "NeurIPS", "ICML", "ACL", "EMNLP"];
const KEYWORDS = ["machine learning", "biology", "physics", "nlp", "computer vision", "robotics", "genetics"];

// Pre-generate 1000 deterministic documents
export const MOCK_DOCUMENTS: RUODocument[] = Array.from({ length: 1000 }).map((_, i) => {
  const year = randomInt(2010, 2026);
  const statusPool: StageStatus[] = ["success", "partial", "failed"];
  const finalStatus = random() > 0.8 ? randomChoice(["partial", "failed"] as StageStatus[]) : "success";
  
  return {
    meta: {
      ruo_id: `doc-${i.toString().padStart(4, '0')}`,
      corpus_ids: ["corpus-1"],
      schema_version: "2.1.0",
      created_at: `2025-01-01T12:00:00Z`,
      updated_at: `2025-01-02T12:00:00Z`,
      pipeline_version: "1.0.0",
      source_file: {
        filename: `paper_${i}.pdf`,
        sha256: `abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234`,
        page_count: randomInt(5, 30),
        has_text_layer: true,
        is_scanned: false,
      },
      extraction_route: "grobid_primary" as ExtractionRoute,
      document_type: "research_article" as DocumentType,
      language: "en",
      arxiv_categories: ["cs.AI"],
      research_fields: ["Computer Science"],
      pipeline_stages: ["success", "success", finalStatus],
    },
    header: {
      title: `Research Paper on ${randomChoice(KEYWORDS)} ${i}`,
      authors: Array.from({ length: randomInt(1, 4) }).map(() => ({
        full_name: randomChoice(AUTHORS),
        affiliations: ["University of Research"],
        evidence_ids: [],
      })),
      document_type: "research_article" as DocumentType,
      publication_date: `${year}-01-01`,
      venue: randomChoice(VENUES),
      keywords: [randomChoice(KEYWORDS), randomChoice(KEYWORDS)],
      confidence: {
        component: "header",
        score: random() * 0.5 + 0.5,
        subscores: [],
      },
      evidence_ids: [],
    },
    body: {
      sections: [],
      chunks: [],
      tables: [],
      figures: [],
      evidence_ids: [],
    },
    references: [],
    citations: [],
    entities: Array.from({ length: randomInt(5, 20) }).map((_, j) => ({
      entity_id: `ent-${i}-${j}`,
      text: `Entity ${j}`,
      label: "method",
      chunk_id: `chunk-${j}`,
      sentence: "Sample sentence",
      confidence: 0.9,
      source: "spacy",
      evidence_ids: [],
    })),
    claims: [],
    triples: [],
    quality: {
      confidence: {
        components: [],
        overall: random() * 0.5 + 0.5,
        component_weights: {},
      },
      evidence_coverage: {},
      pipeline_log: [],
      llm_calls: [],
      requires_manual_review: finalStatus === "failed",
      manual_review_reasons: [],
      overall_confidence: random() * 0.5 + 0.5,
    },
    annotations: [],
    schema_version: "2.1.0",
    lineage: [],
  };
});

export const MOCK_CORPUS_SUMMARY: CorpusSummary = {
  totalDocuments: 1000,
  entityClusters: 45210,
  graphNodes: 89000,
  graphEdges: 215000,
};

export const MOCK_SYSTEM_STATUS: SystemStatus = {
  extraction: "healthy",
  resolution: "healthy",
  graph: "healthy",
  reasoning: "warning",
  synthesis: "healthy",
};

export const MOCK_RECENT_REVIEWS: RecentReview[] = Array.from({ length: 5 }).map((_, i) => ({
  id: `rev-${i}`,
  title: `Literature Review ${i + 1}`,
  type: "meta_analysis",
  confidence: 0.85 + (i * 0.02),
  createdAt: `2025-06-0${i + 1}T10:00:00Z`,
}));
