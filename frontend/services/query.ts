import { QueryType, ParsedQuery, ResearchAnswer } from '@/types/query';
import { apiClient, ApiError } from '@/lib/api-client';

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

export async function generateAnswer(queryText: string): Promise<ResearchAnswer> {
  const qId = crc32(queryText);

  const response = await apiClient.post<any>('/api/v1/query/answer', {
    query_id: qId,
    raw_query: queryText
  });

  // Remediation C: Validate mandatory response structures before mapping
  if (!response || !response.answer || typeof response.answer.text !== 'string') {
    throw new ApiError(502, 'Invalid response: missing answer payload from backend.');
  }
  if (!Array.isArray(response.evidence)) {
    throw new ApiError(502, 'Invalid response: missing evidence array from backend.');
  }
  if (!response.step_route || !Array.isArray(response.step_route.steps)) {
    throw new ApiError(502, 'Invalid response: missing step_route from backend.');
  }

  return {
    queryId: response.answer.query_id,
    text: response.answer.text,
    confidence: response.answer.confidence,
    evidence: response.evidence.map((e: any) => ({
      id: e.evidence_id,
      sourceDocId: e.source_doc_id,
      sourceTitle: e.source_title,
      excerpt: e.excerpt,
      confidence: e.confidence
    })),
    traces: response.step_route.steps.map((s: any) => ({
      id: s.step_id,
      order: s.order,
      description: s.description,
      confidence: s.confidence,
      pathId: s.path_id
    })),
    metrics: {
      executionTimeMs: response.answer.metrics?.execution_time_ms || 1200,
      evidenceCount: response.evidence.length,
      reasoningSteps: response.step_route.steps.length,
      overallConfidence: response.answer.confidence
    }
  };
}
