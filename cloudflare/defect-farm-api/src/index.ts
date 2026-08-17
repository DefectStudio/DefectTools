import { requireRole } from "./auth";
import {
  HttpError,
  jsonResponse,
  readJsonObject,
  requiredString,
  safeIdentifier,
} from "./http";
import {
  acknowledgeWorkerStop,
  claimJob,
  clearBlacklist,
  completeJob,
  deleteJob,
  failJob,
  getJob,
  heartbeatJob,
  listJobs,
  listWorkers,
  releaseJob,
  replaceJob,
  requestWorkerStop,
  resubmitJob,
  submitJob,
  workerStopRequested,
} from "./jobs";
import type { JsonRecord } from "./types";

const SERVICE_NAME = "defect-farm-api";
const SERVICE_VERSION = "0.4.1";
const API_ROOT = "/api/v1";

function requestId(request: Request): string {
  return request.headers.get("cf-ray")?.trim() || crypto.randomUUID();
}

function decodedPathSegment(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    throw new HttpError(400, "invalid_path", "The URL contains an invalid escape sequence.");
  }
}

async function handleRequest(
  request: Request,
  env: Env,
  id: string,
): Promise<Response> {
  const url = new URL(request.url);
  const path = url.pathname.replace(/\/+$/, "") || "/";

  if (request.method === "GET" && (path === "/" || path === "/health")) {
    const database = await env.DB.prepare("SELECT 1 AS ok").first<{ ok: number }>();
    return jsonResponse(
      {
        ok: database?.ok === 1,
        service: SERVICE_NAME,
        service_version: SERVICE_VERSION,
        api_version: env.API_VERSION,
        environment: env.ENVIRONMENT,
        database: "connected",
      },
      200,
      id,
    );
  }

  if (request.method === "GET" && path === `${API_ROOT}/auth/check`) {
    const role = requireRole(request, env, ["submit", "worker", "manager"]);
    return jsonResponse({ ok: true, role }, 200, id);
  }

  if (request.method === "POST" && path === `${API_ROOT}/jobs`) {
    requireRole(request, env, ["submit", "manager"]);
    const body = await readJsonObject(request);
    const idempotencyKey = request.headers.get("idempotency-key")?.trim();
    if (idempotencyKey && idempotencyKey !== body.job_id) {
      throw new HttpError(
        400,
        "idempotency_mismatch",
        "Idempotency-Key must match job_id.",
      );
    }
    const submitted = await submitJob(env, body);
    const detail = await getJob(env, submitted.row.id);
    return jsonResponse(
      {
        ok: true,
        created: submitted.created,
        idempotent_replay: !submitted.created,
        ...detail,
      },
      submitted.created ? 201 : 200,
      id,
    );
  }

  if (request.method === "GET" && path === `${API_ROOT}/jobs`) {
    requireRole(request, env, ["manager"]);
    const listing = await listJobs(env, url.searchParams);
    return jsonResponse({ ok: true, ...listing }, 200, id);
  }

  if (request.method === "POST" && path === `${API_ROOT}/jobs/claim`) {
    requireRole(request, env, ["worker"]);
    const body = await readJsonObject(request);
    const claimResult = await claimJob(env, body);
    const claimed = claimResult.claimed;
    const stopRequested = claimResult.stopRequested;
    return jsonResponse(
      claimed
        ? {
            ok: true,
            job_available: true,
            stop_requested: stopRequested,
            lease_token: claimed.row.lease_token,
            lease_expires_at: claimed.row.lease_expires_at,
            job: claimed.payload,
          }
        : {
            ok: true,
            job_available: false,
            stop_requested: stopRequested,
          },
      200,
      id,
    );
  }

  if (request.method === "GET" && path === `${API_ROOT}/workers`) {
    requireRole(request, env, ["manager"]);
    return jsonResponse({ ok: true, workers: await listWorkers(env) }, 200, id);
  }

  const workerAction = new RegExp(
    `^${API_ROOT}/workers/([^/]+)/(stop|stop-ack)$`,
  ).exec(path);
  if (request.method === "POST" && workerAction) {
    const workerId = safeIdentifier(
      decodedPathSegment(workerAction[1] ?? ""),
      "worker_id",
    );
    const action = workerAction[2];
    if (action === "stop") {
      requireRole(request, env, ["manager"]);
      return jsonResponse(
        { ok: true, worker: await requestWorkerStop(env, workerId) },
        200,
        id,
      );
    }
    requireRole(request, env, ["worker"]);
    return jsonResponse(
      { ok: true, worker: await acknowledgeWorkerStop(env, workerId) },
      200,
      id,
    );
  }

  const jobAction = new RegExp(
    `^${API_ROOT}/jobs/([^/]+)/(heartbeat|release|complete|fail|clear-blacklist|resubmit|replace)$`,
  ).exec(path);
  if (request.method === "POST" && jobAction) {
    const jobId = safeIdentifier(
      decodedPathSegment(jobAction[1] ?? ""),
      "job_id",
    );
    const action = jobAction[2];
    if (action === "clear-blacklist") {
      requireRole(request, env, ["manager"]);
      const result = await clearBlacklist(env, jobId);
      return jsonResponse(
        {
          ok: true,
          cleared: result.cleared,
          job: (await getJob(env, jobId)).job,
        },
        200,
        id,
      );
    }
    if (action === "resubmit") {
      requireRole(request, env, ["manager"]);
      const body = await readJsonObject(request);
      const result = await resubmitJob(env, jobId, body);
      return jsonResponse(
        {
          ok: true,
          created: result.created,
          idempotent_replay: !result.created,
          job: result.payload,
        },
        result.created ? 201 : 200,
        id,
      );
    }
    if (action === "replace") {
      requireRole(request, env, ["manager"]);
      const body = await readJsonObject(request);
      const result = await replaceJob(env, jobId, body);
      return jsonResponse(
        {
          ok: true,
          created: result.created,
          idempotent_replay: !result.created,
          source_deleted: result.sourceDeleted,
          deleted_job_id: jobId,
          job: result.payload,
        },
        result.created ? 201 : 200,
        id,
      );
    }

    requireRole(request, env, ["worker"]);
    const body = await readJsonObject(request);
    if (action === "heartbeat") {
      const row = await heartbeatJob(env, jobId, body);
      return jsonResponse(
        {
          ok: true,
          job_id: row.id,
          lease_expires_at: row.lease_expires_at,
          revision: row.revision,
          stop_requested: await workerStopRequested(
            env,
            requiredString(body, "worker_id", 128),
          ),
        },
        200,
        id,
      );
    }
    if (action === "release") {
      const released = await releaseJob(env, jobId, body);
      return jsonResponse({ ok: true, job: released.payload }, 200, id);
    }
    if (action === "complete") {
      const completed = await completeJob(env, jobId, body);
      return jsonResponse({ ok: true, job: completed.payload }, 200, id);
    }
    const failed = await failJob(env, jobId, body);
    return jsonResponse({ ok: true, job: failed.payload }, 200, id);
  }

  const jobDetail = new RegExp(`^${API_ROOT}/jobs/([^/]+)$`).exec(path);
  if (jobDetail && (request.method === "GET" || request.method === "DELETE")) {
    requireRole(request, env, ["manager"]);
    const jobId = safeIdentifier(
      decodedPathSegment(jobDetail[1] ?? ""),
      "job_id",
    );
    if (request.method === "DELETE") {
      const result = await deleteJob(env, jobId);
      return jsonResponse(
        {
          ok: true,
          deleted: result.deleted,
          idempotent_replay: !result.deleted,
          deletion_confirmed: true,
          deleted_job_id: jobId,
        },
        200,
        id,
      );
    }
    return jsonResponse({ ok: true, ...(await getJob(env, jobId)) }, 200, id);
  }

  throw new HttpError(404, "not_found", "No API route matches this request.");
}

