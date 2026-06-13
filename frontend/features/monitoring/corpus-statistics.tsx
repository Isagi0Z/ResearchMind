"use client"

import { useMonitoringData } from "./monitoring-hooks"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Database } from "lucide-react"

export function CorpusStatistics() {
  const { data, isLoading } = useMonitoringData()

  if (isLoading || !data) return null

  const { corpus } = data

  return (
    <Card className="h-full border-muted shadow-sm flex flex-col">
      <CardHeader className="pb-3 border-b">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <Database className="w-4 h-4 text-purple-500" />
          Global Corpus Snapshot
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 flex-1">
        <div className="grid grid-cols-2 gap-4 h-full">
          <div className="bg-muted/30 p-3 rounded-md flex flex-col justify-center">
            <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1 font-bold">Documents</div>
            <div className="text-2xl font-bold font-mono">{corpus.documentCount.toLocaleString()}</div>
          </div>
          <div className="bg-muted/30 p-3 rounded-md flex flex-col justify-center">
            <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1 font-bold">Entities</div>
            <div className="text-2xl font-bold font-mono">{corpus.entityCount.toLocaleString()}</div>
          </div>
          <div className="bg-muted/30 p-3 rounded-md flex flex-col justify-center">
            <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1 font-bold">Authors</div>
            <div className="text-2xl font-bold font-mono">{corpus.authorCount.toLocaleString()}</div>
          </div>
          <div className="bg-muted/30 p-3 rounded-md flex flex-col justify-center">
            <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1 font-bold">Reviews</div>
            <div className="text-2xl font-bold font-mono">{corpus.reviewCount.toLocaleString()}</div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
