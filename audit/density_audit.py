"""Comprehensive graph-density audit for the 8-paper evaluation corpus."""

import json
import sys
from collections import defaultdict, Counter
from pathlib import Path
from datetime import datetime, timezone

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


def build_ruo_from_sro(data: dict) -> RUODocument:
    meta = data.get("meta", {})
    header = data.get("header", {})
    now = datetime.now(timezone.utc)

    ruo_meta = RUOMeta(
        ruo_id=f"ruo_{meta.get('sro_id', 'unknown')}",
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

    authors = [
        RUOAuthor(full_name=a.get("full_name", ""))
        for a in header.get("authors", []) if a.get("full_name")
    ]
    pub_date = header.get("publication_date") or header.get("publication_date_raw")
    ruo_header = RUOHeader(
        title=header.get("title", "Untitled"),
        authors=authors,
        document_type=DocumentType.RESEARCH_ARTICLE,
        publication_date=str(pub_date) if pub_date else None,
        confidence=ComponentConfidence(
            component="header", score=0.85,
            subscores=[ComponentSubscore(name="header", value=0.85, weight=1.0)],
        ),
    )

    entities = []
    for ent in data.get("entities", []):
        label_str = ent.get("label", "method")
        try:
            label = EntityLabel(label_str)
        except ValueError:
            label = EntityLabel.METHOD
        entities.append(RUOEntity(
            entity_id=ent.get("entity_id", f"ent_{len(entities)}"),
            text=ent.get("text", ""),
            label=label,
            chunk_id=ent.get("chunk_id", "c1"),
            sentence=ent.get("context_sentence", ""),
            confidence=ent.get("confidence", 0.5),
            source="sro_eval",
        ))

    body = RUOBody(
        sections=[RUOSection(
            section_id="s1", level=1, position=0,
            original_header="Introduction",
            canonical_label=CanonicalLabel.INTRODUCTION,
            label_confidence=0.9, page_start=0, page_end=1,
            content="Section content.", extraction_method=ExtractionMethod.GROBID,
        )],
        chunks=[RUOChunk(
            chunk_id="c1", text="Content.", word_count=1,
            section_id="s1",
            canonical_label=CanonicalLabel.INTRODUCTION,
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


def load_corpus() -> CorpusManager:
    sro_dir = Path("eval_output/sro_v2")
    docs = []
    for sf in sorted(sro_dir.glob("*.json")):
        if sf.name == "evaluation_summary_v2.json":
            continue
        raw = json.loads(sf.read_text(encoding="utf-8"))
        doc = build_ruo_from_sro(raw)
        docs.append(doc)
    mgr = CorpusManager.from_documents(docs, "audit-corpus")
    return mgr


def analyze(mgr: CorpusManager):
    g = mgr.corpus_graph
    edges = g.edges
    nodes = g.nodes
    n_nodes = len(nodes)
    n_edges = len(edges)

    print("=" * 70)
    print("CORPUS GRAPH DENSITY AUDIT")
    print(f"Nodes: {n_nodes}   Edges: {n_edges}")
    print("=" * 70)

    # ------------------------------------------------------------------
    # 1. Edge Distribution by relation_type
    # ------------------------------------------------------------------
    print("\n## 1. EDGE DISTRIBUTION BY RELATION TYPE\n")
    edge_type_counts = Counter(e.relation_type.value for e in edges)
    print(f"{'relation_type':<20} {'count':<8} {'%':<8}")
    print("-" * 36)
    for rt, cnt in edge_type_counts.most_common():
        print(f"{rt:<20} {cnt:<8} {100*cnt/n_edges:>6.2f}%")
    print(f"{'TOTAL':<20} {n_edges:<8} {100.0:>6.2f}%")

    # ------------------------------------------------------------------
    # 2. Edge Source Attribution (by edge_id prefix)
    # ------------------------------------------------------------------
    print("\n## 2. EDGE SOURCE ATTRIBUTION (by edge_id prefix)\n")
    stage_prefixes = {
        "de_": "Stage 3 — doc→entity EXTENDS",
        "ee_": "Stage 5 — entity→entity COMPARES_WITH",
        "dc_": "Stage 7a — doc→claim SUPPORTS",
        "cc_": "Stage 7b — cross-doc claim→claim",
    }
    # Stage 4 uses DocumentRelation relation_id (no fixed prefix), detect by edge_kind
    stage4_edges = [e for e in edges if e.metadata.get("edge_kind") == "doc_relation"]
    stage4_count = len(stage4_edges)
    stage4_types = Counter(e.relation_type.value for e in stage4_edges)

    stage_counts = {}
    for prefix, label in stage_prefixes.items():
        count = sum(1 for e in edges if e.edge_id.startswith(prefix))
        stage_counts[label] = count

    stage_counts["Stage 4 — doc→doc (relation_ids)"] = stage4_count

    for label, cnt in sorted(stage_counts.items(), key=lambda x: -x[1]):
        print(f"  {label:<50} {cnt:<8} {100*cnt/n_edges:>6.2f}%")

    # Stage 4 breakdown by type
    print("\n  Stage 4 breakdown by relation_type:")
    for rt, cnt in stage4_types.most_common():
        print(f"    {rt:<20} {cnt}")

    # Cross-check: remaining edges (should be 0)
    accounted = sum(stage_counts.values())
    if n_edges - accounted > 0:
        print(f"\n  UNACCOUNTED: {n_edges - accounted}")

    # ------------------------------------------------------------------
    # 3. Entity Co-occurrence Explosion Analysis
    # ------------------------------------------------------------------
    print("\n## 3. ENTITY CO-OCCURRENCE EXPLOSION (Stage 5)\n")

    # Reconstruct doc→cluster mapping the same way stage 5 does
    eid_to_cluster = {}
    if hasattr(g, '_resolution'):
        resolution = g._resolution
    else:
        resolution = None

    doc_clusters = defaultdict(set)
    for doc in mgr.get_documents():
        doc_id = doc.meta.ruo_id
        for ent in doc.entities:
            # We can't access the builder's eid_to_cluster from the result,
            # so let's infer from the graph
            pass

    # Better approach: use the graph edge data to count per-document clusters
    # Stage 3 edges: de_* target entity cluster
    doc_entity_edges = [e for e in edges if e.edge_id.startswith("de_")]
    doc_entity_counter = Counter(e.source_id for e in doc_entity_edges)
    doc_cluster_sets = defaultdict(set)
    for e in doc_entity_edges:
        doc_cluster_sets[e.source_id].add(e.target_id)

    print(f"  Total Stage 5 (ee_*) edges: {stage_counts.get('Stage 5 — entity→entity COMPARES_WITH', 0)}")
    print()

    print(f"  {'Doc':<30} {'Entities':<10} {'Clusters':<10} {'Pairs':<10}")
    print("-" * 60)
    total_pairs = 0
    total_entities = 0
    for doc_id in sorted(doc_cluster_sets.keys()):
        clusters = doc_cluster_sets[doc_id]
        k = len(clusters)
        pairs = k * (k - 1) // 2
        n_ents = doc_entity_counter.get(doc_id, 0)
        total_pairs += pairs
        total_entities += n_ents
        doc_label = next((n.label[:28] for n in nodes if n.node_id == doc_id), doc_id)
        print(f"  {doc_label:<30} {n_ents:<10} {k:<10} {pairs:<10}")

    print(f"  {'TOTAL':<30} {total_entities:<10} {'':<10} {total_pairs:<10}")

    # Check if seen_pairs cross-doc dedup matters
    ee_edges = [e for e in edges if e.edge_id.startswith("ee_")]
    ee_pairs = set()
    for e in ee_edges:
        pair = (e.source_id, e.target_id)
        ee_pairs.add(pair)

    print(f"\n  Unique entity pairs (across all docs): {len(ee_pairs)}")
    print(f"  Actual ee_ edges: {len(ee_edges)}")
    print(f"  Dedup savings: {total_pairs - len(ee_edges)} (pairs that appeared in multiple docs)")

    # Top docs by co-occurrence pairs
    print(f"\n  Top documents by pair count:")
    for doc_id in sorted(doc_cluster_sets.keys(), key=lambda d: len(doc_cluster_sets[d]), reverse=True)[:5]:
        clusters = doc_cluster_sets[doc_id]
        pairs = len(clusters) * (len(clusters) - 1) // 2
        doc_label = next((n.label[:40] for n in nodes if n.node_id == doc_id), doc_id)
        print(f"    {doc_label:<40} {len(clusters)} clusters, {pairs} pairs")

    # ------------------------------------------------------------------
    # 4. Duplicate Semantic Edge Analysis
    # ------------------------------------------------------------------
    print("\n## 4. DUPLICATE SEMANTIC EDGE ANALYSIS\n")

    # Check for same source+target+relation_type
    edge_signatures = defaultdict(list)
    for e in edges:
        sig = (e.source_id, e.target_id, e.relation_type.value)
        edge_signatures[sig].append(e.edge_id)

    duplicates = {sig: eids for sig, eids in edge_signatures.items() if len(eids) > 1}
    dup_count = sum(len(eids) - 1 for eids in duplicates.values())

    print(f"  Unique (src, tgt, rel_type) signatures: {len(edge_signatures)}")
    print(f"  Duplicate signature groups: {len(duplicates)}")
    print(f"  Duplicate edges (beyond first): {dup_count}")
    print(f"  Duplicate percentage: {100 * dup_count / n_edges:.2f}%")

    if duplicates:
        print(f"\n  Examples of duplicates:")
        for sig, eids in list(duplicates.items())[:5]:
            src, tgt, rt = sig
            print(f"    {src} -> {tgt} [{rt}]: {len(eids)} edges — edge_ids: {eids[:3]}...")

    # ------------------------------------------------------------------
    # 5. Multigraph Inflation Analysis
    # ------------------------------------------------------------------
    print("\n## 5. MULTIGRAPH INFLATION ANALYSIS\n")

    node_pairs = defaultdict(set)  # (src, tgt) -> set of relation_types
    for e in edges:
        pair = (e.source_id, e.target_id)
        node_pairs[pair].add(e.relation_type.value)

    total_unique_pairs = len(node_pairs)
    multi_type_pairs = {p: rts for p, rts in node_pairs.items() if len(rts) > 1}
    single_type_pairs = {p: rts for p, rts in node_pairs.items() if len(rts) == 1}

    print(f"  Unique node pairs: {total_unique_pairs}")
    print(f"  Pairs with 1 relation type: {len(single_type_pairs)}")
    print(f"  Pairs with >1 relation types (multigraph): {len(multi_type_pairs)}")
    print(f"  Edge-per-pair ratio: {n_edges}/{total_unique_pairs} = {n_edges/total_unique_pairs:.2f}")

    if multi_type_pairs:
        print(f"\n  Examples of multigraph pairs:")
        for pair, rts in list(multi_type_pairs.items())[:5]:
            print(f"    {pair[0]} <-> {pair[1]}: {rts}")

        # Show the pair with the most relation types
        max_pair = max(multi_type_pairs, key=lambda p: len(multi_type_pairs[p]))
        print(f"\n  Pair with most relation types: {max_pair[0]} <-> {max_pair[1]}")
        print(f"    Types: {multi_type_pairs[max_pair]}")

    # ------------------------------------------------------------------
    # 6. Density Validation
    # ------------------------------------------------------------------
    print("\n## 6. DENSITY VALIDATION\n")

    # Manual density calculation
    density_formula = n_edges / max(n_nodes * (n_nodes - 1), 1)
    print(f"  n = {n_nodes} nodes")
    print(f"  e = {n_edges} edges")
    print(f"  max_possible_edges = n*(n-1) = {n_nodes}*{n_nodes-1} = {n_nodes*(n_nodes-1)}")
    print(f"  Density (formula: e / n*(n-1)) = {density_formula:.6f}")

    # Reason for ≤1.0 check
    if density_formula > 1.0:
        print(f"  *** WARNING: Raw density exceeds 1.0 — capped at 1.0 ***")

    # Recompute with only document nodes to see the "real" density
    doc_nodes = [n for n in nodes if n.node_type == "document"]
    n_docs = len(doc_nodes)
    doc_ids = {n.node_id for n in doc_nodes}

    # Count edges between documents only
    doc_doc_edges = [e for e in edges if e.source_id in doc_ids and e.target_id in doc_ids]
    doc_doc_pairs = {(e.source_id, e.target_id) for e in doc_doc_edges}
    doc_density = len(doc_doc_edges) / max(n_docs * (n_docs - 1), 1)

    print(f"\n  Document-only density:")
    print(f"    {n_docs} docs, {len(doc_doc_edges)} doc-doc edges")
    print(f"    {len(doc_doc_pairs)} unique doc-doc pairs")
    print(f"    Doc density: {doc_density:.6f}")

    # Entity-cluster density
    ec_nodes = [n for n in nodes if n.node_type == "entity_cluster"]
    n_ec = len(ec_nodes)
    ec_ids = {n.node_id for n in ec_nodes}
    ec_ec_edges = [e for e in edges if e.source_id in ec_ids and e.target_id in ec_ids]
    if n_ec > 1:
        ec_density = len(ec_ec_edges) / max(n_ec * (n_ec - 1), 1)
    else:
        ec_density = 0.0
    print(f"\n  Entity-cluster-only density:")
    print(f"    {n_ec} clusters, {len(ec_ec_edges)} cluster-cluster edges")
    print(f"    EC density: {ec_density:.6f}")

    print(f"\n  Comparison:")
    print(f"    Reported (compute_graph_statistics): {g.compute_statistics().density:.6f}")
    print(f"    Manual formula:                    {density_formula:.6f}")
    print(f"    Match? {'YES' if abs(g.compute_statistics().density - density_formula) < 0.0001 else 'NO'}")

    # ------------------------------------------------------------------
    # 7. Top-20 Highest Degree Nodes
    # ------------------------------------------------------------------
    print("\n## 7. TOP-20 HIGHEST DEGREE NODES\n")

    degree = Counter()
    for e in edges:
        degree[e.source_id] += 1
        if e.source_id != e.target_id:
            degree[e.target_id] += 1

    print(f"  {'Rank':<5} {'Node ID':<25} {'Type':<18} {'Label':<40} {'Degree':<8}")
    print("-" * 96)
    for rank, (nid, deg) in enumerate(degree.most_common(20), 1):
        node = next((n for n in nodes if n.node_id == nid), None)
        ntype = node.node_type if node else "?"
        label = (node.label[:38] if node else nid)
        print(f"  {rank:<5} {nid:<25} {ntype:<18} {label:<40} {deg:<8}")

    # Degree statistics
    all_degrees = list(degree.values())
    if all_degrees:
        print(f"\n  Degree stats:")
        print(f"    Mean:   {sum(all_degrees)/len(all_degrees):.2f}")
        print(f"    Median: {sorted(all_degrees)[len(all_degrees)//2]}")
        print(f"    Max:    {max(all_degrees)}")
        print(f"    Min:    {min(all_degrees)}")

    # Check entity cluster domination
    ec_degrees = {nid: d for nid, d in degree.items() if any(n.node_id == nid and n.node_type == "entity_cluster" for n in nodes)}
    doc_degrees = {nid: d for nid, d in degree.items() if any(n.node_id == nid and n.node_type == "document" for n in nodes)}
    if ec_degrees:
        top_ec = max(ec_degrees, key=ec_degrees.get)
        print(f"\n  Highest-degree entity cluster: {top_ec} ({ec_degrees[top_ec]})")
        print(f"  Highest-degree document: {max(doc_degrees, key=doc_degrees.get) if doc_degrees else 'N/A'} ({max(doc_degrees.values()) if doc_degrees else 0})")

    # ------------------------------------------------------------------
    # 8. Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("AUDIT SUMMARY")
    print("=" * 70)
    print(f"\n  Total nodes:                          {n_nodes}")
    print(f"  Total edges:                          {n_edges}")
    print(f"  Stage 3 (doc→entity EXTENDS):         {stage_counts.get('Stage 3 — doc→entity EXTENDS', 0)}")
    print(f"  Stage 4 (doc→doc, various):            {stage4_count}")
    print(f"  Stage 5 (entity→entity COMPARES_WITH): {stage_counts.get('Stage 5 — entity→entity COMPARES_WITH', 0)}")
    print(f"  Stage 7 (doc→claim + claim→claim):    {stage_counts.get('Stage 7a — doc→claim SUPPORTS', 0) + stage_counts.get('Stage 7b — cross-doc claim→claim', 0)}")
    print(f"  Density:                              {g.compute_statistics().density:.6f}")
    print(f"  Doc-only density:                     {doc_density:.6f}")
    print(f"  Unique (src,tgt,rel) signatures:      {len(edge_signatures)}")
    print(f"  Duplicate edges:                      {dup_count} ({100*dup_count/n_edges:.2f}%)")
    print(f"  Multigraph pairs (>1 rel type):       {len(multi_type_pairs)}")
    print(f"  Edge-per-pair ratio:                  {n_edges/total_unique_pairs:.2f}")
    print(f"  Total entity pairs from Stage 5:      {len(ee_pairs) if 'ee_pairs' in dir() else 'N/A'}")


if __name__ == "__main__":
    mgr = load_corpus()
    analyze(mgr)
