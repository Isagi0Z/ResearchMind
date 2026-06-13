"use client"

import { useReviewStore } from "./review-store"
import { Card, CardContent } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"

export function ReviewMetadataPanel() {
  const { activeReview } = useReviewStore()

  if (!activeReview) return null

  const { metadata } = activeReview

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
      <Card>
        <CardContent className="p-4">
          <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Overall Confidence</div>
          <div className="text-2xl font-bold font-mono">{(metadata.confidence * 100).toFixed(0)}%</div>
          <Progress value={metadata.confidence * 100} className="h-1 mt-2" />
        </CardContent>
      </Card>
      
      <Card>
        <CardContent className="p-4">
          <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Generation Time</div>
          <div className="text-2xl font-bold font-mono">{(metadata.generationTimeMs / 1000).toFixed(1)}s</div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4">
          <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Findings</div>
          <div className="text-2xl font-bold font-mono">{metadata.findingsCount}</div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4">
          <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Evidence Processed</div>
          <div className="text-2xl font-bold font-mono">{metadata.evidenceCount}</div>
        </CardContent>
      </Card>
    </div>
  )
}
