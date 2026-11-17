import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { mkdir, readFile, readdir } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

// The optional runtime lets this suite run without installing dependencies in
// a shared source checkout. All generated files and local D1 state stay here.
const cache = resolve(process.env.DEFECT_FARM_TEST_CACHE ?? "D:/AICache/render-manager-job-controls/cloud/tests");
const runtime = process.env.DEFECT_FARM_TEST_RUNTIME;
const require = createRequire(runtime ? resolve(runtime, "package.json") : import.meta.url);
const { build } = require("esbuild");
const { Miniflare, convertV4MiniflareOptions } = require("miniflare");
const source = resolve(dirname(fileURLToPath(import.meta.url)), "..");
await mkdir(cache, { recursive: true });
process.chdir(cache);
const scriptPath = resolve(cache, "dispatcher.mjs");
await build({ entryPoints: [resolve(source, "src/index.ts")], bundle: true, format: "esm", platform: "neutral", outfile: scriptPath });
const tokens = { submit: "test-submit", worker: "test-worker", manager: "test-manager", viewer: "test-viewer" };
const farmOptions = {
  modules: true, scriptPath, compatibilityDate: "2026-08-18",
  d1Databases: ["DB"], d1Persist: resolve(cache, `d1-${randomUUID()}`),
  bindings: {
    ENVIRONMENT: "v2-local", API_VERSION: "v1", LEASE_SECONDS: "300",
    SUBMIT_TOKEN: tokens.submit, WORKER_TOKEN: tokens.worker,
    MANAGER_TOKEN: tokens.manager, VIEWER_TOKEN: tokens.viewer,
  },
};
const farm = new Miniflare(convertV4MiniflareOptions ? convertV4MiniflareOptions(farmOptions) : farmOptions);

