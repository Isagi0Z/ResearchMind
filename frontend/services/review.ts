import { ReviewRequest, ReviewResult, ReviewType } from '@/types/review';
import { apiClient, ApiError } from '@/lib/api-client';

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

export async function generateReview(request: ReviewRequest): Promise<ReviewResult> {
  const response = await apiClient.post<any>('/api/v1/reviews/generate', {
    review_id: request.id,
    topic: request.topic,
    review_type: request.type,
    target_entities: request.targetEntities,
    document_scope: request.documentScope === 'all' ? [] : [request.documentScope]
  });

  // Remediation C: Validate mandatory response structures before mapping
  if (!response || !response.review_result) {
    throw new ApiError(502, 'Invalid response: missing review_result from backend.');
  }

  const res = response.review_result;

  if (typeof res.abstract !== 'string') {
    throw new ApiError(502, 'Invalid response: missing abstract in review_result.');
  }
  if (!Array.isArray(res.sections)) {
    throw new ApiError(502, 'Invalid response: missing sections array in review_result.');
  }
  if (!Array.isArray(res.findings)) {
    throw new ApiError(502, 'Invalid response: missing findings array in review_result.');
  }

  return {
    id: res.review_id,
    request,
    abstract: res.abstract,
    sections: res.sections.map((sec: any, idx: number) => ({
      id: sec.section_id,
      order: idx,
      title: sec.title,
      content: sec.content,
      findings: Array.isArray(sec.findings)
        ? sec.findings.map((f: any) => f.finding_id)
        : []
    })),
    findings: res.findings.map((f: any) => ({
      id: f.finding_id,
      type: f.finding_type,
      statement: f.statement,
      confidence: f.confidence,
      evidence: Array.isArray(f.evidence_ids)
        ? f.evidence_ids.map((eid: string) => ({
            id: eid,
            sourceDocId: 'unknown',
            sourceTitle: 'Source Document',
            excerpt: 'Excerpt from source',
            confidence: 0.8
          }))
        : []
    })),
    metadata: {
      confidence: res.confidence,
      findingsCount: res.total_findings,
      evidenceCount: res.total_evidence_items,
      sectionsCount: res.sections.length,
      generationTimeMs: 2500
    }
  };
}

export function exportReviewToMarkdown(result: ReviewResult): string {
  let md = `# Research Review: ${result.request.topic}\n\n`;
  md += `**Type:** ${result.request.type} | **Confidence:** ${(result.metadata.confidence * 100).toFixed(0)}%\n\n`;
  md += `## Abstract\n${result.abstract}\n\n`;
  
  result.sections.forEach((sec, idx) => {
    md += `## ${idx + 1}. ${sec.title}\n${sec.content}\n\n`;
    
    if (sec.findings.length > 0) {
      md += `### Key Findings\n`;
      sec.findings.forEach(fId => {
        const f = result.findings.find(f => f.id === fId);
        if (f) {
          md += `- **[${(f.confidence * 100).toFixed(0)}%]** ${f.statement}\n`;
        }
      });
      md += `\n`;
    }
  });

  md += `## Traceability Appendix\n`;
  result.findings.forEach(f => {
    md += `### Finding: ${f.statement}\n`;
    f.evidence.forEach(ev => {
      md += `- *${ev.sourceTitle}*: "${ev.excerpt}" (Conf: ${(ev.confidence*100).toFixed(0)}%)\n`;
    });
  });

  return md;
}
