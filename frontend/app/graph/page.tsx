import { GraphExplorer } from "@/features/graph/graph-explorer"
import { Metadata } from "next"

export const metadata: Metadata = {
  title: "Graph Explorer - ResearchMind",
  description: "Interactive visualization of the ResearchMind corpus graph.",
}

export default function GraphPage() {
  return (
    <div className="h-full flex flex-col space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Graph Explorer</h1>
          <p className="text-muted-foreground mt-1">
            Navigate semantic relationships between entities and documents.
          </p>
        </div>
      </div>
      <GraphExplorer />
    </div>
  )
}
