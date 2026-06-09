# ResearchMind Module 1 Evaluation Report

Evaluation date: 2026-06-06

## Scope

This evaluation ran Module 1 on eight real open-access research papers spanning NLP, computer vision, optimization, generative modeling, biomedical image segmentation, and neural-network regularization.

The evaluated path was:

PDF -> GROBID -> TEI -> Section Normalization -> Chunking -> SRO

## Evaluation Constraints

- No application code was modified.
- GROBID was reachable at `http://localhost:8070/api/isalive`.
- A local evaluation-only dependency target was used: `.eval_deps`.
- SRO outputs were written to `eval_output/sro`.
- CrossRef resolution was disabled for this run because the local bundled Python runtime triggered an OpenSSL linkage error when exercising HTTP client libraries.
- spaCy model `en_core_web_sm` was not installed, so spaCy NER was skipped and entity extraction relied on custom pattern matching.
- NLTK sentence tokenization was replaced by an evaluation-only regex tokenizer to avoid runtime data/download issues in the bundled Python environment.
- GROBID posting used an evaluation-only raw localhost socket transport because the bundled Python `httpx` runtime hit the same OpenSSL linkage issue. This did not change ResearchMind source code.

## Paper Set

| PDF | Paper | Source |
| --- | --- | --- |
| `1406.2661_gan.pdf` | Generative Adversarial Nets | https://arxiv.org/abs/1406.2661 |
| `1412.6980_adam.pdf` | Adam: A Method for Stochastic Optimization | https://arxiv.org/abs/1412.6980 |
| `1502.03167_batchnorm.pdf` | Batch Normalization | https://arxiv.org/abs/1502.03167 |
| `1505.04597_unet.pdf` | U-Net | https://arxiv.org/abs/1505.04597 |
| `1512.03385_resnet.pdf` | Deep Residual Learning for Image Recognition | https://arxiv.org/abs/1512.03385 |
| `1706.03762_attention.pdf` | Attention Is All You Need | https://arxiv.org/abs/1706.03762 |
| `1810.04805_bert.pdf` | BERT | https://arxiv.org/abs/1810.04805 |
| `dropout_jmlr.pdf` | Dropout: A Simple Way to Prevent Neural Networks from Overfitting | https://jmlr.org/papers/v15/srivastava14a.html |

## Aggregate Results

- Papers processed: 8/8
- SROs generated: 8/8
- Validation-error-free SROs: 8/8
- GROBID primary route: 7/8
- GROBID with fallback route: 1/8
- Mean confidence: 0.7621
- Median confidence: 0.8392
- Total sections: 146
- Total chunks: 213
- Total references: 253
- Total citations: 442
- Total entities: 458
- Total claims: 238

## Per-Paper Results

| PDF | Route | Confidence | Manual Review | Sections | Chunks | Refs | Citations | Notes |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| `1406.2661_gan.pdf` | `grobid_primary` | 0.7993 | No | 10 | 13 | 31 | 40 | Clean run |
| `1412.6980_adam.pdf` | `grobid_primary` | 0.7958 | No | 14 | 20 | 23 | 31 | One section without chunks |
| `1502.03167_batchnorm.pdf` | `grobid_with_fallback` | 0.2334 | Yes | 6 | 34 | 0 | 0 | GROBID connection reset, PyMuPDF fallback |
| `1505.04597_unet.pdf` | `grobid_primary` | 0.8765 | No | 6 | 11 | 14 | 23 | Clean run |
| `1512.03385_resnet.pdf` | `grobid_primary` | 0.8538 | No | 18 | 27 | 50 | 135 | Two header-only/no-chunk sections |
| `1706.03762_attention.pdf` | `grobid_primary` | 0.8373 | No | 24 | 25 | 41 | 58 | Clean run |
| `1810.04805_bert.pdf` | `grobid_primary` | 0.8411 | No | 27 | 35 | 58 | 92 | One appendix subsection without chunks |
| `dropout_jmlr.pdf` | `grobid_primary` | 0.8600 | No | 41 | 48 | 36 | 63 | Clean run |

