"use client"

import { useMonitoringData } from "./monitoring-hooks"
import { MonitoringFilters } from "./monitoring-filters"
import { MetricsOverview } from "./metrics-overview"
import { SystemHealthPanel } from "./system-health-panel"
import { PerformanceCharts } from "./performance-charts"
import { ProcessingQueue } from "./processing-queue"
import { RecentErrors } from "./recent-errors"
import { CorpusStatistics } from "./corpus-statistics"
import { ModuleMetrics } from "./module-metrics"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import Link from "next/link"

export function MonitoringDashboard() {
  const { data, isLoading, error } = useMonitoringData()

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">System Monitoring</h1>
            <p className="text-muted-foreground mt-1">Loading monitoring data...</p>
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i}><CardContent className="p-4 h-20 animate-pulse bg-muted/50 rounded-md" /></Card>
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <div className="lg:col-span-1 space-y-6">
            <Card className="h-[400px]"><CardContent className="p-6 animate-pulse bg-muted/50 rounded-md h-full" /></Card>
            <Card className="h-[200px]"><CardContent className="p-6 animate-pulse bg-muted/50 rounded-md h-full" /></Card>
          </div>
          <div className="lg:col-span-3 space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Card className="h-[300px]"><CardContent className="p-6 animate-pulse bg-muted/50 rounded-md h-full" /></Card>
              <Card className="h-[300px]"><CardContent className="p-6 animate-pulse bg-muted/50 rounded-md h-full" /></Card>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Card className="h-[200px]"><CardContent className="p-6 animate-pulse bg-muted/50 rounded-md h-full" /></Card>
              <Card className="h-[200px]"><CardContent className="p-6 animate-pulse bg-muted/50 rounded-md h-full" /></Card>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    const status = (error as any)?.status

    if (status === 401) {
      return (
        <div className="flex items-center justify-center min-h-[60vh]">
          <Card className="w-full max-w-md">
            <CardContent className="p-8 text-center space-y-4">
              <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mx-auto">
                <svg className="w-8 h-8 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" /></svg>
              </div>
              <h2 className="text-xl font-bold">Authentication Required</h2>
              <p className="text-muted-foreground">
                You need to be logged in to access system monitoring. Please log in and try again.
              </p>
              <Button asChild>
                <Link href="/login">Go to Login</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      )
    }

    if (status === 403) {
      return (
        <div className="flex items-center justify-center min-h-[60vh]">
          <Card className="w-full max-w-md border-amber-500/30">
            <CardContent className="p-8 text-center space-y-4">
              <div className="w-16 h-16 rounded-full bg-amber-500/10 flex items-center justify-center mx-auto">
                <svg className="w-8 h-8 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m0 0v2m0-2h2m-2 0H10m9.364-7.364A9 9 0 1112 3a9 9 0 017.364 4.636z" /></svg>
              </div>
              <h2 className="text-xl font-bold">Access Restricted</h2>
              <p className="text-muted-foreground">
                System monitoring requires administrator privileges.
                Contact your administrator to request access.
              </p>
            </CardContent>
          </Card>
        </div>
      )
    }

    const isNetworkError = status === 0 || status === 408
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Card className="w-full max-w-md">
          <CardContent className="p-8 text-center space-y-4">
            <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center mx-auto">
              <svg className={`w-8 h-8 ${isNetworkError ? 'text-muted-foreground' : 'text-red-500'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d={isNetworkError ? "M18.364 5.636a9 9 0 010 12.728m0 0l-2.829-2.829m2.829 2.829L21 21M15.536 8.464a5 5 0 010 7.072m0 0l-2.829-2.829m2.829 2.829L13 21M3 3l18 18" : "M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"} /></svg>
            </div>
            <h2 className="text-xl font-bold">{isNetworkError ? 'Connection Lost' : 'Something Went Wrong'}</h2>
            <p className="text-muted-foreground">
              {isNetworkError
                ? 'Unable to reach the monitoring server. Check your connection and try again.'
                : (error as any)?.message || 'An unexpected error occurred while loading monitoring data.'}
            </p>
            <Button variant="outline" onClick={() => window.location.reload()}>
              <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
              Try Again
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

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
