"use client"

import { useState, useEffect } from "react"
import { Search } from "lucide-react"
import { Input } from "@/components/ui/input"
import { useGraphStore } from "./graph-store"

export function GraphSearch() {
  const { searchQuery, setSearchQuery } = useGraphStore()
  const [localValue, setLocalValue] = useState(searchQuery)

  useEffect(() => {
    const timer = setTimeout(() => {
      setSearchQuery(localValue)
    }, 300)

    return () => clearTimeout(timer)
  }, [localValue, setSearchQuery])

  return (
    <div className="w-80 bg-background/95 backdrop-blur shadow-md rounded-md border flex items-center px-3 h-10">
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
