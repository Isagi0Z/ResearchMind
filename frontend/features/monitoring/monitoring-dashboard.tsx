"use client"

import { MonitoringFilters } from "./monitoring-filters"
import { MetricsOverview } from "./metrics-overview"
import { SystemHealthPanel } from "./system-health-panel"
import { PerformanceCharts } from "./performance-charts"
import { ProcessingQueue } from "./processing-queue"
import { RecentErrors } from "./recent-errors"
import { CorpusStatistics } from "./corpus-statistics"
import { ModuleMetrics } from "./module-metrics"

export function MonitoringDashboard() {
  return (
    <div className="space-y-6">
      
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">System Monitoring</h1>
          <p className="text-muted-foreground mt-1">Real-time operational health and metrics.</p>
        </div>
        <MonitoringFilters />
      </div>

      <MetricsOverview />

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        
        {/* Left Column */}
        <div className="lg:col-span-1 space-y-6">
          <div className="h-[400px]">
            <SystemHealthPanel />
          </div>
          <ModuleMetrics />
        </div>

        {/* Center/Right Column */}
        <div className="lg:col-span-3 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 h-[400px]">
            <PerformanceCharts />
            <ProcessingQueue />
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <RecentErrors />
            <CorpusStatistics />
          </div>
        </div>

      </div>

    </div>
  )
}
