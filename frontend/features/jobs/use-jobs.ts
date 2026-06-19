"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { getJob, listJobs } from "@/services/jobs";
import type { JobProgressEvent, JobStatus } from "@/types/jobs";

export function useJobStatus(jobId: string | null) {
  return useQuery({
    queryKey: ["job", jobId],
    queryFn: () => getJob(jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "completed" || status === "failed") return false;
      return 2000;
    },
  });
}

export function useJobList(params?: {
  pageIndex?: number;
  pageSize?: number;
  status?: string;
  job_type?: string;
}) {
  return useQuery({
    queryKey: ["jobs", params],
    queryFn: () => listJobs(params),
    refetchInterval: 10000,
  });
}

export function useJobEvents(
  jobId: string | null,
  onEvent?: (event: JobProgressEvent) => void
) {
  const [connectionStatus, setConnectionStatus] = useState<"idle" | "connecting" | "connected" | "error">("idle");
  const eventSourceRef = useRef<EventSource | null>(null);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    if (!jobId) {
      setConnectionStatus("idle");
      return;
    }

    const baseUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || "http://localhost/api/v1";
    const url = `${baseUrl}/jobs/${jobId}/events`;

    setConnectionStatus("connecting");
    const es = new EventSource(url, { withCredentials: true } as EventSourceInit);
    eventSourceRef.current = es;

    es.addEventListener("progress", (event: MessageEvent) => {
      try {
        const data: JobProgressEvent = JSON.parse(event.data);
        onEventRef.current?.(data);
      } catch {
        // ignore malformed events
      }
    });

    es.addEventListener("error", () => {
      setConnectionStatus("error");
    });

    es.onopen = () => {
      setConnectionStatus("connected");
    };

    es.onerror = () => {
      setConnectionStatus("error");
      es.close();
    };

    return () => {
      es.close();
      eventSourceRef.current = null;
      setConnectionStatus("idle");
    };
  }, [jobId]);

  const close = useCallback(() => {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    setConnectionStatus("idle");
  }, []);

  return { connectionStatus, close };
}
