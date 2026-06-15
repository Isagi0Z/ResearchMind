from researchmind.storage.corpus import CorpusManager
from researchmind.models.ruo import (
    RUODocument, RUOMeta, RUOHeader, RUOQuality, ComponentConfidence,
    RUOSourceFile, RUOEntity
)
from researchmind.models.enums import DocumentType, ExtractionRoute, StageStatus
from backend.api.schemas.dashboard import RecentReview

# Deterministic random number generator (LCG)
_seed = 12345
def random_float():
    global _seed
    _seed = (_seed * 9301 + 49297) % 233280
    return _seed / 233280.0

def random_int(min_val: int, max_val: int):
    return int(random_float() * (max_val - min_val + 1)) + min_val

def random_choice(arr: list):
    return arr[int(random_float() * len(arr))]

AUTHORS = [
    "Alice Smith", "Bob Jones", "Charlie Brown", "Diana Prince", 
    "Evan Wright", "Fiona Gallagher", "George Clark", "Hannah Abbott"
]
VENUES = ["Nature", "Science", "Cell", "NeurIPS", "ICML", "ACL", "EMNLP"]
KEYWORDS = ["machine learning", "biology", "physics", "nlp", "computer vision", "robotics", "genetics"]

def generate_mock_documents():
    docs = []
    for i in range(1000):
        year = random_int(2010, 2026)
        final_status = random_choice(["partial", "failed"]) if random_float() > 0.8 else "success"
        
        meta = RUOMeta(
            ruo_id=f"doc-{i:04d}",
            corpus_ids=["corpus-1"],
            schema_version="2.1.0",
            created_at="2025-01-01T12:00:00Z",
            updated_at="2025-01-02T12:00:00Z",
            pipeline_version="1.0.0",
            source_file=RUOSourceFile(
                filename=f"paper_{i}.pdf",
                sha256="abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234",
                page_count=random_int(5, 30),
                has_text_layer=True,
                is_scanned=False,
            ),
            extraction_route=ExtractionRoute.GROBID_PRIMARY,
            document_type=DocumentType.RESEARCH_ARTICLE,
            language="en",
            arxiv_categories=["cs.AI"],
            research_fields=["Computer Science"],
            pipeline_stages=["success", "success", final_status],
        )
        
        header = RUOHeader(
            title=f"Research Paper on {random_choice(KEYWORDS)} {i}",
            authors=[
                {
                    "full_name": random_choice(AUTHORS),
                    "affiliations": ["University of Research"],
                    "evidence_ids": []
                }
                for _ in range(random_int(1, 4))
            ],
            document_type=DocumentType.RESEARCH_ARTICLE,
            publication_date=f"{year}-01-01",
            venue=random_choice(VENUES),
            keywords=[random_choice(KEYWORDS), random_choice(KEYWORDS)],
            confidence=ComponentConfidence(
                component="header",
                score=random_float() * 0.5 + 0.5,
                subscores=[]
            ),
            evidence_ids=[]
        )
        
        entities = [
            RUOEntity(
                entity_id=f"ent-{i}-{j}",
                text=f"Entity {j}",
                label="method",
                chunk_id=f"chunk-{j}",
                sentence="Sample sentence",
                confidence=0.9,
                source="spacy",
                evidence_ids=[]
            )
            for j in range(random_int(5, 20))
        ]
        
        quality = RUOQuality(
            confidence={
                "components": [],
                "overall": random_float() * 0.5 + 0.5,
                "component_weights": {}
            },
            evidence_coverage={},
            pipeline_log=[],
            llm_calls=[],
            requires_manual_review=(final_status == "failed"),
            manual_review_reasons=[],
            overall_confidence=random_float() * 0.5 + 0.5,
        )
        
        doc = RUODocument(
            meta=meta,
            header=header,
            body={"sections": [], "chunks": [], "tables": [], "figures": [], "evidence_ids": []},
            references=[],
            citations=[],
            entities=entities,
            claims=[],
            triples=[],
            quality=quality,
            schema_version="2.1.0",
            lineage=[]
        )
        docs.append(doc)
    return docs

def get_mock_recent_reviews():
    reviews = []
    for i in range(5):
        reviews.append(RecentReview(
            id=f"rev-{i}",
            title=f"Literature Review {i + 1}",
            type="meta_analysis",
            confidence=0.85 + (i * 0.02),
            createdAt=f"2025-06-0{i + 1}T10:00:00Z"
        ))
    return reviews
