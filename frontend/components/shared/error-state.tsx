import { AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"

interface ErrorStateProps {
  title?: string;
  description?: string;
  onRetry?: () => void;
}

export function ErrorState({ 
  title = "Something went wrong", 
  description = "There was a problem loading this content. Please try again.",
  onRetry 
}: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center min-h-[300px] border rounded-lg bg-background">
      <AlertCircle className="w-10 h-10 text-destructive mb-4" />
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="text-muted-foreground mt-2 mb-4 max-w-sm">{description}</p>
      {onRetry && (
        <Button variant="outline" onClick={onRetry}>
          Try Again
        </Button>
      )}
    </div>
  )
}
