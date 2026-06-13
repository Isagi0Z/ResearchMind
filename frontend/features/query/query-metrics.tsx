"use client"

import { useQueryStore } from "./query-store"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"

export function QueryMetrics() {
  const { currentAnswer } = useQueryStore()

  if (!currentAnswer) return null

  const { metrics } = currentAnswer

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mt-6">
      <Card>
        <CardHeader className="pb-2 pt-4 px-4">
          <CardTitle className="text-xs text-muted-foreground uppercase tracking-wider">Execution Time</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          <div className="text-2xl font-bold font-mono">{(metrics.executionTimeMs / 1000).toFixed(2)}s</div>
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader className="pb-2 pt-4 px-4">
          <CardTitle className="text-xs text-muted-foreground uppercase tracking-wider">Evidence Extracted</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          <div className="text-2xl font-bold font-mono">{metrics.evidenceCount}</div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2 pt-4 px-4">
          <CardTitle className="text-xs text-muted-foreground uppercase tracking-wider">Reasoning Steps</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          <div className="text-2xl font-bold font-mono">{metrics.reasoningSteps}</div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2 pt-4 px-4">
          <CardTitle className="text-xs text-muted-foreground uppercase tracking-wider">Overall Confidence</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          <div className="text-2xl font-bold font-mono">{(metrics.overallConfidence * 100).toFixed(0)}%</div>
          <Progress value={metrics.overallConfidence * 100} className="h-1.5 mt-2" />
        </CardContent>
      </Card>
    </div>
  )
}
