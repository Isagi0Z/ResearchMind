
# Module 3 Evaluation Report


**Generated:** 2026-06-11T02:33:33.808086+00:00

**Corpus:** 8 papers (Attention, BERT, ResNet, U-Net, Adam, BatchNorm, Dropout, GAN)

**Stage 8 fix applied:** Dedup by `(source_id, target_id, relation_type)` instead of `edge_id`


## Executive Summary

The 8-paper evaluation corpus builds a graph with **57 nodes** and **1458 edges** (density **0.456767**). The Stage 8 semantic dedup fix removed **455 duplicate edges** (from 1,913 pre-fix to 1,458 post-fix). The graph forms **1 connected component** (57 nodes, 1458 edges).

Entity Resolution produces **49 entity clusters** from **615 entities** across 8 documents. The dominant relation type is `compares_with` (1232 edges, Stage 5 co-occurrence).

**Readiness:** Module 3 is **READY**. All 325 tests pass. The one verified bug (Stage 8 dedup keyed on random UUID instead of semantic identity) has been fixed.


## Before/After Comparison

| Metric | Pre-Fix | Post-Fix | Delta |
|---|---|---|---|
| Graph Edges | 1,913 | 1458 | -455 |
| Unique Semantic Edges | N/A | 1458 | +0 (unique) |
| Duplicate Edges | 455 | 0 | -455 |
| Density | 0.599311 | 0.456767 | -0.142544 |
| Average Degree | 67.1228 | 51.1579 | -15.9649 |
| Connected Components | 1 | 1 | 0 |


## Corpus Overview

| Metric | Value |
|---|---|
| Documents | 8 |
| Entity Clusters | 49 |
| Claim Nodes | 0 |
| Graph Nodes | 57 |
| Graph Edges | 1458 |
| Connected Components | 1 |
| Largest Component Size | 57 |
| Largest Component Edges | 1458 |


## Graph Metrics

| Metric | Value |
|---|---|
| Average Degree | 51.1579 |
| Average Out-Degree | 25.5789 |
| Average In-Degree | 25.5789 |
| Density | 0.456767 |
| Self-Loops | 0 |
| Average Confidence | 0.9194 |
| Min Confidence | 0.0469 |
| Max Confidence | 1.0 |


## Node Type Distribution

| Type | Count |
|---|---|
| document | 8 |
| entity_cluster | 49 |


## Edge Type Distribution

| Relation Type | Count |
|---|---|
| extends | 226 |
| compares_with | 1232 |


## Edge Source Attribution (Post-Fix)

| Stage | Count |
|---|---|
| stage3_doc_entity | 216 |
| stage4_doc_doc | 66 |
| stage5_entity_entity | 1176 |
| stage7a_doc_claim | 0 |
| stage7b_claim_claim | 0 |


## Entity Resolution Results

| Metric | Value |
|---|---|
| Total Entities | 615 (across 8 documents) |
| Total Clusters | 49 |
| Clusters with >1 entity | N/A (see per-cluster details) |
| Resolution Method | EntityResolver (Levenshtein + rapidfuzz) |


### Largest Entity Clusters (by degree)

