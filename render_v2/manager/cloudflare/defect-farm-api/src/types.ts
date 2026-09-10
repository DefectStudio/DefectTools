export type JsonRecord = Record<string, unknown>;

export type JobStatus =
  | "queued"
  | "rendering"
  | "complete"
  | "failed"
  | "canceled";

export interface JobRow {
  id: string;
  batch_id: string | null;
  project: string;
  job_type: string;
  shot_name: string;
  render_version: number | null;
  status: JobStatus;
  priority: number;
  submitted_at: string;
  submitted_by: string | null;
  submitted_user: string | null;
  updated_at: string;
  attempt_count: number;
  worker_id: string | null;
  lease_token: string | null;
  lease_expires_at: number | null;
  claimed_at: string | null;
  render_started_at: string | null;
  render_finished_at: string | null;
  progress: number;
  result_json: string | null;
  last_failure_json: string | null;
  payload_json: string;
  resubmitted_from_job_id: string | null;
  resubmit_request_id: string | null;
  revision: number;
}

export interface WorkerRequest {
  workerId: string;
  appVersion: string | null;
  capabilities: JsonRecord | null;
}

export interface LeaseRequest extends WorkerRequest {
  leaseToken: string;
}

export interface JobSummary {
  job_id: string;
  batch_id: string | null;
  project: string;
  job_type: string;
  shot_name: string;
  render_version: number | null;
  status: JobStatus;
  priority: number;
  submitted_utc: string;
  submitted_by: string | null;
  submitted_user: string | null;
  updated_utc: string;
  attempt: number;
  worker: string | null;
  lease_expires_at: number | null;
  claimed_utc: string | null;
  render_started_utc: string | null;
  render_finished_utc: string | null;
  progress: number;
  blacklisted_workers: string[];
  resubmitted_from_job_id: string | null;
  revision: number;
}
