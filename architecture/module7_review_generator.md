# M7-7 Review Generator Architecture

## 1. Scope
**In Scope:**
- Creating a comprehensive UI to interact with the M6 Synthesis Engine.
- Configuring complex review generation parameters.
- Monitoring deterministic 7-stage backend progress tracking.
- Viewing, exploring, and exporting fully synthesized systematic literature reviews and findings.

**Out of Scope:**
- Live editing of synthesized reviews.
- Real-time collaborative document sharing.
- Mutating the underlying evidence corpus via the review interface.

## 2. Review Types
- **GENERAL:** Comprehensive overview. Sections: Intro, Body, Conclusion. Findings: General thematic summaries.
- **METHOD:** Analysis of techniques. Sections: Protocols, Constraints. Findings: Methodological biases.
- **DATASET:** Data-centric review. Sections: Scope, Quality. Findings: Corpus anomalies.
- **CONSENSUS:** High agreement synthesis. Sections: Agreed Metrics. Findings: Statistical overlaps.
- **CONTRADICTION:** Divergent findings. Sections: Debates, Conflicts. Findings: High-variance metrics.
- **RESEARCH_GAP:** Unexplored areas. Sections: Future Work. Findings: Missing data nodes.
- **COMPARATIVE:** A/B analysis. Sections: Comparison Matrices. Findings: Differential insights.
- **LANDSCAPE:** Macro view. Sections: Broad Trends. Findings: Node clusters.

## 3. User Flow
1. **Review Configuration:** Select topic, type, scope.
2. **Review Generation:** Initiate the engine.
3. **Progress Monitoring:** Track the 7-stage M6 pipeline.
4. **Review Viewer:** Read the finalized synthesis.
5. **Traceability Exploration:** Click findings to trace to source documents.
6. **Export:** Download as Markdown, JSON, or Text.

## 4. Screen Design
The UI utilizes a wizard-to-dashboard layout. Initially, a configuration form dominates the screen. During generation, a progress tracker is centered. Upon completion, a dense, multi-pane dashboard reveals the full review alongside metadata and traceability panels.

## 5. Data Mapping
- **ReviewRequest:** Captured from the form.
- **ReviewResult:** Master payload from M6.
- **ReviewSection:** Logical text blocks.
- **ReviewFinding:** Discrete extractable insights.
- **ThemeCluster:** Thematic associations for findings.
- **EvidenceBundle:** Deep traceability arrays linking findings to graph documents.

## 6. State Management
**Zustand (`useReviewStore`):**
- `activeReview`: The currently viewed review object.
- `reviewConfig`: Form state.
- `selectedFindingId`: Controls side-panel trace rendering.
- `selectedSectionId`: Controls section magnification.
- `generationStatus`: Enums mirroring the 7 stages of synthesis.

**TanStack Query:**
- Handles the actual API bridging (mocked for now) ensuring polling doesn't leak memory.

## 7. Accessibility
- All generated review content is semantically tagged (`h1`, `h2`, `article`, `section`).
- ARIA live regions announce generation stage changes to screen readers.

## 8. Performance
- Route load `< 250 KB`.
- Heavy DOM structures (Findings, Evidence chains) utilize scroll virtualization bounds.
