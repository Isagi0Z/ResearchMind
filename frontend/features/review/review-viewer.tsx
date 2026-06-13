"use client"

import { useReviewStore } from "./review-store"
import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

export function ReviewViewer() {
  const { activeReview, selectedSectionId, setSelectedSectionId } = useReviewStore()

  if (!activeReview) return null

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <Card className="overflow-hidden border-primary/20 shadow-sm">
        <div className="h-2 w-full bg-gradient-to-r from-blue-500 to-purple-500" />
        <CardContent className="p-8">
          <h2 className="text-3xl font-bold mb-6">{activeReview.request.topic}</h2>
          
          <div className="bg-muted/30 p-4 rounded-md border mb-8">
            <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-wider mb-2">Abstract</h3>
            <p className="text-sm leading-relaxed">{activeReview.abstract}</p>
          </div>

          <div className="space-y-8">
            {activeReview.sections.map(section => {
              const isSelected = selectedSectionId === section.id
              
              return (
                <section 
                  key={section.id} 
                  className={cn(
                    "cursor-pointer transition-all border-l-4 pl-4 py-1",
                    isSelected ? "border-l-primary" : "border-l-transparent hover:border-l-muted-foreground/30"
                  )}
                  onClick={() => setSelectedSectionId(isSelected ? null : section.id)}
                >
                  <h3 className="text-xl font-semibold mb-3 flex items-center gap-2">
                    <span className="text-muted-foreground text-base">{section.order}.</span>
                    {section.title}
                  </h3>
                  <p className="text-base text-foreground/90 leading-relaxed">
                    {section.content}
                  </p>
                </section>
              )
            })}
          </div>

        </CardContent>
      </Card>
    </div>
  )
}
