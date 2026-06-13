# Repository Audit for M1-M6

## M1 Extraction Engine
* Import Path: `researchmind.extraction`, `researchmind.structuring`
* Primary Entry Points: `grobid_client.py`, `ocr_extractor.py`, `pymupdf_extractor.py`, `tei_parser.py`, `chunker.py`
* Public Classes/Functions: Various parsers and extractors.
* Status: **FOUND**

## M2 Entity Resolution
* Import Path: `researchmind.corpus.entity_resolution`, `researchmind.enrichment`
* Primary Entry Points: `entity_resolution.py`, `ner_extractor.py`, `claim_detector.py`
* Public Classes/Functions: Various extractors and entity resolvers.
* Status: **FOUND**

## M3 Corpus Graph
* Import Path: `researchmind.corpus.graph`, `researchmind.understanding.knowledge_graph`
* Primary Entry Points: `graph.py`, `knowledge_graph.py`
* Public Classes/Functions: `CorpusGraph`, `KnowledgeGraph`
* Status: **FOUND**

## M4 Reasoning Engine
* Import Path: Expected `researchmind.reasoning.*`
* Primary Entry Points: N/A
* Public Classes/Functions: N/A
* Status: **NOT FOUND**

## M5 Query System
* Import Path: Expected `researchmind.query.*`
* Primary Entry Points: N/A
* Public Classes/Functions: N/A
* Status: **NOT FOUND**

## M6 Synthesis Engine
* Import Path: Expected `researchmind.synthesis.*`
* Primary Entry Points: N/A
* Public Classes/Functions: N/A
* Status: **NOT FOUND**
