"use client"

import { useQueryStore } from "./query-store"
import { Button } from "@/components/ui/button"
import { Clock } from "lucide-react"

export function QueryHistory() {
  const { queryHistory, setActiveQueryText } = useQueryStore()

  if (queryHistory.length === 0) {
    return (
      <div className="text-sm text-muted-foreground italic text-center p-4 border rounded-md border-dashed">
        No recent queries.
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {queryHistory.map((query) => (
        <Button
          key={query.id}
          variant="ghost"
          className="w-full justify-start text-left h-auto py-2 font-normal"
          onClick={() => setActiveQueryText(query.text)}
        >
          <Clock className="w-3 h-3 mr-2 shrink-0 text-muted-foreground" />
          <span className="truncate">{query.text}</span>
        </Button>
      ))}
    </div>
  )
}
