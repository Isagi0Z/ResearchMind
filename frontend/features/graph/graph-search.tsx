"use client"

import { useState, useEffect } from "react"
import { Search } from "lucide-react"
import { Input } from "@/components/ui/input"
import { useGraphStore } from "./graph-store"
import { MOCK_GRAPH } from "@/services/mock-graph"

export function GraphSearch() {
  const { searchQuery, setSearchQuery, setHighlightedNodeIds } = useGraphStore()
  const [localValue, setLocalValue] = useState(searchQuery)

  useEffect(() => {
    const timer = setTimeout(() => {
      setSearchQuery(localValue)
      
      // Perform case-insensitive search if query exists
      if (localValue.trim().length > 0) {
        const query = localValue.toLowerCase()
        const matches = new Set<string>()
        MOCK_GRAPH.nodes.forEach(n => {
          if (n.data.label.toLowerCase().includes(query)) {
            matches.add(n.id)
          }
        })
        setHighlightedNodeIds(matches)
      } else {
        setHighlightedNodeIds(new Set())
      }
    }, 300) // 300ms debounce as required

    return () => clearTimeout(timer)
  }, [localValue, setSearchQuery, setHighlightedNodeIds])

  return (
    <div className="absolute top-4 left-4 z-10 w-80 bg-background/95 backdrop-blur shadow-md rounded-md border flex items-center px-3 h-10">
      <Search className="w-4 h-4 text-muted-foreground mr-2 shrink-0" />
      <Input
        value={localValue}
        onChange={(e) => setLocalValue(e.target.value)}
        placeholder="Search nodes by label..."
        className="border-0 shadow-none focus-visible:ring-0 px-0"
      />
    </div>
  )
}
