"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { useJobStatus, useJobEvents } from "./use-jobs";
import type { JobProgressEvent, JobStatus } from "@/types/jobs";
import { Loader2, CheckCircle, XCircle, Clock } from "lucide-react";

const STATUS_ICONS: Record<JobStatus, React.ReactNode> = {
  queued: <Clock className="h-4 w-4 text-muted-foreground" />,
  running: <Loader2 className="h-4 w-4 animate-spin text-primary" />,
  completed: <CheckCircle className="h-4 w-4 text-green-500" />,
  failed: <XCircle className="h-4 w-4 text-red-500" />,
};

export function JobProgressPanel({ jobId }: { jobId: string | null }) {
  const { data: job, isLoading } = useJobStatus(jobId);
  const [liveEvent, setLiveEvent] = useState<JobProgressEvent | null>(null);

  useJobEvents(jobId, (event) => {
    setLiveEvent(event);
  });

  if (!jobId) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Job Progress</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No active job selected.</p>
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Job Progress</CardTitle>
        </CardHeader>
        <CardContent>
          <Loader2 className="h-4 w-4 animate-spin" />
        </CardContent>
      </Card>
    );
  }

  const displayStatus = liveEvent?.status || job?.status || "queued";
  const displayProgress = liveEvent?.progress ?? job?.progress ?? 0;
  const displayError = liveEvent?.error_message || job?.error_message;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">Job Progress</CardTitle>
        <div className="flex items-center gap-2">
          {STATUS_ICONS[displayStatus]}
          <span className="text-xs capitalize text-muted-foreground">{displayStatus}</span>
        </div>
      </CardHeader>
      <CardContent>
        <Progress value={displayProgress} className="h-2" />
        <p className="mt-2 text-xs text-muted-foreground">{displayProgress}% complete</p>
        {displayStatus === "completed" && (
          <p className="mt-2 text-xs text-green-600">Job completed successfully.</p>
        )}
        {displayStatus === "failed" && displayError && (
          <p className="mt-2 text-xs text-red-600">Error: {displayError}</p>
        )}
      </CardContent>
    </Card>
  );
}
