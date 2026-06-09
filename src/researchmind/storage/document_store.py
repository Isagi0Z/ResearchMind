"""Concrete DocumentStore implementations.

Provides two backends for the abstract :class:`DocumentStore` defined in
:mod:`researchmind.models.ruo`:

* :class:`FilesystemDocumentStore` — stores each document as a JSON file.
* :class:`InMemoryDocumentStore` — keeps documents in a dict (useful for
  testing or small corpora).

Both support the full CRUD contract and can be used with :class:`RUOCorpus`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from researchmind.models.ruo import DocumentStore, RUODocument

logger = logging.getLogger(__name__)

_ENCODING = "utf-8"


# -----------------------------------------------------------------------
# InMemoryDocumentStore
# -----------------------------------------------------------------------


class InMemoryDocumentStore(DocumentStore):
    """Document store backed by an in-memory ``dict``.

    Useful for testing, short-lived corpora, or as a cache layer.

    Parameters
    ----------
    docs:
        Optional initial mapping of ``{ruo_id: RUODocument}``.
    """

    def __init__(self, docs: dict[str, RUODocument] | None = None) -> None:
        self._docs: dict[str, RUODocument] = {}
        if docs is not None:
            for ruo_id, doc in docs.items():
                self._validate_key(ruo_id, doc)
            self._docs.update(docs)

    @staticmethod
    def _validate_key(ruo_id: str, doc: RUODocument) -> None:
        if ruo_id != doc.meta.ruo_id:
            raise ValueError(
                f"Key '{ruo_id}' does not match document.meta.ruo_id "
                f"'{doc.meta.ruo_id}'"
            )

    # -- CRUD ----------------------------------------------------------

    def get(self, ruo_id: str) -> RUODocument | None:
        return self._docs.get(ruo_id)

    def get_batch(self, ruo_ids: list[str]) -> dict[str, RUODocument]:
        return {rid: self._docs[rid] for rid in ruo_ids if rid in self._docs}

    def put(self, doc: RUODocument) -> None:
        self._docs[doc.meta.ruo_id] = doc

    def delete(self, ruo_id: str) -> bool:
        return self._docs.pop(ruo_id, None) is not None

    def contains(self, ruo_id: str) -> bool:
        return ruo_id in self._docs

    def list_ids(self) -> list[str]:
        return list(self._docs.keys())

    def count(self) -> int:
        return len(self._docs)


# -----------------------------------------------------------------------
# FilesystemDocumentStore
# -----------------------------------------------------------------------


class FilesystemDocumentStore(DocumentStore):
    """Document store backed by individual JSON files on the filesystem.

    Each document is serialised as ``{directory}/{ruo_id}.json``.
    Documents are deserialised lazily (on ``get`` / ``get_batch``).

    Parameters
    ----------
    directory:
        Path to the directory holding (or to hold) document JSON files.
        Created automatically if it does not exist.
    """

    def __init__(self, directory: str | Path) -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)
        logger.info("FilesystemDocumentStore initialised at %s", self._dir)

    # -- helpers -------------------------------------------------------

    def _path_for(self, ruo_id: str) -> Path:
        return (self._dir / ruo_id).with_suffix(".json")

    def _load(self, path: Path) -> RUODocument | None:
        try:
            raw = path.read_text(encoding=_ENCODING)
            data: dict[str, Any] = json.loads(raw)
            return RUODocument(**data)
        except FileNotFoundError:
            return None
        except Exception:
            logger.exception("Failed to load document from %s", path)
            return None

    # -- CRUD ----------------------------------------------------------

    def get(self, ruo_id: str) -> RUODocument | None:
        path = self._path_for(ruo_id)
        if not path.exists():
            return None
        return self._load(path)

    def get_batch(self, ruo_ids: list[str]) -> dict[str, RUODocument]:
        result: dict[str, RUODocument] = {}
        for rid in ruo_ids:
            doc = self.get(rid)
            if doc is not None:
                result[rid] = doc
        return result

    def put(self, doc: RUODocument) -> None:
        path = self._path_for(doc.meta.ruo_id)
        raw = doc.model_dump_json(indent=2)
        path.write_text(raw, encoding=_ENCODING)
        logger.debug("Stored document %s (%d bytes)", doc.meta.ruo_id, len(raw))

    def delete(self, ruo_id: str) -> bool:
        path = self._path_for(ruo_id)
        if not path.exists():
            return False
        path.unlink()
        logger.debug("Deleted document %s", ruo_id)
        return True

    def contains(self, ruo_id: str) -> bool:
        return self._path_for(ruo_id).exists()

    def list_ids(self) -> list[str]:
        return sorted(
            p.stem for p in self._dir.glob("*.json")
        )

    def count(self) -> int:
        return len(list(self._dir.glob("*.json")))
