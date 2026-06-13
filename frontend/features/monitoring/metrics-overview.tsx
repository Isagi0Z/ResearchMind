"use client"

import { useMonitoringData } from "./monitoring-hooks"
import { Card, CardContent } from "@/components/ui/card"

export function MetricsOverview() {
  const { data, isLoading } = useMonitoringData()

  if (isLoading || !data) return null

  const { metrics } = data

  const items = [
    { label: "Docs Processed", value: metrics.documentsProcessed.toLocaleString() },
    { label: "Entities Resolved", value: metrics.entitiesResolved.toLocaleString() },
    { label: "Graph Nodes", value: metrics.graphNodes.toLocaleString() },
    { label: "Graph Edges", value: metrics.graphEdges.toLocaleString() },
    { label: "Queries Executed", value: metrics.queriesExecuted.toLocaleString() },
    { label: "Reviews Generated", value: metrics.reviewsGenerated.toLocaleString() },
  ]

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
      {items.map((item, i) => (
        <Card key={i}>
          <CardContent className="p-4">
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 font-bold">{item.label}</div>
            <div className="text-xl font-bold font-mono text-primary">{item.value}</div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
