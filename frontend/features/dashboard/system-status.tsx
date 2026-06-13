"use client"

import { useSystemStatus } from "./use-dashboard-data"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { StatusBadge } from "@/components/shared/status-badge"
import { Skeleton } from "@/components/ui/skeleton"

export function SystemStatusPanel() {
  const { data, isLoading } = useSystemStatus()

  const subsystems = [
    { name: "Extraction", key: "extraction" as const },
    { name: "Resolution", key: "resolution" as const },
    { name: "Graph", key: "graph" as const },
    { name: "Reasoning", key: "reasoning" as const },
    { name: "Synthesis", key: "synthesis" as const },
  ]

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="text-lg">System Status</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4">
        {subsystems.map((sys) => (
          <div key={sys.name} className="flex items-center justify-between">
            <span className="text-sm font-medium">{sys.name} Engine</span>
            {isLoading || !data ? (
              <Skeleton className="h-6 w-20" />
            ) : (
              <StatusBadge status={data[sys.key]} />
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
