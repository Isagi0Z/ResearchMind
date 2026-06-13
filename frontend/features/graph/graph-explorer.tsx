"use client"

import { GraphCanvas } from "./graph-canvas"
import { GraphSearch } from "./graph-search"
import { GraphSidebar } from "./graph-sidebar"
import { MOCK_GRAPH } from "@/services/mock-graph"
import { Database, FileText, Network, Layers, Info } from "lucide-react"

function GraphStats() {
  return (
    <div className="absolute bottom-4 left-4 z-10 bg-background/90 backdrop-blur shadow-sm rounded-md border text-xs px-3 py-2 text-muted-foreground flex items-center gap-4">
      <div><span className="font-semibold text-foreground">{MOCK_GRAPH.nodes.length}</span> Nodes</div>
      <div><span className="font-semibold text-foreground">{MOCK_GRAPH.edges.length}</span> Edges</div>
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
  return (
    <div className="relative w-full h-[calc(100vh-6rem)] rounded-xl border overflow-hidden bg-muted/20">
      <GraphSearch />
      <GraphCanvas />
      <GraphSidebar />
      <GraphStats />
      <GraphLegend />
    </div>
  )
}
