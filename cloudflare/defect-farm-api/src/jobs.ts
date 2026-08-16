import {
  HttpError,
  optionalNumber,
  optionalString,
  parseStoredRecord,
  requiredInteger,
  requiredString,
  requireRecord,
  safeIdentifier,
} from "./http";
import type {
  JobRow,
  JobStatus,
  JobSummary,
  JsonRecord,
  LeaseRequest,
  WorkerRequest,
} from "./types";

const NOW_SQL = "strftime('%Y-%m-%dT%H:%M:%fZ','now')";
const MAX_LIST_LIMIT = 100;

interface CreatedJob {
  created: boolean;
  row: JobRow;
}

interface NormalizedJob {
  payload: JsonRecord;
  payloadJson: string;
  id: string;
  batchId: string | null;
  project: string;
  jobType: string;
  shotName: string;
  renderVersion: number | null;
  priority: number;
  submittedAt: string;
  submittedBy: string | null;
  submittedUser: string | null;
  resubmittedFromJobId: string | null;
}

function parseLeaseSeconds(env: Env): number {
  const parsed = Number(env.LEASE_SECONDS);
  if (!Number.isInteger(parsed) || parsed < 60 || parsed > 3600) {
    throw new Error("LEASE_SECONDS must be an integer between 60 and 3600");
  }
  return parsed;
}

function normalizeJobPayload(input: JsonRecord): NormalizedJob {
  if (input.schema_version !== 1) {
    throw new HttpError(
      400,
      "unsupported_schema",
      "schema_version must currently be 1.",
    );
  }
  const id = safeIdentifier(requiredString(input, "job_id", 220), "job_id");
  const project = safeIdentifier(requiredString(input, "project", 100), "project");
  const jobType = requiredString(input, "job_type", 100);
  const shotName = requiredString(input, "shot_name", 220);
  const priority = requiredInteger(input, "priority", -1_000_000, 1_000_000);
  const submittedAt = requiredString(input, "submitted_utc", 50);
  if (!Number.isFinite(Date.parse(submittedAt))) {
    throw new HttpError(
      400,
      "invalid_field",
      "submitted_utc must be an ISO-8601 timestamp.",
    );
  }

  const rawRenderVersion = input.render_version;
  let renderVersion: number | null = null;
  if (rawRenderVersion !== undefined && rawRenderVersion !== null) {
    if (!Number.isInteger(rawRenderVersion) || (rawRenderVersion as number) < 0) {
      throw new HttpError(
        400,
        "invalid_field",
        "render_version must be a non-negative integer.",
      );
    }
    renderVersion = rawRenderVersion as number;
  }

  const payload: JsonRecord = { ...input };
  payload.status = "queued";
  payload.attempt = 0;
  payload.worker = null;
  payload.claimed_utc = null;
  payload.render_started_utc = null;
  payload.render_finished_utc = null;
  payload.result = null;
  payload.last_failure = null;
  payload.blacklisted_workers = [];
  if (payload.overwrite_existing_mp4 === undefined) {
    payload.overwrite_existing_mp4 = true;
  }
  if (payload.overwrite_existing_exr === undefined) {
    payload.overwrite_existing_exr = true;
  }

  return {
    payload,
    payloadJson: JSON.stringify(payload),
    id,
    batchId: optionalString(payload, "batch_id", 220),
    project,
    jobType,
    shotName,
    renderVersion,
    priority,
    submittedAt,
    submittedBy: optionalString(payload, "submitted_by", 220),
    submittedUser: optionalString(payload, "submitted_user", 220),
    resubmittedFromJobId: optionalString(
      payload,
      "resubmitted_from_job_id",
      220,
    ),
  };
}

async function insertNormalizedJob(env: Env, job: NormalizedJob): Promise<CreatedJob> {
  const insert = await env.DB.prepare(
    `INSERT INTO jobs (
       id, batch_id, project, job_type, shot_name, render_version,
       status, priority, submitted_at, submitted_by, submitted_user,
       updated_at, payload_json, resubmitted_from_job_id
     ) VALUES (
       ?1, ?2, ?3, ?4, ?5, ?6,
       'queued', ?7, ?8, ?9, ?10,
       ${NOW_SQL}, ?11, ?12
     )
     ON CONFLICT(id) DO NOTHING`,
  )
    .bind(
      job.id,
      job.batchId,
      job.project,
      job.jobType,
      job.shotName,
      job.renderVersion,
      job.priority,
      job.submittedAt,
      job.submittedBy,
      job.submittedUser,
      job.payloadJson,
      job.resubmittedFromJobId,
    )
    .run();

  const row = await env.DB.prepare("SELECT * FROM jobs WHERE id = ?1")
    .bind(job.id)
    .first<JobRow>();
  if (!row) {
    throw new Error(`Job ${job.id} was not readable after submission`);
  }

  if (insert.meta.changes > 0) {
    await env.DB.prepare(
      `INSERT INTO job_events (
         job_id, event_type, created_at, details_json
       ) VALUES (?1, 'submitted', ${NOW_SQL}, ?2)`,
    )
      .bind(job.id, JSON.stringify({ submitted_by: job.submittedBy }))
      .run();
  }
  return { created: insert.meta.changes > 0, row };
}

