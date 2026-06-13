"use client"

import { useMonitoringData } from "./monitoring-hooks"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { BarChart3 } from "lucide-react"

export function PerformanceCharts() {
  const { data, isLoading } = useMonitoringData()

  if (isLoading || !data) {
    return <Card className="h-full min-h-[300px] animate-pulse bg-muted/50" />
  }

  const { charts } = data
  const maxThroughput = Math.max(...charts.map(c => c.throughput)) || 1
  const maxLatency = Math.max(...charts.map(c => c.latencyMs)) || 1

  return (
    <Card className="h-full border-muted shadow-sm flex flex-col">
      <CardHeader className="pb-3 border-b">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-blue-500" />
          Throughput & Latency 
        </CardTitle>
      </CardHeader>
      <CardContent className="p-6 flex-1 flex flex-col gap-8 justify-center">
        
        {/* Throughput Chart */}
        <div>
          <div className="text-xs text-muted-foreground mb-2 flex justify-between">
            <span>Throughput (jobs/hr)</span>
            <span className="font-mono">{maxThroughput} max</span>
          </div>
          <div className="h-24 flex items-end gap-1 w-full relative group">
            {charts.map((point, i) => {
              const heightPct = (point.throughput / maxThroughput) * 100
              return (
                <div key={i} className="flex-1 bg-blue-500/80 hover:bg-blue-500 transition-colors rounded-t-sm" style={{ height: `${heightPct}%` }} title={`${point.label}: ${point.throughput} jobs`} aria-valuenow={point.throughput} />
              )
            })}
          </div>
        </div>

        {/* Latency Chart */}
        <div>
          <div className="text-xs text-muted-foreground mb-2 flex justify-between">
            <span>Latency (ms)</span>
            <span className="font-mono">{maxLatency}ms max</span>
          </div>
          <div className="h-24 flex items-end gap-1 w-full relative">
            {charts.map((point, i) => {
              const heightPct = (point.latencyMs / maxLatency) * 100
              const isHigh = point.latencyMs > maxLatency * 0.8
              return (
                <div key={i} className={`flex-1 transition-colors rounded-t-sm ${isHigh ? 'bg-amber-500/80 hover:bg-amber-500' : 'bg-purple-500/80 hover:bg-purple-500'}`} style={{ height: `${heightPct}%` }} title={`${point.label}: ${point.latencyMs}ms`} aria-valuenow={point.latencyMs} />
              )
            })}
          </div>
        </div>

      </CardContent>
    </Card>
  )
}
