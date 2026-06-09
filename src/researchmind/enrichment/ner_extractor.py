"""Named-entity recognition extractor for the enrichment pipeline stage.

Provides lazy-loaded spaCy / ScispaCy NER plus custom regex+dictionary
pattern matching for domain-specific entity types (datasets, metrics,
tools, methods).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from researchmind.models.enums import EntityLabel
from researchmind.models.intermediates import NERConfig
from researchmind.models.sro import SROChunk, SROEntity

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# spaCy label → EntityLabel mapping
# ---------------------------------------------------------------------------
_SPACY_LABEL_MAP: dict[str, EntityLabel] = {
    "ORG": EntityLabel.ORGANIZATION,
    "PERSON": EntityLabel.PERSON,
    "GPE": EntityLabel.LOCATION,
    "LOC": EntityLabel.LOCATION,
    "NORP": EntityLabel.ORGANIZATION,
    "FAC": EntityLabel.LOCATION,
    "PRODUCT": EntityLabel.TOOL,
    "WORK_OF_ART": EntityLabel.OTHER,
    "EVENT": EntityLabel.OTHER,
    "LAW": EntityLabel.OTHER,
    "LANGUAGE": EntityLabel.OTHER,
}

# ScispaCy label → EntityLabel mapping
_SCISPACY_LABEL_MAP: dict[str, EntityLabel] = {
    "DISEASE": EntityLabel.DISEASE,
    "CHEMICAL": EntityLabel.DRUG,
    "SIMPLE_CHEMICAL": EntityLabel.DRUG,
    "GGP": EntityLabel.GENE_PROTEIN,
    "GENE_OR_GENE_PRODUCT": EntityLabel.GENE_PROTEIN,
    "SO": EntityLabel.OTHER,
    "TAXON": EntityLabel.ORGANISM,
    "ORGANISM": EntityLabel.ORGANISM,
    "CELL_TYPE": EntityLabel.MATERIAL,
    "CELL_LINE": EntityLabel.MATERIAL,
    "DNA": EntityLabel.GENE_PROTEIN,
    "RNA": EntityLabel.GENE_PROTEIN,
    "PROTEIN": EntityLabel.GENE_PROTEIN,
    "CANCER": EntityLabel.DISEASE,
    "ORGAN": EntityLabel.MATERIAL,
    "TISSUE": EntityLabel.MATERIAL,
    "AMINO_ACID": EntityLabel.MATERIAL,
}

# ---------------------------------------------------------------------------
# Known dictionaries for custom pattern matching
# ---------------------------------------------------------------------------
_KNOWN_DATASETS: set[str] = {
    "ImageNet", "MNIST", "CIFAR", "CIFAR-10", "CIFAR-100", "COCO",
    "MS COCO", "WMT", "SQuAD", "GLUE", "SuperGLUE", "MNLI", "SST",
    "SST-2", "QQP", "QNLI", "MRPC", "RTE", "WNLI", "CoLA",
    "Penn Treebank", "SNLI", "MultiNLI", "Visual Genome", "Open Images",
    "Pascal VOC", "Cityscapes", "ADE20K", "LVIS", "Flickr30k",
    "Flickr8k", "MS MARCO", "Natural Questions", "TriviaQA",
    "HotpotQA", "WikiQA", "WebQuestions", "DROP", "CoQA",
    "CommonsenseQA", "HellaSwag", "WinoGrande", "ARC", "RACE",
    "BoolQ", "PIQA", "SWAG", "AG News", "IMDB", "Yelp",
    "Amazon Reviews", "DBpedia", "Yahoo Answers", "CommonCrawl",
    "BookCorpus", "WikiText", "WikiText-103", "C4", "The Pile",
    "RedPajama", "LAION", "LAION-5B", "CC-12M", "WebText",
    "OpenWebText", "LibriSpeech", "CommonVoice", "VoxCeleb",
}

_KNOWN_METRICS: set[str] = {
    "BLEU", "ROUGE", "ROUGE-L", "ROUGE-1", "ROUGE-2", "METEOR",
    "F1", "F1-score", "accuracy", "precision", "recall",
    "AUC", "AUC-ROC", "AUC-PR", "mAP", "AP",
    "perplexity", "IoU", "mIoU", "RMSE", "MAE", "MSE",
    "PSNR", "SSIM", "FID", "IS", "Inception Score",
    "CIDEr", "SPICE", "WER", "CER", "TER", "NIST",
    "BERTScore", "MoverScore", "COMET", "chrF", "SacreBLEU",
    "top-1 accuracy", "top-5 accuracy", "mean accuracy",
    "micro-F1", "macro-F1", "weighted-F1",
    "Pearson", "Spearman", "Cohen's kappa", "Matthews correlation",
    "log-loss", "cross-entropy", "Dice", "Dice coefficient",
    "sensitivity", "specificity", "PPV", "NPV",
    "R-squared", "R²", "adjusted R²",
    "NDCG", "MRR", "Hit Rate", "MAP", "Recall@K",
}

_KNOWN_TOOLS: set[str] = {
    "TensorFlow", "PyTorch", "scikit-learn", "sklearn", "Keras",
    "JAX", "Flax", "Hugging Face", "HuggingFace", "Transformers",
    "NLTK", "spaCy", "OpenCV", "R", "SPSS", "MATLAB",
    "Stata", "SAS", "Mathematica", "Caffe", "Caffe2", "MXNet",
    "PaddlePaddle", "Theano", "ONNX", "TensorRT", "CoreML",
    "DeepSpeed", "Megatron", "Ray", "Dask", "Spark",
    "Apache Spark", "Hadoop", "Flink", "Airflow",
    "MLflow", "Weights & Biases", "WandB", "Neptune",
    "DVC", "Kubeflow", "Docker", "Kubernetes",
    "NumPy", "SciPy", "Pandas", "Matplotlib", "Seaborn",
    "Plotly", "Bokeh", "Gensim", "FastText", "Word2Vec",
    "GloVe", "ELMo", "BERT", "GPT", "GPT-2", "GPT-3", "GPT-4",
    "LLaMA", "PaLM", "Gemini", "Claude", "Mistral",
    "CUDA", "cuDNN", "OpenCL", "Triton",
    "Jupyter", "Colab", "Google Colab", "Anaconda",
    "Git", "GitHub", "GitLab", "Bitbucket",
    "AWS", "GCP", "Azure", "Lambda",
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch",
    "Neo4j", "NetworkX", "igraph",
    "StanfordNLP", "Stanza", "AllenNLP", "Fairseq",
    "Detectron2", "YOLO", "YOLOv5", "YOLOv8",
    "Stable Diffusion", "DALL-E", "Midjourney",
    "LangChain", "LlamaIndex", "Pinecone", "Weaviate", "ChromaDB",
}

# Regex for dataset detection: capitalized name followed by dataset-related words
_DATASET_PATTERN = re.compile(
    r"\b([A-Z][A-Za-z0-9\-]*(?:\s+[A-Z][A-Za-z0-9\-]*)*)"
    r"\s+(?:dataset|corpus|corpora|benchmark|testbed|test\s*set|training\s*set)\b",
    re.IGNORECASE,
)

# Regex for method detection: capitalized multi-word name preceded by keywords
_METHOD_PATTERN = re.compile(
    r"(?:using|propose|proposed|present|presents|based\s+on|introduce|introduces|employ|employs)"
    r"\s+(?:a\s+|an\s+|the\s+)?"
    r"([A-Z][A-Za-z0-9\-]*(?:[\s\-]+[A-Z][A-Za-z0-9\-]*)+)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Module-level cache for lazy-loaded NLP models
# ---------------------------------------------------------------------------
_nlp_cache: dict[str, Any] = {}


def _load_spacy_model(model_name: str) -> Any | None:
    """Lazy-load a spaCy model, returning None on failure.

    Caches the model so subsequent calls are instant.
    """
    if model_name in _nlp_cache:
        return _nlp_cache[model_name]

    try:
        import spacy  # type: ignore[import-untyped]

        nlp = spacy.load(model_name)
        _nlp_cache[model_name] = nlp
        logger.info("Loaded spaCy model '%s'", model_name)
        return nlp
    except ImportError:
        logger.warning("spaCy is not installed — NER extraction will be skipped")
        return None
    except OSError:
        logger.warning(
            "spaCy model '%s' not found — will try fallback", model_name
        )
        return None


def _sentence_for_span(doc_text: str, char_start: int, char_end: int) -> str:
    """Extract the containing sentence for a character span.

    Uses a simple heuristic: walk backwards/forwards to find sentence
    boundaries (period + space or newline).
    """
    # Walk backwards to find sentence start
    sent_start = char_start
    while sent_start > 0:
        ch = doc_text[sent_start - 1]
        if ch == "\n":
            break
        if ch == "." and sent_start >= 2 and doc_text[sent_start - 2] != ".":
            # Don't break on ellipsis or abbreviations like "e.g."
            break
        sent_start -= 1

    # Walk forward to find sentence end
    sent_end = char_end
    text_len = len(doc_text)
    while sent_end < text_len:
        ch = doc_text[sent_end]
        if ch in (".", "!", "?"):
            sent_end += 1  # include the punctuation
            break
        if ch == "\n":
            break
        sent_end += 1

    return doc_text[sent_start:sent_end].strip()


def _determine_model_confidence(model_name: str) -> float:
    """Return a default confidence based on the model type.

    spaCy does not provide per-entity confidence scores, so we assign
    fixed values reflecting empirical model quality.
    """
    if "trf" in model_name:
        return 0.85
    if "sci" in model_name:
        return 0.70
    # sm, md, lg non-transformer models
    return 0.75


def _extract_spacy_entities(
    chunks: list[SROChunk],
    model_name: str,
    label_map: dict[str, EntityLabel],
    source_tag: str,
    counter: list[int],
) -> list[SROEntity]:
    """Run a spaCy/ScispaCy model over chunks and return SROEntity objects."""
    nlp = _load_spacy_model(model_name)
    if nlp is None:
        return []

    confidence = _determine_model_confidence(model_name)
    entities: list[SROEntity] = []

    for chunk in chunks:
        try:
            doc = nlp(chunk.text)
        except Exception:
            logger.warning(
                "spaCy processing failed for chunk '%s' — skipping",
                chunk.chunk_id,
                exc_info=True,
            )
            continue

        for ent in doc.ents:
            mapped_label = label_map.get(ent.label_)
            if mapped_label is None:
                continue

            # Skip very short entities (likely noise)
            if len(ent.text.strip()) < 2:
                continue

            counter[0] += 1
            sentence = _sentence_for_span(chunk.text, ent.start_char, ent.end_char)

            entities.append(
                SROEntity(
                    entity_id=f"ent_{counter[0]:03d}",
                    text=ent.text.strip(),
                    label=mapped_label,
                    chunk_id=chunk.chunk_id,
                    sentence=sentence,
                    confidence=confidence,
                    source=source_tag,
                )
            )

    return entities


def _extract_custom_pattern_entities(
    chunks: list[SROChunk],
    counter: list[int],
) -> list[SROEntity]:
    """Run custom regex and dictionary patterns over chunks."""
    entities: list[SROEntity] = []
    pattern_confidence = 0.60

    for chunk in chunks:
        text = chunk.text

        # --- Dataset detection: dictionary ---
        for ds_name in _KNOWN_DATASETS:
            # Use word-boundary matching for known datasets
            try:
                pattern = re.compile(r"\b" + re.escape(ds_name) + r"\b")
            except re.error:
                continue
            for match in pattern.finditer(text):
                counter[0] += 1
                sentence = _sentence_for_span(text, match.start(), match.end())
                entities.append(
                    SROEntity(
                        entity_id=f"ent_{counter[0]:03d}",
                        text=match.group(),
                        label=EntityLabel.DATASET,
                        chunk_id=chunk.chunk_id,
                        sentence=sentence,
                        confidence=pattern_confidence,
                        source="pattern_match",
                    )
                )

        # --- Dataset detection: regex pattern ---
        for match in _DATASET_PATTERN.finditer(text):
            candidate = match.group(1).strip()
            # Avoid duplicating known datasets already captured
            if candidate in _KNOWN_DATASETS:
                continue
            # Must be at least 2 characters
            if len(candidate) < 2:
                continue
            counter[0] += 1
            sentence = _sentence_for_span(text, match.start(), match.end())
            entities.append(
                SROEntity(
                    entity_id=f"ent_{counter[0]:03d}",
                    text=candidate,
                    label=EntityLabel.DATASET,
                    chunk_id=chunk.chunk_id,
                    sentence=sentence,
                    confidence=pattern_confidence,
                    source="pattern_match",
                )
            )

        # --- Metric detection: dictionary ---
        for metric_name in _KNOWN_METRICS:
            try:
                pattern = re.compile(r"\b" + re.escape(metric_name) + r"\b")
            except re.error:
                continue
            for match in pattern.finditer(text):
                counter[0] += 1
                sentence = _sentence_for_span(text, match.start(), match.end())
                entities.append(
                    SROEntity(
                        entity_id=f"ent_{counter[0]:03d}",
                        text=match.group(),
                        label=EntityLabel.METRIC,
                        chunk_id=chunk.chunk_id,
                        sentence=sentence,
                        confidence=pattern_confidence,
                        source="pattern_match",
                    )
                )

        # --- Tool detection: dictionary ---
        for tool_name in _KNOWN_TOOLS:
            try:
                pattern = re.compile(r"\b" + re.escape(tool_name) + r"\b")
            except re.error:
                continue
            for match in pattern.finditer(text):
                counter[0] += 1
                sentence = _sentence_for_span(text, match.start(), match.end())
                entities.append(
                    SROEntity(
                        entity_id=f"ent_{counter[0]:03d}",
                        text=match.group(),
                        label=EntityLabel.TOOL,
                        chunk_id=chunk.chunk_id,
                        sentence=sentence,
                        confidence=pattern_confidence,
                        source="pattern_match",
                    )
                )

        # --- Method detection: regex ---
        for match in _METHOD_PATTERN.finditer(text):
            candidate = match.group(1).strip()
            if len(candidate) < 3:
                continue
            # Avoid capturing known tools/datasets as methods
            if candidate in _KNOWN_TOOLS or candidate in _KNOWN_DATASETS:
                continue
            counter[0] += 1
            sentence = _sentence_for_span(text, match.start(), match.end())
            entities.append(
                SROEntity(
                    entity_id=f"ent_{counter[0]:03d}",
                    text=candidate,
                    label=EntityLabel.METHOD,
                    chunk_id=chunk.chunk_id,
                    sentence=sentence,
                    confidence=pattern_confidence,
                    source="pattern_match",
                )
            )

    return entities


def _deduplicate_entities(entities: list[SROEntity]) -> list[SROEntity]:
    """Remove duplicate entities in the same chunk with the same text & label.

    Keeps the entity with the highest confidence.
    """
    seen: dict[tuple[str, str, str], SROEntity] = {}
    for ent in entities:
        key = (ent.chunk_id, ent.text.lower(), ent.label.value)
        existing = seen.get(key)
        if existing is None or ent.confidence > existing.confidence:
            seen[key] = ent

    # Re-number to keep IDs contiguous
    result: list[SROEntity] = []
    for idx, ent in enumerate(seen.values(), start=1):
        result.append(
            ent.model_copy(update={"entity_id": f"ent_{idx:03d}"})
        )
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_entities(
    chunks: list[SROChunk],
    config: NERConfig,
) -> list[SROEntity]:
    """Extract named entities from text chunks using NER models and patterns.

    Parameters
    ----------
    chunks:
        Paragraph-level text chunks from the structured body.
    config:
        NER configuration controlling model selection and feature flags.

    Returns
    -------
    list[SROEntity]
        Extracted entities with globally unique IDs (ent_001 …).
        Returns an empty list (with a warning) if no NER model can be loaded
        and custom patterns are disabled.
    """
    if not chunks:
        logger.info("No chunks provided — skipping NER extraction")
        return []

    # Mutable counter shared across helpers so IDs are globally unique
    counter: list[int] = [0]
    all_entities: list[SROEntity] = []

    # --- General spaCy model ---
    primary_model = config.general_model
    nlp = _load_spacy_model(primary_model)
    if nlp is None and primary_model != "en_core_web_sm":
        logger.info("Trying fallback model 'en_core_web_sm'")
        primary_model = "en_core_web_sm"
        nlp = _load_spacy_model(primary_model)

    if nlp is not None:
        general_ents = _extract_spacy_entities(
            chunks, primary_model, _SPACY_LABEL_MAP, "spacy", counter
        )
        all_entities.extend(general_ents)
        logger.info(
            "General NER (%s) extracted %d entities", primary_model, len(general_ents)
        )
    else:
        logger.warning(
            "No general spaCy model available — spaCy NER will be skipped"
        )

    # --- Biomedical ScispaCy model (optional) ---
    if config.enable_biomedical:
        bio_model = config.biomedical_model
        bio_nlp = _load_spacy_model(bio_model)
        if bio_nlp is not None:
            bio_ents = _extract_spacy_entities(
                chunks, bio_model, _SCISPACY_LABEL_MAP, "scispacy", counter
            )
            all_entities.extend(bio_ents)
            logger.info(
                "Biomedical NER (%s) extracted %d entities",
                bio_model,
                len(bio_ents),
            )
        else:
            logger.warning(
                "ScispaCy model '%s' not available — biomedical NER skipped",
                bio_model,
            )

    # --- Custom pattern matching ---
    if config.enable_custom_patterns:
        pattern_ents = _extract_custom_pattern_entities(chunks, counter)
        all_entities.extend(pattern_ents)
        logger.info("Pattern matching extracted %d entities", len(pattern_ents))

    if not all_entities:
        logger.warning("NER extraction produced zero entities")
        return []

    # Deduplicate and re-number
    deduped = _deduplicate_entities(all_entities)
    logger.info(
        "NER extraction complete: %d entities after deduplication (from %d raw)",
        len(deduped),
        len(all_entities),
    )
    return deduped
