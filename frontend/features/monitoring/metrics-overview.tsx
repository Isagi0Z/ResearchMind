"use client"

import { useMonitoringData } from "./monitoring-hooks"
import { Card, CardContent } from "@/components/ui/card"

export function MetricsOverview() {
  const { data, isLoading } = useMonitoringData()

  if (isLoading || !data) return null

  const { metrics } = data

  const items = [
    { label: "Queries Executed", value: metrics.queriesExecuted.toLocaleString() },
    { label: "Queries Today", value: metrics.queriesToday.toLocaleString() },
    { label: "Query Success Rate", value: `${(metrics.querySuccessRate * 100).toFixed(1)}%` },
    { label: "Reviews Generated", value: metrics.reviewsGenerated.toLocaleString() },
    { label: "Reviews Today", value: metrics.reviewsToday.toLocaleString() },
    { label: "Documents Processed", value: metrics.documentsProcessed.toLocaleString() },
    { label: "Registered Users", value: metrics.registeredUsers.toLocaleString() },
    { label: "Active Users", value: metrics.activeUsers.toLocaleString() },
    { label: "Active Refresh Tokens", value: metrics.refreshTokensActive.toLocaleString() },
  ]

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4">
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
