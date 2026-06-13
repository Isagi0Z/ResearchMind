import { Metadata } from "next"
import { MonitoringDashboard } from "@/features/monitoring/monitoring-dashboard"

export const metadata: Metadata = {
  title: "System Monitoring - ResearchMind",
  description: "Operational health and metrics for the ResearchMind pipeline.",
}

export default function MonitoringPage() {
  return (
    <div className="h-full">
      <MonitoringDashboard />
    </div>
  )
}
