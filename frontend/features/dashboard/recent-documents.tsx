"use client"

import { useRecentDocuments } from "./use-dashboard-data"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { StatusBadge } from "@/components/shared/status-badge"
import { ExternalLink } from "lucide-react"

export function RecentDocuments() {
  const { data, isLoading } = useRecentDocuments()

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="text-lg">Recent Documents</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading || !data ? (
          <div className="space-y-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex flex-col gap-2 p-3 border rounded-lg">
                <Skeleton className="h-5 w-3/4" />
                <Skeleton className="h-4 w-1/2" />
                <div className="flex gap-2">
                  <Skeleton className="h-5 w-16" />
                  <Skeleton className="h-5 w-16" />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            {data.map((doc) => {
              const authors = doc.header.authors.map(a => a.surname || a.full_name).join(", ")
              const status = doc.meta.pipeline_stages[doc.meta.pipeline_stages.length - 1] || "failed"
              
              return (
                <div key={doc.meta.ruo_id} className="flex flex-col gap-2 p-3 border rounded-lg hover:bg-muted/50 transition-colors">
                  <div className="flex items-start justify-between gap-4">
                    <h4 className="text-sm font-semibold leading-tight line-clamp-2">
                      {doc.header.title}
                    </h4>
                    <Button variant="ghost" size="icon" className="h-6 w-6 shrink-0 -mt-1 -mr-1">
                      <ExternalLink className="h-3 w-3" />
                    </Button>
                  </div>
                  <div className="text-xs text-muted-foreground line-clamp-1">
                    {authors} {doc.header.publication_date ? `(${doc.header.publication_date.substring(0,4)})` : ""}
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <StatusBadge status={status} className="text-[10px] px-1.5 py-0 h-4" />
                    {doc.header.venue && (
                      <span className="text-[10px] text-muted-foreground bg-muted px-1.5 rounded">{doc.header.venue}</span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
