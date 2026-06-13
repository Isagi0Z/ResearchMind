"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useCorpusSummary } from "./use-dashboard-data"
import { Skeleton } from "@/components/ui/skeleton"
import { ErrorState } from "@/components/shared/error-state"
import { Database, Network, Users, BookOpen } from "lucide-react"

export function CorpusSummaryCards() {
  const { data, isLoading, isError, refetch } = useCorpusSummary()

  if (isError) {
    return <ErrorState title="Failed to load summary" description="Could not load corpus statistics." onRetry={refetch} />
  }

  const items = [
    { title: "Total Documents", value: data?.totalDocuments, icon: BookOpen },
    { title: "Entity Clusters", value: data?.entityClusters, icon: Users },
    { title: "Graph Nodes", value: data?.graphNodes, icon: Database },
    { title: "Graph Edges", value: data?.graphEdges, icon: Network },
  ]

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {items.map((item, i) => (
        <Card key={i}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              {item.title}
            </CardTitle>
            <item.icon className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-8 w-24" />
            ) : (
              <div className="text-2xl font-bold">
                {item.value?.toLocaleString() ?? 0}
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
