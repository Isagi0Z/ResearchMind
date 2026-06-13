import { Node, Edge } from '@xyflow/react';
import { GraphNodeData, GraphEdgeData, GraphNodeType, GraphEdgeType } from '@/types/graph';

// Simple deterministic LCG for random generation without Math.random()
class DeterministicRandom {
  private seed: number;

  constructor(seed: number) {
    this.seed = seed;
  }

  next(): number {
    this.seed = (this.seed * 1664525 + 1013904223) % 4294967296;
    return this.seed / 4294967296;
  }

  nextInt(min: number, max: number): number {
    return Math.floor(this.next() * (max - min + 1)) + min;
  }

  nextElement<T>(array: T[]): T {
    return array[this.nextInt(0, array.length - 1)];
  }
}

export const generateMockGraph = (nodeCount: number = 1000, edgeCount: number = 3000) => {
  const rng = new DeterministicRandom(12345); // Fixed seed
  const nodes: Node<GraphNodeData>[] = [];
  const edges: Edge<GraphEdgeData>[] = [];

  const types: GraphNodeType[] = ['entity', 'entity', 'entity', 'document', 'document', 'theme', 'cluster'];
  const edgeTypes: GraphEdgeType[] = ['USES_METHOD', 'COMPARES_WITH', 'SUPPORTS', 'CONTRADICTS', 'REFERENCES', 'CO_OCCURS'];
  
  const authors = ['Smith, J.', 'Doe, A.', 'Johnson, M.', 'Williams, K.', 'Brown, C.'];
  const words = ['Neural', 'Network', 'Quantum', 'Algorithm', 'Analysis', 'Optimization', 'Framework', 'System', 'Data', 'Model', 'Machine', 'Learning', 'Deep', 'Structure', 'Graph', 'Semantic', 'Representation', 'Attention', 'Transformer', 'Language'];

  // Generate Nodes in a spiral/sunflower layout for deterministic and spaced out coordinates
  const goldenRatio = (1 + Math.sqrt(5)) / 2;
  const angleIncrement = Math.PI * 2 * goldenRatio;

  for (let i = 0; i < nodeCount; i++) {
    const type = rng.nextElement(types);
    const id = `node-${i}`;
    
    // Sunflower layout distribution
    const radius = Math.sqrt(i) * 60; // Scale factor
    const angle = i * angleIncrement;
    const x = radius * Math.cos(angle);
    const y = radius * Math.sin(angle);

    const data: GraphNodeData = {
      label: `${rng.nextElement(words)} ${rng.nextElement(words)}`,
      type
    };

    if (type === 'entity') {
      data.confidence = Number(rng.next().toFixed(2));
      data.relatedDocuments = rng.nextInt(1, 50);
    } else if (type === 'document') {
      data.title = `A Novel Approach to ${rng.nextElement(words)} ${rng.nextElement(words)}`;
      data.year = rng.nextInt(2010, 2026);
      data.authors = [rng.nextElement(authors), rng.nextElement(authors)];
    } else if (type === 'cluster') {
      data.size = rng.nextInt(5, 150);
      data.containedEntities = [`${rng.nextElement(words)}`, `${rng.nextElement(words)}`];
      data.label = `${rng.nextElement(words)} Cluster`;
    } else if (type === 'theme') {
      data.label = `${rng.nextElement(words)} Theme`;
    }

    nodes.push({
      id,
      type: type, // Matches the custom node key in React Flow
      position: { x, y },
      data,
    });
  }

  // Generate Edges (Barabasi-Albert style preferential attachment approximation for realism)
  for (let i = 0; i < edgeCount; i++) {
    // Bias towards lower indexed nodes to create hubs
    const sourceIndex = Math.floor(Math.pow(rng.next(), 2) * nodeCount);
    const targetIndex = Math.floor(rng.next() * nodeCount);
    
    if (sourceIndex === targetIndex) continue;

    const source = nodes[sourceIndex].id;
    const target = nodes[targetIndex].id;
    
    edges.push({
      id: `edge-${i}`,
      source,
      target,
      type: 'customEdge',
      data: {
        type: rng.nextElement(edgeTypes),
        confidence: Number((rng.next() * 0.5 + 0.5).toFixed(2)) // 0.5 - 1.0
      },
      animated: rng.next() > 0.8, // some edges animated
    });
  }

  return { nodes, edges };
};

export const MOCK_GRAPH = generateMockGraph(1000, 3000);
