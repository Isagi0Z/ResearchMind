"use client"

import { useQueryStore } from "./query-store"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { FileText, Percent } from "lucide-react"
import { cn } from "@/lib/utils"

export function EvidencePanel() {
  const { currentAnswer, selectedEvidenceId, setSelectedEvidenceId } = useQueryStore()

  if (!currentAnswer || currentAnswer.evidence.length === 0) return null

  return (
    <Card className="h-full flex flex-col border-muted shadow-sm">
      <CardHeader className="pb-3 border-b">
        <CardTitle className="text-sm font-semibold flex items-center justify-between">
          <span>Evidence Sources</span>
          <span className="bg-secondary text-secondary-foreground text-xs px-2 py-0.5 rounded-full">
            {currentAnswer.evidence.length}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 p-0 overflow-hidden">
        <ScrollArea className="h-full">
          <div className="divide-y">
            {currentAnswer.evidence.map((ev) => {
              const isSelected = selectedEvidenceId === ev.id
              return (
                <div 
                  key={ev.id}
                  className={cn(
                    "p-4 cursor-pointer transition-colors hover:bg-muted/50",
                    isSelected && "bg-muted border-l-2 border-l-primary"
                  )}
                  onClick={() => setSelectedEvidenceId(isSelected ? null : ev.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      setSelectedEvidenceId(isSelected ? null : ev.id)
                    }
                  }}
                  aria-pressed={isSelected}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2 text-sm font-medium text-primary">
                      <FileText className="w-4 h-4 shrink-0" />
                      <span className="truncate" title={ev.sourceTitle}>{ev.sourceTitle}</span>
                    </div>
                    <div className="flex items-center gap-1 text-xs text-muted-foreground bg-background px-1.5 py-0.5 rounded border font-mono">
                      <Percent className="w-3 h-3" />
                      {Math.round(ev.confidence * 100)}
                    </div>
                  </div>
                  <p className={cn(
                    "text-sm text-muted-foreground",
                    !isSelected && "line-clamp-3"
                  )}>
                    "{ev.excerpt}"
                  </p>
                </div>
              )
            })}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