## Observed Failure Modes

### 1. GROBID Transport Failure Causes Severe Metadata Loss

The BatchNorm paper encountered a GROBID connection reset:

`[WinError 10054] An existing connection was forcibly closed by the remote host`

The pipeline recovered with PyMuPDF fallback, but the SRO lost title, authors, abstract, references, citations, tables, and figures. This produced:

- title: `Untitled`
- authors: 0
- abstract words: 0
- references: 0
- citations: 0
- confidence: 0.2334
- manual review: true

Impact: the pipeline remains operational, but fallback output is not a faithful SRO for scientific-paper ingestion.

### 2. Fallback Extraction Is Structurally Useful But Bibliographically Incomplete

PyMuPDF fallback produced body text and chunks for BatchNorm, but not bibliographic metadata or citation graph structure. This is expected from the current fallback extractor.

Impact: fallback SROs should be treated as partial text-only records.

### 3. Section Normalization Overuses `other`

Several GROBID-primary papers had many sections classified as `other`, especially appendices, technical subsections, numbered method details, and experiment subheaders.

Examples:

- BERT: 20 of 27 sections were `other`
- Attention: 15 of 24 sections were `other`
- Dropout: 29 of 41 sections were `other`

Impact: downstream section-aware retrieval or claim weighting will be less precise.

### 4. Header-Only Sections Produce Validation Warnings

Some sections had no associated chunks:

- Adam: `EXTENSIONS`
- ResNet: `Deep Residual Learning`, `Experiments`
- BERT: `C Additional Ablation Studies`
- BatchNorm fallback: `Appendix`

Impact: not a schema blocker, but it indicates section nodes can be created from headings without body text, which can create sparse or misleading section structure.

### 5. Reference Resolution Is Incomplete Without CrossRef

CrossRef was disabled in this run. GROBID-consolidated DOI resolution still resolved some references, but most references remained unresolved.

Observed resolved reference counts:

- Adam: 2/23
- U-Net: 4/14
- BERT: 15/58
- Attention: 5/41
- ResNet: 15/50
- GAN: 8/31
- Dropout: 14/36

Impact: SRO reference lists exist, but canonical identifiers are incomplete.

### 6. Citation Linking Is Strong But Not Perfect

Most GROBID-primary papers linked citations successfully, but some were unlinked:

- BERT: 77/92 linked
- Adam: 29/31 linked
- U-Net: 22/23 linked
- ResNet: 133/135 linked
- Dropout: 62/63 linked

Impact: the citation graph is generally usable, but some citation edges are missing.

### 7. Enrichment Quality Depends On Missing Runtime Models

The configured spaCy model was unavailable, so spaCy NER was skipped. Entity extraction still ran using patterns.

Impact: entity counts in this report are not representative of full NER quality.

### 8. Tables And Figures Depend Heavily On GROBID

GROBID-primary papers extracted table/figure metadata, while the fallback BatchNorm run produced zero tables and figures.

Impact: fallback route loses non-text scientific objects.

## Readiness Assessment

Module 1 is ready for broader GROBID-primary integration testing on born-digital PDFs. Seven of eight real papers completed through `grobid_primary`, all eight produced valid SRO JSON, and no generated SRO had validation errors.

The main readiness caveat is operational: GROBID transport stability matters. When GROBID fails mid-request, the pipeline recovers but produces a materially incomplete fallback SRO.

## Recommended Next Evaluation Pass

1. Run the same corpus from a clean Python environment where `httpx` works normally.
2. Enable CrossRef and measure reference-resolution improvement.
3. Install the configured spaCy model and rerun enrichment.
4. Add 2-3 scanned PDFs to intentionally exercise OCR routing.
5. Re-run BatchNorm to determine whether the GROBID reset was transient or paper-specific.
