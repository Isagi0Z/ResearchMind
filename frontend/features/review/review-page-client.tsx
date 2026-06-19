"use client"

import { ReviewGeneratorForm } from "@/features/review/review-generator-form"
import { ReviewProgressTracker } from "@/features/review/review-progress-tracker"
import { ReviewViewer } from "@/features/review/review-viewer"
import { FindingsPanel } from "@/features/review/findings-panel"
import { TraceabilityPanel } from "@/features/review/traceability-panel"
import { ReviewMetadataPanel } from "@/features/review/review-metadata-panel"
import { ReviewExportPanel } from "@/features/review/review-export-panel"
import { JobProgressPanel } from "@/features/jobs/job-progress-panel"
import { useReviewStore } from "@/features/review/review-store"

export function ReviewPageClient() {
  const { activeReview, generationStage, jobId } = useReviewStore()

  if (generationStage !== 'completed' && generationStage !== 'idle' && generationStage !== 'failed') {
    return (
      <div className="space-y-6">
        <ReviewProgressTracker />
        <JobProgressPanel jobId={jobId} />
      </div>
    )
  }

  if (!activeReview) {
    return <ReviewGeneratorForm />
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 min-h-0 h-auto">
      
      {/* Left/Center: Main Review Reading Pane */}
      <div className="lg:col-span-3 space-y-6">
        <div className="flex items-center justify-between">
          <ReviewExportPanel />
        </div>
        <ReviewMetadataPanel />
        <ReviewViewer />
      </div>

      {/* Right: Traces and Findings */}
      <div className="lg:col-span-1 flex flex-col gap-6 h-[calc(100vh-6rem)] sticky top-0">
        <div className="flex-1 min-h-0">
          <FindingsPanel />
        </div>
        <div className="flex-1 min-h-0">
          <TraceabilityPanel />
        </div>
      </div>
      
    </div>
  )
}