let assertions = 0;
function equal(actual, expected, message) { assert.deepEqual(actual, expected, message); assertions++; }
async function request(path, { role = "manager", method = "GET", body, expected = 200 } = {}) {
  const response = await farm.dispatchFetch(`https://farm.test${path}`, {
    method, headers: { Authorization: `Bearer ${tokens[role]}`, "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (Array.isArray(expected)) {
    equal(expected.includes(response.status), true, `${method} ${path}: ${JSON.stringify(data)}`);
  } else {
    equal(response.status, expected, `${method} ${path}: ${JSON.stringify(data)}`);
  }
  return data;
}
const workerBody = (worker, extra = {}) => ({ worker_id: worker, app_version: "job-controls-test", ...extra });
async function claim(worker, project) {
  return request("/api/v1/jobs/claim", { role: "worker", method: "POST", body: workerBody(worker, { claim_request_id: randomUUID(), eligible_project_ids: [project] }) });
}
async function submit(id, project, extra = {}) {
  return request("/api/v1/jobs", { role: "submit", method: "POST", expected: 201, body: {
    schema_version: 1, job_id: id, project, job_type: "unreal_mrq", shot_name: id,
    render_version: 7, priority: 50, submitted_utc: new Date().toISOString(), output_directory: `D:/renders/${id}`, ...extra,
  } });
}
const control = (id, action, snapshot, requestId = randomUUID(), extra = {}) => request(`/api/v1/jobs/${id}/${action}`, {
  method: "POST", body: { request_id: requestId, expected_attempt: snapshot.attempt, expected_status: snapshot.status, ...extra },
});

try {
  const db = await farm.getD1Database("DB");
  for (const migration of (await readdir(resolve(source, "migrations"))).filter(name => name.endsWith(".sql")).sort()) {
    const sql = await readFile(resolve(source, "migrations", migration), "utf8");
    for (const statement of sql.split(/;\s*(?:\r?\n|$)/).map(part => part.trim()).filter(Boolean)) {
      await db.prepare(statement).run();
    }
  }
  equal((await request("/health")).features.job_controls, true);
  equal((await request("/health")).features.requeue_clears_blacklist, true);
  await submit("controlled", "target-project");
  await submit("unrelated", "other-project");
  const owner = await claim("OWNER", "target-project");
  const unrelated = await claim("OTHER-ACTIVE", "other-project");
  await claim("IDLE-ACTIVE", "empty-project");
  await claim("STOPPED", "empty-project");
  await request("/api/v1/workers/STOPPED/stop-ack", { role: "worker", method: "POST" });
  await claim("STALE-IDLE", "empty-project");
  await db.prepare("UPDATE workers SET last_seen_at = '2000-01-01T00:00:00Z' WHERE id IN ('STALE-IDLE', 'OWNER')").run();
  const rendering = (await request("/api/v1/jobs/controlled")).summary;
  // A normal progress heartbeat changes revision; the selected attempt remains
  // valid, so stopping it must still succeed.
  await request("/api/v1/jobs/controlled/heartbeat", { role: "worker", method: "POST", body: workerBody("OWNER", { lease_token: owner.lease_token, progress: 45 }) });
  await db.prepare("UPDATE workers SET last_seen_at = '2000-01-01T00:00:00Z' WHERE id = 'OWNER'").run();
  const stopId = randomUUID();
  const stopped = await control("controlled", "stop", rendering, stopId);
  equal(stopped.job.status, "canceled");
  equal(stopped.job.job_id, "controlled");
  equal(stopped.job.render_version, 7);
  equal(stopped.job.blacklisted_workers.slice().sort(), ["IDLE-ACTIVE", "OTHER-ACTIVE", "OWNER"]);
  equal(stopped.summary.worker, null);
  equal(stopped.summary.lease_expires_at, null);
  equal(stopped.attempts[0].status, "released");
  equal(JSON.parse(stopped.attempts[0].result_json).action, "stop");
  equal((await control("controlled", "stop", rendering, stopId)).idempotent_replay, true);
  const workers = (await request("/api/v1/workers")).workers;
  equal(workers.every(worker => worker.stop_requested === 0), true, "Job controls never stop listeners");
  equal((await request("/api/v1/jobs/unrelated")).summary.worker, "OTHER-ACTIVE");
  equal((await request("/api/v1/jobs/unrelated")).summary.status, "rendering");

  for (const action of ["heartbeat", "complete", "fail", "release"]) {
    const response = await request(`/api/v1/jobs/controlled/${action}`, { role: "worker", method: "POST", expected: 409,
      body: workerBody("OWNER", { lease_token: owner.lease_token, reason: "stale worker report" }) });
    equal(response.error.code, "lease_lost");
    equal(response.error.details.job_control_requested, true);
    equal(response.error.details.action, "stop");
  }
  const wrongToken = await request("/api/v1/jobs/controlled/heartbeat", { role: "worker", method: "POST", expected: 409,
    body: workerBody("OWNER", { lease_token: randomUUID() }) });
  equal(wrongToken.error.code, "lease_lost");

  const queued = await control("controlled", "requeue", stopped.summary);
  equal(queued.job.status, "queued");
  equal(queued.job.job_id, "controlled");
  equal(queued.job.render_version, 7);
  equal(queued.job.blacklisted_workers, [], "Requeue clears the stopped job's active-farm blacklist");
  const newClaim = await claim("OWNER", "target-project");
  equal(newClaim.job_available, true, "The original worker can claim again after observing its canceled lease");
  equal(newClaim.job.job_id, "controlled");
  const oldRequest = await control("controlled", "stop", rendering, stopId);
  equal(oldRequest.idempotent_replay, true);
  equal(oldRequest.job.status, "rendering", "A retried stop cannot cancel a newer attempt");
  const stale = await request("/api/v1/jobs/controlled/stop", { method: "POST", expected: 409,
    body: { request_id: randomUUID(), expected_attempt: rendering.attempt, expected_status: "rendering" } });
  equal(stale.error.code, "job_state_changed");
  const newSnapshot = (await request("/api/v1/jobs/controlled")).summary;
  await db.prepare("INSERT INTO job_blacklist (job_id, worker_id, reason, created_at) VALUES ('controlled', 'PREVIOUS-FAILURE', 'Previous render failure', '2000-01-01T00:00:00Z')").run();
  const requeueId = randomUUID();
  const requeued = await control("controlled", "requeue", newSnapshot, requeueId);
  equal(requeued.job.status, "queued");
  equal(requeued.job.blacklisted_workers, [], "Requeue of a rendering job clears all pre-existing blacklist entries");
  equal(requeued.job.progress, 0);
  equal(requeued.job.progress_details, null);
  const aborted = await request("/api/v1/jobs/controlled/heartbeat", { role: "worker", method: "POST", expected: 409,
    body: workerBody("OWNER", { lease_token: newClaim.lease_token }) });
  equal(aborted.error.details.action, "requeue");
  equal((await control("controlled", "requeue", newSnapshot, requeueId)).idempotent_replay, true);

  equal((await claim("WAITING-FOR-CLEANUP", "target-project")).job_available, false, "Other workers wait while the old render is stopping");
  equal((await claim("OWNER", "target-project")).job_available, false, "The original worker must confirm cleanup before reclaiming");
  await request("/api/v1/jobs/controlled/release", { role: "worker", method: "POST", expected: 409,
    body: workerBody("OWNER", { lease_token: newClaim.lease_token, reason: "Interrupted job process cleanup completed" }) });
  const reclaimed = await claim("OWNER", "target-project");
  equal(reclaimed.job_available, true);
  await request("/api/v1/jobs/controlled/fail", { role: "worker", method: "POST",
    body: workerBody("OWNER", { lease_token: reclaimed.lease_token, reason: "Failure after the manager's requeue", retryable: true }) });
  const failedRetry = await request("/api/v1/jobs/controlled");
  equal(failedRetry.job.blacklisted_workers, ["OWNER"]);
  const replayAfterFailure = await control("controlled", "requeue", newSnapshot, requeueId);
  equal(replayAfterFailure.idempotent_replay, true);
  equal(replayAfterFailure.job.blacklisted_workers, ["OWNER"], "Replaying an older requeue cannot clear a later attempt's blacklist");
  const staleRequeue = await request("/api/v1/jobs/controlled/requeue", { method: "POST", expected: 409,
    body: { request_id: randomUUID(), expected_attempt: newSnapshot.attempt, expected_status: newSnapshot.status } });
  equal(staleRequeue.error.code, "job_state_changed");
  equal((await request("/api/v1/jobs/controlled")).job.blacklisted_workers, ["OWNER"], "Rejected stale requests cannot clear the blacklist");
  const queuedReset = await control("controlled", "requeue", failedRetry.summary);
  equal(queuedReset.job.blacklisted_workers, [], "Requeue also clears a queued job's failure blacklist");
  equal((await claim("OWNER", "target-project")).job_available, true);
  const finalSnapshot = (await request("/api/v1/jobs/controlled")).summary;
  // Both concurrent calls must observe the same action receipt.
  const duplicateId = randomUUID();
  const duplicates = await Promise.all([control("controlled", "stop", finalSnapshot, duplicateId), control("controlled", "stop", finalSnapshot, duplicateId)]);
  equal(duplicates.filter(result => !result.idempotent_replay).length, 1);
  const eventCount = await db.prepare("SELECT count(*) AS count FROM job_events WHERE job_id = 'controlled' AND json_extract(details_json, '$.request_id') = ?1").bind(duplicateId).first();
  equal(eventCount.count, 1);

  for (const role of ["worker", "submit", "viewer"]) {
    await request("/api/v1/jobs/controlled/requeue", { role, method: "POST", expected: 403,
      body: { request_id: randomUUID(), expected_attempt: finalSnapshot.attempt, expected_status: "canceled" } });
  }
  const mismatch = await request("/api/v1/jobs/controlled/requeue", { method: "POST", expected: 409,
    body: { request_id: stopId, expected_attempt: rendering.attempt, expected_status: "rendering" } });
  equal(mismatch.error.code, "request_id_conflict");
  await request("/api/v1/jobs/controlled/stop", { method: "POST", body: { request_id: randomUUID() }, expected: 400 });
  await request("/api/v1/jobs/controlled/requeue", { method: "POST", body: { request_id: randomUUID(), expected_attempt: 0, expected_status: "complete" }, expected: 409 });
  await request("/api/v1/jobs/missing/requeue", { method: "POST", body: { request_id: randomUUID(), expected_attempt: 0, expected_status: "queued" }, expected: 404 });

  // A revoked worker can proceed to another queued job without a stop request.
  await submit("next-job", "next-project");
  equal((await claim("OWNER", "next-project")).job_available, true);
  equal((await request("/api/v1/jobs/unrelated")).summary.worker, "OTHER-ACTIVE");
  equal(unrelated.job.job_id, "unrelated");

  const outputPolicy = { publisher_schema_version: 4, output_relative_directory: "SHOTS/shared/v007", output_file_name_format: "shared.{frame_number}" };
  await submit("old-output", "conflict-project", outputPolicy);
  const oldOutputSnapshot = (await request("/api/v1/jobs/old-output")).summary;
  const oldOutputStopped = await control("old-output", "stop", oldOutputSnapshot);
  await submit("new-output", "conflict-project", outputPolicy);
  const blockedRequeueId = randomUUID();
  const outputConflict = await request("/api/v1/jobs/old-output/requeue", { method: "POST", expected: 409,
    body: { request_id: blockedRequeueId, expected_attempt: 0, expected_status: "canceled" } });
  equal(outputConflict.error.code, "active_output_conflict");
  const oldAfterConflict = await request("/api/v1/jobs/old-output");
  equal(oldAfterConflict.summary.status, "canceled");
  equal(oldAfterConflict.job.blacklisted_workers, oldOutputStopped.job.blacklisted_workers);
  equal(oldAfterConflict.events.length, oldOutputStopped.events.length, "Rejected requeue must not write an idempotency event");
  const newOutputSnapshot = (await request("/api/v1/jobs/new-output")).summary;
  await control("new-output", "stop", newOutputSnapshot);
  const outputRace = await Promise.all(["old-output", "new-output"].map(id => request(`/api/v1/jobs/${id}/requeue`, {
    method: "POST", expected: [200, 409], body: { request_id: randomUUID(), expected_attempt: 0, expected_status: "canceled" },
  })));
  equal(outputRace.filter(result => result.ok).length, 1, "Concurrent requeues cannot share one output target");
  equal((await db.prepare("SELECT count(*) AS count FROM jobs WHERE project = 'conflict-project' AND status = 'queued'").first()).count, 1);

  // Submission fingerprint uniqueness also survives requeue of older jobs.
  await submit("old-fingerprint", "fingerprint-project", { submission_fingerprint: "identical-render" });
  await control("old-fingerprint", "stop", (await request("/api/v1/jobs/old-fingerprint")).summary);
  await submit("new-fingerprint", "fingerprint-project", { submission_fingerprint: "identical-render" });
  const fingerprintConflict = await request("/api/v1/jobs/old-fingerprint/requeue", { method: "POST", expected: 409,
    body: { request_id: randomUUID(), expected_attempt: 0, expected_status: "canceled" } });
  equal(fingerprintConflict.error.code, "active_output_conflict");

  // Stop followed immediately by Requeue inherits the Stop attempt's cleanup
  // barrier, even though its entire blacklist has already been cleared.
  await submit("stop-then-requeue", "cleanup-project");
  const cleanupOwner = await claim("CLEANUP-OWNER", "cleanup-project");
  const cleanupStopped = await control("stop-then-requeue", "stop", (await request("/api/v1/jobs/stop-then-requeue")).summary);
  const cleanupQueued = await control("stop-then-requeue", "requeue", cleanupStopped.summary);
  equal(cleanupQueued.job.blacklisted_workers, []);
  const pendingCleanup = async () => (await db.prepare("SELECT json_extract(result_json, '$.cleanup_pending') AS pending FROM job_attempts WHERE job_id = 'stop-then-requeue' AND lease_token = ?1").bind(cleanupOwner.lease_token).first()).pending;
  equal(await pendingCleanup(), 1);
  equal((await claim("CLEANUP-NEXT", "cleanup-project")).job_available, false);
  await request("/api/v1/jobs/stop-then-requeue/heartbeat", { role: "worker", method: "POST", expected: 409,
    body: workerBody("CLEANUP-OWNER", { lease_token: cleanupOwner.lease_token }) });
  equal(await pendingCleanup(), 1, "An interrupted heartbeat never acknowledges process cleanup");
  for (const [worker, token] of [["WRONG-WORKER", cleanupOwner.lease_token], ["CLEANUP-OWNER", randomUUID()]]) {
    await request("/api/v1/jobs/stop-then-requeue/release", { role: "worker", method: "POST", expected: 409,
      body: workerBody(worker, { lease_token: token }) });
    equal(await pendingCleanup(), 1, "Only the exact interrupted worker and token may acknowledge cleanup");
  }
  await request("/api/v1/jobs/stop-then-requeue/fail", { role: "worker", method: "POST", expected: 409,
    body: workerBody("CLEANUP-OWNER", { lease_token: cleanupOwner.lease_token, retryable: false, result: { process_still_running: true } }) });
  equal(await pendingCleanup(), 1, "An unsafe terminal failure does not acknowledge cleanup");
  equal((await claim("CLEANUP-NEXT", "cleanup-project")).job_available, false);
  for (const deadline of [null, -1, "invalid"]) {
    await db.prepare("UPDATE job_attempts SET result_json = json_set(result_json, '$.claim_after_unix', ?1) WHERE job_id = 'stop-then-requeue'").bind(deadline).run();
    equal((await claim("CLEANUP-NEXT", "cleanup-project")).job_available, false, "Missing or invalid saved lease deadlines fail closed");
  }
  await request("/api/v1/jobs/stop-then-requeue/release", { role: "worker", method: "POST", expected: 409,
    body: workerBody("CLEANUP-OWNER", { lease_token: cleanupOwner.lease_token, reason: "Interrupted job process cleanup completed" }) });
  equal(await pendingCleanup(), 0);
  equal((await claim("CLEANUP-NEXT", "cleanup-project")).job_available, true);

  // Offline/legacy workers cannot hold an otherwise healthy queue forever;
  // the original finite lease deadline remains the existing fallback.
  await submit("expired-cleanup", "expiry-project");
  await claim("EXPIRY-OWNER", "expiry-project");
  await control("expired-cleanup", "requeue", (await request("/api/v1/jobs/expired-cleanup")).summary);
  equal((await claim("EXPIRY-NEXT", "expiry-project")).job_available, false);
  await db.prepare("UPDATE job_attempts SET result_json = json_set(result_json, '$.claim_after_unix', unixepoch() - 1) WHERE job_id = 'expired-cleanup'").run();
  equal((await claim("EXPIRY-NEXT", "expiry-project")).job_available, true);

  // Stop of a job that has never been claimed introduces no cleanup barrier.
  await submit("queued-only", "queued-only-project");
  const neverClaimed = await control("queued-only", "stop", (await request("/api/v1/jobs/queued-only")).summary);
  const queuedOnly = await control("queued-only", "requeue", neverClaimed.summary);
  equal(queuedOnly.attempts, []);
  equal((await claim("QUEUED-OWNER", "queued-only-project")).job_available, true);

  // Model a manager action in the gap between claim's atomic lease write and
  // its later audit INSERT. Control must create the barrier attempt itself.
  await submit("claim-audit-gap", "audit-gap-project");
  const gapClaim = await claim("GAP-OWNER", "audit-gap-project");
  await db.prepare("DELETE FROM job_attempts WHERE job_id = 'claim-audit-gap'").run();
  const gapQueued = await control("claim-audit-gap", "requeue", (await request("/api/v1/jobs/claim-audit-gap")).summary);
  equal(gapQueued.attempts.length, 1);
  equal(gapQueued.attempts[0].status, "released");
  equal((await claim("GAP-NEXT", "audit-gap-project")).job_available, false);
  await request("/api/v1/jobs/claim-audit-gap/release", { role: "worker", method: "POST", expected: 409,
    body: workerBody("GAP-OWNER", { lease_token: gapClaim.lease_token }) });
  equal((await claim("GAP-NEXT", "audit-gap-project")).job_available, true);

  await submit("terminal-failure", "terminal-project");
  const firstFailure = await claim("FAILED-FIRST", "terminal-project");
  await request("/api/v1/jobs/terminal-failure/fail", { role: "worker", method: "POST",
    body: workerBody("FAILED-FIRST", { lease_token: firstFailure.lease_token, retryable: true }) });
  const terminalFailure = await claim("FAILED-SECOND", "terminal-project");
  await request("/api/v1/jobs/terminal-failure/fail", { role: "worker", method: "POST",
    body: workerBody("FAILED-SECOND", { lease_token: terminalFailure.lease_token, retryable: false }) });
  const terminalState = await request("/api/v1/jobs/terminal-failure");
  equal(terminalState.job.status, "failed");
  equal(terminalState.job.blacklisted_workers, ["FAILED-FIRST"]);
  equal((await control("terminal-failure", "requeue", terminalState.summary)).job.blacklisted_workers, []);
  equal((await claim("FAILED-FIRST", "terminal-project")).job_available, true);
  console.log(`Job controls integration passed (${assertions} assertions).`);
} finally {
  await farm.dispose();
}
