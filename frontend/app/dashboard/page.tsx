import { CorpusSummaryCards } from "@/features/dashboard/corpus-summary-cards"
import { RecentDocuments } from "@/features/dashboard/recent-documents"
import { SystemStatusPanel } from "@/features/dashboard/system-status"
import { RecentReviews } from "@/features/dashboard/recent-reviews"

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground mt-1">
          Overview of your research corpus and system status.
        </p>
      </div>

      <CorpusSummaryCards />

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-7">
        <div className="md:col-span-1 lg:col-span-4">
          <RecentDocuments />
        </div>
        <div className="md:col-span-1 lg:col-span-3 space-y-6 flex flex-col">
          <div className="flex-1">
            <SystemStatusPanel />
          </div>
          <div className="flex-1">
             <RecentReviews />
          </div>
        </div>
      </div>
    </div>
  )
}
