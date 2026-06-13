import * as React from "react"
import { Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"

export function LoadingState({ className }: { className?: string }) {
  return (
    <div className={cn("flex flex-col items-center justify-center min-h-[300px] p-8", className)}>
      <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      <span className="sr-only">Loading...</span>
    </div>
  )
}
