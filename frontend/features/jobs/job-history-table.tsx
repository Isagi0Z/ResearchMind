"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useJobList } from "./use-jobs";
import { Loader2 } from "lucide-react";

const STATUS_COLORS: Record<string, string> = {
  queued: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  running: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  completed: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  failed: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
};

export function JobHistoryTable() {
  const { data, isLoading, isError } = useJobList({ pageSize: 20 });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium">Job History</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && (
          <div className="flex justify-center py-4">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        )}
        {isError && (
          <p className="text-sm text-red-500">Failed to load job history.</p>
        )}
        {data && data.data.length === 0 && (
          <p className="text-sm text-muted-foreground">No jobs found.</p>
        )}
        {data && data.data.length > 0 && (
          <div className="space-y-2">
            {data.data.slice(0, 10).map((job) => (
              <div key={job.id} className="flex items-center justify-between rounded-md border px-3 py-2 text-sm">
                <div className="flex items-center gap-2">
                  <Badge className={STATUS_COLORS[job.status] || ""} variant="outline">
                    {job.status}
                  </Badge>
                  <span className="font-medium">{job.job_type.replace(/_/g, " ")}</span>
                </div>
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  <span>{job.progress}%</span>
                  <span>{job.created_at ? new Date(job.created_at).toLocaleString() : "—"}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
