"use client"

import { useMonitoringData } from "./monitoring-hooks"
import { useMonitoringStore } from "./monitoring-store"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { CheckCircle2, AlertTriangle, XCircle, Activity } from "lucide-react"

export function SystemHealthPanel() {
  const { data, isLoading } = useMonitoringData()
  const { selectedModuleId, setSelectedModuleId } = useMonitoringStore()

  if (isLoading || !data) {
    return <Card className="h-full animate-pulse bg-muted/50"><CardContent className="p-6" /></Card>
  }

  return (
    <Card className="h-full border-muted shadow-sm">
      <CardHeader className="pb-3 border-b">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <Activity className="w-4 h-4 text-primary" />
          System Health
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <div className="divide-y">
          {data.health.map(module => {
            const isSelected = selectedModuleId === module.moduleId
            return (
              <div 
                key={module.moduleId}
                className={`p-3 cursor-pointer transition-colors hover:bg-muted/50 flex items-center justify-between ${isSelected ? 'bg-muted border-l-2 border-l-primary' : ''}`}
                onClick={() => setSelectedModuleId(isSelected ? null : module.moduleId)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    setSelectedModuleId(isSelected ? null : module.moduleId)
                  }
                }}
              >
                <div className="flex items-center gap-3">
                  {module.status === 'Healthy' && <CheckCircle2 className="w-5 h-5 text-emerald-500" aria-label="Healthy" />}
                  {module.status === 'Warning' && <AlertTriangle className="w-5 h-5 text-amber-500" aria-label="Warning" />}
                  {module.status === 'Error' && <XCircle className="w-5 h-5 text-red-500" aria-label="Error" />}
                  
                  <div>
                    <div className="text-sm font-medium">{module.name}</div>
                    <div className="text-xs text-muted-foreground font-mono">Uptime: {module.uptime}</div>
                  </div>
                </div>
                <div className="text-xs bg-secondary text-secondary-foreground px-2 py-0.5 rounded-full font-mono">
                  {module.activeThreads} thr
                </div>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
