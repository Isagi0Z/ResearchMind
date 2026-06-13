import { Metadata } from "next"
import { QueryWorkspace } from "@/features/query/query-workspace"
import { QueryHistory } from "@/features/query/query-history"
import { QueryResults } from "@/features/query/query-results"
import { EvidencePanel } from "@/features/query/evidence-panel"
import { TraceViewer } from "@/features/query/trace-viewer"
import { QueryMetrics } from "@/features/query/query-metrics"

export const metadata: Metadata = {
  title: "Query Interface - ResearchMind",
  description: "Execute complex semantic queries across the research corpus.",
}

export default function QueryPage() {
  return (
    <div className="h-full flex flex-col space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Query Interface</h1>
          <p className="text-muted-foreground mt-1">
            Run multi-hop reasoning, consensus building, and comparative analysis.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 flex-1 min-h-0">
        
        {/* Left Sidebar: Workspace & History */}
        <div className="lg:col-span-1 space-y-6 flex flex-col h-full">
          <div className="bg-card border rounded-xl p-4 shadow-sm">
             <h2 className="text-sm font-semibold mb-4 text-muted-foreground uppercase tracking-wider">Workspace</h2>
             <QueryWorkspace />
          </div>
          
          <div className="bg-card border rounded-xl p-4 shadow-sm flex-1 overflow-hidden flex flex-col">
             <h2 className="text-sm font-semibold mb-4 text-muted-foreground uppercase tracking-wider">History</h2>
             <div className="overflow-y-auto flex-1 pr-2 -mr-2">
               <QueryHistory />
             </div>
          </div>
        </div>

        {/* Center/Right: Results, Evidence, Traces */}
        <div className="lg:col-span-3 flex flex-col h-full overflow-y-auto pr-2 -mr-2 pb-6">
          
          {/* Top: Results & Metrics */}
          <div className="mb-6">
            <QueryResults />
            <QueryMetrics />
          </div>
          
          {/* Bottom: Split Evidence and Traces */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 min-h-[400px]">
             <EvidencePanel />
             <TraceViewer />
          </div>
          
        </div>

      </div>
    </div>
  )
}