export async function submitJob(
  env: Env,
  payload: JsonRecord,
): Promise<CreatedJob> {
  return insertNormalizedJob(env, normalizeJobPayload(payload));
}

async function blacklistForJob(env: Env, jobId: string): Promise<string[]> {
  const rows = await env.DB.prepare(
    "SELECT worker_id FROM job_blacklist WHERE job_id = ?1 ORDER BY created_at, worker_id",
  )
    .bind(jobId)
    .all<{ worker_id: string }>();
  return rows.results.map((row) => row.worker_id);
}

function runtimePayload(
  row: JobRow,
  blacklistedWorkers: string[],
): JsonRecord {
  const storedPayload = parseStoredRecord(row.payload_json);
  if (!storedPayload) {
    throw new Error(`Job ${row.id} has no stored payload`);
  }
  return {
    ...storedPayload,
    job_id: row.id,
    batch_id: row.batch_id,
    project: row.project,
    job_type: row.job_type,
    shot_name: row.shot_name,
    render_version: row.render_version,
    status: row.status,
    priority: row.priority,
    submitted_utc: row.submitted_at,
    submitted_by: row.submitted_by,
    submitted_user: row.submitted_user,
    attempt: row.attempt_count,
    worker: row.worker_id,
    claimed_utc: row.claimed_at,
    render_started_utc: row.render_started_at,
    render_finished_utc: row.render_finished_at,
    result: parseStoredRecord(row.result_json),
    last_failure: parseStoredRecord(row.last_failure_json),
    blacklisted_workers: blacklistedWorkers,
    resubmitted_from_job_id: row.resubmitted_from_job_id,
    progress: row.progress,
    revision: row.revision,
  };
}

function summaryFromRow(row: JobRow, blacklist: string[]): JobSummary {
  return {
    job_id: row.id,
    batch_id: row.batch_id,
    project: row.project,
    job_type: row.job_type,
    shot_name: row.shot_name,
    render_version: row.render_version,
    status: row.status,
    priority: row.priority,
    submitted_utc: row.submitted_at,
    submitted_by: row.submitted_by,
    submitted_user: row.submitted_user,
    updated_utc: row.updated_at,
    attempt: row.attempt_count,
    worker: row.worker_id,
    lease_expires_at: row.lease_expires_at,
    claimed_utc: row.claimed_at,
    render_started_utc: row.render_started_at,
    render_finished_utc: row.render_finished_at,
    progress: row.progress,
    blacklisted_workers: blacklist,
    resubmitted_from_job_id: row.resubmitted_from_job_id,
    revision: row.revision,
  };
}

async function upsertWorker(
  env: Env,
  worker: WorkerRequest,
  status: "waiting" | "rendering" | "stopped",
  currentJobId: string | null,
): Promise<void> {
  await env.DB.prepare(
    `INSERT INTO workers (
       id, display_name, first_seen_at, last_seen_at, status,
       current_job_id, app_version, capabilities_json
     ) VALUES (?1, ?1, ${NOW_SQL}, ${NOW_SQL}, ?2, ?3, ?4, ?5)
     ON CONFLICT(id) DO UPDATE SET
       display_name = excluded.display_name,
       last_seen_at = excluded.last_seen_at,
       status = excluded.status,
       current_job_id = excluded.current_job_id,
       app_version = excluded.app_version,
       capabilities_json = excluded.capabilities_json`,
  )
    .bind(
      worker.workerId,
      status,
      currentJobId,
      worker.appVersion,
      worker.capabilities ? JSON.stringify(worker.capabilities) : null,
    )
    .run();
}

export function parseWorkerRequest(data: JsonRecord): WorkerRequest {
  const workerId = safeIdentifier(
    requiredString(data, "worker_id", 128),
    "worker_id",
  );
  const capabilitiesValue = data.capabilities;
  const capabilities =
    capabilitiesValue === undefined || capabilitiesValue === null
      ? null
      : requireRecord(capabilitiesValue, "capabilities");
  return {
    workerId,
    appVersion: optionalString(data, "app_version", 100),
    capabilities,
  };
}

export function parseLeaseRequest(data: JsonRecord): LeaseRequest {
  return {
    ...parseWorkerRequest(data),
    leaseToken: safeIdentifier(
      requiredString(data, "lease_token", 128),
      "lease_token",
    ),
  };
}

