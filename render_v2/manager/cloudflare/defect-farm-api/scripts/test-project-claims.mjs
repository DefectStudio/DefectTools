import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";

const base = process.env.DEFECT_FARM_TEST_URL ?? "http://127.0.0.1:8796";
assert.ok(["127.0.0.1", "localhost"].includes(new URL(base).hostname), "These tests require an isolated local dispatcher");
const suffix = randomUUID().slice(0, 8);
const bishop = `Bishop_${suffix}`;
const spectrum = `Spectrum_${suffix}`;
async function request(path, body, role = "worker", expected = 200) {
  const response = await fetch(base + path, {
    method: "POST", headers: {"Content-Type": "application/json", Authorization: `Bearer local-${role}-token-for-tests`},
    body: JSON.stringify(body),
  });
  const result = await response.json();
  assert.equal(response.status, expected, JSON.stringify(result));
  return result;
}
async function submit(project, priority) {
  const id = `claim_${project}`;
  await request("/api/v1/jobs", {
    schema_version: 1, publisher_schema_version: 4, job_id: id, project,
    job_type: "unreal_mrq", shot_name: id, render_version: 1, priority,
    submitted_utc: new Date().toISOString(), submitted_by: "LOCAL-CLAIM-TEST", submitted_user: "test",
    output_directory: `F:/claim-tests/${id}`, output_relative_directory: `claims/${id}`,
    output_file_name_format: `${id}.{frame_number}`, submission_fingerprint: id,
  }, "submit", 201);
  return id;
}
const bishopJob = await submit(bishop, 20);
const spectrumJob = await submit(spectrum, 100);
function claim(worker, projects, extra = {}) {
  return request("/api/v1/jobs/claim", {worker_id: worker, claim_request_id: randomUUID(),
    eligible_project_ids: projects, capabilities: {registered_projects: projects}, ...extra});
}
assert.equal((await claim(`empty_${suffix}`, [])).job_available, false);
assert.equal((await claim(`other_${suffix}`, ["UnknownShow"])).job_available, false);
await request("/api/v1/jobs/claim", {worker_id: `bad_${suffix}`, claim_request_id: randomUUID(),
  eligible_project_ids: "Bishop"}, "worker", 400);
const workers = [`one_${suffix}`, `two_${suffix}`];
const claims = await Promise.all(workers.map(worker => claim(worker, [bishop.toLowerCase()])));
assert.equal(claims.filter(result => result.job_available).length, 1, "Only one worker wins the claim");
const winnerIndex = claims.findIndex(result => result.job_available);
const winner = workers[winnerIndex];
const lease = claims[winnerIndex];
assert.equal(lease.job.job_id, bishopJob, "Higher-priority unregistered show must remain queued");
await request("/api/v1/jobs/claim", {worker_id: winner, claim_request_id: randomUUID(),
  eligible_project_ids: [spectrum]}, "worker", 409);
const replay = await claim(winner, [bishop]);
assert.equal(replay.lease_token, lease.lease_token, "Repeat request keeps the active lease");
await request(`/api/v1/jobs/${bishopJob}/heartbeat`, {worker_id: winner, lease_token: lease.lease_token});
const complete = await request(`/api/v1/jobs/${bishopJob}/complete`, {
  worker_id: winner, lease_token: lease.lease_token, result: {output_verified: true},
});
assert.equal(complete.job.status, "complete");
const spectrumLease = await claim(`spectrum_${suffix}`, [bishop, spectrum]);
assert.equal(spectrumLease.job.job_id, spectrumJob);
await request(`/api/v1/jobs/${spectrumJob}/complete`, {
  worker_id: `spectrum_${suffix}`, lease_token: spectrumLease.lease_token, result: {output_verified: true},
});
console.log("Project claims passed: eligibility, empty list, validation, priority, atomic competition, lease replay, heartbeat, completion, multiple shows.");
