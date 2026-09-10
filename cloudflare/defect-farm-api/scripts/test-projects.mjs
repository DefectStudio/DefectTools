import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";

const base = process.env.DEFECT_FARM_TEST_URL ?? "http://127.0.0.1:8795";
assert.ok(["127.0.0.1", "localhost"].includes(new URL(base).hostname), "Use an isolated local test database.");
const tokens = Object.fromEntries(["manager", "worker", "viewer", "submit"].map(role => [role, `local-${role}-token-for-tests`]));
let checks = 0;
async function request(method, path, role, body, expected = 200) {
  const response = await fetch(`${base}/api/v1${path}`, {
    method,
    headers: { ...(role ? { Authorization: `Bearer ${tokens[role]}` } : {}), "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  assert.equal(response.status, expected, `${method} ${path}: ${JSON.stringify(data)}`);
  checks++;
  return data;
}

const id = `project_${randomUUID().replaceAll("-", "").slice(0, 12)}`;
const initial = { project_id: id, display_name: "Registry test", active: true };
await request("GET", "/projects", null, undefined, 401);
await request("POST", "/projects", "worker", initial, 403);
await request("POST", "/projects", "viewer", initial, 403);
await request("POST", "/projects", "submit", initial, 403);
await request("POST", "/projects", "manager", { ...initial, project_id: "Bad ID" }, 400);
await request("POST", "/projects", "manager", { ...initial, active: "yes" }, 400);
const created = await request("POST", "/projects", "manager", initial, 201);
assert.equal(created.project.revision, 1);
assert.equal(created.project.active, true);
assert.equal((await request("POST", "/projects", "manager", initial)).created, false);
await request("POST", "/projects", "manager", { ...initial, display_name: "Duplicate" }, 409);
for (const role of ["worker", "viewer", "submit"]) {
  assert.ok((await request("GET", "/projects", role)).projects.some(project => project.project_id === id));
}
await request("GET", "/projects?include_inactive=true", "worker", undefined, 403);
await request("PUT", `/projects/${id}`, "worker", { display_name: "No", active: true, revision: 1 }, 403);
await request("PUT", `/projects/${id}`, "manager", { ...initial, project_id: `${id}_rename`, revision: 1 }, 400);
await request("PUT", `/projects/${id}`, "manager", { display_name: "No revision", active: true }, 400);
const edit = { display_name: "Edited display name", active: false, revision: 1 };
const updated = await request("PUT", `/projects/${id}`, "manager", edit);
assert.equal(updated.project.revision, 2);
assert.equal((await request("PUT", `/projects/${id}`, "manager", edit)).project.revision, 2);
assert.ok(!(await request("GET", "/projects", "worker")).projects.some(project => project.project_id === id));
assert.ok((await request("GET", "/projects?include_inactive=true", "manager")).projects.some(project => project.project_id === id && !project.active));
await request("PUT", `/projects/${id}`, "manager", { display_name: "Stale edit", active: true, revision: 1 }, 409);
await request("PUT", `/projects/not_present_${id}`, "manager", { display_name: "Missing", active: true, revision: 1 }, 404);
await request("PUT", `/projects/${id}`, "manager", { display_name: "Restored", active: true, revision: 2 });
const race = await Promise.all(["Editor A", "Editor B"].map(display_name => fetch(`${base}/api/v1/projects/${id}`, {
  method: "PUT", headers: { Authorization: `Bearer ${tokens.manager}`, "Content-Type": "application/json" },
  body: JSON.stringify({ display_name, active: true, revision: 3 }),
})));
assert.deepEqual(race.map(response => response.status).sort(), [200, 409]);
checks++;
console.log(`Project registry integration passed: ${checks} checks (authorization, persistence, replay, deactivation, concurrent edits).`);