export async function expireStaleLeases(env: Env): Promise<number> {
  const results = await env.DB.batch([
    env.DB.prepare(
      `UPDATE job_attempts
       SET status = 'lease_expired', finished_at = ${NOW_SQL},
           result_json = json_object(
             'status', 'failed',
             'reason', 'Worker lease expired before completion'
           )
       WHERE status = 'rendering'
         AND lease_token IN (
           SELECT lease_token FROM jobs
           WHERE status = 'rendering'
             AND lease_expires_at IS NOT NULL
             AND lease_expires_at <= unixepoch()
         )`,
    ),
    env.DB.prepare(
      `INSERT INTO job_blacklist (
         job_id, worker_id, reason, created_at, attempt_number
       )
       SELECT id, worker_id, 'Worker lease expired', ${NOW_SQL}, attempt_count
       FROM jobs
       WHERE status = 'rendering'
         AND worker_id IS NOT NULL
         AND lease_expires_at IS NOT NULL
         AND lease_expires_at <= unixepoch()
       ON CONFLICT(job_id, worker_id) DO UPDATE SET
         reason = excluded.reason,
         created_at = excluded.created_at,
         attempt_number = excluded.attempt_number`,
    ),
    env.DB.prepare(
      `INSERT INTO job_events (
         job_id, event_type, created_at, worker_id, attempt_number, details_json
       )
       SELECT id, 'lease_expired', ${NOW_SQL}, worker_id, attempt_count,
              json_object('reason', 'Worker lease expired before completion')
       FROM jobs
       WHERE status = 'rendering'
         AND lease_expires_at IS NOT NULL
         AND lease_expires_at <= unixepoch()`,
    ),
    env.DB.prepare(
      `UPDATE workers
       SET status = 'waiting', current_job_id = NULL, last_seen_at = ${NOW_SQL}
       WHERE current_job_id IN (
         SELECT id FROM jobs
         WHERE status = 'rendering'
           AND lease_expires_at IS NOT NULL
           AND lease_expires_at <= unixepoch()
       )`,
    ),
    env.DB.prepare(
      `UPDATE jobs
       SET status = 'queued', worker_id = NULL, lease_token = NULL,
           lease_expires_at = NULL, claimed_at = NULL,
           render_started_at = NULL, render_finished_at = NULL,
           progress = 0,
           last_failure_json = json_object(
             'status', 'failed',
             'reason', 'Worker lease expired before completion'
           ),
           updated_at = ${NOW_SQL}, revision = revision + 1
       WHERE status = 'rendering'
         AND lease_expires_at IS NOT NULL
         AND lease_expires_at <= unixepoch()`,
    ),
  ]);
  return results[results.length - 1]?.meta.changes ?? 0;
}

export async function claimJob(
  env: Env,
  data: JsonRecord,
): Promise<{ row: JobRow; payload: JsonRecord } | null> {
  const worker = parseWorkerRequest(data);
  const claimRequestId = safeIdentifier(
    requiredString(data, "claim_request_id", 128),
    "claim_request_id",
  );
  const leaseSeconds = parseLeaseSeconds(env);

  await expireStaleLeases(env);

  const priorClaim = await env.DB.prepare(
    `SELECT * FROM jobs
     WHERE lease_token = ?1 AND worker_id = ?2 AND status = 'rendering'`,
  )
    .bind(claimRequestId, worker.workerId)
    .first<JobRow>();
  if (priorClaim) {
    return {
      row: priorClaim,
      payload: runtimePayload(
        priorClaim,
        await blacklistForJob(env, priorClaim.id),
      ),
    };
  }

  const activeWorkerClaim = await env.DB.prepare(
    `SELECT * FROM jobs
     WHERE worker_id = ?1 COLLATE NOCASE AND status = 'rendering'
     ORDER BY claimed_at, id
     LIMIT 1`,
  )
    .bind(worker.workerId)
    .first<JobRow>();
  if (activeWorkerClaim) {
    return {
      row: activeWorkerClaim,
      payload: runtimePayload(
        activeWorkerClaim,
        await blacklistForJob(env, activeWorkerClaim.id),
      ),
    };
  }

  await upsertWorker(env, worker, "waiting", null);
  if (await workerStopRequested(env, worker.workerId)) {
    return null;
  }

  const row = await env.DB.prepare(
    `UPDATE jobs
     SET status = 'rendering', worker_id = ?1, lease_token = ?2,
         lease_expires_at = unixepoch() + ?3,
         claimed_at = ${NOW_SQL}, render_started_at = ${NOW_SQL},
         render_finished_at = NULL, progress = 0,
         attempt_count = attempt_count + 1,
         updated_at = ${NOW_SQL}, revision = revision + 1
     WHERE id = (
       SELECT candidate.id
       FROM jobs AS candidate
       WHERE candidate.status = 'queued'
         AND NOT EXISTS (
           SELECT 1 FROM job_blacklist AS blocked
           WHERE blocked.job_id = candidate.id
             AND blocked.worker_id = ?1 COLLATE NOCASE
         )
         AND NOT EXISTS (
           SELECT 1 FROM jobs AS existing
           WHERE existing.lease_token = ?2
         )
       ORDER BY candidate.priority DESC,
                candidate.submitted_at ASC,
                candidate.id ASC
       LIMIT 1
     )
       AND status = 'queued'
     RETURNING *`,
  )
    .bind(worker.workerId, claimRequestId, leaseSeconds)
    .first<JobRow>();

  if (!row) {
    return null;
  }

  await env.DB.batch([
    env.DB.prepare(
      `INSERT INTO job_attempts (
         job_id, attempt_number, worker_id, lease_token, status, claimed_at
       ) VALUES (?1, ?2, ?3, ?4, 'rendering', ${NOW_SQL})
       ON CONFLICT(lease_token) DO NOTHING`,
    ).bind(row.id, row.attempt_count, worker.workerId, claimRequestId),
    env.DB.prepare(
      `INSERT INTO job_events (
         job_id, event_type, created_at, worker_id, attempt_number, details_json
       ) VALUES (
         ?1, 'claimed', ${NOW_SQL}, ?2, ?3,
         json_object('lease_token', ?4, 'lease_seconds', ?5)
       )`,
    ).bind(
      row.id,
      worker.workerId,
      row.attempt_count,
      claimRequestId,
      leaseSeconds,
    ),
    env.DB.prepare(
      `UPDATE workers
       SET status = 'rendering', current_job_id = ?1, last_seen_at = ${NOW_SQL}
       WHERE id = ?2`,
    ).bind(row.id, worker.workerId),
  ]);

  return {
    row,
    payload: runtimePayload(row, await blacklistForJob(env, row.id)),
  };
}

