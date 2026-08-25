import { HttpError } from "./http";

export type AuthRole = "submit" | "worker" | "manager" | "viewer";

function bearerToken(request: Request): string | null {
  const authorization = request.headers.get("authorization") ?? "";
  const match = /^Bearer\s+(.+)$/i.exec(authorization.trim());
  return match?.[1]?.trim() || null;
}

function timingSafeEqualText(candidate: string, expected: string): boolean {
  const encoder = new TextEncoder();
  const candidateBytes = encoder.encode(candidate);
  const expectedBytes = encoder.encode(expected);
  if (candidateBytes.byteLength !== expectedBytes.byteLength) {
    return false;
  }
  return crypto.subtle.timingSafeEqual(candidateBytes, expectedBytes);
}

export function requireRole(
  request: Request,
  env: Env,
  roles: readonly AuthRole[],
): AuthRole {
  const candidate = bearerToken(request);
  if (!candidate) {
    throw new HttpError(401, "unauthorized", "A Bearer token is required.");
  }

  const configuredTokens: ReadonlyArray<readonly [AuthRole, string]> = [
    ["manager", env.MANAGER_TOKEN],
    ["submit", env.SUBMIT_TOKEN],
    ["worker", env.WORKER_TOKEN],
    ["viewer", env.VIEWER_TOKEN],
  ];
  for (const [role, expected] of configuredTokens) {
    if (roles.includes(role) && timingSafeEqualText(candidate, expected)) {
      return role;
    }
  }
  throw new HttpError(403, "forbidden", "The supplied token lacks permission.");
}
