"use client"

import { useMonitoringData } from "./monitoring-hooks"
import { useMonitoringStore } from "./monitoring-store"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { ListTree, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"

export function ProcessingQueue() {
  const { data, isLoading } = useMonitoringData()
  const { queueFilter, setQueueFilter } = useMonitoringStore()

  if (isLoading || !data) {
    return <Card className="h-full min-h-[300px] animate-pulse bg-muted/50" />
  }

  const { queue } = data
  const filteredQueue = queueFilter === 'all' ? queue : queue.filter(q => q.status === queueFilter)

  return (
    <Card className="h-full flex flex-col border-muted shadow-sm">
      <CardHeader className="pb-3 border-b">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <ListTree className="w-4 h-4 text-emerald-500" />
            Active Queue
            <span className="bg-secondary text-secondary-foreground text-xs px-2 py-0.5 rounded-full font-mono">
              {filteredQueue.length}
            </span>
          </CardTitle>
          <div className="flex items-center gap-1 bg-muted p-1 rounded-md">
            {(['all', 'active', 'pending', 'completed', 'failed'] as const).map(f => (
              <Button 
                key={f}
                variant={queueFilter === f ? "secondary" : "ghost"}
                size="sm"
                className="h-6 text-[10px] uppercase px-2 py-0"
                onClick={() => setQueueFilter(f)}
              >
                {f}
              </Button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex-1 p-0 overflow-hidden">
        <ScrollArea className="h-[300px] lg:h-full">
          <div className="divide-y">
            {filteredQueue.length === 0 && (
              <div className="p-8 text-center text-muted-foreground text-sm italic">
                No jobs found for filter: {queueFilter}
              </div>
            )}
            {filteredQueue.map(job => (
              <div key={job.id} className="p-3 hover:bg-muted/30 transition-colors flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-mono text-xs font-bold">{job.id.substring(0, 8)}</span>
                    <span className="text-[10px] uppercase tracking-wider text-muted-foreground border px-1 rounded">{job.type}</span>
                  </div>
                  <div className="text-xs text-muted-foreground">Module: {job.moduleId} • Submitted: {job.submitTimeStr}</div>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <div className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full flex items-center gap-1
                    ${job.status === 'active' ? 'bg-blue-500/10 text-blue-500' : ''}
                    ${job.status === 'pending' ? 'bg-amber-500/10 text-amber-500' : ''}
                    ${job.status === 'completed' ? 'bg-emerald-500/10 text-emerald-500' : ''}
                    ${job.status === 'failed' ? 'bg-red-500/10 text-red-500' : ''}
                  `}>
                    {job.status === 'active' && <Loader2 className="w-3 h-3 animate-spin" />}
                    {job.status}
                  </div>
                  <div className="text-xs font-mono text-muted-foreground">{(job.durationMs / 1000).toFixed(1)}s</div>
                </div>
              </div>
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