export async function heartbeatJob(
  env: Env,
  jobId: string,
  data: JsonRecord,
): Promise<JobRow> {
  const lease = parseLeaseRequest(data);
  const progress = optionalNumber(data, "progress", 0, 100);
  const leaseSeconds = parseLeaseSeconds(env);
  const row = await env.DB.prepare(
    `UPDATE jobs
     SET lease_expires_at = unixepoch() + ?1,
         progress = COALESCE(?2, progress),
         updated_at = ${NOW_SQL}, revision = revision + 1
     WHERE id = ?3 AND status = 'rendering'
       AND worker_id = ?4 COLLATE NOCASE
       AND lease_token = ?5
     RETURNING *`,
  )
    .bind(leaseSeconds, progress, jobId, lease.workerId, lease.leaseToken)
    .first<JobRow>();
  if (!row) {
    throw new HttpError(
      409,
      "lease_lost",
      "The job is no longer owned by this worker lease.",
    );
  }
  await upsertWorker(env, lease, "rendering", jobId);
  return row;
}

export async function releaseJob(
  env: Env,
  jobId: string,
  data: JsonRecord,
): Promise<{ row: JobRow; payload: JsonRecord }> {
  const lease = parseLeaseRequest(data);
  const active = await findActiveLease(env, jobId, lease);
  if (!active) {
    const replay = await completedAttemptReplay(
      env,
      jobId,
      lease,
      "released",
      new Set<JobStatus>(["queued"]),
    );
    if (replay) {
      return replay;
    }
    throw new HttpError(
      409,
      "lease_lost",
      "The job is no longer owned by this worker lease.",
    );
  }
  const reason =
    optionalString(data, "reason", 10_000) ??
    "Worker released the job before rendering";
  const resultJson = JSON.stringify({
    schema_version: 1,
    status: "released",
    worker: lease.workerId,
    reason,
    released_utc: new Date().toISOString(),
  });
  const results = await env.DB.batch([
    env.DB.prepare(
      `UPDATE job_attempts
       SET status = 'released', finished_at = ${NOW_SQL}, result_json = ?1
       WHERE job_id = ?2 AND attempt_number = ?3
         AND lease_token = ?4 AND status = 'rendering'`,
    ).bind(resultJson, jobId, active.attempt_count, lease.leaseToken),
    env.DB.prepare(
      `INSERT INTO job_events (
         job_id, event_type, created_at, worker_id, attempt_number, details_json
       )
       SELECT id, 'released', ${NOW_SQL}, worker_id, attempt_count, ?1
       FROM jobs
       WHERE id = ?2 AND status = 'rendering'
         AND worker_id = ?3 COLLATE NOCASE AND lease_token = ?4`,
    ).bind(resultJson, jobId, lease.workerId, lease.leaseToken),
    env.DB.prepare(
      `UPDATE workers
       SET status = 'waiting', current_job_id = NULL, last_seen_at = ${NOW_SQL}
       WHERE id = ?1 AND current_job_id = ?2
         AND EXISTS (
           SELECT 1 FROM jobs
           WHERE id = ?2 AND status = 'rendering'
             AND worker_id = ?1 COLLATE NOCASE AND lease_token = ?3
         )`,
    ).bind(lease.workerId, jobId, lease.leaseToken),
    env.DB.prepare(
      `UPDATE jobs
       SET status = 'queued', worker_id = NULL, lease_token = NULL,
           lease_expires_at = NULL, claimed_at = NULL,
           render_started_at = NULL, render_finished_at = NULL,
           progress = 0, updated_at = ${NOW_SQL}, revision = revision + 1
       WHERE id = ?1 AND status = 'rendering'
         AND worker_id = ?2 COLLATE NOCASE AND lease_token = ?3`,
    ).bind(jobId, lease.workerId, lease.leaseToken),
  ]);
  if ((results[results.length - 1]?.meta.changes ?? 0) === 0) {
    throw new HttpError(409, "lease_lost", "The worker lease changed during release.");
  }
  const row = await getJobRow(env, jobId);
  return {
    row,
    payload: runtimePayload(row, await blacklistForJob(env, jobId)),
  };
}

function resultFromRequest(
  data: JsonRecord,
  lease: LeaseRequest,
  status: "complete" | "failed",
): JsonRecord {
  const resultValue = data.result;
  const suppliedResult =
    resultValue === undefined || resultValue === null
      ? {}
      : requireRecord(resultValue, "result");
  const reason = optionalString(data, "reason", 10_000);
  return {
    ...suppliedResult,
    schema_version: 1,
    status,
    worker: lease.workerId,
    reason: reason ?? suppliedResult.reason ?? "",
    render_finished_utc: new Date().toISOString(),
  };
}

