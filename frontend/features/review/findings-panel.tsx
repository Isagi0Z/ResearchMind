"use client"

import { useReviewStore } from "./review-store"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Target } from "lucide-react"
import { cn } from "@/lib/utils"

export function FindingsPanel() {
  const { activeReview, selectedFindingId, setSelectedFindingId } = useReviewStore()

  if (!activeReview) return null

  return (
    <Card className="h-full flex flex-col border-muted shadow-sm">
      <CardHeader className="pb-3 border-b">
        <CardTitle className="text-sm font-semibold flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Target className="w-4 h-4 text-blue-500" />
            Extracted Findings
          </div>
          <span className="bg-blue-500/10 text-blue-600 text-xs px-2 py-0.5 rounded-full font-mono">
            {activeReview.findings.length}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 p-0 overflow-hidden">
        <ScrollArea className="h-[300px] lg:h-full">
          <div className="divide-y">
            {activeReview.findings.map(finding => {
              const isSelected = selectedFindingId === finding.id
              return (
                <div 
                  key={finding.id}
                  className={cn(
                    "p-4 cursor-pointer transition-colors hover:bg-muted/50",
                    isSelected && "bg-muted border-l-2 border-l-blue-500"
                  )}
                  onClick={() => setSelectedFindingId(isSelected ? null : finding.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      setSelectedFindingId(isSelected ? null : finding.id)
                    }
                  }}
                  aria-pressed={isSelected}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider bg-background border px-1 rounded">
                      {finding.type}
                    </span>
                    <span className="text-[10px] font-mono text-muted-foreground">
                      conf: {(finding.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p className="text-sm text-foreground">
                    {finding.statement}
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
