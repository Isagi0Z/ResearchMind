"use client"

import { useQueryStore } from "./query-store"
import { MOCK_QUERY_SUGGESTIONS } from "@/services/mock-query"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"

export function QuerySuggestions() {
  const { setActiveQueryText } = useQueryStore()

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-muted-foreground">Suggested Queries</h3>
      <div className="flex flex-wrap gap-2">
        {MOCK_QUERY_SUGGESTIONS.map((suggestion) => (
          <Button
            key={suggestion.id}
            variant="outline"
            className="h-auto py-2 px-3 text-left justify-start font-normal whitespace-normal w-full sm:w-[calc(50%-0.25rem)] lg:w-[calc(33.333%-0.5rem)] flex-col items-start gap-1"
            onClick={() => setActiveQueryText(suggestion.text)}
          >
            <div className="w-full flex justify-between items-center">
              <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                {suggestion.type}
              </Badge>
            </div>
            <span className="text-sm">{suggestion.text}</span>
          </Button>
        ))}
      </div>
    </div>
  )
}