async function findActiveLease(
  env: Env,
  jobId: string,
  lease: LeaseRequest,
): Promise<JobRow | null> {
  return env.DB.prepare(
    `SELECT * FROM jobs
     WHERE id = ?1 AND status = 'rendering'
       AND worker_id = ?2 COLLATE NOCASE
       AND lease_token = ?3`,
  )
    .bind(jobId, lease.workerId, lease.leaseToken)
    .first<JobRow>();
}

async function completedAttemptReplay(
  env: Env,
  jobId: string,
  lease: LeaseRequest,
  attemptStatus: "complete" | "failed" | "released",
  validJobStatuses: ReadonlySet<JobStatus>,
): Promise<{ row: JobRow; payload: JsonRecord } | null> {
  const attempt = await env.DB.prepare(
    `SELECT 1 AS found FROM job_attempts
     WHERE job_id = ?1 AND worker_id = ?2 COLLATE NOCASE
       AND lease_token = ?3 AND status = ?4
     LIMIT 1`,
  )
    .bind(jobId, lease.workerId, lease.leaseToken, attemptStatus)
    .first<{ found: number }>();
  if (!attempt) {
    return null;
  }
  const row = await getJobRow(env, jobId);
  if (!validJobStatuses.has(row.status)) {
    return null;
  }
  return {
    row,
    payload: runtimePayload(row, await blacklistForJob(env, jobId)),
  };
}

export async function completeJob(
  env: Env,
  jobId: string,
  data: JsonRecord,
): Promise<{ row: JobRow; payload: JsonRecord }> {
  const lease = parseLeaseRequest(data);
  const active = await findActiveLease(env, jobId, lease);
  if (!active) {
    const replay = await completedAttemptReplay(
      env,
      jobId,
      lease,
      "complete",
      new Set<JobStatus>(["complete"]),
    );
    if (replay) {
      return replay;
    }
    throw new HttpError(
      409,
      "lease_lost",
      "The job is no longer owned by this worker lease.",
    );
  }
  const resultJson = JSON.stringify(resultFromRequest(data, lease, "complete"));
  const batchResults = await env.DB.batch([
    env.DB.prepare(
      `UPDATE job_attempts
       SET status = 'complete', finished_at = ${NOW_SQL}, result_json = ?1
       WHERE job_id = ?2 AND attempt_number = ?3
         AND lease_token = ?4 AND status = 'rendering'`,
    ).bind(resultJson, jobId, active.attempt_count, lease.leaseToken),
    env.DB.prepare(
      `INSERT INTO job_events (
         job_id, event_type, created_at, worker_id, attempt_number, details_json
       )
       SELECT id, 'completed', ${NOW_SQL}, worker_id, attempt_count, ?1
       FROM jobs
       WHERE id = ?2 AND status = 'rendering'
         AND worker_id = ?3 COLLATE NOCASE AND lease_token = ?4`,
    ).bind(resultJson, jobId, lease.workerId, lease.leaseToken),
    env.DB.prepare(
      `UPDATE workers
       SET status = 'waiting', current_job_id = NULL, last_seen_at = ${NOW_SQL}
       WHERE id = ?1 AND current_job_id = ?2
         AND EXISTS (
           SELECT 1 FROM jobs
           WHERE id = ?2 AND status = 'rendering'
             AND worker_id = ?1 COLLATE NOCASE AND lease_token = ?3
         )`,
    ).bind(lease.workerId, jobId, lease.leaseToken),
    env.DB.prepare(
      `UPDATE jobs
       SET status = 'complete', result_json = ?1,
           render_finished_at = ${NOW_SQL}, progress = 100,
           worker_id = NULL, lease_token = NULL, lease_expires_at = NULL,
           updated_at = ${NOW_SQL}, revision = revision + 1
       WHERE id = ?2 AND status = 'rendering'
         AND worker_id = ?3 COLLATE NOCASE AND lease_token = ?4
       RETURNING *`,
    ).bind(resultJson, jobId, lease.workerId, lease.leaseToken),
  ]);
  if ((batchResults[batchResults.length - 1]?.meta.changes ?? 0) === 0) {
    throw new HttpError(409, "lease_lost", "The worker lease changed during completion.");
  }
  const row = await getJobRow(env, jobId);
  return {
    row,
    payload: runtimePayload(row, await blacklistForJob(env, jobId)),
  };
}

