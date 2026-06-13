import { Metadata } from "next"
import { ReviewPageClient } from "@/features/review/review-page-client"

export const metadata: Metadata = {
  title: "Review Generator - ResearchMind",
  description: "Synthesize systematic reviews from the M6 Engine.",
}

export default function ReviewPage() {
  return (
    <div className="h-full flex flex-col space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Review Generator</h1>
          <p className="text-muted-foreground mt-1">
            Automated synthesis and systematic review generation.
          </p>
        </div>
      </div>
      
      <ReviewPageClient />
    </div>
  )
}
