"use client"

import { useReviewStore } from "./review-store"
import { Card, CardContent } from "@/components/ui/card"
import { Loader2, CheckCircle2 } from "lucide-react"

const STAGE_LABELS: Record<string, string> = {
  theme_detection: "Detecting core themes",
  evidence_collection: "Collecting graph evidence",
  finding_generation: "Generating atomic findings",
  section_building: "Building logical sections",
  traceability_verification: "Verifying trace integrity",
  confidence_computation: "Computing confidence scores",
  final_assembly: "Assembling final review payload"
}

const STAGES = Object.keys(STAGE_LABELS)

export function ReviewProgressTracker() {
  const { generationStage } = useReviewStore()

  if (generationStage === 'idle' || generationStage === 'completed' || generationStage === 'failed') {
    return null
  }

  const currentIndex = STAGES.indexOf(generationStage)

  return (
    <Card className="max-w-2xl mx-auto mt-12 bg-muted/20 border-dashed">
      <CardContent className="p-8 flex flex-col items-center">
        <Loader2 className="w-12 h-12 text-primary animate-spin mb-6" />
        <h3 className="text-xl font-semibold mb-8 text-center" aria-live="polite">
          {STAGE_LABELS[generationStage]}...
        </h3>

        <div className="w-full space-y-4">
          {STAGES.map((stage, idx) => {
            const isPast = idx < currentIndex
            const isCurrent = idx === currentIndex
            
            return (
              <div key={stage} className={`flex items-center gap-3 ${isPast ? 'opacity-50' : ''} ${isCurrent ? 'opacity-100 font-medium scale-105 transition-transform' : 'opacity-30'}`}>
                {isPast ? (
                  <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                ) : isCurrent ? (
                  <Loader2 className="w-5 h-5 text-primary animate-spin" />
                ) : (
                  <div className="w-5 h-5 rounded-full border-2 border-muted-foreground/30" />
                )}
                <span>{STAGE_LABELS[stage]}</span>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
