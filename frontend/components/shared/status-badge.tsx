import { Badge } from "@/components/ui/badge"
import { StageStatus } from "@/types/enums"
import { cn } from "@/lib/utils"

interface StatusBadgeProps {
  status: StageStatus | "healthy" | "warning" | "error"
  className?: string
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const isHealthy = status === "success" || status === "healthy"
  const isWarning = status === "partial" || status === "warning" || status === "skipped"
  const isError = status === "failed" || status === "error"

  return (
    <Badge 
      variant="outline" 
      className={cn(
        "capitalize font-medium",
        isHealthy && "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/50 dark:text-emerald-400 dark:border-emerald-800",
        isWarning && "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/50 dark:text-amber-400 dark:border-amber-800",
        isError && "bg-destructive/10 text-destructive border-destructive/20 dark:bg-destructive/20 dark:text-destructive-foreground dark:border-destructive/30",
        className
      )}
    >
      {status}
    </Badge>
  )
}
