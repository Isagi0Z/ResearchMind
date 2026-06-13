"use client"

import { useQueryStore } from "./query-store"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { GitMerge, Activity } from "lucide-react"
import { cn } from "@/lib/utils"

export function TraceViewer() {
  const { currentAnswer, selectedReasoningStepId, setSelectedReasoningStepId } = useQueryStore()

  if (!currentAnswer || currentAnswer.traces.length === 0) return null

  return (
    <Card className="h-full flex flex-col border-muted shadow-sm">
      <CardHeader className="pb-3 border-b bg-muted/20">
        <CardTitle className="text-sm font-semibold flex items-center justify-between">
          <div className="flex items-center gap-2">
            <GitMerge className="w-4 h-4 text-purple-500" />
            Reasoning Trace
          </div>
          <span className="bg-purple-500/10 text-purple-600 text-xs px-2 py-0.5 rounded-full font-mono">
            {currentAnswer.traces.length} steps
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 p-0 overflow-hidden">
        <ScrollArea className="h-[300px] lg:h-full">
          <div className="p-4 space-y-4">
            {currentAnswer.traces.map((step, idx) => {
              const isSelected = selectedReasoningStepId === step.id
              const isLast = idx === currentAnswer.traces.length - 1
              
              return (
                <div key={step.id} className="relative flex gap-4">
                  {!isLast && (
                    <div className="absolute top-8 bottom-[-16px] left-[11px] w-[2px] bg-border" />
                  )}
                  
                  <div className={cn(
                    "relative z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border bg-background text-xs font-mono font-bold",
                    isSelected ? "border-primary bg-primary text-primary-foreground" : "border-muted-foreground text-muted-foreground"
                  )}>
                    {step.order}
                  </div>
                  
                  <div 
                    className={cn(
                      "flex-1 rounded-md border p-3 cursor-pointer transition-all hover:border-primary/50",
                      isSelected ? "border-primary bg-primary/5 shadow-sm" : "bg-card"
                    )}
                    onClick={() => setSelectedReasoningStepId(isSelected ? null : step.id)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        setSelectedReasoningStepId(isSelected ? null : step.id)
                      }
                    }}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="text-xs font-mono text-muted-foreground flex items-center gap-1">
                        <Activity className="w-3 h-3" />
                        {step.pathId}
                      </div>
                      <div className="text-[10px] font-mono text-muted-foreground border px-1 rounded">
                        conf: {step.confidence.toFixed(2)}
                      </div>
                    </div>
                    <p className="text-sm">
                      {step.description}
                    </p>
                  </div>
                </div>
              )
            })}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
