import { ReviewRequest, ReviewResult, ReviewSection, ReviewFinding, EvidenceBundle, ReviewType } from '@/types/review';

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

const SECTION_TITLES: Record<ReviewType, string[]> = {
  GENERAL: ['Introduction', 'Core Thematic Analysis', 'Methodological Overviews', 'Conclusion'],
  METHOD: ['Methodological Frameworks', 'Experimental Protocols', 'Statistical Techniques', 'Constraints'],
  DATASET: ['Data Sources', 'Corpus Integrity', 'Sampling Biases', 'Anomaly Detection'],
  CONSENSUS: ['Agreed Frameworks', 'Replicated Results', 'Statistical Overlaps', 'Consolidated Models'],
  CONTRADICTION: ['Core Debates', 'Conflicting Methodologies', 'High-Variance Metrics', 'Divergent Theories'],
  RESEARCH_GAP: ['Current Limitations', 'Unexplored Nodes', 'Theoretical Deficits', 'Future Directions'],
  COMPARATIVE: ['Baseline Comparisons', 'A/B Matrix Analysis', 'Differential Metrics', 'Outcome Synthesis'],
  LANDSCAPE: ['Macro Trends', 'Citation Clusters', 'Temporal Evolution', 'Broad Horizons']
};

const FINDING_TEMPLATES = [
  "Significantly limits subgraph extraction capabilities.",
  "Demonstrates high variance across repeated randomized trials.",
  "Establishes a solid baseline for semantic entity resolution.",
  "Highlights a critical missing linkage in current literature.",
  "Confirms the reproducibility of earlier deterministic hashing models.",
  "Suggests an inverse correlation between node density and rendering FPS.",
];

export function generateMockReview(request: ReviewRequest): ReviewResult {
  const rng = new LCG(request.id + request.topic);
  
  const findingCount = rng.nextInt(5, 15);
  const findings: ReviewFinding[] = [];
  const allEvidence: EvidenceBundle[] = [];

  for (let i = 0; i < findingCount; i++) {
    const fId = crc32(`${request.id}-finding-${i}`);
    const evidenceCount = rng.nextInt(1, 5);
    const evidence: EvidenceBundle[] = [];
    
    for (let j = 0; j < evidenceCount; j++) {
      const ev: EvidenceBundle = {
        id: crc32(`${fId}-ev-${j}`),
        sourceDocId: crc32(`doc-${rng.nextInt(100, 999)}`),
        sourceTitle: `Research Archive Vol ${rng.nextInt(1, 50)}`,
        excerpt: `The analysis clearly ${rng.nextElement(FINDING_TEMPLATES).toLowerCase()}`,
        confidence: Number((rng.next() * 0.4 + 0.6).toFixed(2))
      };
      evidence.push(ev);
      allEvidence.push(ev);
    }
    
    findings.push({
      id: fId,
      type: rng.nextElement(['Primary', 'Secondary', 'Outlier', 'Supporting']),
      statement: rng.nextElement(FINDING_TEMPLATES),
      confidence: Number((rng.next() * 0.5 + 0.5).toFixed(2)),
      evidence
    });
  }

  const sections: ReviewSection[] = [];
  const titles = SECTION_TITLES[request.type];
  
  titles.forEach((title, idx) => {
    // Distribute findings to sections
    const secFindings = findings.filter((_, fIdx) => fIdx % titles.length === idx).map(f => f.id);
    
    sections.push({
      id: crc32(`${request.id}-sec-${idx}`),
      order: idx + 1,
      title,
      content: `The section exploring ${title.toLowerCase()} provides significant insight into ${request.topic}. ` + 
               `Based on our analysis, we observe ${rng.nextElement(FINDING_TEMPLATES).toLowerCase()} ` +
               `This aligns with broader trends in the graph dataset.`,
      findings: secFindings
    });
  });

  return {
    id: crc32(`${request.id}-result`),
    request,
    abstract: `This review synthesizes the current understanding of ${request.topic} using a ${request.type} approach. We analyzed ${allEvidence.length} specific data points to derive ${findings.length} key findings structured across ${sections.length} core sections.`,
    sections,
    findings,
    metadata: {
      confidence: Number((rng.next() * 0.2 + 0.8).toFixed(2)),
      findingsCount: findings.length,
      evidenceCount: allEvidence.length,
      sectionsCount: sections.length,
      generationTimeMs: rng.nextInt(5000, 15000)
    }
  };
}

export function exportReviewToMarkdown(result: ReviewResult): string {
  let md = `# Research Review: ${result.request.topic}\n\n`;
  md += `**Type:** ${result.request.type} | **Confidence:** ${(result.metadata.confidence * 100).toFixed(0)}%\n\n`;
  md += `## Abstract\n${result.abstract}\n\n`;
  
  result.sections.forEach(sec => {
    md += `## ${sec.order}. ${sec.title}\n${sec.content}\n\n`;
    
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
