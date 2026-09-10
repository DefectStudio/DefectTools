import { HttpError, requiredString } from "./http";
import type { JsonRecord } from "./types";

interface ProjectRow {
  project_id: string;
  display_name: string;
  active: number;
  revision: number;
  created_at: string;
  updated_at: string;
}

const NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')";

function identifier(value: string): string {
  if (!/^[a-z0-9][a-z0-9_-]{0,63}$/.test(value)) {
    throw new HttpError(400, "invalid_project_id", "Project ID must use lowercase letters, numbers, underscores or hyphens (maximum 64 characters).");
  }
  return value;
}

function activeValue(data: JsonRecord): number {
  if (typeof data.active !== "boolean") {
    throw new HttpError(400, "invalid_field", "active must be a boolean.");
  }
  return data.active ? 1 : 0;
}

function publicProject(row: ProjectRow): JsonRecord {
  return { ...row, active: row.active === 1 };
}

export async function listProjects(env: Env, includeInactive: boolean): Promise<JsonRecord[]> {
  const result = await env.DB.prepare(
    `SELECT * FROM projects WHERE (?1 = 1 OR active = 1)
     ORDER BY display_name COLLATE NOCASE, project_id`,
  ).bind(includeInactive ? 1 : 0).all<ProjectRow>();
  return result.results.map(publicProject);
}

export async function createProject(env: Env, data: JsonRecord): Promise<{ project: JsonRecord; created: boolean }> {
  const id = identifier(requiredString(data, "project_id", 64));
  const name = requiredString(data, "display_name", 200);
  const active = data.active === undefined ? 1 : activeValue(data);
  const inserted = await env.DB.prepare(
    `INSERT INTO projects (project_id, display_name, active, created_at, updated_at)
     VALUES (?1, ?2, ?3, ${NOW}, ${NOW})
     ON CONFLICT(project_id) DO NOTHING RETURNING *`,
  ).bind(id, name, active).first<ProjectRow>();
  if (inserted) return { project: publicProject(inserted), created: true };
  const existing = await env.DB.prepare("SELECT * FROM projects WHERE project_id = ?1")
    .bind(id).first<ProjectRow>();
  // A retried create must not create duplicates or overwrite another manager.
  if (existing?.display_name === name && existing.active === active) {
    return { project: publicProject(existing), created: false };
  }
  throw new HttpError(409, "project_exists", "That Project ID already exists. Refresh the list to edit it.");
}

export async function updateProject(env: Env, id: string, data: JsonRecord): Promise<JsonRecord> {
  identifier(id);
  if (data.project_id !== undefined && data.project_id !== id) {
    throw new HttpError(400, "immutable_project_id", "Project IDs cannot be renamed. Create a new ID and deactivate the old entry.");
  }
  const name = requiredString(data, "display_name", 200);
  const active = activeValue(data);
  const revision = data.revision;
  if (typeof revision !== "number" || !Number.isSafeInteger(revision) || revision < 1) {
    throw new HttpError(400, "invalid_revision", "The current project revision is required.");
  }
  const updated = await env.DB.prepare(
    `UPDATE projects SET display_name = ?1, active = ?2,
     revision = revision + 1, updated_at = ${NOW}
     WHERE project_id = ?3 AND revision = ?4 RETURNING *`,
  ).bind(name, active, id, revision).first<ProjectRow>();
  if (updated) return publicProject(updated);
  const current = await env.DB.prepare("SELECT * FROM projects WHERE project_id = ?1")
    .bind(id).first<ProjectRow>();
  if (!current) throw new HttpError(404, "project_not_found", "Project not found.");
  if (current.revision === revision + 1 && current.display_name === name && current.active === active) {
    return publicProject(current); // Safe replay after a lost HTTP response.
  }
  throw new HttpError(409, "project_changed", "This project changed in another manager. Refresh before editing again.");
}
