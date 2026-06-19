export interface JobResponse {
  id: string;
  user_id: string;
  job_type: string;
  status: JobStatus;
  progress: number;
  error_message: string | null;
  result_reference: unknown | null;
  created_at: string | null;
  updated_at: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export type JobStatus = "queued" | "running" | "completed" | "failed";

export interface JobListResponse {
  data: JobResponse[];
  total: number;
}

export interface JobSubmitResponse {
  job_id: string;
  status: string;
}

export interface JobProgressEvent {
  status: JobStatus;
  progress: number;
  error_message: string | null;
}
