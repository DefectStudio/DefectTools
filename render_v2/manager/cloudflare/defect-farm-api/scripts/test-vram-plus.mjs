import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";

const base = new URL(process.env.DEFECT_FARM_TEST_URL ?? "http://127.0.0.1:8796");
assert.ok(
  base.protocol === "http:" && ["127.0.0.1", "localhost"].includes(base.hostname),
  "These tests require an isolated local dispatcher",
);

async function request(path, { role, method = "GET", body, expected = 200 } = {}) {
  const response = await fetch(new URL(path, base), {
    method,
    redirect: "error",
    headers: {
      ...(role ? { Authorization: `Bearer local-${role}-token-for-tests` } : {}),
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json();
  assert.equal(response.status, expected, `${method} ${path}: ${JSON.stringify(data)}`);
  return data;
}

const health = await request("/health");
assert.equal(health.service, "defect-farm-api-v2");
assert.equal(health.environment, "v2-local");
assert.equal(health.database, "connected");

const suffix = randomUUID().slice(0, 8);
const project = `VramPlus_${suffix}`;
const boundaryAdapter = { model: "Boundary adapter", vram_mib: 20_480 };
const smallAdapter = { model: "Below boundary adapter", vram_mib: 20_479 };
const bigAdapter = { model: "NVIDIA GeForce RTX 4090", vram_mib: 24_564 };
const boundaryCapabilities = { render_adapter: boundaryAdapter };
const bigCapabilities = { render_adapter: bigAdapter, gpus: [bigAdapter, smallAdapter] };

async function submit(name, priority, fields = {}, expected = 201) {
  const id = `${project}_${name}`;
  return request("/api/v1/jobs", {
    role: "submit", method: "POST", expected,
    body: {
      schema_version: 1, publisher_schema_version: 4, job_id: id, project,
      job_type: "unreal_movie_render_graph", shot_name: id, render_version: 1, priority,
      submitted_utc: new Date().toISOString(), submitted_by: "LOCAL-VRAM-TEST", submitted_user: "test",
      output_directory: `F:/vram-tests/${id}`, output_relative_directory: `vram-tests/${id}`,
      output_file_name_format: `${id}.{frame_number}`, submission_fingerprint: id,
      ...fields,
    },
  });
}

function claim(worker, capabilities, { requestId = randomUUID(), expected = 200 } = {}) {
  return request("/api/v1/jobs/claim", {
    role: "worker", method: "POST", expected,
    body: {
      worker_id: `${project}_${worker}`, claim_request_id: requestId,
      eligible_project_ids: [project], capabilities,
    },
  });
}

function finish(lease, action = "complete", fields = { result: { output_verified: true } }) {
  return request(`/api/v1/jobs/${lease.job.job_id}/${action}`, {
    role: "worker", method: "POST",
    body: { worker_id: lease.job.worker, lease_token: lease.lease_token, ...fields },
  });
}

for (const value of [null, 1, "true", {}]) {
  const rejected = await submit("bad_flag", 1, { requires_vram_plus: value }, 400);
  assert.equal(rejected.error.code, "invalid_field");
}
for (const render_adapter of [
  [], {}, true,
  { model: " ", vram_mib: 20_480 },
  { model: "GPU", vram_mib: "20480" },
  { model: "GPU", vram_mib: true },
  { model: "GPU", vram_mib: 0 },
  { model: "GPU", vram_mib: 20_480.5 },
]) {
  const rejected = await claim("bad_adapter", { render_adapter }, { expected: 400 });
  assert.equal(rejected.error.code, "invalid_field");
}

const explicit = (await submit("explicit", 200, { requires_vram_plus: true })).job;
const graph = (await submit("graph", 100, {
  requires_vram_plus: false,
  graph_variable_overrides: { vRaMpLuS: { name: "vRaMpLuS", enabled: true, value: true } },
})).job;
assert.equal(explicit.requires_vram_plus, true);
assert.equal(graph.requires_vram_plus, true);
const submittedReplay = await submit("explicit", 200, { requires_vram_plus: true }, 200);
assert.equal(submittedReplay.idempotent_replay, true);
const submissionConflict = await submit("explicit", 200, { requires_vram_plus: false }, 409);
assert.equal(submissionConflict.error.code, "vram_plus_replay_conflict");
const fingerprintConflict = await submit("fingerprint_replay", 200, {
  requires_vram_plus: false, submission_fingerprint: explicit.job_id,
}, 409);
assert.equal(fingerprintConflict.error.code, "vram_plus_replay_conflict");

const ineligibleWorkers = [
  ["legacy", undefined, {}],
  ["unknown", { render_adapter: null, gpus: [bigAdapter] }, { requires_vram_plus: false }],
  ["inventory_only", { gpus: [bigAdapter] }, {
    graph_variable_overrides: { VRAMPlus: { name: "VRAMPlus", enabled: false, value: true } },
  }],
  ["too_small", { render_adapter: smallAdapter, gpus: [smallAdapter, bigAdapter] }, {
    graph_variable_overrides: { VRAMPlus: { name: "VRAMPlus", enabled: true, value: false } },
  }],
];
for (const [worker, capabilities, ordinaryFields] of ineligibleWorkers) {
  const ordinary = (await submit(`ordinary_${worker}`, 10, ordinaryFields)).job;
  const lease = await claim(worker, capabilities);
  assert.equal(lease.job?.job_id, ordinary.job_id, `${worker} must skip higher-priority restricted jobs`);
  await finish(lease);
  assert.equal((await claim(worker, capabilities)).job_available, false);
}

const urgent = (await submit("urgent_ordinary", 300)).job;
const urgentLease = await claim("boundary", boundaryCapabilities);
assert.equal(urgentLease.job?.job_id, urgent.job_id, "An ordinary job keeps its higher priority");
await finish(urgentLease);

const requestId = randomUUID();
const explicitLease = await claim("boundary", boundaryCapabilities, { requestId });
assert.equal(explicitLease.job?.job_id, explicit.job_id, "Exactly 20,480 MiB qualifies");
const rejectedReplay = await claim("boundary", undefined, { requestId, expected: 409 });
assert.equal(rejectedReplay.error.code, "active_vram_plus_unavailable");
const rejectedRecovery = await claim("boundary", { render_adapter: smallAdapter }, { expected: 409 });
assert.equal(rejectedRecovery.error.code, "active_vram_plus_unavailable");
const replay = await claim("boundary", boundaryCapabilities, { requestId });
assert.equal(replay.lease_token, explicitLease.lease_token, "Request replay retains the active lease");
const recovered = await claim("boundary", boundaryCapabilities);
assert.equal(recovered.lease_token, explicitLease.lease_token, "Recovery retains the lease with a new request ID");
assert.equal(recovered.job.attempt, 1);
await finish(explicitLease);

const contenders = ["big_one", "big_two"];
const leases = await Promise.all(contenders.map((worker) => claim(worker, bigCapabilities)));
assert.equal(leases.filter((lease) => lease.job_available).length, 1, "Only one worker claims the restricted job");
const winnerIndex = leases.findIndex((lease) => lease.job_available);
const graphLease = leases[winnerIndex];
assert.equal(graphLease.job.job_id, graph.job_id);
const requeued = await finish(graphLease, "fail", { retryable: true, reason: "Local retry test" });
assert.equal(requeued.job.status, "queued");
assert.equal(requeued.job.requires_vram_plus, true);
assert.equal((await claim("legacy")).job_available, false, "Retry does not remove the restriction");
const retriedLease = await claim(contenders[1 - winnerIndex], bigCapabilities);
assert.equal(retriedLease.job?.job_id, graph.job_id);
assert.equal(retriedLease.job.attempt, 2);
await finish(retriedLease);

const resubmitted = await request(`/api/v1/jobs/${explicit.job_id}/resubmit`, {
  role: "manager", method: "POST", expected: 201,
  body: { request_id: randomUUID(), submitted_by: "LOCAL-VRAM-TEST", submitted_user: "test" },
});
assert.equal(resubmitted.job.requires_vram_plus, true);

function replace(source, label, fields, expected = 201) {
  const body = {
    ...source, job_id: `${project}_${label}`, resubmitted_from_job_id: source.job_id, ...fields,
  };
  return request(`/api/v1/jobs/${source.job_id}/replace`, {
    role: "manager", method: "POST", body, expected,
  });
}

const replacement = await replace(resubmitted.job, "replacement", { requires_vram_plus: undefined });
assert.equal(replacement.source_deleted, true);
assert.equal(replacement.job.requires_vram_plus, true, "An omitted flag preserves the source requirement");
assert.equal((await claim("legacy")).job_available, false);
const replacementReplay = await replace(resubmitted.job, "replacement", { requires_vram_plus: undefined }, 200);
assert.equal(replacementReplay.idempotent_replay, true);
assert.equal(replacementReplay.job.requires_vram_plus, true);
const replacementConflict = await replace(resubmitted.job, "replacement", { requires_vram_plus: false }, 409);
assert.equal(replacementConflict.error.code, "vram_plus_replay_conflict");

const unrestricted = await replace(replacement.job, "unrestricted", { requires_vram_plus: false });
const legacyLease = await claim("legacy");
assert.equal(legacyLease.job?.job_id, unrestricted.job.job_id, "Turning VRAM+ off restores unrestricted routing");
await finish(legacyLease);

console.log("VRAM+ routing passed: validation, compatibility, inclusive threshold, priority, concurrency, lease replay, retry and replacement.");
