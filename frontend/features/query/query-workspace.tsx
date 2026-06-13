"use client"

import { useState } from "react"
import { useQueryStore } from "./query-store"
import { generateMockAnswer, determineQueryType } from "@/services/mock-query"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Search, Loader2 } from "lucide-react"
import { ParsedQuery } from "@/types/query"
import { QuerySuggestions } from "./query-suggestions"

// Simple CRC32 for deterministic ID mapping to history
function crc32(str: string): string {
  let crc = 0 ^ (-1);
  for (let i = 0; i < str.length; i++) {
    let byte = str.charCodeAt(i);
    crc = crc ^ byte;
    for (let j = 0; j < 8; j++) {
      crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
    }
  }
  return ((crc ^ (-1)) >>> 0).toString(16).padStart(8, '0');
}

export function QueryWorkspace() {
  const { 
    activeQueryText, 
    setActiveQueryText, 
    executionState, 
    setExecutionState,
    setCurrentAnswer,
    addToHistory,
    queryHistory
  } = useQueryStore()

  const isExecuting = executionState !== 'idle' && executionState !== 'completed' && executionState !== 'failed'

  const handleSubmit = async () => {
    if (!activeQueryText.trim() || isExecuting) return

    const type = determineQueryType(activeQueryText)
    const parsed: ParsedQuery = {
      id: crc32(activeQueryText),
      text: activeQueryText,
      type
    }
    
    addToHistory(parsed)
    setCurrentAnswer(null)

    // Simulate progressive loading states
    setExecutionState('parsing')
    await new Promise(r => setTimeout(r, 400))
    
    setExecutionState('planning')
    await new Promise(r => setTimeout(r, 600))
    
    setExecutionState('reasoning')
    await new Promise(r => setTimeout(r, 1200))
    
    setExecutionState('synthesis')
    await new Promise(r => setTimeout(r, 800))
    
    const mockAnswer = generateMockAnswer(activeQueryText)
    setCurrentAnswer(mockAnswer)
    setExecutionState('completed')
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const currentType = determineQueryType(activeQueryText || "")

  return (
    <div className="space-y-6">
      <div className="relative">
        <Textarea 
          placeholder="Ask a question, request a comparison, or explore a research gap..."
          className="min-h-[120px] resize-none pr-24 text-base focus-visible:ring-primary/50"
          value={activeQueryText}
          onChange={(e) => setActiveQueryText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isExecuting}
          aria-label="Query Input"
        />
        
        <div className="absolute bottom-3 left-3">
           <Badge variant="outline" className="text-xs uppercase tracking-wider text-muted-foreground bg-background">
             {activeQueryText.trim().length > 0 ? currentType : "AWAITING INPUT"}
           </Badge>
        </div>

        <div className="absolute bottom-3 right-3 flex items-center gap-2">
           <div className="text-xs text-muted-foreground hidden sm:block">
             Press <kbd className="font-sans border rounded px-1 py-0.5 bg-muted">Enter</kbd>
           </div>
           <Button 
             size="sm" 
             onClick={handleSubmit} 
             disabled={!activeQueryText.trim() || isExecuting}
           >
             {isExecuting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4 mr-2" />}
             {isExecuting ? <span className="sr-only">Executing...</span> : "Run Query"}
           </Button>
        </div>
      </div>

      {executionState === 'idle' && queryHistory.length === 0 && (
        <QuerySuggestions />
      )}
    </div>
  )
}
