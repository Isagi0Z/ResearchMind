"use client"

import { useMonitoringData } from "./monitoring-hooks"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { AlertCircle } from "lucide-react"

export function RecentErrors() {
  const { data, isLoading } = useMonitoringData()

  if (isLoading || !data) return null

  return (
    <Card className="h-full border-red-500/20 shadow-sm flex flex-col">
      <CardHeader className="pb-3 border-b bg-red-500/5">
        <CardTitle className="text-sm font-semibold flex items-center gap-2 text-red-500">
          <AlertCircle className="w-4 h-4" />
          Recent Errors
          <span className="bg-red-500/10 text-red-600 text-xs px-2 py-0.5 rounded-full font-mono">
            {data.recentErrors.length}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0 flex-1 max-h-[300px] overflow-y-auto">
        <div className="divide-y">
          {data.recentErrors.length === 0 && (
            <div className="p-4 text-center text-muted-foreground text-sm">No errors detected.</div>
          )}
          {data.recentErrors.map(err => (
            <div key={err.id} className="p-3 hover:bg-muted/30">
              <div className="flex items-start justify-between mb-1">
                <span className={`text-[10px] uppercase font-bold tracking-wider px-1.5 rounded
                  ${err.severity === 'critical' ? 'bg-red-500 text-white' : ''}
                  ${err.severity === 'high' ? 'bg-red-500/20 text-red-500' : ''}
                  ${err.severity === 'medium' ? 'bg-amber-500/20 text-amber-500' : ''}
                  ${err.severity === 'low' ? 'bg-muted text-muted-foreground' : ''}
                `}>
                  {err.severity}
                </span>
                <span className="text-xs text-muted-foreground font-mono">{err.timeStr}</span>
              </div>
              <div className="text-sm font-medium my-1">{err.message}</div>
              <div className="text-xs text-muted-foreground">Module: {err.moduleId} | Type: {err.type}</div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