export async function failJob(
  env: Env,
  jobId: string,
  data: JsonRecord,
): Promise<{ row: JobRow; payload: JsonRecord }> {
  const lease = parseLeaseRequest(data);
  const retryableValue = data.retryable;
  if (retryableValue !== undefined && typeof retryableValue !== "boolean") {
    throw new HttpError(400, "invalid_field", "retryable must be a boolean.");
  }
  const retryable = retryableValue !== false;
  const active = await findActiveLease(env, jobId, lease);
  if (!active) {
    const replay = await completedAttemptReplay(
      env,
      jobId,
      lease,
      "failed",
      new Set<JobStatus>(retryable ? ["queued"] : ["failed"]),
    );
    if (replay) {
      return replay;
    }
    throw new HttpError(
      409,
      "lease_lost",
      "The job is no longer owned by this worker lease.",
    );
  }
  const resultJson = JSON.stringify(resultFromRequest(data, lease, "failed"));
  const nextStatus: JobStatus = retryable ? "queued" : "failed";

  const statements: D1PreparedStatement[] = [
    env.DB.prepare(
      `UPDATE job_attempts
       SET status = 'failed', finished_at = ${NOW_SQL}, result_json = ?1
       WHERE job_id = ?2 AND attempt_number = ?3
         AND lease_token = ?4 AND status = 'rendering'`,
    ).bind(resultJson, jobId, active.attempt_count, lease.leaseToken),
  ];
  if (retryable) {
    statements.push(
      env.DB.prepare(
        `INSERT INTO job_blacklist (
           job_id, worker_id, reason, created_at, attempt_number
         )
         SELECT id, worker_id,
                COALESCE(json_extract(?1, '$.reason'), 'Render failed'),
                ${NOW_SQL}, attempt_count
         FROM jobs
         WHERE id = ?2 AND status = 'rendering'
           AND worker_id = ?3 COLLATE NOCASE AND lease_token = ?4
         ON CONFLICT(job_id, worker_id) DO UPDATE SET
           reason = excluded.reason,
           created_at = excluded.created_at,
           attempt_number = excluded.attempt_number`,
      ).bind(resultJson, jobId, lease.workerId, lease.leaseToken),
    );
  }
  statements.push(
    env.DB.prepare(
      `INSERT INTO job_events (
         job_id, event_type, created_at, worker_id, attempt_number, details_json
       )
       SELECT id, ?1, ${NOW_SQL}, worker_id, attempt_count, ?2
       FROM jobs
       WHERE id = ?3 AND status = 'rendering'
         AND worker_id = ?4 COLLATE NOCASE AND lease_token = ?5`,
    ).bind(
      retryable ? "failed_requeued" : "failed_terminal",
      resultJson,
      jobId,
      lease.workerId,
      lease.leaseToken,
    ),
    env.DB.prepare(
      `UPDATE workers
       SET status = 'waiting', current_job_id = NULL, last_seen_at = ${NOW_SQL}
       WHERE id = ?1 AND current_job_id = ?2
         AND EXISTS (
           SELECT 1 FROM jobs
           WHERE id = ?2 AND status = 'rendering'
             AND worker_id = ?1 COLLATE NOCASE AND lease_token = ?3
         )`,
    ).bind(lease.workerId, jobId, lease.leaseToken),
    env.DB.prepare(
      `UPDATE jobs
       SET status = ?1, last_failure_json = ?2,
           result_json = CASE WHEN ?1 = 'failed' THEN ?2 ELSE NULL END,
           render_finished_at = CASE
             WHEN ?1 = 'failed' THEN ${NOW_SQL} ELSE NULL END,
           claimed_at = CASE WHEN ?1 = 'queued' THEN NULL ELSE claimed_at END,
           render_started_at = CASE
             WHEN ?1 = 'queued' THEN NULL ELSE render_started_at END,
           progress = 0, worker_id = NULL, lease_token = NULL,
           lease_expires_at = NULL, updated_at = ${NOW_SQL},
           revision = revision + 1
       WHERE id = ?3 AND status = 'rendering'
         AND worker_id = ?4 COLLATE NOCASE AND lease_token = ?5`,
    ).bind(nextStatus, resultJson, jobId, lease.workerId, lease.leaseToken),
  );

  const batchResults = await env.DB.batch(statements);
  if ((batchResults[batchResults.length - 1]?.meta.changes ?? 0) === 0) {
    throw new HttpError(409, "lease_lost", "The worker lease changed during failure handling.");
  }
  const row = await getJobRow(env, jobId);
  return {
    row,
    payload: runtimePayload(row, await blacklistForJob(env, jobId)),
  };
}

async function getJobRow(env: Env, jobId: string): Promise<JobRow> {
  const row = await env.DB.prepare("SELECT * FROM jobs WHERE id = ?1")
    .bind(jobId)
    .first<JobRow>();
  if (!row) {
    throw new HttpError(404, "job_not_found", `Job ${jobId} was not found.`);
  }
  return row;
}

export async function getJob(
  env: Env,
  jobId: string,
): Promise<JsonRecord> {
  const row = await getJobRow(env, jobId);
  const [blacklist, attempts, events] = await Promise.all([
    blacklistForJob(env, jobId),
    env.DB.prepare(
      `SELECT attempt_number, worker_id, status, claimed_at, finished_at,
              result_json
       FROM job_attempts WHERE job_id = ?1 ORDER BY attempt_number DESC`,
    )
      .bind(jobId)
      .all<Record<string, unknown>>(),
    env.DB.prepare(
      `SELECT id, event_type, created_at, worker_id, attempt_number, details_json
       FROM job_events WHERE job_id = ?1 ORDER BY id DESC LIMIT 200`,
    )
      .bind(jobId)
      .all<Record<string, unknown>>(),
  ]);
  return {
    job: runtimePayload(row, blacklist),
    summary: summaryFromRow(row, blacklist),
    attempts: attempts.results,
    events: events.results,
  };
}

