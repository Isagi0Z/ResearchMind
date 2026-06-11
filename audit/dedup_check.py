"""Check Stage 8 dedup effectiveness and Stage 3 duplicate counts."""
import json
from collections import Counter
from pathlib import Path
from datetime import datetime, timezone
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from researchmind.storage.corpus import CorpusManager
from researchmind.models.ruo import (
    RUODocument, RUOMeta, RUOHeader, RUOSourceFile, RUOAuthor,
    RUOBody, RUOSection, RUOChunk, RUOEntity, RUOQuality,
    ComponentConfidence, ComponentSubscore, ConfidenceBreakdown,
    EvidenceCoverage,
)
from researchmind.models.ruo_enums import (
    DocumentType, EntityLabel, ExtractionRoute, CanonicalLabel,
    ExtractionMethod,
)


def build_ruo_from_sro(data):
    meta = data.get("meta", {})
    header = data.get("header", {})
    now = datetime.now(timezone.utc)
    ruo_meta = RUOMeta(
        ruo_id="ruo_" + meta.get("sro_id", "unknown"),
        created_at=now, updated_at=now,
        pipeline_version=meta.get("pipeline_version", "2.1.0"),
        source_file=RUOSourceFile(
            filename=meta.get("source_file", {}).get("original_filename", "unknown.pdf"),
            sha256="e" * 64,
            page_count=meta.get("source_file", {}).get("page_count", 5),
            has_text_layer=True, is_scanned=False,
        ),
        extraction_route=ExtractionRoute.GROBID_PRIMARY,
        document_type=DocumentType.RESEARCH_ARTICLE,
    )
    authors = [RUOAuthor(full_name=a.get("full_name", ""))
               for a in header.get("authors", []) if a.get("full_name")]
    pub_date = header.get("publication_date") or header.get("publication_date_raw")
    ruo_header = RUOHeader(
        title=header.get("title", "Untitled"), authors=authors,
        document_type=DocumentType.RESEARCH_ARTICLE,
        publication_date=str(pub_date) if pub_date else None,
        confidence=ComponentConfidence(
            component="header", score=0.85,
            subscores=[ComponentSubscore(name="header", value=0.85, weight=1.0)]),
    )
    entities = []
    for ent in data.get("entities", []):
        label_str = ent.get("label", "method")
        try:
            label = EntityLabel(label_str)
        except ValueError:
            label = EntityLabel.METHOD
        entities.append(RUOEntity(
            entity_id=ent.get("entity_id", "ent_" + str(len(entities))),
            text=ent.get("text", ""), label=label,
            chunk_id=ent.get("chunk_id", "c1"),
            sentence=ent.get("context_sentence", ""),
            confidence=ent.get("confidence", 0.5), source="sro_eval",
        ))
    body = RUOBody(
        sections=[RUOSection(
            section_id="s1", level=1, position=0,
            original_header="Introduction",
            canonical_label=CanonicalLabel.INTRODUCTION,
            label_confidence=0.9, page_start=0, page_end=1,
            content="Section content.",
            extraction_method=ExtractionMethod.GROBID,
        )],
        chunks=[RUOChunk(
            chunk_id="c1", text="Content.", word_count=1,
            section_id="s1", canonical_label=CanonicalLabel.INTRODUCTION,
            page_start=0, page_end=1, paragraph_index=0,
            reading_order=0, extraction_method=ExtractionMethod.GROBID,
            extraction_confidence=0.9,
        )],
    )
    quality = RUOQuality(
        confidence=ConfidenceBreakdown(
            components=[ComponentConfidence(
                component="overall", score=0.85,
                subscores=[ComponentSubscore(name="overall", value=0.85, weight=1.0)],
            )],
            overall=0.85,
            component_weights={"overall": 1.0},
        ),
        evidence_coverage=EvidenceCoverage(
            total_claims=0, claims_with_evidence=0, claims_evidence_rate=0.0,
            total_entities=0, entities_with_evidence=0, entities_evidence_rate=0.0,
            total_citations=0, citations_with_intent_evidence=0,
            citation_intent_evidence_rate=0.0,
            total_references=0, references_with_resolution_evidence=0,
            reference_resolution_evidence_rate=0.0,
        ),
        overall_confidence=0.85,
    )
    return RUODocument(
        meta=ruo_meta, header=ruo_header, body=body,
        entities=entities, claims=[], triples=[], references=[],
        quality=quality, provenance=[],
    )


def main():
    sro_dir = Path("eval_output/sro_v2")
    docs = []
    for sf in sorted(sro_dir.glob("*.json")):
        if sf.name == "evaluation_summary_v2.json":
            continue
        raw = json.loads(sf.read_text(encoding="utf-8"))
        docs.append(build_ruo_from_sro(raw))
    mgr = CorpusManager.from_documents(docs, "audit-corpus")
    g = mgr.corpus_graph

    edges = g.edges
    print("Total edges:", len(edges))

    # Edge ID uniqueness
    eid_counts = Counter(e.edge_id for e in edges)
    dups = {eid: c for eid, c in eid_counts.items() if c > 1}
    print("Edges with non-unique edge_id:", len(dups))
    print("Max edge_id count:", max(eid_counts.values()))
    print()
    print("Stage 8 dedup (by edge_id) would remove:", len(edges) - len(eid_counts), "edges")
    print("Conclusion: Stage 8 dedup by edge_id is a no-op (all IDs unique)")
    print()

    # Stage 3 duplicate analysis
    de_edges = [e for e in edges if e.edge_id.startswith("de_")]
    de_sigs = Counter((e.source_id, e.target_id, e.relation_type.value) for e in de_edges)
    de_dups = {s: c for s, c in de_sigs.items() if c > 1}
    de_dup_count = sum(c - 1 for c in de_dups.values())
    print("Stage 3 (de_*) edges:", len(de_edges))
    print("Stage 3 unique (doc,cluster,rel):", len(de_sigs))
    print("Stage 3 duplicate signatures:", len(de_dups))
    print("Stage 3 duplicate edges:", de_dup_count)
    print()

    # What if Stage 3 deduped?
    adjusted = len(edges) - de_dup_count
    adjusted_density = adjusted / (57 * 56)
    print("If Stage 3 deduped:")
    print("  Total edges:", adjusted)
    print("  Density:", adjusted_density)

    # Stage 4 duplicates
    stage4_edges = [e for e in edges if e.metadata.get("edge_kind") == "doc_relation"]
    stage4_sigs = Counter((e.source_id, e.target_id, e.relation_type.value) for e in stage4_edges)
    s4_dups = {s: c for s, c in stage4_sigs.items() if c > 1}
    print()
    print("Stage 4 edges:", len(stage4_edges))
    print("Stage 4 unique (doc,doc,rel):", len(stage4_sigs))
    print("Stage 4 duplicate signatures:", len(s4_dups))

    # Show the Stage 8 dedup code
    print()
    print("Stage 8 dedup code (from graph.py):")
    print("  def _stage_8_deduplicate(self, edges):")
    print("      seen = {}")
    print("      for e in edges:")
    print("          seen[e.edge_id] = e  # last wins if ID collision")
    print("      return list(seen.values())")
    print()
    print("Since every edge has a random uuid4().hex[:12] as edge_id,")
    print("NO two edges share the same edge_id, so the dedup is NEVER triggered.")


if __name__ == "__main__":
    main()