function errorBody(error: HttpError, id: string): JsonRecord {
  const body: JsonRecord = {
    ok: false,
    error: {
      code: error.code,
      message: error.message,
      ...(error.details ? { details: error.details } : {}),
    },
    request_id: id,
  };
  return body;
}

export default {
  async fetch(request, env): Promise<Response> {
    const id = requestId(request);
    try {
      const response = await handleRequest(request, env, id);
      console.log(
        JSON.stringify({
          level: "info",
          request_id: id,
          method: request.method,
          path: new URL(request.url).pathname,
          status: response.status,
        }),
      );
      return response;
    } catch (error) {
      if (error instanceof HttpError) {
        console.warn(
          JSON.stringify({
            level: "warn",
            request_id: id,
            method: request.method,
            path: new URL(request.url).pathname,
            status: error.status,
            error_code: error.code,
          }),
        );
        return jsonResponse(errorBody(error, id), error.status, id);
      }

      const message = error instanceof Error ? error.message : "Unknown error";
      console.error(
        JSON.stringify({
          level: "error",
          request_id: id,
          method: request.method,
          path: new URL(request.url).pathname,
          error: message,
        }),
      );
      return jsonResponse(
        {
          ok: false,
          error: {
            code: "internal_error",
            message: "The Dispatcher encountered an internal error.",
          },
          request_id: id,
        },
        500,
        id,
      );
    }
  },
} satisfies ExportedHandler<Env>;
