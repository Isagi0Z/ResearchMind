"use client"

import { useGraphStore } from "./graph-store"
import { MOCK_GRAPH } from "@/services/mock-graph"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { X, Network, FileText, Database, Layers } from "lucide-react"
import { Button } from "@/components/ui/button"

export function GraphSidebar() {
  const { selectedNodeId, selectedEdgeId, setSelectedNodeId, setSelectedEdgeId } = useGraphStore()

  if (!selectedNodeId && !selectedEdgeId) return null

  let content = null

  if (selectedNodeId) {
    const node = MOCK_GRAPH.nodes.find(n => n.id === selectedNodeId)
    if (node) {
      const data = node.data
      content = (
        <div className="space-y-4">
          <div className="flex items-center gap-2 mb-2">
            {data.type === 'entity' && <Database className="w-5 h-5 text-blue-500" />}
            {data.type === 'document' && <FileText className="w-5 h-5 text-emerald-500" />}
            {data.type === 'cluster' && <Network className="w-5 h-5 text-amber-500" />}
            {data.type === 'theme' && <Layers className="w-5 h-5 text-purple-500" />}
            <span className="uppercase text-xs font-bold text-muted-foreground tracking-wider">{data.type}</span>
          </div>
          <h3 className="font-semibold text-lg">{data.label || data.title}</h3>
          
          {data.type === 'entity' && (
            <div className="grid grid-cols-2 gap-4 mt-4">
              <div>
                <div className="text-xs text-muted-foreground">Confidence</div>
                <div className="font-mono">{data.confidence}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Related Docs</div>
                <div>{data.relatedDocuments}</div>
              </div>
            </div>
          )}
          
          {data.type === 'document' && (
            <div className="space-y-3 mt-4">
              <div>
                <div className="text-xs text-muted-foreground">Year</div>
                <div>{data.year}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Authors</div>
                <div className="text-sm">{data.authors?.join(", ")}</div>
              </div>
            </div>
          )}
          
          {data.type === 'cluster' && (
            <div className="space-y-3 mt-4">
              <div>
                <div className="text-xs text-muted-foreground">Size</div>
                <div>{data.size} nodes</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Key Entities</div>
                <ul className="list-disc pl-4 text-sm mt-1">
                  {data.containedEntities?.map((e: string, i: number) => <li key={i}>{e}</li>)}
                </ul>
              </div>
            </div>
          )}
        </div>
      )
    }
  } else if (selectedEdgeId) {
    const edge = MOCK_GRAPH.edges.find(e => e.id === selectedEdgeId)
    if (edge) {
      const source = MOCK_GRAPH.nodes.find(n => n.id === edge.source)
      const target = MOCK_GRAPH.nodes.find(n => n.id === edge.target)
      
      content = (
        <div className="space-y-4">
          <div className="uppercase text-xs font-bold text-muted-foreground tracking-wider mb-2">EDGE RELATIONSHIP</div>
          <h3 className="font-semibold text-lg text-primary">{edge.data?.type}</h3>
          <div className="text-sm border-l-2 pl-3 py-1 my-4 space-y-2">
            <div><span className="text-muted-foreground">From:</span> {source?.data.label}</div>
            <div><span className="text-muted-foreground">To:</span> {target?.data.label}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Confidence</div>
            <div className="font-mono">{edge.data?.confidence}</div>
          </div>
        </div>
      )
    }
  }

  return (
    <Card className="absolute top-4 right-4 z-10 w-80 shadow-lg border-muted h-auto max-h-[calc(100vh-2rem)] overflow-y-auto">
      <CardHeader className="pb-2 pt-4 px-4 flex flex-row items-center justify-between">
        <CardTitle className="text-sm font-medium">Details</CardTitle>
        <Button variant="ghost" size="icon" className="h-6 w-6 rounded-full" onClick={() => {
          setSelectedNodeId(null)
          setSelectedEdgeId(null)
        }}>
          <X className="w-4 h-4" />
          <span className="sr-only">Close details</span>
        </Button>
      </CardHeader>
      <CardContent className="p-4 pt-0">
        {content}
      </CardContent>
    </Card>
  )
}
