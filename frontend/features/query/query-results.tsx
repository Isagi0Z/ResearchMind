"use client"

import { useQueryStore } from "./query-store"
import { Card, CardContent } from "@/components/ui/card"
import { Sparkles, BrainCircuit, Search, Database } from "lucide-react"

export function QueryResults() {
  const { executionState, currentAnswer } = useQueryStore()

  if (executionState === 'idle') return null

  if (executionState !== 'completed' && executionState !== 'failed') {
    // Loading states
    let icon = <Search className="w-8 h-8 animate-pulse text-muted-foreground" />
    let text = "Analyzing query..."
    
    if (executionState === 'planning') {
      icon = <BrainCircuit className="w-8 h-8 animate-pulse text-blue-500" />
      text = "Formulating execution plan..."
    } else if (executionState === 'reasoning') {
      icon = <Database className="w-8 h-8 animate-pulse text-purple-500" />
      text = "Extracting semantic evidence..."
    } else if (executionState === 'synthesis') {
      icon = <Sparkles className="w-8 h-8 animate-pulse text-emerald-500" />
      text = "Synthesizing research response..."
    }

    return (
      <Card className="w-full mt-6 bg-muted/20 border-dashed">
        <CardContent className="flex flex-col items-center justify-center py-16 space-y-4">
          {icon}
          <div className="text-lg font-medium text-muted-foreground" aria-live="polite">
            {text}
          </div>
        </CardContent>
      </Card>
    )
  }

  if (executionState === 'failed' || !currentAnswer) {
    return (
      <Card className="w-full mt-6 border-red-500/20 bg-red-500/5">
        <CardContent className="flex flex-col items-center justify-center py-12">
          <div className="text-red-500 font-medium">Failed to execute query.</div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="mt-6 space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <Card className="overflow-hidden border-primary/20 shadow-sm">
        <div className="h-2 w-full bg-gradient-to-r from-blue-500 via-purple-500 to-emerald-500" />
        <CardContent className="p-6 md:p-8">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center shrink-0 mt-1">
              <Sparkles className="w-5 h-5 text-primary" />
            </div>
            <div className="flex-1">
              <h2 className="text-2xl font-semibold mb-4">Research Synthesis</h2>
              <div className="prose prose-sm dark:prose-invert max-w-none">
                {currentAnswer.text.split('\n\n').map((paragraph, i) => (
                  <p key={i} className="text-base leading-relaxed text-foreground/90">
                    {paragraph}
                  </p>
                ))}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
