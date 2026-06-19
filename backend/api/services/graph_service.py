from typing import Optional
from researchmind.storage.corpus import CorpusManager
from backend.api.schemas.graph import (
    GraphDataResponse,
    GraphNodeResponse,
    GraphNodeData,
    GraphEdgeResponse,
    GraphEdgeData,
)


class GraphService:
    def __init__(self, corpus_manager):
        self._corpus_manager = corpus_manager

    def _store_available(self) -> bool:
        mgr = self._corpus_manager
        if mgr is None:
            return False
        if not hasattr(mgr, "store"):
            return False
        return mgr.store is not None

    def _build_graph(
        self,
        node_type: Optional[str] = None,
        search: Optional[str] = None,
        offset: int = 0,
        limit: int = 200,
    ) -> GraphDataResponse:
        if not self._store_available():
            return GraphDataResponse(nodes=[], edges=[])

        all_docs = self._corpus_manager.get_documents()
        if not all_docs:
            return GraphDataResponse(nodes=[], edges=[])

        nodes = []
        edges = []
        search_lower = search.lower() if search else None

        for i, doc in enumerate(all_docs):
            if search_lower and search_lower not in doc.header.title.lower():
                continue

            doc_id = f"doc-{i}"
            col = i % 10
            row = i // 10

            author_names = [a.full_name for a in doc.header.authors or []]
            pub_year = None
            if doc.header.publication_date:
                try:
                    pub_year = int(doc.header.publication_date[:4])
                except (ValueError, TypeError):
                    pass

            nodes.append(
                GraphNodeResponse(
                    id=doc_id,
                    type="document",
                    position={"x": float(col * 220 + 100), "y": float(row * 180 + 100)},
                    data=GraphNodeData(
                        label=doc.header.title,
                        type="document",
                        title=doc.header.title,
                        year=pub_year,
                        authors=author_names,
                    ),
                )
            )

            for j, entity in enumerate(doc.entities or []):
                if not entity.text.strip():
                    continue
                ent_id = f"ent-{i}-{j}"

                nodes.append(
                    GraphNodeResponse(
                        id=ent_id,
                        type="entity",
                        position={
                            "x": float(col * 220 + 140 + (j % 3) * 30),
                            "y": float(row * 180 + 130 + (j // 3) * 30),
                        },
                        data=GraphNodeData(
                            label=entity.text,
                            type="entity",
                            confidence=entity.confidence,
                            relatedDocuments=1,
                        ),
                    )
                )

                edges.append(
                    GraphEdgeResponse(
                        id=f"edge-{ent_id}-{doc_id}",
                        source=ent_id,
                        target=doc_id,
                        type="customEdge",
                        data=GraphEdgeData(
                            type="CO_OCCURS",
                            confidence=entity.confidence,
                        ),
                    )
                )

        if node_type == "document":
            nodes = [n for n in nodes if n.type == "document"]
        elif node_type == "entity":
            nodes = [n for n in nodes if n.type == "entity"]

        paginated_nodes = nodes[offset : offset + limit]
        visible_ids = {n.id for n in paginated_nodes}
        paginated_edges = [
            e for e in edges if e.source in visible_ids and e.target in visible_ids
        ]

        return GraphDataResponse(nodes=paginated_nodes, edges=paginated_edges)

    def get_graph(
        self,
        node_type: Optional[str] = None,
        search: Optional[str] = None,
        offset: int = 0,
        limit: int = 200,
    ) -> GraphDataResponse:
        return self._build_graph(
            node_type=node_type,
            search=search,
            offset=offset,
            limit=limit,
        )

    def get_node(self, node_id: str) -> Optional[GraphNodeResponse]:
        if not self._store_available():
            return None

        all_docs = self._corpus_manager.get_documents()

        if node_id.startswith("doc-"):
            try:
                idx = int(node_id[4:])
            except ValueError:
                return None
            if 0 <= idx < len(all_docs):
                doc = all_docs[idx]
                col = idx % 10
                row = idx // 10
                author_names = [a.full_name for a in doc.header.authors or []]
                pub_year = None
                if doc.header.publication_date:
                    try:
                        pub_year = int(doc.header.publication_date[:4])
                    except (ValueError, TypeError):
                        pass
                return GraphNodeResponse(
                    id=node_id,
                    type="document",
                    position={"x": float(col * 220 + 100), "y": float(row * 180 + 100)},
                    data=GraphNodeData(
                        label=doc.header.title,
                        type="document",
                        title=doc.header.title,
                        year=pub_year,
                        authors=author_names,
                    ),
                )

        elif node_id.startswith("ent-"):
            parts = node_id.split("-")
            if len(parts) >= 3:
                try:
                    doc_idx = int(parts[1])
                    ent_idx = int(parts[2])
                except ValueError:
                    return None
                if 0 <= doc_idx < len(all_docs):
                    doc = all_docs[doc_idx]
                    entities = doc.entities or []
                    if 0 <= ent_idx < len(entities):
                        entity = entities[ent_idx]
                        col = doc_idx % 10
                        row = doc_idx // 10
                        return GraphNodeResponse(
                            id=node_id,
                            type="entity",
                            position={
                                "x": float(col * 220 + 140 + (ent_idx % 3) * 30),
                                "y": float(row * 180 + 130 + (ent_idx // 3) * 30),
                            },
                            data=GraphNodeData(
                                label=entity.text,
                                type="entity",
                                confidence=entity.confidence,
                                relatedDocuments=1,
                            ),
                        )

        return None
