from backend.api.schemas.graph import GraphDataResponse, GraphNodeResponse, GraphEdgeResponse
from backend.api.schemas.monitoring import MonitoringSnapshot, ModuleHealth, PerformanceMetric, QueueJob, ErrorEvent, CorpusStatistic
import math
import zlib

class DeterministicLCG:
    def __init__(self, seed: int):
        self.seed = seed

    def next_float(self) -> float:
        self.seed = (self.seed * 1664525 + 1013904223) % 4294967296
        return self.seed / 4294967296.0

    def next_int(self, min_val: int, max_val: int) -> int:
        return math.floor(self.next_float() * (max_val - min_val + 1)) + min_val

    def next_element(self, arr: list):
        return arr[self.next_int(0, len(arr) - 1)]

def generate_mock_graph(node_count: int = 1000, edge_count: int = 3000) -> GraphDataResponse:
    rng = DeterministicLCG(12345)
    nodes = []
    edges = []

    types = ['entity', 'entity', 'entity', 'document', 'document', 'theme', 'cluster']
    edge_types = ['USES_METHOD', 'COMPARES_WITH', 'SUPPORTS', 'CONTRADICTS', 'REFERENCES', 'CO_OCCURS']
    authors = ['Smith, J.', 'Doe, A.', 'Johnson, M.', 'Williams, K.', 'Brown, C.']
    words = ['Neural', 'Network', 'Quantum', 'Algorithm', 'Analysis', 'Optimization', 'Framework', 'System', 'Data', 'Model', 'Machine', 'Learning', 'Deep', 'Structure', 'Graph', 'Semantic', 'Representation', 'Attention', 'Transformer', 'Language']

    golden_ratio = (1 + math.sqrt(5)) / 2
    angle_increment = math.pi * 2 * golden_ratio

    for i in range(node_count):
        ntype = rng.next_element(types)
        nid = f"node-{i}"

        radius = math.sqrt(i) * 60
        angle = i * angle_increment
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)

        data = {
            "label": f"{rng.next_element(words)} {rng.next_element(words)}",
            "type": ntype
        }

        if ntype == 'entity':
            data["confidence"] = round(rng.next_float(), 2)
            data["relatedDocuments"] = rng.next_int(1, 50)
        elif ntype == 'document':
            data["title"] = f"A Novel Approach to {rng.next_element(words)} {rng.next_element(words)}"
            data["year"] = rng.next_int(2010, 2026)
            data["authors"] = [rng.next_element(authors), rng.next_element(authors)]
        elif ntype == 'cluster':
            data["size"] = rng.next_int(5, 150)
            data["containedEntities"] = [rng.next_element(words), rng.next_element(words)]
            data["label"] = f"{rng.next_element(words)} Cluster"
        elif ntype == 'theme':
            data["label"] = f"{rng.next_element(words)} Theme"

        nodes.append(GraphNodeResponse(
            id=nid,
            type=ntype,
            position={"x": x, "y": y},
            data=data
        ))

    for i in range(edge_count):
        source_index = math.floor(pow(rng.next_float(), 2) * node_count)
        target_index = math.floor(rng.next_float() * node_count)

        if source_index == target_index:
            continue

        source = nodes[source_index].id
        target = nodes[target_index].id

        edges.append(GraphEdgeResponse(
            id=f"edge-{i}",
            source=source,
            target=target,
            type="customEdge",
            data={
                "type": rng.next_element(edge_types),
                "confidence": round(rng.next_float() * 0.5 + 0.5, 2)
            },
            animated=rng.next_float() > 0.8
        ))

    return GraphDataResponse(nodes=nodes, edges=edges)

def generate_mock_monitoring(time_range_str: str) -> MonitoringSnapshot:
    seed_str = f"monitoring-{time_range_str}"
    seed = zlib.crc32(seed_str.encode()) & 0xffffffff
    rng = DeterministicLCG(seed)

    modules = [
        {"id": 'm1', "name": 'M1 Extraction Engine'},
        {"id": 'm2', "name": 'M2 Entity Resolution'},
        {"id": 'm3', "name": 'M3 Corpus Graph'},
        {"id": 'm4', "name": 'M4 Reasoning Engine'},
        {"id": 'm5', "name": 'M5 Query System'},
        {"id": 'm6', "name": 'M6 Synthesis Engine'}
    ]

    error_messages = [
        "Timeout establishing graph connection",
        "Entity resolution conflict detected",
        "Malformed PDF extraction attempt",
        "Synthesis token limit exceeded",
        "Worker thread crash"
    ]

    health_status_options = ['Healthy', 'Healthy', 'Healthy', 'Warning', 'Error']

    health = []
    for mod in modules:
        health.append(ModuleHealth(
            moduleId=mod["id"],
            name=mod["name"],
            status=rng.next_element(health_status_options),
            uptime=f"{rng.next_int(1, 100)}h {rng.next_int(0, 59)}m",
            activeThreads=rng.next_int(2, 64)
        ))

    charts = []
    for i in range(24):
        charts.append(PerformanceMetric(
            label=f"{i:02d}:00",
            throughput=rng.next_int(100, 1000),
            latencyMs=rng.next_int(50, 400),
            successRate=round(rng.next_float() * 0.1 + 0.9, 3)
        ))

    queue = []
    for i in range(15):
        queue.append(QueueJob(
            id=f"job-{rng.next_int(1000, 9999)}",
            moduleId=rng.next_element(modules)["id"],
            type="Extraction",
            status=rng.next_element(['active', 'pending', 'completed', 'failed']),
            submitTimeStr=f"2025-06-01T{rng.next_int(0, 23):02d}:{rng.next_int(0, 59):02d}:00Z",
            durationMs=rng.next_int(100, 5000)
        ))

    recent_errors = []
    for i in range(5):
        recent_errors.append(ErrorEvent(
            id=f"err-{rng.next_int(1000, 9999)}",
            moduleId=rng.next_element(modules)["id"],
            type="RuntimeError",
            severity=rng.next_element(['low', 'medium', 'high', 'critical']),
            message=rng.next_element(error_messages),
            timeStr=f"2025-06-01T{rng.next_int(0, 23):02d}:{rng.next_int(0, 59):02d}:00Z"
        ))

    return MonitoringSnapshot(
        id=f"snap-{rng.next_int(1000, 9999)}",
        health=health,
        metrics={
            "documentsProcessed": rng.next_int(5000, 10000),
            "entitiesResolved": rng.next_int(100000, 500000),
            "graphNodes": rng.next_int(50000, 200000),
            "graphEdges": rng.next_int(100000, 600000),
            "queriesExecuted": rng.next_int(1000, 5000),
            "reviewsGenerated": rng.next_int(100, 500)
        },
        charts=charts,
        queue=queue,
        recentErrors=recent_errors,
        corpus=CorpusStatistic(
            documentCount=rng.next_int(1000, 5000),
            authorCount=rng.next_int(2000, 8000),
            entityCount=rng.next_int(50000, 150000),
            reviewCount=rng.next_int(100, 500)
        )
    )