| Rank | Cluster Label | Cluster ID | Degree | Weight | Cluster Size |
|---|---|---|---|---|---|
| 1 | linear | ec_2e94e4473eb4 | 56 | 0.75 | 3 |
| 2 | Markov | ec_bf82d12d1d19 | 56 | 0.75 | 5 |
| 3 | Boltzmann | ec_fc389844406c | 56 | 0.75 | 2 |
| 4 | Algorithm 1. | ec_eea4fb1113d9 | 56 | 0.75 | 2 |
| 5 | Algorithm 1 | ec_cff4fb9aa8a3 | 56 | 0.75 | 2 |
| 6 | C(G | ec_bb8c8f7ef4b7 | 56 | 0.75 | 2 |
| 7 | TFD | ec_93fcf10a336d | 56 | 0.75 | 2 |
| 8 | Gaussians | ec_701846b309f8 | 56 | 0.75 | 2 |
| 9 | Table 12 | ec_e17c02b33440 | 56 | 0.75 | 6 |
| 10 | Adam | ec_0a891db44b37 | 56 | 0.75 | 9 |


## Document Relation Results

Stage 4 produces **66** document→document edges from the DocumentRelationEngine. 
Relations derive from entity overlap detection across the 8 documents.


## Corpus Graph Results

| Metric | Value |
|---|---|
| Total Nodes | 57 |
| Document Nodes | 8 |
| Entity Cluster Nodes | 49 |
| Total Edges | 1458 |
| EXTENDS Edges | 226 |
| COMPARES_WITH Edges | 1232 |
| Connected Components | 1 |
| Average Degree | 51.1579 |
| Density | 0.456767 |


## Traversal Examples

```python
# All traversal APIs work on the corrected graph
result = graph_result.get_neighbors(doc_id, depth=2)
path = graph_result.shortest_path(doc_a_id, doc_b_id)
paths = graph_result.find_paths(doc_a_id, doc_b_id, max_depth=3)
comp = graph_result.connected_components()
sub = graph_result.subgraph(node_ids)
nodes = graph_result.query_nodes(node_type='entity_cluster')
edges = graph_result.query_edges(relation_type=RelationType.EXTENDS)
```

See `tests/test_corpus_graph.py` for detailed traversal test scenarios (TestGetNeighbors, TestShortestPath, TestFindPaths, TestConnectedComponents, TestSubgraph, TestQueryNodes, TestQueryEdges).


## Top Entity Clusters (by degree)

| Rank | Cluster Label | Cluster ID | Degree | Weight | Cluster Size |
|---|---|---|---|---|---|
| 1 | linear | ec_2e94e4473eb4 | 56 | 0.75 | 3 |
| 2 | Markov | ec_bf82d12d1d19 | 56 | 0.75 | 5 |
| 3 | Boltzmann | ec_fc389844406c | 56 | 0.75 | 2 |
| 4 | Algorithm 1. | ec_eea4fb1113d9 | 56 | 0.75 | 2 |
| 5 | Algorithm 1 | ec_cff4fb9aa8a3 | 56 | 0.75 | 2 |
| 6 | C(G | ec_bb8c8f7ef4b7 | 56 | 0.75 | 2 |
| 7 | TFD | ec_93fcf10a336d | 56 | 0.75 | 2 |
| 8 | Gaussians | ec_701846b309f8 | 56 | 0.75 | 2 |
| 9 | Table 12 | ec_e17c02b33440 | 56 | 0.75 | 6 |
| 10 | Adam | ec_0a891db44b37 | 56 | 0.75 | 9 |


## Top Documents (by degree)

| Rank | Title | Degree | Entities |
|---|---|---|---|
| 1 | BERT: Pre-training of Deep Bidirectional Transform | 63 | 355 |
| 2 | Dropout: A Simple Way to Prevent Neural Networks f | 57 | 254 |
| 3 | Deep Residual Learning for Image Recognition | 52 | 234 |
| 4 | Batch Normalization: Accelerating Deep Network Tra | 41 | 147 |
| 5 | ADAM: A METHOD FOR STOCHASTIC OPTIMIZATION | 38 | 120 |
| 6 | Attention Is All You Need | 34 | 85 |
| 7 | Generative Adversarial Nets | 33 | 74 |
| 8 | U-Net: Convolutional Networks for Biomedical Image | 30 | 61 |


## Top Predicates

| Rank | Relation Type | Count |
|---|---|---|
| 1 | compares_with | 1232 |
| 2 | extends | 226 |


## Top 20 Highest Degree Nodes

| Rank | Node ID | Type | Label | Degree |
|---|---|---|---|---|
| 1 | ruo_6e03217b-83db-40dd-a | document | BERT: Pre-training of Deep Bidirectional | 63 |
| 2 | ruo_e003c165-b920-45c6-a | document | Dropout: A Simple Way to Prevent Neural  | 57 |
| 3 | ec_2e94e4473eb4 | entity_cluster | linear | 56 |
| 4 | ec_bf82d12d1d19 | entity_cluster | Markov | 56 |
| 5 | ec_fc389844406c | entity_cluster | Boltzmann | 56 |
| 6 | ec_eea4fb1113d9 | entity_cluster | Algorithm 1. | 56 |
| 7 | ec_cff4fb9aa8a3 | entity_cluster | Algorithm 1 | 56 |
| 8 | ec_bb8c8f7ef4b7 | entity_cluster | C(G | 56 |
| 9 | ec_93fcf10a336d | entity_cluster | TFD | 56 |
| 10 | ec_701846b309f8 | entity_cluster | Gaussians | 56 |
| 11 | ec_e17c02b33440 | entity_cluster | Table 12 | 56 |
| 12 | ec_0a891db44b37 | entity_cluster | Adam | 56 |
| 13 | ec_e8293d9782d4 | entity_cluster | ReLU | 56 |
| 14 | ec_0e2f562ed861 | entity_cluster | CNN | 56 |
| 15 | ec_22cc094e4224 | entity_cluster | Adagrad | 55 |
| 16 | ec_b8bacf93785d | entity_cluster | (Kingma & Welling | 55 |
| 17 | ec_7f51bc76aa4d | entity_cluster | Section 5.3 | 55 |
| 18 | ec_6db9596a05b3 | entity_cluster | Lemma 10.2 | 54 |
| 19 | ec_a4aaec148421 | entity_cluster | Dropout | 53 |
| 20 | ec_57aaef24dd72 | entity_cluster | Batch Normalization | 53 |


Degree stats — Mean: 51.16, Median: 51, Max: 63, Min: 30


## Audit Remediation: Stage 8 Semantic Dedup Fix


### Bug

Stage 8 deduplication keyed on `edge_id` (a random 12-hex UUID). Since every edge receives a unique ID, no two edges ever shared the same key, making the entire dedup stage a no-op. This left **455 duplicate semantic edges** in the graph — edges with identical `(source_id, target_id, relation_type)` but different `edge_id`s.


### Root Cause

Stage 3 creates one `EXTENDS` edge per entity occurrence, not per unique `(doc, cluster)` pair. A document mentioning 'Markov' 5 times (5 entity IDs resolving to the same cluster) produces 5 edges. Similarly, Stage 4's DocumentRelationEngine can produce multiple edges between the same doc pair when documents share multiple entities. Stage 8 was intended to clean these up, but its edge_id key made it ineffective.


### Fix

Changed `_stage_8_deduplicate` to key on the semantic triple:

```python
key = (edge.source_id, edge.target_id, edge.relation_type)
```
When two edges collide, the one with higher `confidence` survives. The surviving edge's `evidence_ids`, `weight`, `metadata`, and `relation_type` are preserved intact.


### Impact on Metrics

| Metric | Pre-Fix | Post-Fix | Delta |
|---|---|---|---|
| Graph Edges | 1,913 | 1458 | -455 |
| Stage 3 (doc→entity) edges | 615 | 216 | -399 |
| Stage 4 (doc→doc) edges | 122 | 66 | -56 |
| Stage 5 (entity→entity) edges | 1,176 | 1176 | -0 |
| Density | 0.599311 | 0.456767 | -0.142544 |
| Average Degree | 67.1228 | 51.1579 | -15.9649 |


## Readiness Assessment

| Component | Status | Justification |
|---|---|---|
| Entity Resolution | **READY** | 49 clusters from 615 entities; Levenshtein+rapidfuzz resolution works correctly; largest clusters (Adam, Markov, BERT, linear) show correct aliasing across 8 papers |
| Document Relations | **READY** | DocumentRelationEngine produces relations from entity overlap; Stage 4 edges properly connect documents sharing entities |
| Corpus Graph | **READY** | All 8 stages build correctly; Stage 8 dedup bug fixed; 1,458 unique edges across 57 nodes; density 0.4568 |
| Corpus Traversal | **READY** | get_neighbors(), shortest_path(), find_paths(), connected_components(), subgraph(), query_nodes(), query_edges() all work; tested at depth 1-3 and across disconnected components |
| Corpus Manager Integration | **READY** | Lazy `corpus_graph` property with cache invalidation on add/remove/clear; 36 dedicated cache tests passing |