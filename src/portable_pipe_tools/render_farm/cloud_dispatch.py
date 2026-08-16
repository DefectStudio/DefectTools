from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import socket
import subprocess
import time
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from portable_pipe_tools.render_farm.queue import (
    create_directory_with_retry,
    read_json_object,
    write_json_atomic,
)


DispatcherRole = Literal["submit", "worker", "manager"]
CLOUD_SETTINGS_SCHEMA_VERSION = 1
CLOUD_SETTINGS_FILENAME = "cloud_connection.json"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 20.0
DEFAULT_RETRY_DELAYS_SECONDS = (0.25, 1.0)
USER_AGENT = "DefectRenderFarm/1.0"


class DispatcherError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        code: str = "dispatcher_error",
        response: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.response = response


class DispatcherConnectionError(DispatcherError):
    pass


class DispatcherConfigurationError(DispatcherError):
    pass


@dataclass(frozen=True)
class DispatcherConnection:
    api_url: str
    role: DispatcherRole
    token: str = field(repr=False)

    def __post_init__(self) -> None:
        normalized_url = self.api_url.strip().rstrip("/")
        if not normalized_url.startswith(("https://", "http://127.0.0.1", "http://localhost")):
            raise DispatcherConfigurationError(
                "Dispatcher URL must use HTTPS (localhost HTTP is allowed for tests)."
            )
        if not self.token.strip():
            raise DispatcherConfigurationError("Dispatcher token cannot be empty.")
        object.__setattr__(self, "api_url", normalized_url)
        object.__setattr__(self, "token", self.token.strip())


@dataclass(frozen=True)
class CloudJobLease:
    job: dict[str, Any]
    lease_token: str
    lease_expires_at: int
    stop_requested: bool

    @property
    def job_id(self) -> str:
        value = self.job.get("job_id")
        if not isinstance(value, str) or not value.strip():
            raise DispatcherError("Claim response did not contain a valid job_id.")
        return value.strip()


@dataclass(frozen=True)
class CloudClaimResult:
    lease: CloudJobLease | None
    stop_requested: bool


def get_default_cloud_settings_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data)
    else:
        base = Path.home() / "AppData" / "Local"
    return base / "DefectStudio" / "RenderFarm" / CLOUD_SETTINGS_FILENAME


def load_cloud_settings(settings_path: Path | None = None) -> dict[str, Any]:
    path = settings_path or get_default_cloud_settings_path()
    try:
        return read_json_object(path)
    except (FileNotFoundError, OSError, ValueError):
        return {}


