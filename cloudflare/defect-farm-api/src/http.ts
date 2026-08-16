import type { JsonRecord } from "./types";

const MAX_JSON_BODY_BYTES = 1_900_000;

export class HttpError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: JsonRecord | undefined;

  constructor(
    status: number,
    code: string,
    message: string,
    details?: JsonRecord,
  ) {
    super(message);
    this.name = "HttpError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function jsonResponse(
  body: JsonRecord,
  status = 200,
  requestId?: string,
): Response {
  const headers = new Headers({
    "Cache-Control": "no-store",
    "Content-Type": "application/json; charset=utf-8",
    "X-Content-Type-Options": "nosniff",
  });
  if (requestId) {
    headers.set("X-Request-Id", requestId);
  }
  return new Response(JSON.stringify(body), { status, headers });
}

export function emptyResponse(status: number, requestId: string): Response {
  return new Response(null, {
    status,
    headers: {
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
      "X-Request-Id": requestId,
    },
  });
}

export async function readJsonObject(request: Request): Promise<JsonRecord> {
  if (!request.body) {
    throw new HttpError(400, "missing_body", "A JSON request body is required.");
  }

  const contentType = request.headers.get("content-type") ?? "";
  if (!contentType.toLowerCase().includes("application/json")) {
    throw new HttpError(
      415,
      "unsupported_media_type",
      "Content-Type must be application/json.",
    );
  }

  const statedLength = Number(request.headers.get("content-length") ?? "0");
  if (Number.isFinite(statedLength) && statedLength > MAX_JSON_BODY_BYTES) {
    throw new HttpError(413, "body_too_large", "The JSON body is too large.");
  }

  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let totalBytes = 0;
  while (true) {
    const read = await reader.read();
    if (read.done) {
      break;
    }
    totalBytes += read.value.byteLength;
    if (totalBytes > MAX_JSON_BODY_BYTES) {
      await reader.cancel("JSON request body exceeded the size limit");
      throw new HttpError(413, "body_too_large", "The JSON body is too large.");
    }
    chunks.push(read.value);
  }

  const body = new Uint8Array(totalBytes);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(new TextDecoder().decode(body));
  } catch (error) {
    const message = error instanceof Error ? error.message : "Invalid JSON";
    throw new HttpError(400, "invalid_json", `Could not parse JSON: ${message}`);
  }
  return requireRecord(parsed, "JSON body");
}

export function requireRecord(value: unknown, label: string): JsonRecord {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new HttpError(400, "invalid_field", `${label} must be a JSON object.`);
  }
  return value as JsonRecord;
}

export function requiredString(
  data: JsonRecord,
  field: string,
  maxLength = 500,
): string {
  const value = data[field];
  if (typeof value !== "string" || !value.trim()) {
    throw new HttpError(400, "invalid_field", `${field} must be a non-empty string.`);
  }
  const result = value.trim();
  if (result.length > maxLength) {
    throw new HttpError(
      400,
      "invalid_field",
      `${field} must be at most ${maxLength} characters.`,
    );
  }
  return result;
}

export function optionalString(
  data: JsonRecord,
  field: string,
  maxLength = 500,
): string | null {
  const value = data[field];
  if (value === undefined || value === null || value === "") {
    return null;
  }
  if (typeof value !== "string") {
    throw new HttpError(400, "invalid_field", `${field} must be a string.`);
  }
  const result = value.trim();
  if (result.length > maxLength) {
    throw new HttpError(
      400,
      "invalid_field",
      `${field} must be at most ${maxLength} characters.`,
    );
  }
  return result || null;
}

export function requiredInteger(
  data: JsonRecord,
  field: string,
  minimum: number,
  maximum: number,
): number {
  const value = data[field];
  if (!Number.isInteger(value)) {
    throw new HttpError(400, "invalid_field", `${field} must be an integer.`);
  }
  const numberValue = value as number;
  if (numberValue < minimum || numberValue > maximum) {
    throw new HttpError(
      400,
      "invalid_field",
      `${field} must be between ${minimum} and ${maximum}.`,
    );
  }
  return numberValue;
}

export function optionalNumber(
  data: JsonRecord,
  field: string,
  minimum: number,
  maximum: number,
): number | null {
  const value = data[field];
  if (value === undefined || value === null) {
    return null;
  }
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new HttpError(400, "invalid_field", `${field} must be a number.`);
  }
  if (value < minimum || value > maximum) {
    throw new HttpError(
      400,
      "invalid_field",
      `${field} must be between ${minimum} and ${maximum}.`,
    );
  }
  return value;
}

export function safeIdentifier(value: string, label: string): string {
  if (!/^[A-Za-z0-9._:-]+$/.test(value)) {
    throw new HttpError(
      400,
      "invalid_field",
      `${label} may contain only letters, numbers, dots, underscores, colons, and hyphens.`,
    );
  }
  return value;
}

export function parseStoredRecord(value: string | null): JsonRecord | null {
  if (value === null) {
    return null;
  }
  const parsed: unknown = JSON.parse(value);
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Stored JSON was not an object");
  }
  return parsed as JsonRecord;
}
