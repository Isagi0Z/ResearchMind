"use client"

import { useReviewStore } from "./review-store"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { FileText, Link } from "lucide-react"

export function TraceabilityPanel() {
  const { activeReview, selectedFindingId } = useReviewStore()

  if (!activeReview || !selectedFindingId) return null

  const finding = activeReview.findings.find(f => f.id === selectedFindingId)
  if (!finding) return null

  return (
    <Card className="h-full flex flex-col border-muted shadow-sm">
      <CardHeader className="pb-3 border-b bg-muted/20">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <Link className="w-4 h-4 text-primary" />
          Traceability Link
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 p-0 overflow-hidden">
        <ScrollArea className="h-[300px] lg:h-full">
          <div className="p-4 space-y-6">
            
            <div className="space-y-2">
              <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Derived Finding</h4>
              <p className="text-sm border-l-2 border-primary pl-3">{finding.statement}</p>
            </div>

            <div className="space-y-3">
              <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider flex justify-between">
                Source Evidence
                <span className="font-mono">{finding.evidence.length} docs</span>
              </h4>
              
              <div className="space-y-3">
                {finding.evidence.map(ev => (
                  <div key={ev.id} className="text-sm border rounded-md p-3 bg-card">
                    <div className="flex items-center gap-2 mb-2 text-emerald-600 dark:text-emerald-400 font-medium">
                      <FileText className="w-3 h-3" />
                      {ev.sourceTitle}
                    </div>
                    <p className="text-muted-foreground">"{ev.excerpt}"</p>
                    <div className="mt-2 text-xs font-mono bg-muted inline-block px-1.5 py-0.5 rounded">
                      conf: {(ev.confidence * 100).toFixed(0)}%
                    </div>
                  </div>
                ))}
              </div>
            </div>

          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
