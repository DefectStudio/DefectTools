import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";

const baseUrl = process.env.DEFECT_FARM_TEST_URL ?? "http://127.0.0.1:8787";
const tokens = {
  submit: process.env.DEFECT_FARM_SUBMIT_TOKEN ?? "local-submit-token-for-tests",
  worker: process.env.DEFECT_FARM_WORKER_TOKEN ?? "local-worker-token-for-tests",
  manager: process.env.DEFECT_FARM_MANAGER_TOKEN ?? "local-manager-token-for-tests",
  viewer: process.env.DEFECT_FARM_VIEWER_TOKEN ?? "local-viewer-token-for-tests",
};

async function request(path, { role, method = "GET", body, expected = 200 } = {}) {
  const response = await fetch(`${baseUrl}${path}`, {
    method,
    headers: {
      ...(role ? { Authorization: `Bearer ${tokens[role]}` } : {}),
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json();
  const expectedStatuses = Array.isArray(expected) ? expected : [expected];
  assert.ok(
    expectedStatuses.includes(response.status),
    `${method} ${path} returned ${response.status}: ${JSON.stringify(data)}`,
  );
  return data;
}

function workerBody(workerId, extra = {}) {
  return {
    worker_id: workerId,
    app_version: "smoke-test",
    capabilities: { test: true },
    ...extra,
  };
}

const suffix = randomUUID().replaceAll("-", "").slice(0, 10);
const jobId = `smoke_job_${suffix}`;
const job = {
  schema_version: 1,
  publisher_schema_version: 4,
  job_id: jobId,
  batch_id: `smoke_batch_${suffix}`,
  project: "s3bishop",
  job_type: "unreal_mrq",
  shot_name: "smoke_shot",
  render_version: 1,
  priority: 50,
  submitted_utc: new Date().toISOString(),
  submitted_by: "SMOKE-TEST",
  submitted_user: "smoke-test",
  output_directory: "F:/smoke-test",
  output_relative_directory: "SHOTS/smoke/lite/unreal/_output/smoke/v001",
  output_file_name_format: "smoke.{frame_number}",
  submission_fingerprint: `smoke-fingerprint-${suffix}`,
};

const health = await request("/health");
assert.equal(health.ok, true);
for (const role of ["submit", "worker", "manager", "viewer"]) {
  const auth = await request("/api/v1/auth/check", { role });
  assert.equal(auth.role, role);
}

await request("/api/v1/jobs", { method: "POST", body: job, expected: 401 });

const submitted = await request("/api/v1/jobs", {
  role: "submit",
  method: "POST",
  body: job,
  expected: 201,
});
assert.equal(submitted.created, true);
assert.equal(submitted.job.overwrite_existing_mp4, true);
assert.equal(submitted.job.overwrite_existing_exr, true);

const replay = await request("/api/v1/jobs", {
  role: "submit",
  method: "POST",
  body: job,
});
assert.equal(replay.idempotent_replay, true);

const fingerprintReplay = await request("/api/v1/jobs", {
  role: "submit",
  method: "POST",
  body: { ...job, job_id: `${jobId}_retry` },
});
assert.equal(fingerprintReplay.idempotent_replay, true);
assert.equal(fingerprintReplay.job.job_id, jobId);

const outputConflict = await request("/api/v1/jobs", {
  role: "submit",
  method: "POST",
  body: {
    ...job,
    job_id: `${jobId}_conflict`,
    submission_fingerprint: `different-fingerprint-${suffix}`,
  },
  expected: 409,
});
assert.equal(outputConflict.error.code, "active_output_conflict");
assert.equal(outputConflict.error.details.conflicting_job_id, jobId);

const initialListing = await request("/api/v1/jobs?limit=100&offset=0", {
  role: "manager",
});
assert.equal(
  initialListing.jobs.some((listedJob) => listedJob.job_id === jobId),
  true,
);

const workerQueuedListing = await request(
  "/api/v1/jobs?status=queued&limit=100&offset=0",
  { role: "worker" },
);
const viewerQueuedListing = await request(
  "/api/v1/jobs?status=queued&limit=100&offset=0",
  { role: "viewer" },
);
assert.equal(
  viewerQueuedListing.jobs.some((listedJob) => listedJob.job_id === jobId),
  true,
  "viewer tokens should be able to see submitted renders",
);
await request("/api/v1/jobs", {
  role: "viewer",
  method: "POST",
  body: { ...job, job_id: `${jobId}_viewer_rejected` },
  expected: 403,
});
await request("/api/v1/jobs/claim", {
  role: "viewer",
  method: "POST",
  body: workerBody("viewer-cannot-claim"),
  expected: 403,
});
assert.equal(
  workerQueuedListing.jobs.some((listedJob) => listedJob.job_id === jobId),
  true,
  "worker tokens should be able to see submitted renders",
);

const workers = ["smoke-worker-a", "smoke-worker-b"];
const claims = await Promise.all(
  workers.map((workerId) =>
    request("/api/v1/jobs/claim", {
      role: "worker",
      method: "POST",
      body: workerBody(workerId, { claim_request_id: randomUUID() }),
    }),
  ),
);
const winningClaim = claims.find((claim) => claim.job_available);
const losingClaim = claims.find((claim) => !claim.job_available);
assert.ok(winningClaim, "exactly one worker should receive the job");
assert.ok(losingClaim, "the other worker must not receive the same job");
assert.equal(claims.filter((claim) => claim.job_available).length, 1);
assert.equal(winningClaim.job.job_id, jobId);
const firstWorker = winningClaim.job.worker;
const secondWorker = workers.find((worker) => worker !== firstWorker);
assert.ok(secondWorker);

const workerRenderingListing = await request(
  "/api/v1/jobs?status=rendering&limit=100&offset=0",
  { role: "worker" },
);
assert.equal(
  workerRenderingListing.jobs.some((listedJob) => listedJob.job_id === jobId),
  true,
  "worker tokens should be able to see ongoing renders",
);

const workerVisibleWorkers = await request("/api/v1/workers", {
  role: "worker",
});
assert.equal(
  workerVisibleWorkers.workers.some((worker) => worker.id === firstWorker),
  true,
  "worker tokens should be able to see render-worker status",
);

const workerVisibleJobDetail = await request(`/api/v1/jobs/${jobId}`, {
  role: "worker",
});
assert.equal(workerVisibleJobDetail.job.job_id, jobId);
assert.equal(workerVisibleJobDetail.job.status, "rendering");

const viewerRenderingListing = await request(
  "/api/v1/jobs?status=rendering&limit=100&offset=0",
  { role: "viewer" },
);
assert.equal(
  viewerRenderingListing.jobs.some((listedJob) => listedJob.job_id === jobId),
  true,
  "viewer tokens should be able to see ongoing renders",
);
const viewerVisibleWorkers = await request("/api/v1/workers", {
  role: "viewer",
});
assert.equal(
  viewerVisibleWorkers.workers.some((worker) => worker.id === firstWorker),
  true,
  "viewer tokens should be able to see render-worker status",
);
const viewerVisibleJobDetail = await request(`/api/v1/jobs/${jobId}`, {
  role: "viewer",
});
assert.equal(viewerVisibleJobDetail.job.job_id, jobId);
await request(`/api/v1/jobs/${jobId}/heartbeat`, {
  role: "viewer",
  method: "POST",
  body: workerBody(firstWorker, {
    lease_token: winningClaim.lease_token,
    progress: 25,
  }),
  expected: 403,
});

const repeatedClaim = await request("/api/v1/jobs/claim", {
  role: "worker",
  method: "POST",
  body: workerBody(firstWorker, { claim_request_id: randomUUID() }),
});
assert.equal(repeatedClaim.job.job_id, jobId);
assert.equal(repeatedClaim.lease_token, winningClaim.lease_token);

await request(`/api/v1/jobs/${jobId}/heartbeat`, {
  role: "worker",
  method: "POST",
  body: workerBody(firstWorker, {
    lease_token: winningClaim.lease_token,
    progress: 12.5,
  }),
});

const failed = await request(`/api/v1/jobs/${jobId}/fail`, {
  role: "worker",
  method: "POST",
  body: workerBody(firstWorker, {
    lease_token: winningClaim.lease_token,
    retryable: true,
    reason: "Intentional smoke-test failure",
  }),
});
assert.equal(failed.job.status, "queued");
assert.deepEqual(failed.job.blacklisted_workers, [firstWorker]);
const failedReplay = await request(`/api/v1/jobs/${jobId}/fail`, {
  role: "worker",
  method: "POST",
  body: workerBody(firstWorker, {
    lease_token: winningClaim.lease_token,
    retryable: true,
    reason: "Intentional smoke-test failure",
  }),
});
assert.equal(failedReplay.job.status, "queued");

const secondClaim = await request("/api/v1/jobs/claim", {
  role: "worker",
  method: "POST",
  body: workerBody(secondWorker, { claim_request_id: randomUUID() }),
});
assert.equal(secondClaim.job_available, true);
assert.equal(secondClaim.job.job_id, jobId);
assert.equal(secondClaim.job.attempt, 2);

const completed = await request(`/api/v1/jobs/${jobId}/complete`, {
  role: "worker",
  method: "POST",
  body: workerBody(secondWorker, {
    lease_token: secondClaim.lease_token,
    result: { output_verified: true },
  }),
});
assert.equal(completed.job.status, "complete");
assert.equal(completed.job.result.output_verified, true);
const completedReplay = await request(`/api/v1/jobs/${jobId}/complete`, {
  role: "worker",
  method: "POST",
  body: workerBody(secondWorker, {
    lease_token: secondClaim.lease_token,
    result: { output_verified: true },
  }),
});
assert.equal(completedReplay.job.status, "complete");

const detail = await request(`/api/v1/jobs/${jobId}`, { role: "manager" });
assert.equal(detail.job.status, "complete");
assert.equal(detail.attempts.length, 2);
assert.equal(detail.events.some((event) => event.event_type === "failed_requeued"), true);

const stopWorker = `smoke-stop-worker-${suffix}`;
const idleStopWorker = await request("/api/v1/jobs/claim", {
  role: "worker",
  method: "POST",
  body: workerBody(stopWorker, { claim_request_id: randomUUID() }),
});
assert.equal(idleStopWorker.job_available, false);
assert.equal(idleStopWorker.stop_requested, false);
await request(`/api/v1/workers/${stopWorker}/stop`, {
  role: "worker",
  method: "POST",
  expected: 403,
});
await request(`/api/v1/workers/${stopWorker}/stop`, {
  role: "viewer",
  method: "POST",
  expected: 403,
});
await request(`/api/v1/workers/${stopWorker}/stop`, {
  role: "manager",
  method: "POST",
});
const stoppedWorkerClaim = await request("/api/v1/jobs/claim", {
  role: "worker",
  method: "POST",
  body: workerBody(stopWorker, { claim_request_id: randomUUID() }),
});
assert.equal(stoppedWorkerClaim.job_available, false);
assert.equal(stoppedWorkerClaim.stop_requested, true);
await request(`/api/v1/workers/${stopWorker}/stop-ack`, {
  role: "worker",
  method: "POST",
});

const cleared = await request(`/api/v1/jobs/${jobId}/clear-blacklist`, {
  role: "manager",
  method: "POST",
  body: {},
});
assert.equal(cleared.cleared, 1);
assert.deepEqual(cleared.job.blacklisted_workers, []);

const resubmitRequestId = randomUUID();
const resubmitBody = {
  request_id: resubmitRequestId,
  submitted_by: "SMOKE-MANAGER",
  submitted_user: "smoke-test",
};
const resubmitted = await request(`/api/v1/jobs/${jobId}/resubmit`, {
  role: "manager",
  method: "POST",
  body: resubmitBody,
  expected: 201,
});
assert.equal(resubmitted.job.status, "queued");
assert.equal(resubmitted.job.resubmitted_from_job_id, jobId);
assert.equal(resubmitted.job.overwrite_existing_mp4, true);
assert.equal(resubmitted.job.overwrite_existing_exr, true);
const resubmittedReplay = await request(`/api/v1/jobs/${jobId}/resubmit`, {
  role: "manager",
  method: "POST",
  body: resubmitBody,
});
assert.equal(resubmittedReplay.idempotent_replay, true);
assert.equal(resubmittedReplay.job.job_id, resubmitted.job.job_id);

const releaseClaim = await request("/api/v1/jobs/claim", {
  role: "worker",
  method: "POST",
  body: workerBody("smoke-release-worker", { claim_request_id: randomUUID() }),
});
assert.equal(releaseClaim.job_available, true);
assert.equal(releaseClaim.job.job_id, resubmitted.job.job_id);
const replacementJobId = `smoke_replacement_${suffix}`;
const replacementJob = {
  ...resubmitted.job,
  job_id: replacementJobId,
  batch_id: `smoke_replacement_batch_${suffix}`,
  status: "queued",
  submitted_utc: new Date().toISOString(),
  resubmitted_from_job_id: resubmitted.job.job_id,
};
const renderingReplacementRejected = await request(
  `/api/v1/jobs/${resubmitted.job.job_id}/replace`,
  {
    role: "manager",
    method: "POST",
    body: replacementJob,
    expected: 409,
  },
);
assert.equal(renderingReplacementRejected.error.code, "job_rendering");
const released = await request(
  `/api/v1/jobs/${resubmitted.job.job_id}/release`,
  {
    role: "worker",
    method: "POST",
    body: workerBody("smoke-release-worker", {
      lease_token: releaseClaim.lease_token,
      reason: "Package has not synced to this worker yet",
    }),
  },
);
assert.equal(released.job.status, "queued");
assert.deepEqual(released.job.blacklisted_workers, []);
const releasedReplay = await request(
  `/api/v1/jobs/${resubmitted.job.job_id}/release`,
  {
    role: "worker",
    method: "POST",
    body: workerBody("smoke-release-worker", {
      lease_token: releaseClaim.lease_token,
      reason: "Package has not synced to this worker yet",
    }),
  },
);
assert.equal(releasedReplay.job.status, "queued");

await request(`/api/v1/jobs/${resubmitted.job.job_id}/replace`, {
  role: "submit",
  method: "POST",
  body: replacementJob,
  expected: 403,
});
const replaced = await request(
  `/api/v1/jobs/${resubmitted.job.job_id}/replace`,
  {
    role: "manager",
    method: "POST",
    body: replacementJob,
    expected: 201,
  },
);
assert.equal(replaced.created, true);
assert.equal(replaced.source_deleted, true);
assert.equal(replaced.deleted_job_id, resubmitted.job.job_id);
assert.equal(replaced.job.job_id, replacementJobId);
const replaceReplay = await request(
  `/api/v1/jobs/${resubmitted.job.job_id}/replace`,
  {
    role: "manager",
    method: "POST",
    body: replacementJob,
  },
);
assert.equal(replaceReplay.idempotent_replay, true);
assert.equal(replaceReplay.source_deleted, true);
assert.equal(replaceReplay.job.job_id, replacementJobId);
await request(`/api/v1/jobs/${resubmitted.job.job_id}`, {
  role: "manager",
  expected: 404,
});
const replacementDetail = await request(
  `/api/v1/jobs/${replacementJobId}`,
  { role: "manager" },
);
assert.equal(replacementDetail.job.status, "queued");

const deletionClaim = await request("/api/v1/jobs/claim", {
  role: "worker",
  method: "POST",
  body: workerBody("smoke-delete-worker", { claim_request_id: randomUUID() }),
});
assert.equal(deletionClaim.job_available, true);
assert.equal(deletionClaim.job.job_id, replacementJobId);
await request(`/api/v1/jobs/${replacementJobId}`, {
  role: "worker",
  method: "DELETE",
  expected: 403,
});
await request(`/api/v1/jobs/${replacementJobId}`, {
  role: "viewer",
  method: "DELETE",
  expected: 403,
});
const renderingDeleteRejected = await request(
  `/api/v1/jobs/${replacementJobId}`,
  {
    role: "manager",
    method: "DELETE",
    expected: 409,
  },
);
assert.equal(renderingDeleteRejected.error.code, "job_rendering");
await request(`/api/v1/jobs/${replacementJobId}/release`, {
  role: "worker",
  method: "POST",
  body: workerBody("smoke-delete-worker", {
    lease_token: deletionClaim.lease_token,
    reason: "Preparing deletion smoke test",
  }),
});
await request(`/api/v1/jobs/${replacementJobId}`, {
  role: "submit",
  method: "DELETE",
  expected: 403,
});
const replacementDeleted = await request(
  `/api/v1/jobs/${replacementJobId}`,
  {
    role: "manager",
    method: "DELETE",
  },
);
assert.equal(replacementDeleted.deleted, true);
assert.equal(replacementDeleted.deletion_confirmed, true);
await request(`/api/v1/jobs/${replacementJobId}`, {
  role: "manager",
  expected: 404,
});
const replacementDeleteReplay = await request(
  `/api/v1/jobs/${replacementJobId}`,
  {
    role: "manager",
    method: "DELETE",
  },
);
assert.equal(replacementDeleteReplay.deleted, false);
assert.equal(replacementDeleteReplay.idempotent_replay, true);
assert.equal(replacementDeleteReplay.deletion_confirmed, true);

const historyDeleted = await request(`/api/v1/jobs/${jobId}`, {
  role: "manager",
  method: "DELETE",
});
assert.equal(historyDeleted.deleted, true);
await request(`/api/v1/jobs/${jobId}`, {
  role: "manager",
  expected: 404,
});

const fingerprintRaceJob = {
  ...job,
  batch_id: `fingerprint_race_batch_${suffix}`,
  output_relative_directory: `smoke/fingerprint-race/${suffix}`,
  output_file_name_format: "race.{frame_number}",
  submission_fingerprint: `fingerprint-race-${suffix}`,
};
const fingerprintRace = await Promise.all(
  ["a", "b"].map((label) =>
    request("/api/v1/jobs", {
      role: "submit",
      method: "POST",
      body: { ...fingerprintRaceJob, job_id: `fingerprint_race_${label}_${suffix}` },
      expected: [200, 201],
    }),
  ),
);
assert.equal(fingerprintRace.filter((response) => response.created).length, 1);
assert.equal(fingerprintRace[0].job.job_id, fingerprintRace[1].job.job_id);
await request(`/api/v1/jobs/${fingerprintRace[0].job.job_id}`, {
  role: "manager",
  method: "DELETE",
});

const outputRaceBase = {
  ...job,
  batch_id: `output_race_batch_${suffix}`,
  output_relative_directory: `smoke/output-race/${suffix}`,
  output_file_name_format: "race.{frame_number}",
};
const outputRace = await Promise.all(
  ["a", "b"].map((label) =>
    request("/api/v1/jobs", {
      role: "submit",
      method: "POST",
      body: {
        ...outputRaceBase,
        job_id: `output_race_${label}_${suffix}`,
        submission_fingerprint: `output-race-${label}-${suffix}`,
      },
      expected: [201, 409],
    }),
  ),
);
assert.equal(outputRace.filter((response) => response.created).length, 1);
assert.equal(
  outputRace.filter(
    (response) => response.error?.code === "active_output_conflict",
  ).length,
  1,
);
const outputRaceWinner = outputRace.find((response) => response.created);
assert.ok(outputRaceWinner);
await request(`/api/v1/jobs/${outputRaceWinner.job.job_id}`, {
  role: "manager",
  method: "DELETE",
});

console.log(
  JSON.stringify({
    ok: true,
    tested_job_id: jobId,
    resubmitted_job_id: resubmitted.job.job_id,
    replacement_job_id: replacementJobId,
    deleted_history_job_id: jobId,
    atomic_claim_winner: firstWorker,
    retry_claim_winner: secondWorker,
  }),
);
