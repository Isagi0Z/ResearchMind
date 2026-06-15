"use client"

import { GraphCanvas } from "./graph-canvas"
import { GraphSearch } from "./graph-search"
import { GraphSidebar } from "./graph-sidebar"
import { useGraphData } from "./graph-hooks"
import { Database, FileText, Network, Layers, Info, Loader2 } from "lucide-react"

function GraphStats({ nodesCount, edgesCount }: { nodesCount: number, edgesCount: number }) {
  return (
    <div className="absolute bottom-4 left-4 z-10 bg-background/90 backdrop-blur shadow-sm rounded-md border text-xs px-3 py-2 text-muted-foreground flex items-center gap-4">
      <div><span className="font-semibold text-foreground">{nodesCount}</span> Nodes</div>
      <div><span className="font-semibold text-foreground">{edgesCount}</span> Edges</div>
      <div className="flex items-center gap-1">
        <Info className="w-3 h-3" />
        Tier 1 Rendering
      </div>
    </div>
  )
}

function GraphLegend() {
  return (
    <div className="absolute bottom-4 right-4 z-10 bg-background/90 backdrop-blur shadow-sm rounded-md border p-3 text-xs">
      <div className="font-semibold mb-2">Legend</div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-2">
        <div className="flex items-center gap-2"><Database className="w-3 h-3 text-blue-500" /> Entity</div>
        <div className="flex items-center gap-2"><FileText className="w-3 h-3 text-emerald-500" /> Document</div>
        <div className="flex items-center gap-2"><Layers className="w-3 h-3 text-purple-500" /> Theme</div>
        <div className="flex items-center gap-2"><Network className="w-3 h-3 text-amber-500" /> Cluster</div>
      </div>
    </div>
  )
}

export function GraphExplorer() {
  const { data, isLoading, error } = useGraphData()

  if (isLoading) {
    return (
      <div className="relative w-full h-[calc(100vh-6rem)] rounded-xl border flex flex-col items-center justify-center bg-muted/20">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground mb-4" />
        <div className="text-muted-foreground">Loading graph data...</div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="relative w-full h-[calc(100vh-6rem)] rounded-xl border flex items-center justify-center bg-muted/20 text-destructive">
        Failed to load graph data
      </div>
    )
  }

  return (
    <div className="relative w-full h-[calc(100vh-6rem)] rounded-xl border overflow-hidden bg-muted/20">
      <GraphSearch data={data} />
      <GraphCanvas data={data} />
      <GraphSidebar graphData={data} />
      <GraphStats nodesCount={data.nodes.length} edgesCount={data.edges.length} />
      <GraphLegend />
    </div>
  )
}
