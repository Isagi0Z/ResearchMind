import { ReviewRequest, ReviewResult, ReviewType } from '@/types/review';
import { apiClient } from '@/lib/api-client';

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
  // Phase 3A: Replace mock with real FastAPI call
  // We keep the function name generateMockReview temporarily to minimize UI changes 
  // as per instructions to preserve existing UI, or we can just rename it and update UI.
  // Actually, we'll keep the signature, but make it async.
  
  const response = await apiClient.post<any>('/api/v1/reviews/generate', {
    review_id: request.id,
    topic: request.topic,
    review_type: request.type,
    target_entities: request.targetEntities,
    document_scope: request.documentScope === 'all' ? [] : [request.documentScope] // Mapping to backend expectations
  });

  const res = response.review_result;

  return {
    id: res.review_id,
    request,
    abstract: res.abstract,
    sections: res.sections.map((sec: any) => ({
      id: sec.section_id,
      order: 0, // Backend might not have order, but we can set a default
      title: sec.title,
      content: sec.content,
      findings: sec.findings.map((f: any) => f.finding_id)
    })),
    findings: res.findings.map((f: any) => ({
      id: f.finding_id,
      type: f.finding_type,
      statement: f.statement,
      confidence: f.confidence,
      evidence: f.evidence_ids.map((eid: string) => ({
         id: eid,
         sourceDocId: "unknown", // Backend findings use evidence_ids strings
         sourceTitle: "Source Document",
         excerpt: "Excerpt from source",
         confidence: 0.8
      }))
    })),
    metadata: {
      confidence: res.confidence,
      findingsCount: res.total_findings,
      evidenceCount: res.total_evidence_items,
      sectionsCount: res.sections.length,
      generationTimeMs: 2500 // Not provided by backend ReviewResult explicitly
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
