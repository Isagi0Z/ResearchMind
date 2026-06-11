# Corpus Graph Evaluation Report

Generated: 2026-06-11T02:04:33.998170+00:00

## Corpus Summary

| Metric | Value |
|--------|-------|
| Documents | 8 |
| Entity Clusters | 49 |
| Claim Nodes | 0 |
| Graph Nodes | 57 |
| Graph Edges | 1913 |

## Graph Metrics

| Metric | Value |
|--------|-------|
| Connected Components | 1 |
| Largest Component Size | 57 |
| Largest Component Edges | 1913 |
| Average Degree | 67.1228 |
| Average Out-Degree | 33.5614 |
| Average In-Degree | 33.5614 |
| Density | 0.599311 |
| Self-Loops | 0 |
| Average Confidence | 0.8501 |
| Min Confidence | 0.0469 |
| Max Confidence | 1.0 |

## Node Type Distribution

| Type | Count |
|------|-------|
| document | 8 |
| entity_cluster | 49 |

## Relation Distribution

| Relation Type | Count |
|--------------|-------|
| compares_with | 1288 |
| extends | 625 |

## Top Entity Clusters

| Rank | Cluster | Weight |
|------|---------|--------|
| 1 | linear (ec_1d0af0fed96b) | 0.75 |
| 2 | Markov (ec_0b805ca117c1) | 0.75 |
| 3 | Boltzmann (ec_0ae9c08af9fd) | 0.75 |
| 4 | Algorithm 1. (ec_065ce2b988e0) | 0.75 |
| 5 | Algorithm 1 (ec_635a8b03068f) | 0.75 |
| 6 | C(G (ec_0a62ec01d4cc) | 0.75 |
| 7 | TFD (ec_3d1b2e0f9e77) | 0.75 |
| 8 | Gaussians (ec_bf38ce8a30bd) | 0.75 |
| 9 | Table 12 (ec_70ad4ae8f513) | 0.75 |
| 10 | Adam (ec_0a1feb8d6ebc) | 0.75 |

## Top Documents

| Rank | Document | Weight |
|------|----------|--------|
| 1 | Generative Adversarial Nets (ruo_fc175182-dd2b-410f-94c8-9b56826fa335) | 0.85 |
| 2 | ADAM: A METHOD FOR STOCHASTIC OPTIMIZATION (ruo_29e59552-8543-4348-a9c7-3e028f4b7e45) | 0.85 |
| 3 | Batch Normalization: Accelerating Deep Network Training by R (ruo_876bea85-3b91-4147-8da6-88ccb75c1d76) | 0.85 |
| 4 | U-Net: Convolutional Networks for Biomedical Image Segmentat (ruo_25600c88-81a2-47b9-a952-cd52c30e7ada) | 0.85 |
| 5 | Deep Residual Learning for Image Recognition (ruo_8100e111-4b47-4f0f-8107-931c030b9594) | 0.85 |
| 6 | Attention Is All You Need (ruo_2cb56102-a3f8-4f08-a770-f4b8a711f9f1) | 0.85 |
| 7 | BERT: Pre-training of Deep Bidirectional Transformers for La (ruo_6e03217b-83db-40dd-a51e-e874c2eed09f) | 0.85 |
| 8 | Dropout: A Simple Way to Prevent Neural Networks from Overfi (ruo_e003c165-b920-45c6-a13f-957dbffafc15) | 0.85 |

## Top Predicates

| Rank | Predicate | Count |
|------|-----------|-------|
| 1 | compares_with | 1288 |
| 2 | extends | 625 |

## Entity Cluster Details

| Cluster ID | Label | Size | Confidence | Resolution Method |
|------------|-------|------|------------|-------------------|
| ec_5c0010758a13 | BERT | 22 | 0.6 | exact |
| ec_082ec0006c35 | BERT | 11 | 0.75 | exact |
| ec_d14bc483f49d | GPT | 11 | 0.6 | exact |
| ec_0a1feb8d6ebc | Adam | 9 | 0.75 | exact |
| ec_70ad4ae8f513 | Table 12 | 6 | 0.75 | fuzzy |
| ec_fb02b0b8c209 | GLUE | 6 | 0.6 | exact |
| ec_0b805ca117c1 | Markov | 5 | 0.75 | exact |
| ec_ab761c2ffb24 | OpenAI GPT | 5 | 0.75 | exact |
| ec_df2ee259afca | ELMo | 5 | 0.6 | exact |
| ec_8f9122951b6c | MNLI | 5 | 0.6 | exact |
| ec_884f0eba7b35 | ImageNet | 4 | 0.75 | exact |
| ec_6227d1600191 | SQuAD | 4 | 0.6 | exact |
| ec_2f515730db2c | F1 | 4 | 0.6 | exact |
| ec_1d0af0fed96b | linear | 3 | 0.75 | exact |
| ec_00783c7b8fde | CNN | 3 | 0.75 | exact |
| ec_c60d59003a9b | Batch Normalization | 3 | 0.75 | exact |
| ec_ebef4785de2d | ResNet-101 | 3 | 0.75 | exact |
| ec_117ea4e68fb7 | MLM | 3 | 0.75 | exact |
| ec_f3c3c23d7e49 | MNLI | 3 | 0.75 | exact |
| ec_8f6d4c69265a | GLUE | 3 | 0.75 | exact |
| ec_88650f0e4b1f | Transformer | 3 | 0.75 | exact |
| ec_c8312c9d2b19 | R | 3 | 0.6 | exact |
| ec_50487549dbc4 | accuracy | 3 | 0.6 | exact |
| ec_91ac61e206bd | MRPC | 3 | 0.6 | exact |
| ec_0ae9c08af9fd | Boltzmann | 2 | 0.75 | exact |
| ec_065ce2b988e0 | Algorithm 1. | 2 | 0.75 | exact |
| ec_635a8b03068f | Algorithm 1 | 2 | 0.75 | exact |
| ec_0a62ec01d4cc | C(G | 2 | 0.75 | exact |
| ec_3d1b2e0f9e77 | TFD | 2 | 0.75 | exact |
| ec_bf38ce8a30bd | Gaussians | 2 | 0.75 | fuzzy |
| ec_2f304eced655 | ReLU | 2 | 0.75 | exact |
| ec_aa96a385d734 | Adagrad | 2 | 0.75 | exact |
| ec_49e10ae4a65c | (Kingma & Welling | 2 | 0.75 | exact |
| ec_5a70e07c4167 | Section 5.3 | 2 | 0.75 | fuzzy |
| ec_a3dd9b34c8ac | Lemma 10.2 | 2 | 0.75 | exact |
| ec_7e668c120c3e | Dropout | 2 | 0.75 | exact |
| ec_555f596b0dfe | Faster | 2 | 0.75 | exact |
| ec_70676b67e02b | Table 9 | 2 | 0.75 | exact |
| ec_911aa5f50fae | PASCAL VOC 2012 | 2 | 0.75 | fuzzy |
| ec_4306b334e540 | al. | 2 | 0.75 | exact |
| ec_07009889e304 | NSP | 2 | 0.75 | exact |
| ec_0adefce72ac5 | GPT | 2 | 0.75 | exact |
| ec_82661f75e189 | MRPC | 2 | 0.75 | exact |
| ec_031baf615f80 | NER | 2 | 0.75 | exact |
| ec_3511324e30c0 | WordPiece | 2 | 0.75 | exact |
| ec_eb403e62b7c6 | Section 3.1 | 2 | 0.75 | exact |
| ec_241855b6384c | Transformers | 2 | 0.6 | exact |
| ec_d221c0bf4369 | TriviaQA | 2 | 0.6 | exact |
| ec_371284dba749 | QNLI | 2 | 0.6 | exact |

## Document Details

| Document ID | Title | Year | Authors | Entities | Claims |
|-------------|-------|------|---------|----------|--------|
| ruo_2cb56102-a3f8-4f08-a770-f4b8a711f9f1 | Attention Is All You Need | 2023 | Ashish Vaswani, Noam Shazeer | 85 | 0 |
| ruo_6e03217b-83db-40dd-a51e-e874c2eed09f | BERT: Pre-training of Deep Bidirectional Transformers for La | 2019 | Jacob Devlin, Ming-Wei Chang | 355 | 0 |
| ruo_29e59552-8543-4348-a9c7-3e028f4b7e45 | ADAM: A METHOD FOR STOCHASTIC OPTIMIZATION | 2017 | Diederik P Kingma, Jimmy Lei Ba | 120 | 0 |
| ruo_876bea85-3b91-4147-8da6-88ccb75c1d76 | Batch Normalization: Accelerating Deep Network Training by R | 2015 | Sergey Ioffe, Christian Szegedy | 147 | 0 |
| ruo_25600c88-81a2-47b9-a952-cd52c30e7ada | U-Net: Convolutional Networks for Biomedical Image Segmentat | 2015 | Olaf Ronneberger, Philipp Fischer | 61 | 0 |
| ruo_8100e111-4b47-4f0f-8107-931c030b9594 | Deep Residual Learning for Image Recognition | 2015 | Kaiming He, Xiangyu Zhang | 234 | 0 |
| ruo_fc175182-dd2b-410f-94c8-9b56826fa335 | Generative Adversarial Nets | 2014 | Ian J Goodfellow, Jean Pouget-Abadie | 74 | 0 |
| ruo_e003c165-b920-45c6-a13f-957dbffafc15 | Dropout: A Simple Way to Prevent Neural Networks from Overfi | None | Nitish Srivastava, Geoffrey Hinton | 254 | 0 |

## Graph Quality Notes

### Strengths

- Entity resolution correctly clusters shared entities across documents.
- Citation edges are created from document references with resolved target_ruo_id.
- Graph traversal APIs (shortest_path, get_neighbors, find_paths) operate correctly.
- Connected component analysis identifies isolated subgraphs.
- Top entities and documents can be ranked by weight.
- Statistics provide comprehensive graph metrics (density, average degree, etc.).

### Weaknesses

- Density computation caps at 1.0 for multigraphs (multiple edge types between same nodes).
- Entity resolution requires >=2 occurrences of an entity text to form a cluster; singletons remain unresolved and don't appear as graph nodes.
- No entity->entity edges for singleton entities (they must be resolved to a cluster first).
- Graph cache is not serialized; rebuild from scratch on CorpusManager.load().

### Potential Improvements

- Add singleton entity nodes to the graph even when they don't form clusters.
- Serialize the graph cache alongside indexes and statistics in CorpusManager.save/load.
- Add edge weight normalization based on confidence scores.
- Support incremental graph updates (add edges/nodes without full rebuild).
- Add metadata filters for traversal APIs (e.g., filter by year, author, entity type).
- Expose node/edge pagination for large graphs.
