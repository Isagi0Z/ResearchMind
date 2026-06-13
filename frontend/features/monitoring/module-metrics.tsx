"use client"

import { useMonitoringData } from "./monitoring-hooks"
import { useMonitoringStore } from "./monitoring-store"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { X, Server } from "lucide-react"

export function ModuleMetrics() {
  const { data, isLoading } = useMonitoringData()
  const { selectedModuleId, setSelectedModuleId } = useMonitoringStore()

  if (isLoading || !data || !selectedModuleId) return null

  const module = data.health.find(m => m.moduleId === selectedModuleId)
  if (!module) return null

  // Calculate synthetic specific metrics based on the ID
  const seed = module.name.length * data.charts.length
  const memUsage = (seed % 64) + 16
  const cpuUsage = (seed % 80) + 5

  return (
    <Card className="border-primary/50 shadow-md animate-in fade-in slide-in-from-right-4">
      <CardHeader className="pb-3 border-b bg-muted/20">
        <div className="flex items-start justify-between">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Server className="w-4 h-4 text-primary" />
            Module Detailed View
          </CardTitle>
          <button onClick={() => setSelectedModuleId(null)} className="text-muted-foreground hover:text-foreground">
            <X className="w-4 h-4" />
          </button>
        </div>
      </CardHeader>
      <CardContent className="p-4 space-y-4">
        
        <div>
          <h3 className="font-bold text-lg">{module.name}</h3>
          <p className="text-sm text-muted-foreground">ID: {module.moduleId}</p>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="p-2 border rounded text-center">
            <div className="text-[10px] uppercase text-muted-foreground mb-1">Status</div>
            <div className={`text-sm font-bold ${module.status === 'Healthy' ? 'text-emerald-500' : module.status === 'Warning' ? 'text-amber-500' : 'text-red-500'}`}>
              {module.status}
            </div>
          </div>
          <div className="p-2 border rounded text-center">
            <div className="text-[10px] uppercase text-muted-foreground mb-1">Uptime</div>
            <div className="text-sm font-mono">{module.uptime}</div>
          </div>
          <div className="p-2 border rounded text-center">
            <div className="text-[10px] uppercase text-muted-foreground mb-1">CPU Usage</div>
            <div className="text-sm font-mono">{cpuUsage}%</div>
          </div>
          <div className="p-2 border rounded text-center">
            <div className="text-[10px] uppercase text-muted-foreground mb-1">Mem Usage</div>
            <div className="text-sm font-mono">{memUsage} GB</div>
          </div>
        </div>

      </CardContent>
    </Card>
  )
}