def save_cloud_settings(
    *,
    api_url: str,
    submit_token: str | None = None,
    worker_token: str | None = None,
    manager_token: str | None = None,
    settings_path: Path | None = None,
) -> Path:
    path = settings_path or get_default_cloud_settings_path()
    settings = load_cloud_settings(path)
    settings["schema_version"] = CLOUD_SETTINGS_SCHEMA_VERSION
    settings["api_url"] = api_url.strip().rstrip("/")
    for key, value in (
        ("submit_token", submit_token),
        ("worker_token", worker_token),
        ("manager_token", manager_token),
    ):
        if value is not None:
            cleaned = value.strip()
            if cleaned:
                settings[key] = cleaned
            else:
                settings.pop(key, None)
    create_directory_with_retry(path.parent, parents=True, exist_ok=True)
    write_json_atomic(path, settings)
    if os.name == "nt" and (username := os.environ.get("USERNAME")):
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.run(
            [
                "icacls.exe",
                str(path),
                "/inheritance:r",
                "/grant:r",
                f"{username}:(F)",
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
        )
    return path


def load_dispatcher_connection(
    role: DispatcherRole,
    *,
    settings_path: Path | None = None,
    required: bool = False,
) -> DispatcherConnection | None:
    settings = load_cloud_settings(settings_path)
    api_url = str(
        os.environ.get("DEFECT_FARM_API_URL") or settings.get("api_url") or ""
    ).strip()
    token_environment_name = f"DEFECT_FARM_{role.upper()}_TOKEN"
    token = str(
        os.environ.get(token_environment_name)
        or settings.get(f"{role}_token")
        or ""
    ).strip()
    if not api_url and not token and not required:
        return None
    if not api_url:
        raise DispatcherConfigurationError(
            "The Cloud Dispatcher URL has not been configured."
        )
    if not token:
        raise DispatcherConfigurationError(
            f"The Cloud Dispatcher {role} token has not been configured."
        )
    return DispatcherConnection(api_url=api_url, role=role, token=token)


class DispatcherClient:
    def __init__(
        self,
        connection: DispatcherConnection,
        *,
        timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
        retry_delays_seconds: tuple[float, ...] = DEFAULT_RETRY_DELAYS_SECONDS,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.connection = connection
        self.timeout_seconds = timeout_seconds
        self.retry_delays_seconds = retry_delays_seconds

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        query: dict[str, str | int | None] | None = None,
        headers: dict[str, str] | None = None,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        url = f"{self.connection.api_url}{path}"
        if query:
            encoded_query = urlencode(
                {key: value for key, value in query.items() if value is not None}
            )
            if encoded_query:
                url = f"{url}?{encoded_query}"
        payload = None
        request_headers = {
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            **(headers or {}),
        }
        if authenticated:
            request_headers["Authorization"] = f"Bearer {self.connection.token}"
        if body is not None:
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            request_headers["Content-Type"] = "application/json"

        delays = (*self.retry_delays_seconds, None)
        for attempt, retry_delay in enumerate(delays, start=1):
            request = Request(
                url=url,
                data=payload,
                headers=request_headers,
                method=method,
            )
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    raw_response = response.read()
                    parsed = json.loads(raw_response.decode("utf-8"))
                    if not isinstance(parsed, dict):
                        raise DispatcherError(
                            "Dispatcher returned JSON that was not an object."
                        )
                    return parsed
            except HTTPError as error:
                raw_error = error.read()
                parsed_error: dict[str, Any] | None = None
                try:
                    decoded_error = json.loads(raw_error.decode("utf-8"))
                    if isinstance(decoded_error, dict):
                        parsed_error = decoded_error
                except (UnicodeDecodeError, json.JSONDecodeError):
                    pass
                error_info = (
                    parsed_error.get("error")
                    if isinstance(parsed_error, dict)
                    else None
                )
                code = (
                    str(error_info.get("code") or "http_error")
                    if isinstance(error_info, dict)
                    else "http_error"
                )
                message = (
                    str(error_info.get("message") or error.reason)
                    if isinstance(error_info, dict)
                    else str(error.reason)
                )
                if error.code >= 500 and retry_delay is not None:
                    time.sleep(retry_delay)
                    continue
                raise DispatcherError(
                    message,
                    status=error.code,
                    code=code,
                    response=parsed_error,
                ) from error
            except (URLError, TimeoutError, socket.timeout, OSError) as error:
                if retry_delay is not None:
                    time.sleep(retry_delay)
                    continue
                reason = getattr(error, "reason", error)
                raise DispatcherConnectionError(
                    f"Could not reach the Cloud Dispatcher after {attempt} attempts: {reason}",
                    code="dispatcher_unavailable",
                ) from error
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise DispatcherError(
                    f"Dispatcher returned invalid JSON: {error}",
                    code="invalid_response",
                ) from error
        raise AssertionError("Dispatcher request retry loop exited unexpectedly")

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health", authenticated=False)

    def check_auth(self) -> DispatcherRole:
        response = self._request("GET", "/api/v1/auth/check")
        role = response.get("role")
        if role not in {"submit", "worker", "manager"}:
            raise DispatcherError("Dispatcher authentication response was invalid.")
        return role

    def submit_job(self, job: dict[str, Any]) -> dict[str, Any]:
        job_id = str(job.get("job_id") or "").strip()
        if not job_id:
            raise ValueError("job must contain job_id")
        return self._request(
            "POST",
            "/api/v1/jobs",
            body=job,
            headers={"Idempotency-Key": job_id},
        )

    def claim_job(
        self,
        worker_id: str,
        *,
        app_version: str | None = None,
        capabilities: dict[str, Any] | None = None,
        claim_request_id: str | None = None,
    ) -> CloudClaimResult:
        response = self._request(
            "POST",
            "/api/v1/jobs/claim",
            body={
                "worker_id": worker_id,
                "claim_request_id": claim_request_id or str(uuid4()),
                "app_version": app_version,
                "capabilities": capabilities,
            },
        )
        stop_requested = bool(response.get("stop_requested"))
        if not response.get("job_available"):
            return CloudClaimResult(lease=None, stop_requested=stop_requested)
        job = response.get("job")
        lease_token = response.get("lease_token")
        lease_expires_at = response.get("lease_expires_at")
        if not isinstance(job, dict):
            raise DispatcherError("Claim response did not contain a job object.")
        if not isinstance(lease_token, str) or not lease_token:
            raise DispatcherError("Claim response did not contain a lease token.")
        if not isinstance(lease_expires_at, int):
            raise DispatcherError("Claim response did not contain a lease expiration.")
        return CloudClaimResult(
            lease=CloudJobLease(
                job=job,
                lease_token=lease_token,
                lease_expires_at=lease_expires_at,
                stop_requested=stop_requested,
            ),
            stop_requested=stop_requested,
        )

    @staticmethod
    def _lease_body(
        worker_id: str,
        lease_token: str,
        **values: Any,
    ) -> dict[str, Any]:
        return {
            "worker_id": worker_id,
            "lease_token": lease_token,
            **values,
        }

    def heartbeat_job(
        self,
        job_id: str,
        worker_id: str,
        lease_token: str,
        *,
        progress: float | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/jobs/{quote(job_id, safe='')}/heartbeat",
            body=self._lease_body(
                worker_id,
                lease_token,
                **({"progress": progress} if progress is not None else {}),
            ),
        )

    def release_job(
        self,
        job_id: str,
        worker_id: str,
        lease_token: str,
        *,
        reason: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/jobs/{quote(job_id, safe='')}/release",
            body=self._lease_body(worker_id, lease_token, reason=reason),
        )

    def complete_job(
        self,
        job_id: str,
        worker_id: str,
        lease_token: str,
        *,
        result: dict[str, Any] | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/jobs/{quote(job_id, safe='')}/complete",
            body=self._lease_body(
                worker_id,
                lease_token,
                result=result or {},
                **({"reason": reason} if reason else {}),
            ),
        )

    def fail_job(
        self,
        job_id: str,
        worker_id: str,
        lease_token: str,
        *,
        reason: str,
        retryable: bool = True,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/jobs/{quote(job_id, safe='')}/fail",
            body=self._lease_body(
                worker_id,
                lease_token,
                reason=reason,
                retryable=retryable,
                result=result or {},
            ),
        )

    def list_jobs(
        self,
        *,
        status: str | None = None,
        project: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        response = self._request(
            "GET",
            "/api/v1/jobs",
            query={
                "status": status,
                "project": project,
                "limit": limit,
                "offset": offset,
            },
        )
        jobs = response.get("jobs")
        if not isinstance(jobs, list) or not all(isinstance(job, dict) for job in jobs):
            raise DispatcherError("Job list response was invalid.")
        return jobs

    def get_job(self, job_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/jobs/{quote(job_id, safe='')}")

    def clear_blacklist(self, job_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/jobs/{quote(job_id, safe='')}/clear-blacklist",
            body={},
        )

    def resubmit_job(
        self,
        job_id: str,
        *,
        submitted_by: str,
        submitted_user: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/jobs/{quote(job_id, safe='')}/resubmit",
            body={
                "request_id": request_id or str(uuid4()),
                "submitted_by": submitted_by,
                "submitted_user": submitted_user,
            },
        )

    def replace_job(
        self,
        source_job_id: str,
        replacement_job: dict[str, Any],
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/jobs/{quote(source_job_id, safe='')}/replace",
            body=replacement_job,
        )

    def list_workers(self) -> list[dict[str, Any]]:
        response = self._request("GET", "/api/v1/workers")
        workers = response.get("workers")
        if not isinstance(workers, list) or not all(
            isinstance(worker, dict) for worker in workers
        ):
            raise DispatcherError("Worker list response was invalid.")
        return workers

    def request_worker_stop(self, worker_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/workers/{quote(worker_id, safe='')}/stop",
            body={},
        )

    def acknowledge_worker_stop(self, worker_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/workers/{quote(worker_id, safe='')}/stop-ack",
            body={},
        )
