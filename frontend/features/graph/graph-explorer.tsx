"use client"

import { GraphCanvas } from "./graph-canvas"
import { GraphSearch } from "./graph-search"
import { GraphSidebar } from "./graph-sidebar"
import { useGraphData } from "./graph-hooks"
import { useGraphStore } from "./graph-store"
import { Database, FileText, Network, Layers, Info, ChevronLeft, ChevronRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { LoadingState } from "@/components/shared/loading-state"
import { ErrorState } from "@/components/shared/error-state"
import { EmptyState } from "@/components/shared/empty-state"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
const PAGE_SIZE = 500

function GraphStats({ nodesCount, edgesCount }: { nodesCount: number; edgesCount: number }) {
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

function PaginationBar({ page, totalCount }: { page: number; totalCount: number }) {
  const setPage = useGraphStore((s) => s.setPage)
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE))

  return (
    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10 bg-background/90 backdrop-blur shadow-sm rounded-md border text-xs px-3 py-2 text-muted-foreground flex items-center gap-3">
      <Button variant="ghost" size="icon" className="h-6 w-6" disabled={page <= 0} onClick={() => setPage(page - 1)}>
        <ChevronLeft className="w-4 h-4" />
      </Button>
      <span className="whitespace-nowrap">Page {page + 1} of {totalPages}</span>
      <Button variant="ghost" size="icon" className="h-6 w-6" disabled={page >= totalPages - 1} onClick={() => setPage(page + 1)}>
        <ChevronRight className="w-4 h-4" />
      </Button>
    </div>
  )
}

function TypeFilter() {
  const { nodeTypeFilter, setNodeTypeFilter } = useGraphStore()
  return (
    <Select value={nodeTypeFilter || "all"} onValueChange={(v) => setNodeTypeFilter(v === "all" ? "" : v)}>
      <SelectTrigger className="w-[140px] h-10 bg-background/95 backdrop-blur shadow-md border text-xs">
        <SelectValue placeholder="All Types" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="all">All Types</SelectItem>
        <SelectItem value="document">Documents</SelectItem>
        <SelectItem value="entity">Entities</SelectItem>
      </SelectContent>
    </Select>
  )
}

export function GraphExplorer() {
  const { page, nodeTypeFilter, searchQuery } = useGraphStore()
  const params: Record<string, unknown> = { offset: page * PAGE_SIZE, limit: PAGE_SIZE }
  if (nodeTypeFilter) params.nodeType = nodeTypeFilter
  if (searchQuery) params.search = searchQuery

  const { data, isLoading, error, refetch } = useGraphData(params)

  if (isLoading) return <LoadingState />

  if (error) return <ErrorState onRetry={() => refetch()} />

  if (!data || data.nodes.length === 0) return (
    <div className="relative w-full h-[calc(100vh-6rem)] rounded-xl border overflow-hidden bg-muted/20">
      <div className="absolute top-4 left-4 z-10 flex gap-2">
        <GraphSearch />
        <TypeFilter />
      </div>
      <EmptyState title="No graph data available" description="Try adjusting your search or filter criteria" />
      <GraphStats nodesCount={0} edgesCount={0} />
      <GraphLegend />
    </div>
  )

  return (
    <div className="relative w-full h-[calc(100vh-6rem)] rounded-xl border overflow-hidden bg-muted/20">
      <div className="absolute top-4 left-4 z-10 flex gap-2">
        <GraphSearch />
        <TypeFilter />
      </div>
      <GraphCanvas data={data} />
      <GraphSidebar graphData={data} />
      <GraphStats nodesCount={data.nodes.length} edgesCount={data.edges.length} />
      <GraphLegend />
      <PaginationBar page={page} totalCount={data.nodes.length + (nodeTypeFilter ? 0 : (page + 1) * PAGE_SIZE)} />
    </div>
  )
}
