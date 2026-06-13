import { QueryType, ParsedQuery, ResearchAnswer, AggregatedEvidence, ReasoningStep } from '@/types/query';

// Simple deterministic hash function for IDs
function crc32(str: string): string {
  let crc = 0 ^ (-1);
  for (let i = 0; i < str.length; i++) {
    let byte = str.charCodeAt(i);
    crc = crc ^ byte;
    for (let j = 0; j < 8; j++) {
      crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
    }
  }
  return ((crc ^ (-1)) >>> 0).toString(16).padStart(8, '0');
}

class LCG {
  private seed: number;
  constructor(seedStr: string) {
    this.seed = parseInt(crc32(seedStr), 16) || 12345;
  }
  next(): number {
    this.seed = (this.seed * 1664525 + 1013904223) % 4294967296;
    return this.seed / 4294967296;
  }
  nextInt(min: number, max: number): number {
    return Math.floor(this.next() * (max - min + 1)) + min;
  }
  nextElement<T>(arr: T[]): T {
    return arr[this.nextInt(0, arr.length - 1)];
  }
}

const PARAGRAPHS = [
  "The fundamental constraints of the system rely heavily on optimizing graph traversal paths. As demonstrated by multiple experiments, limiting the scope of subgraph rendering directly impacts the overall FPS and visual fluidity.",
  "Researchers widely agree that utilizing deterministic layouts drastically improves testing capabilities. Hydration mismatches are frequently cited as the primary obstacle in modern SSR frameworks.",
  "Contrastingly, some studies suggest that dynamic force-directed layouts offer superior user discovery mechanics, despite the performance overhead.",
  "The intersection of semantic clustering and hardware acceleration presents a novel area of exploration, particularly when node counts exceed established memory limits."
];

export const MOCK_QUERY_SUGGESTIONS: ParsedQuery[] = [
  { id: crc32('q1'), text: "What is the primary constraint of graph visualization?", type: 'FACTUAL' },
  { id: crc32('q2'), text: "Explain how deterministic rendering solves hydration issues.", type: 'EXPLANATION' },
  { id: crc32('q3'), text: "Compare force-directed layouts with pre-calculated static coordinates.", type: 'COMPARISON' },
  { id: crc32('q4'), text: "What is the consensus on DOM limits for WebGL fallback?", type: 'CONSENSUS' },
  { id: crc32('q5'), text: "Are there any contradictions regarding physics engine performance?", type: 'CONTRADICTION' },
  { id: crc32('q6'), text: "What are the research gaps in hardware acceleration for semantic clustering?", type: 'RESEARCH_GAP' },
  { id: crc32('q7'), text: "Trace the relationship between semantic clusters and layout optimization.", type: 'MULTI_HOP' },
  { id: crc32('q8'), text: "Explore emerging concepts in graph UX.", type: 'EXPLORATION' },
];

export function determineQueryType(queryText: string): QueryType {
  const lower = queryText.toLowerCase();
  if (lower.includes('compare') || lower.includes('versus') || lower.includes('vs')) return 'COMPARISON';
  if (lower.includes('explain') || lower.includes('how does')) return 'EXPLANATION';
  if (lower.includes('consensus') || lower.includes('agree')) return 'CONSENSUS';
  if (lower.includes('contradict') || lower.includes('conflict')) return 'CONTRADICTION';
  if (lower.includes('gap') || lower.includes('future')) return 'RESEARCH_GAP';
  if (lower.includes('trace') || lower.includes('connect')) return 'MULTI_HOP';
  if (lower.includes('explore') || lower.includes('emerging')) return 'EXPLORATION';
  return 'FACTUAL';
}

export function generateMockAnswer(queryText: string): ResearchAnswer {
  const type = determineQueryType(queryText);
  const qId = crc32(queryText);
  const rng = new LCG(queryText);

  const evidenceCount = rng.nextInt(3, 12);
  const evidence: AggregatedEvidence[] = [];
  for (let i = 0; i < evidenceCount; i++) {
    evidence.push({
      id: crc32(`${qId}-ev-${i}`),
      sourceDocId: crc32(`doc-${rng.nextInt(1, 1000)}`),
      sourceTitle: `Study on Constraint Limits Vol ${rng.nextInt(1, 10)}`,
      excerpt: rng.nextElement(PARAGRAPHS),
      confidence: Number((rng.next() * 0.4 + 0.6).toFixed(2))
    });
  }

  const stepsCount = rng.nextInt(2, 6);
  const traces: ReasoningStep[] = [];
  for (let i = 0; i < stepsCount; i++) {
    traces.push({
      id: crc32(`${qId}-tr-${i}`),
      order: i + 1,
      description: `Extracted sub-graph for path traversal iteration ${i+1}. Filtered noise nodes.`,
      confidence: Number((rng.next() * 0.5 + 0.5).toFixed(2)),
      pathId: `path-${rng.nextInt(100, 999)}`
    });
  }

  let text = rng.nextElement(PARAGRAPHS);
  if (type === 'COMPARISON') text = `On one hand: ${text}\n\nOn the other hand: ${rng.nextElement(PARAGRAPHS)}`;
  if (type === 'CONTRADICTION') text = `Conflict Detected! ${text} However, conflicting evidence suggests: ${rng.nextElement(PARAGRAPHS)}`;
  if (type === 'EXPLANATION') text = `${text} ${rng.nextElement(PARAGRAPHS)} Therefore, we conclude the system is bounded.`;

  return {
    queryId: qId,
    text,
    confidence: Number((rng.next() * 0.3 + 0.7).toFixed(2)),
    evidence,
    traces,
    metrics: {
      executionTimeMs: rng.nextInt(800, 4500),
      evidenceCount: evidence.length,
      reasoningSteps: traces.length,
      overallConfidence: Number((rng.next() * 0.2 + 0.8).toFixed(2))
    }
  };
}