const VALID_STATUSES = new Set<JobStatus>([
  "queued",
  "rendering",
  "complete",
  "failed",
  "canceled",
]);

export async function listJobs(
  env: Env,
  search: URLSearchParams,
): Promise<{ jobs: JobSummary[]; limit: number; offset: number }> {
  await expireStaleLeases(env);
  const limitValue = Number(search.get("limit") ?? "100");
  const offsetValue = Number(search.get("offset") ?? "0");
  const limit = Number.isInteger(limitValue)
    ? Math.max(1, Math.min(MAX_LIST_LIMIT, limitValue))
    : 100;
  const offset = Number.isInteger(offsetValue) ? Math.max(0, offsetValue) : 0;

  const clauses: string[] = [];
  const bindings: unknown[] = [];
  const status = search.get("status");
  if (status) {
    if (!VALID_STATUSES.has(status as JobStatus)) {
      throw new HttpError(400, "invalid_status", `Unsupported status: ${status}`);
    }
    bindings.push(status);
    clauses.push(`status = ?${bindings.length}`);
  }
  const project = search.get("project")?.trim();
  if (project) {
    bindings.push(project);
    clauses.push(`project = ?${bindings.length}`);
  }
  bindings.push(limit, offset);
  const where = clauses.length ? `WHERE ${clauses.join(" AND ")}` : "";
  const rows = await env.DB.prepare(
    `SELECT * FROM jobs
     ${where}
     ORDER BY submitted_at DESC, id DESC
     LIMIT ?${bindings.length - 1} OFFSET ?${bindings.length}`,
  )
    .bind(...bindings)
    .all<JobRow>();

  const blacklistByJob = new Map<string, string[]>();
  if (rows.results.length > 0) {
    const placeholders = rows.results.map((_, index) => `?${index + 1}`).join(",");
    const blocked = await env.DB.prepare(
      `SELECT job_id, worker_id FROM job_blacklist
       WHERE job_id IN (${placeholders}) ORDER BY created_at, worker_id`,
    )
      .bind(...rows.results.map((row) => row.id))
      .all<{ job_id: string; worker_id: string }>();
    for (const entry of blocked.results) {
      const workers = blacklistByJob.get(entry.job_id) ?? [];
      workers.push(entry.worker_id);
      blacklistByJob.set(entry.job_id, workers);
    }
  }
  return {
    jobs: rows.results.map((row) =>
      summaryFromRow(row, blacklistByJob.get(row.id) ?? []),
    ),
    limit,
    offset,
  };
}

export async function clearBlacklist(
  env: Env,
  jobId: string,
): Promise<{ cleared: number; row: JobRow }> {
  const row = await getJobRow(env, jobId);
  if (row.status === "rendering") {
    throw new HttpError(
      409,
      "job_rendering",
      "A blacklist cannot be cleared while the job is rendering.",
    );
  }
  const results = await env.DB.batch([
    env.DB.prepare("DELETE FROM job_blacklist WHERE job_id = ?1").bind(jobId),
    env.DB.prepare(
      `INSERT INTO job_events (
         job_id, event_type, created_at, details_json
       ) VALUES (?1, 'blacklist_cleared', ${NOW_SQL}, json_object())`,
    ).bind(jobId),
    env.DB.prepare(
      `UPDATE jobs SET updated_at = ${NOW_SQL}, revision = revision + 1
       WHERE id = ?1`,
    ).bind(jobId),
  ]);
  return {
    cleared: results[0]?.meta.changes ?? 0,
    row: await getJobRow(env, jobId),
  };
}

function compactTimestamp(date: Date): string {
  return date.toISOString().replace(/[-:.]/g, "");
}

