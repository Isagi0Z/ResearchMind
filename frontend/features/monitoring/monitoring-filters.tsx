"use client"

import { useMonitoringStore, TimeRangeFilter } from "./monitoring-store"
import { Button } from "@/components/ui/button"
import { Clock } from "lucide-react"

const RANGES: { value: TimeRangeFilter; label: string }[] = [
  { value: '1h', label: 'Last 1 Hour' },
  { value: '24h', label: 'Last 24 Hours' },
  { value: '7d', label: 'Last 7 Days' },
  { value: '30d', label: 'Last 30 Days' }
]

export function MonitoringFilters() {
  const { timeRange, setTimeRange } = useMonitoringStore()

  return (
    <div className="flex items-center gap-2">
      <Clock className="w-4 h-4 text-muted-foreground mr-2" />
      <div className="bg-muted p-1 rounded-md flex items-center">
        {RANGES.map(r => (
          <Button
            key={r.value}
            variant={timeRange === r.value ? "default" : "ghost"}
            size="sm"
            onClick={() => setTimeRange(r.value)}
            className="h-8 px-3 text-xs"
          >
            {r.label}
          </Button>
        ))}
      </div>
    </div>
  )
}
