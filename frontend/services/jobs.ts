import { apiClient } from "@/lib/api-client";
import type { JobListResponse, JobResponse, JobSubmitResponse } from "@/types/jobs";

export async function listJobs(params?: {
  pageIndex?: number;
  pageSize?: number;
  status?: string;
  job_type?: string;
}): Promise<JobListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.pageIndex !== undefined) searchParams.set("pageIndex", String(params.pageIndex));
  if (params?.pageSize !== undefined) searchParams.set("pageSize", String(params.pageSize));
  if (params?.status) searchParams.set("status", params.status);
  if (params?.job_type) searchParams.set("job_type", params.job_type);
  const qs = searchParams.toString();
  return apiClient.get<JobListResponse>(`/api/v1/jobs${qs ? `?${qs}` : ""}`);
}

export async function getJob(jobId: string): Promise<JobResponse> {
  return apiClient.get<JobResponse>(`/api/v1/jobs/${jobId}`);
}

export async function submitReviewGeneration(data: Record<string, unknown>): Promise<JobSubmitResponse> {
  return apiClient.post<JobSubmitResponse>("/api/v1/reviews/generate-async", data);
}

export async function submitDocumentProcessing(): Promise<JobSubmitResponse> {
  return apiClient.post<JobSubmitResponse>("/api/v1/documents/process", {});
}