export async function resubmitJob(
  env: Env,
  sourceJobId: string,
  data: JsonRecord,
): Promise<{ created: boolean; row: JobRow; payload: JsonRecord }> {
  const requestId = safeIdentifier(
    requiredString(data, "request_id", 128),
    "request_id",
  );
  const prior = await env.DB.prepare(
    `SELECT * FROM jobs
     WHERE resubmit_request_id = ?1 AND resubmitted_from_job_id = ?2`,
  )
    .bind(requestId, sourceJobId)
    .first<JobRow>();
  if (prior) {
    return {
      created: false,
      row: prior,
      payload: runtimePayload(prior, await blacklistForJob(env, prior.id)),
    };
  }
  const source = await getJobRow(env, sourceJobId);
  if (source.status === "rendering") {
    throw new HttpError(
      409,
      "job_rendering",
      "A rendering job cannot be resubmitted.",
    );
  }
  const now = new Date();
  const suffix = requestId.replaceAll("-", "").slice(0, 10);
  const submittedAt = now.toISOString();
  const versionText = `v${String(source.render_version ?? 0).padStart(3, "0")}`;
  const newJobId = safeIdentifier(
    `${source.shot_name}_${versionText}_${compactTimestamp(now)}_${suffix}`,
    "generated job_id",
  );
  const submittedBy = optionalString(data, "submitted_by", 220) ?? "FARM-MANAGER";
  const submittedUser = optionalString(data, "submitted_user", 220) ?? "manager";
  const storedPayload = parseStoredRecord(source.payload_json);
  if (!storedPayload) {
    throw new Error(`Job ${sourceJobId} has no stored payload`);
  }
  const payload: JsonRecord = {
    ...storedPayload,
    job_id: newJobId,
    batch_id: `${source.project}_manager_resubmit_${compactTimestamp(now)}_${suffix}`,
    status: "queued",
    submitted_utc: submittedAt,
    submitted_by: submittedBy,
    submitted_user: submittedUser,
    resubmitted_from_job_id: sourceJobId,
    resubmitted_utc: submittedAt,
    resubmitted_by: submittedBy,
    resubmitted_user: submittedUser,
    attempt: 0,
    worker: null,
    claimed_utc: null,
    render_started_utc: null,
    render_finished_utc: null,
    result: null,
    last_failure: null,
    blacklisted_workers: [],
    overwrite_existing_mp4: true,
    overwrite_existing_exr: true,
  };
  const normalized = normalizeJobPayload(payload);

  const results = await env.DB.batch([
    env.DB.prepare(
      `INSERT INTO jobs (
         id, batch_id, project, job_type, shot_name, render_version,
       status, priority, submitted_at, submitted_by, submitted_user,
         updated_at, payload_json, resubmitted_from_job_id,
         resubmit_request_id
       )
       SELECT ?1, ?2, ?3, ?4, ?5, ?6,
              'queued', ?7, ?8, ?9, ?10,
              ${NOW_SQL}, ?11, ?12, ?13
       FROM jobs AS source
       WHERE source.id = ?12 AND source.status != 'rendering'`,
    ).bind(
      normalized.id,
      normalized.batchId,
      normalized.project,
      normalized.jobType,
      normalized.shotName,
      normalized.renderVersion,
      normalized.priority,
      normalized.submittedAt,
      normalized.submittedBy,
      normalized.submittedUser,
      normalized.payloadJson,
      sourceJobId,
      requestId,
    ),
    env.DB.prepare(
      `INSERT INTO job_events (
         job_id, event_type, created_at, details_json
       )
       SELECT ?1, 'resubmitted', ${NOW_SQL},
              json_object('resubmitted_from_job_id', ?2)
       WHERE EXISTS (SELECT 1 FROM jobs WHERE id = ?1)`,
    ).bind(newJobId, sourceJobId),
    env.DB.prepare(
      `UPDATE jobs
       SET status = 'canceled', updated_at = ${NOW_SQL}, revision = revision + 1
       WHERE id = ?1 AND status = 'queued'`,
    ).bind(sourceJobId),
    env.DB.prepare(
      `INSERT INTO job_events (
         job_id, event_type, created_at, details_json
       )
       SELECT ?1, 'superseded', ${NOW_SQL}, json_object('replacement_job_id', ?2)
       WHERE EXISTS (SELECT 1 FROM jobs WHERE id = ?2)`,
    ).bind(sourceJobId, newJobId),
  ]);
  if ((results[0]?.meta.changes ?? 0) === 0) {
    throw new HttpError(
      409,
      "resubmit_race",
      "The source job began rendering before it could be resubmitted.",
    );
  }
  const row = await getJobRow(env, newJobId);
  return { created: true, row, payload: runtimePayload(row, []) };
}

export async function workerStopRequested(
  env: Env,
  workerId: string,
): Promise<boolean> {
  const row = await env.DB.prepare(
    "SELECT stop_requested FROM workers WHERE id = ?1 COLLATE NOCASE",
  )
    .bind(workerId)
    .first<{ stop_requested: number }>();
  return row?.stop_requested === 1;
}

export async function listWorkers(env: Env): Promise<JsonRecord[]> {
  const rows = await env.DB.prepare(
    `SELECT id, display_name, first_seen_at, last_seen_at,
            CASE
              WHEN unixepoch(last_seen_at) < unixepoch() - 180 THEN 'offline'
              ELSE status
            END AS status,
            current_job_id, stop_requested, stop_requested_at,
            app_version, capabilities_json
     FROM workers
     ORDER BY last_seen_at DESC, id COLLATE NOCASE`,
  ).all<Record<string, unknown>>();
  return rows.results;
}

export async function requestWorkerStop(
  env: Env,
  workerId: string,
): Promise<JsonRecord> {
  const result = await env.DB.prepare(
    `UPDATE workers
     SET stop_requested = 1, stop_requested_at = ${NOW_SQL}
     WHERE id = ?1 COLLATE NOCASE
     RETURNING id, stop_requested, stop_requested_at`,
  )
    .bind(workerId)
    .first<Record<string, unknown>>();
  if (!result) {
    throw new HttpError(404, "worker_not_found", `Worker ${workerId} was not found.`);
  }
  return result;
}

export async function acknowledgeWorkerStop(
  env: Env,
  workerId: string,
): Promise<JsonRecord> {
  const result = await env.DB.prepare(
    `UPDATE workers
     SET stop_requested = 0, stop_requested_at = NULL,
         status = 'stopped', current_job_id = NULL, last_seen_at = ${NOW_SQL}
     WHERE id = ?1 COLLATE NOCASE
     RETURNING id, status, stop_requested`,
  )
    .bind(workerId)
    .first<Record<string, unknown>>();
  if (!result) {
    throw new HttpError(404, "worker_not_found", `Worker ${workerId} was not found.`);
  }
  return result;
}
