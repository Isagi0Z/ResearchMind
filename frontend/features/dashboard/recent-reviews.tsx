"use client"

import { useRecentReviews } from "./use-dashboard-data"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { FileText, ArrowRight } from "lucide-react"

export function RecentReviews() {
  const { data, isLoading } = useRecentReviews()

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="text-lg">Recent Reviews</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading || !data ? (
          <div className="space-y-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4">
                <Skeleton className="h-10 w-10 rounded-full" />
                <div className="space-y-2 flex-1">
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-3 w-2/3" />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-6">
            {data.map((review) => (
              <div key={review.id} className="flex items-center justify-between group">
                <div className="flex items-center gap-4 min-w-0">
                  <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center shrink-0 text-primary">
                    <FileText className="w-5 h-5" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">{review.title}</p>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground mt-1">
                      <span className="capitalize">{review.type.replace('_', ' ')}</span>
                      <span>•</span>
                      <span>{(review.confidence * 100).toFixed(0)}% conf</span>
                      <span>•</span>
                      <span>{new Date(review.createdAt).toLocaleDateString()}</span>
                    </div>
                  </div>
                </div>
                <Button variant="ghost" size="icon" className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
