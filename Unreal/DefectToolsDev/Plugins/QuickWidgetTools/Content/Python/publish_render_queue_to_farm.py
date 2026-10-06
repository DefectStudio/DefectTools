"""Publish the current Unreal Movie Render Queue to the Defect render farm.

Blueprint Execute Python Script usage::

    import publish_render_queue_to_farm
    import importlib
    importlib.reload(publish_render_queue_to_farm)

    result_summary = publish_render_queue_to_farm.run()

The publisher is deliberately independent of PortablePipeTools so it can run in
Unreal's bundled Python environment. It sends each complete schema-v1 job
package directly to the Cloudflare D1 Dispatcher over HTTPS. D1 is the sole
authority for submission and worker leases. Dropbox is used only for the render
output paths already configured in Movie Render Queue; no Dropbox queue folder
or duplicate ``job.json`` package is created.

Frame ranges are *not* corrected here.  The current Level Sequence playback
bounds are copied exactly as Unreal reports them.  In particular,
``frame_end`` is the current exclusive playback end and the JSON records that
semantics explicitly.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import getpass
import hashlib
import importlib
import json
import os
import re
import socket
import stat as stat_module
import subprocess
import time
import traceback
from typing import Any, Callable, TypeVar
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

import unreal


LOG_PREFIX = "[PublishRenderQueueToFarm]"

JOB_SCHEMA_VERSION = 1
PUBLISHER_SCHEMA_VERSION = 4
OVERWRITE_EXISTING_MP4_FIELD = "overwrite_existing_mp4"
OVERWRITE_EXISTING_EXR_FIELD = "overwrite_existing_exr"
DISPATCHER_COORDINATION_FIELD = "dispatcher_coordination"
CLOUD_DISPATCHER_COORDINATION = "cloud"
DISPATCHER_REQUEST_TIMEOUT_SECONDS = 20.0
DISPATCHER_RETRY_DELAYS_SECONDS = (0.25, 1.0)

DEFAULT_PRIORITY = 50
LOCK_RETRY_TIMEOUT_SECONDS = 15.0
LOCK_RETRY_INITIAL_DELAY_SECONDS = 0.1
LOCK_RETRY_MAX_DELAY_SECONDS = 1.0
TRANSIENT_WINDOWS_LOCK_ERRORS = frozenset((32, 33))

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
_VERSION_RE = re.compile(
    r"(?:^|[_/\\.\-])v(\d{1,6})(?=$|[_/\\.\-])",
    re.IGNORECASE,
)
_DIRECTORY_PATH_RE = re.compile(r'^\(Path="(.*)"\)$', re.DOTALL)
_OperationResult = TypeVar("_OperationResult")


def _log(message: str) -> None:
    unreal.log(f"{LOG_PREFIX} {message}")


def _log_warning(message: str) -> None:
    unreal.log_warning(f"{LOG_PREFIX} Warning: {message}")


def _log_error(message: str) -> None:
    unreal.log_error(f"{LOG_PREFIX} Error: {message}")


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _safe_name(value: Any, fallback: str) -> str:
    cleaned = _SAFE_NAME_RE.sub("-", _safe_text(value).strip()).strip("-._")
    return cleaned or fallback


def _utc_now(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    return current.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _timestamp_token(now: datetime) -> str:
    return now.strftime("%Y%m%dT%H%M%S.") + f"{now.microsecond // 1000:03d}Z"


def _retry_transient_windows_lock(
    operation: Callable[[], _OperationResult],
    description: str,
    timeout_seconds: float = LOCK_RETRY_TIMEOUT_SECONDS,
    retry_winerrors: frozenset[int] = TRANSIENT_WINDOWS_LOCK_ERRORS,
) -> _OperationResult:
    """Retry selected transient Dropbox/Windows filesystem errors."""
    deadline = time.monotonic() + timeout_seconds
    delay_seconds = LOCK_RETRY_INITIAL_DELAY_SECONDS

    while True:
        try:
            return operation()
        except OSError as error:
            winerror = getattr(error, "winerror", None)
            if winerror not in retry_winerrors:
                raise

            remaining_seconds = deadline - time.monotonic()
            if remaining_seconds <= 0:
                _log_error(
                    f"{description} remained unavailable for {timeout_seconds:.1f} "
                    "seconds; giving up."
                )
                raise

            wait_seconds = min(delay_seconds, remaining_seconds)
            _log_warning(
                f"{description} is temporarily unavailable "
                f"(WinError {winerror}); retrying in {wait_seconds:.1f} seconds."
            )
            time.sleep(wait_seconds)
            delay_seconds = min(
                delay_seconds * 2,
                LOCK_RETRY_MAX_DELAY_SECONDS,
            )


def _path_status(path: str) -> os.stat_result | None:
    def inspect() -> os.stat_result | None:
        try:
            return os.stat(path)
        except FileNotFoundError:
            return None

    return _retry_transient_windows_lock(inspect, f"Inspect path {path}")


def _path_exists(path: str) -> bool:
    return _path_status(path) is not None


def _is_directory(path: str) -> bool:
    status = _path_status(path)
    return status is not None and stat_module.S_ISDIR(status.st_mode)


def _read_json_object(path: str) -> dict[str, Any]:
    def read() -> dict[str, Any]:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"Expected a JSON object in {path}")
        return data

    return _retry_transient_windows_lock(read, f"Read JSON {path}")


class DispatcherSubmissionError(RuntimeError):
    pass


BUNDLED_V2_SUBMIT_PROFILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "render_farm_v2_submit.json"
)


def _bundled_v2_submit_token(expected_url: str) -> str:
    """Use the company submit-only credential shipped with the editor plugin."""
    try:
        settings = _read_json_object(BUNDLED_V2_SUBMIT_PROFILE)
    except (OSError, ValueError):
        raise DispatcherSubmissionError(
            "The bundled V2 submit connection is missing or invalid. "
            "Update Quick Widget Tools to the complete company release."
        ) from None
    api_url = _safe_text(settings.get("api_url")).strip().rstrip("/")
    token = _safe_text(settings.get("submit_token")).strip()
    if api_url != expected_url or not token:
        raise DispatcherSubmissionError(
            "The bundled V2 submit connection is invalid. "
            "Update Quick Widget Tools to the complete company release."
        )
    return token


def _load_dispatcher_submit_connection(use_v2: bool = False) -> tuple[str, str]:
    if not isinstance(use_v2, bool):
        raise ValueError("use_v2 must be a boolean.")
    version = "V2" if use_v2 else "V1"
    expected_url = (
        "https://defect-farm-api-v2.twilight-tooth-7b7c.workers.dev"
        if use_v2 else "https://defect-farm-api.twilight-tooth-7b7c.workers.dev"
    )
    local_app_data = os.environ.get("LOCALAPPDATA") or os.path.join(
        os.path.expanduser("~"),
        "AppData",
        "Local",
    )
    settings_path = os.path.join(
        local_app_data,
        "DefectStudio",
        "RenderFarmV2" if use_v2 else "RenderFarm",
        "company-submit.json" if use_v2 else "cloud_connection.json",
    )
    try:
        settings = _read_json_object(settings_path)
    except (FileNotFoundError, OSError, ValueError):
        settings = {}

    api_url = _safe_text(
        os.environ.get(f"DEFECT_FARM_{version}_API_URL")
        or settings.get("api_url") or expected_url
    ).strip().rstrip("/")
    # Legacy/session credentials may only be reused for the selected service.
    # A previous V2 preview session must never silently redirect the V1 checkbox.
    legacy_url = _safe_text(os.environ.get("DEFECT_FARM_API_URL")).strip().rstrip("/")
    legacy_matches = legacy_url == expected_url or (not legacy_url and not use_v2)
    token = _safe_text(
        os.environ.get(f"DEFECT_FARM_{version}_SUBMIT_TOKEN")
        or (os.environ.get("DEFECT_FARM_SUBMIT_TOKEN") if legacy_matches else "")
        or settings.get("submit_token")
    ).strip()
    if api_url != expected_url:
        raise DispatcherSubmissionError(
            f"The {version} submitter profile must point to the company {version} service."
        )
    if use_v2 and not token:
        token = _bundled_v2_submit_token(expected_url)
    if not token:
        raise DispatcherSubmissionError(
            f"The {version} submit credential is not configured on this computer. "
            f"Ask the administrator to provision the {version} submitter profile."
        )
    return api_url, token


def _dispatcher_json_request(
    method: str,
    url: str,
    *,
    token: str | None = None,
    body: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    payload = (
        json.dumps(body, ensure_ascii=False).encode("utf-8")
        if body is not None
        else None
    )
    headers = {
        "Accept": "application/json",
        "User-Agent": "DefectUnrealFarmSubmitter/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    attempts = (*DISPATCHER_RETRY_DELAYS_SECONDS, None)
    for attempt_number, retry_delay in enumerate(attempts, start=1):
        request = Request(url, data=payload, headers=headers, method=method)
        try:
            with urlopen(request, timeout=DISPATCHER_REQUEST_TIMEOUT_SECONDS) as response:
                parsed = json.loads(response.read().decode("utf-8"))
                if not isinstance(parsed, dict):
                    raise DispatcherSubmissionError(
                        "Cloud Dispatcher returned JSON that was not an object."
                    )
                return parsed
        except HTTPError as error:
            try:
                parsed_error = json.loads(error.read().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                parsed_error = {}
            error_info = (
                parsed_error.get("error")
                if isinstance(parsed_error, dict)
                else None
            )
            message = (
                _safe_text(error_info.get("message"))
                if isinstance(error_info, dict)
                else _safe_text(error.reason)
            )
            if error.code >= 500 and retry_delay is not None:
                time.sleep(retry_delay)
                continue
            raise DispatcherSubmissionError(
                f"Cloud Dispatcher rejected the request (HTTP {error.code}): {message}"
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            if retry_delay is not None:
                time.sleep(retry_delay)
                continue
            reason = getattr(error, "reason", error)
            raise DispatcherSubmissionError(
                "Could not reach the Cloud Dispatcher after "
                f"{attempt_number} attempts: {reason}"
            ) from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DispatcherSubmissionError(
                f"Cloud Dispatcher returned invalid JSON: {error}"
            ) from error
    raise AssertionError("Cloud Dispatcher retry loop exited unexpectedly")


def _verify_dispatcher_health(api_url: str) -> None:
    health = _dispatcher_json_request("GET", f"{api_url}/health")
    if health.get("ok") is not True or health.get("database") != "connected":
        raise DispatcherSubmissionError(
            "Cloud Dispatcher health check did not confirm a D1 connection."
        )


def _submit_job_to_dispatcher(
    package: dict[str, Any],
    api_url: str,
    token: str,
) -> str:
    job_id = _safe_text(package.get("job_id")).strip()
    response = _dispatcher_json_request(
        "POST",
        f"{api_url}/api/v1/jobs",
        token=token,
        body=package,
        idempotency_key=job_id,
    )
    accepted_job = response.get("job")
    accepted_job_id = (
        _safe_text(accepted_job.get("job_id")).strip()
        if isinstance(accepted_job, dict)
        else ""
    )
    if not accepted_job_id:
        raise DispatcherSubmissionError(
            "Cloud Dispatcher accepted the request but did not return a job ID."
        )
    disposition = (
        "created"
        if response.get("created") is True
        else "already registered"
    )
    _log(
        f"Cloud Dispatcher accepted {job_id} ({disposition} as "
        f"{accepted_job_id})."
    )
    return accepted_job_id


def _load_show_file_server_root() -> str:
    try:
        module = importlib.import_module("get_file_server_path")
        module = importlib.reload(module)
        show_root = _safe_text(module.run()).strip()
    except Exception as exc:
        raise RuntimeError(
            f"Could not read ShowFileServerPath from QuickWidgetToolsSettings.ini: {exc}"
        ) from exc

    if not show_root:
        raise ValueError(
            "ShowFileServerPath is empty. Set the show file-server project folder "
            "before publishing."
        )

    show_root = os.path.normpath(os.path.expandvars(os.path.expanduser(show_root)))
    if not _is_directory(show_root):
        raise FileNotFoundError(
            f"ShowFileServerPath does not exist or is not a folder: {show_root}"
        )
    return show_root


def _inspect_current_queue() -> dict[str, Any]:
    module = importlib.import_module("inspect_render_queue")
    module = importlib.reload(module)
    document = module.inspect_queue()
    if not isinstance(document, dict):
        raise TypeError("inspect_render_queue.inspect_queue() did not return a dictionary.")
    return document


def _decode_quoted_text(value: str) -> str:
    try:
        return json.loads(f'"{value}"')
    except (TypeError, ValueError, json.JSONDecodeError):
        return value.replace(r"\\", "\\").replace(r'\"', '"')


def _decode_graph_value(variable: dict[str, Any]) -> Any:
    serialized = _safe_text(variable.get("serialized_value"))
    value_type = _safe_text(variable.get("value_type")).casefold()

    if value_type == "bool":
        lowered = serialized.strip().casefold()
        if lowered == "true":
            return True
        if lowered == "false":
            return False

    if value_type in ("int32", "int64", "byte"):
        try:
            return int(serialized.strip())
        except ValueError:
            pass

    if value_type in ("float", "double"):
        try:
            return float(serialized.strip())
        except ValueError:
            pass

    directory_match = _DIRECTORY_PATH_RE.match(serialized)
    if directory_match:
        return _decode_quoted_text(directory_match.group(1))

    return serialized


def _effective_graph_overrides(job: dict[str, Any]) -> dict[str, dict[str, Any]]:
    overrides: dict[str, dict[str, Any]] = {}
    assignments = job.get("graph_variable_assignments") or []
    if not isinstance(assignments, list):
        raise ValueError("graph_variable_assignments is not a list.")

    for assignment in assignments:
        if not isinstance(assignment, dict):
            continue
        variables = assignment.get("variables") or []
        if not isinstance(variables, list):
            continue
        for variable in variables:
            if not isinstance(variable, dict) or variable.get("enabled") is not True:
                continue
            name = _safe_text(variable.get("name")).strip()
            if not name:
                continue
            overrides[name.casefold()] = {
                "name": name,
                "enabled": True,
                "value": _decode_graph_value(variable),
                "serialized_value": _safe_text(variable.get("serialized_value")),
                "value_type": _safe_text(variable.get("value_type")),
                "container_type": _safe_text(variable.get("container_type")),
                "value_type_object": _safe_text(variable.get("value_type_object")),
            }
    return overrides


def _override_value(
    overrides: dict[str, dict[str, Any]],
    variable_name: str,
    default: Any = None,
) -> Any:
    variable = overrides.get(variable_name.casefold())
    return variable.get("value", default) if variable else default


def _legacy_output_directory(job: dict[str, Any]) -> str:
    setting = job.get("legacy_output_setting") or {}
    if not isinstance(setting, dict):
        return ""
    directory = setting.get("output_directory") or {}
    if isinstance(directory, dict):
        return _safe_text(directory.get("path")).strip()
    return _safe_text(directory).strip()


def _extract_render_version(*values: Any) -> int:
    matches: list[int] = []
    for value in values:
        for match in _VERSION_RE.finditer(_safe_text(value)):
            matches.append(int(match.group(1)))
    if not matches:
        raise ValueError(
            "Could not find a render version such as v012 in the configured "
            "file-name formats."
        )
    return matches[-1]


def _normalized_output_key(output_directory: Any, file_name_format: Any) -> str:
    directory = os.path.normcase(os.path.normpath(_safe_text(output_directory)))
    file_format = _safe_text(file_name_format).replace("\\", "/").casefold()
    if not directory and not file_format:
        return ""
    return f"{directory}|{file_format}"


def _fingerprint_payload(job_package: dict[str, Any]) -> dict[str, Any]:
    return {
        "project": job_package.get("project"),
        "uproject": job_package.get("uproject"),
        "level": job_package.get("level"),
        "sequence": job_package.get("sequence"),
        "render_config": job_package.get("render_config"),
        "frame_start": job_package.get("frame_start"),
        "frame_end": job_package.get("frame_end"),
        "frame_end_semantics": job_package.get("frame_end_semantics"),
        "output_directory": job_package.get("output_directory"),
        "output_file_name_format": job_package.get("output_file_name_format"),
        "mp4_file_name_format": job_package.get("mp4_file_name_format"),
        OVERWRITE_EXISTING_MP4_FIELD: job_package.get(
            OVERWRITE_EXISTING_MP4_FIELD
        ),
        OVERWRITE_EXISTING_EXR_FIELD: job_package.get(
            OVERWRITE_EXISTING_EXR_FIELD
        ),
        "graph_variable_overrides": job_package.get("graph_variable_overrides"),
    }


def _calculate_fingerprint(job_package: dict[str, Any]) -> str:
    canonical = json.dumps(
        _fingerprint_payload(job_package),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _project_file_from_document(document: dict[str, Any]) -> str:
    source = document.get("source") or {}
    if not isinstance(source, dict):
        source = {}

    project_file = _safe_text(source.get("project_file")).strip()
    if project_file and not os.path.isabs(project_file):
        project_file = os.path.join(
            _safe_text(source.get("project_dir")),
            project_file,
        )
    project_file = os.path.normpath(project_file) if project_file else ""

    if not project_file or not _path_exists(project_file):
        raise FileNotFoundError(
            f"Could not resolve the local Unreal project file: {project_file or '<empty>'}"
        )
    return project_file


def _submitted_git_commit(project_file: str) -> str | None:
    """Read the artist checkout's current commit for diagnostics only."""
    project_directory = os.path.dirname(project_file)
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            ["git", "-C", project_directory, "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=creation_flags,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        _log_warning(f"Could not query submitted Git commit: {exc}")
        return None

    commit = completed.stdout.strip()
    if completed.returncode != 0 or not re.fullmatch(r"[0-9a-fA-F]{40,64}", commit):
        detail = completed.stderr.strip() or "Git did not return a commit hash."
        _log_warning(f"Could not query submitted Git commit: {detail}")
        return None
    return commit.lower()


def _portable_output_relative_directory(
    output_directory: str,
    show_file_server_path: str,
    label: str,
) -> str:
    normalized_output = os.path.abspath(os.path.normpath(output_directory))
    normalized_show_root = os.path.abspath(os.path.normpath(show_file_server_path))
    try:
        common_path = os.path.commonpath((normalized_show_root, normalized_output))
        relative_path = os.path.relpath(normalized_output, normalized_show_root)
    except ValueError as exc:
        raise ValueError(
            f"{label}: output directory is not on the configured show file-server "
            f"path '{normalized_show_root}': {normalized_output}"
        ) from exc

    if os.path.normcase(common_path) != os.path.normcase(normalized_show_root):
        raise ValueError(
            f"{label}: output directory is outside the configured show file-server "
            f"path '{normalized_show_root}': {normalized_output}"
        )
    if relative_path in ("", "."):
        raise ValueError(
            f"{label}: output directory cannot be the show file-server root itself."
        )
    return relative_path.replace("\\", "/")


def _build_job_package(
    inspected_job: dict[str, Any],
    document: dict[str, Any],
    batch_id: str,
    submitted_utc: str,
    timestamp: str,
    priority: int,
    submitted_git_commit: str | None,
    show_file_server_path: str,
) -> dict[str, Any]:
    queue_index = inspected_job.get("queue_index", "?")
    job_name = _safe_text(inspected_job.get("job_name")).strip()
    label = job_name or f"queue index {queue_index}"

    if inspected_job.get("inspection_error"):
        raise ValueError(f"{label}: {inspected_job['inspection_error']}")
    if not job_name:
        raise ValueError(f"Queue job {queue_index} has no job name.")
    if inspected_job.get("consumed") is True:
        raise ValueError(f"{label}: consumed jobs cannot be published.")

    level = _safe_text(inspected_job.get("map")).strip()
    sequence = _safe_text(inspected_job.get("sequence")).strip()
    graph = _safe_text(inspected_job.get("graph_preset")).strip()
    if not level:
        raise ValueError(f"{label}: map/level is missing.")
    if not sequence:
        raise ValueError(f"{label}: Level Sequence is missing.")
    if not graph or inspected_job.get("is_using_graph_configuration") is not True:
        raise ValueError(f"{label}: a Movie Render Graph preset is required.")

    legacy_output = inspected_job.get("legacy_output_setting") or {}
    if isinstance(legacy_output, dict) and legacy_output.get("use_custom_playback_range"):
        raise ValueError(
            f"{label}: a legacy MRQ custom playback range is active. The publisher "
            "will not guess which range wins."
        )
    basic_config = inspected_job.get("basic_config") or {}
    if isinstance(basic_config, dict) and (
        basic_config.get("override_custom_start_frame")
        or basic_config.get("override_custom_end_frame")
    ):
        raise ValueError(
            f"{label}: a basic-config frame override is active. The publisher will "
            "not guess which range wins."
        )

    playback = inspected_job.get("sequence_playback_range") or {}
    if not isinstance(playback, dict):
        raise ValueError(f"{label}: playback-range inspection is missing.")
    frame_start = playback.get("display_start")
    frame_end = playback.get("display_end_exclusive")
    frame_count = playback.get("display_frame_count")
    if (
        not isinstance(frame_start, int)
        or isinstance(frame_start, bool)
        or not isinstance(frame_end, int)
        or isinstance(frame_end, bool)
        or frame_end <= frame_start
    ):
        raise ValueError(
            f"{label}: invalid sequence playback range [{frame_start}, {frame_end})."
        )

    overrides = _effective_graph_overrides(inspected_job)
    output_directory = _safe_text(
        _override_value(overrides, "OutputDirectory", "")
    ).strip()
    if not output_directory:
        output_directory = _legacy_output_directory(inspected_job)
    if not output_directory:
        raise ValueError(f"{label}: effective output directory is missing.")
    output_directory = os.path.normpath(output_directory)
    output_relative_directory = _portable_output_relative_directory(
        output_directory,
        show_file_server_path,
        label,
    )

    file_name_format = _safe_text(
        _override_value(overrides, "FileNameFormat", "")
    ).strip()
    if not file_name_format:
        raise ValueError(f"{label}: enabled FileNameFormat graph override is missing.")

    mp4_file_name_format = _safe_text(
        _override_value(overrides, "MP4FileNameFormat", "")
    ).strip()
    render_version = _extract_render_version(
        file_name_format,
        mp4_file_name_format,
    )

    mp4_enabled = bool(_override_value(overrides, "MP4", False))
    exr_enabled = bool(_override_value(overrides, "EXR", False))
    hero_enabled = bool(_override_value(overrides, "Hero", False))
    if not mp4_enabled and not exr_enabled:
        raise ValueError(f"{label}: both MP4 and EXR graph outputs are disabled.")

    source = document.get("source") or {}
    if not isinstance(source, dict):
        source = {}
    project_file = _project_file_from_document(document)
    project_name = _safe_text(source.get("project_name")).strip()
    if not project_name:
        project_name = os.path.splitext(os.path.basename(project_file))[0]

    computer = _safe_name(
        source.get("computer") or os.environ.get("COMPUTERNAME") or socket.gethostname(),
        "UNKNOWN-COMPUTER",
    )
    submitted_user = _safe_text(source.get("user") or getpass.getuser()).strip()
    shot_name = _safe_name(job_name, f"QUEUE-{queue_index}")
    job_id = _safe_name(
        f"{shot_name}_v{render_version:03d}_{timestamp}_{uuid4().hex[:6]}",
        f"UNREAL-JOB-{uuid4().hex[:12]}",
    )

    sorted_overrides = {
        variable["name"]: variable
        for variable in sorted(
            overrides.values(),
            key=lambda item: item["name"].casefold(),
        )
    }

    package: dict[str, Any] = {
        "schema_version": JOB_SCHEMA_VERSION,
        "publisher_schema_version": PUBLISHER_SCHEMA_VERSION,
        DISPATCHER_COORDINATION_FIELD: CLOUD_DISPATCHER_COORDINATION,
        "job_type": "unreal_movie_render_graph",
        "job_id": job_id,
        "batch_id": batch_id,
        "status": "queued",
        "priority": priority,
        "shot_name": shot_name,
        "render_version": render_version,
        "submitted_by": computer,
        "submitted_user": submitted_user,
        "submitted_utc": submitted_utc,
        "project": project_name,
        "uproject": project_file.replace("\\", "/"),
        "engine_version": _safe_text(source.get("engine_version")),
        "level": level,
        "sequence": sequence,
        "render_config": graph,
        "config_mode": _safe_text(inspected_job.get("config_mode")),
        "frame_start": frame_start,
        "frame_end": frame_end,
        "frame_end_semantics": "exclusive",
        "frame_count": frame_count if isinstance(frame_count, int) else frame_end - frame_start,
        "frame_range_source": _safe_text(playback.get("source")),
        "output_directory": output_directory,
        "submitted_output_directory": output_directory,
        "submitted_show_file_server_path": os.path.normpath(show_file_server_path),
        "output_relative_directory": output_relative_directory,
        "worker_show_file_server_path": None,
        "worker_output_directory": None,
        "output_file_name_format": file_name_format,
        "mp4_file_name_format": mp4_file_name_format,
        "outputs": {
            "mp4": mp4_enabled,
            "exr": exr_enabled,
            "hero": hero_enabled,
        },
        OVERWRITE_EXISTING_MP4_FIELD: mp4_enabled,
        OVERWRITE_EXISTING_EXR_FIELD: exr_enabled,
        "graph_variable_overrides": sorted_overrides,
        "mrq_snapshot": inspected_job,
        "sync_policy": "latest",
        "submitted_git_commit": submitted_git_commit,
        "rendered_git_commit": None,
        "worker": None,
        "claimed_utc": None,
        "render_started_utc": None,
        "render_finished_utc": None,
        "attempt": 0,
        "result": None,
        "test_job": False,
    }
    package["submission_fingerprint"] = _calculate_fingerprint(package)
    return package


def _validate_and_build_packages(
    document: dict[str, Any],
    priority: int,
    show_file_server_path: str,
) -> tuple[list[dict[str, Any]], str, str]:
    document_warnings = document.get("warnings") or []
    if document_warnings:
        raise ValueError(
            "Queue inspection produced document-level warnings: "
            + " | ".join(_safe_text(item) for item in document_warnings)
        )

    queue = document.get("queue") or {}
    jobs = queue.get("jobs") or [] if isinstance(queue, dict) else []
    if not isinstance(jobs, list) or not jobs:
        raise ValueError("The Movie Render Queue is empty.")

    publishable_jobs: list[dict[str, Any]] = []
    disabled_count = 0
    consumed_count = 0
    for job in jobs:
        if not isinstance(job, dict):
            raise ValueError("Queue inspection contained a non-object job entry.")
        if job.get("enabled") is not True:
            disabled_count += 1
            continue
        if job.get("consumed") is True:
            consumed_count += 1
            continue
        warnings = job.get("warnings") or []
        shot_warnings = [
            warning
            for shot in (job.get("shots") or [])
            if isinstance(shot, dict)
            for warning in (shot.get("warnings") or [])
        ]
        if warnings or shot_warnings:
            label = _safe_text(job.get("job_name")) or _safe_text(job.get("queue_index"))
            raise ValueError(
                f"{label}: inspection warnings must be resolved before publishing: "
                + " | ".join(_safe_text(item) for item in list(warnings) + shot_warnings)
            )
        publishable_jobs.append(job)

    if not publishable_jobs:
        raise ValueError(
            "The queue contains no enabled, unconsumed jobs to publish "
            f"({disabled_count} disabled, {consumed_count} consumed)."
        )

    names = [_safe_text(job.get("job_name")).strip().casefold() for job in publishable_jobs]
    duplicate_names = sorted(
        name for name, count in Counter(names).items() if name and count > 1
    )
    if duplicate_names:
        raise ValueError(
            "Duplicate enabled MRQ job names were found. Clear the old queue and "
            "rebuild it before publishing: " + ", ".join(duplicate_names)
        )

    now = datetime.now(timezone.utc)
    submitted_utc = _utc_now(now)
    timestamp = _timestamp_token(now)
    source = document.get("source") or {}
    project_name = _safe_name(
        source.get("project_name") if isinstance(source, dict) else "",
        "UNREAL",
    )
    batch_id = _safe_name(
        f"{project_name}_{timestamp}_{uuid4().hex[:6]}",
        f"UNREAL-BATCH-{uuid4().hex[:12]}",
    )

    project_file = _project_file_from_document(document)
    submitted_git_commit = _submitted_git_commit(project_file)
    if submitted_git_commit:
        _log(f"Submitted Git commit: {submitted_git_commit}")

    packages = [
        _build_job_package(
            inspected_job=job,
            document=document,
            batch_id=batch_id,
            submitted_utc=submitted_utc,
            timestamp=timestamp,
            priority=priority,
            submitted_git_commit=submitted_git_commit,
            show_file_server_path=show_file_server_path,
        )
        for job in publishable_jobs
    ]

    output_keys = [
        _normalized_output_key(
            package.get("output_directory"),
            package.get("output_file_name_format"),
        )
        for package in packages
    ]
    duplicate_output_keys = [
        key for key, count in Counter(output_keys).items() if key and count > 1
    ]
    if duplicate_output_keys:
        duplicate_shots = [
            package["shot_name"]
            for package, key in zip(packages, output_keys)
            if key in duplicate_output_keys
        ]
        raise ValueError(
            "Multiple enabled jobs resolve to the same output target: "
            + ", ".join(duplicate_shots)
        )

    fingerprints = [package["submission_fingerprint"] for package in packages]
    if len(fingerprints) != len(set(fingerprints)):
        raise ValueError("Duplicate render-job payloads were found in the current queue.")

    return packages, batch_id, submitted_utc


def _show_confirmation(packages: list[dict[str, Any]], farm_root: str, use_v2: bool = False) -> bool:
    editor_dialog = getattr(unreal, "EditorDialog", None)
    app_message_type = getattr(unreal, "AppMsgType", None)
    app_return_type = getattr(unreal, "AppReturnType", None)
    if editor_dialog is None or app_message_type is None or app_return_type is None:
        raise RuntimeError(
            "Unreal Editor confirmation dialog API is unavailable; nothing was published."
        )

    shot_preview = ", ".join(package["shot_name"] for package in packages[:8])
    if len(packages) > 8:
        shot_preview += f", and {len(packages) - 8} more"
    overwrite_count = sum(
        package.get(OVERWRITE_EXISTING_MP4_FIELD) is True
        or package.get(OVERWRITE_EXISTING_EXR_FIELD) is True
        for package in packages
    )
    message = (
        f"Send {len(packages)} render job(s) to the {'V2' if use_v2 else 'V1'} farm?\n\n"
        f"Farm: {farm_root}\n\n"
        f"Jobs: {shot_preview}\n\n"
        f"Overwrite existing MP4 + EXRs: enabled for {overwrite_count} job(s)\n\n"
        "Job packages and leases: Cloudflare D1 Dispatcher\n"
        "Render outputs: Dropbox\n\n"
        "The current Unreal frame ranges will be preserved exactly.\n\n"
        "Successfully published jobs will be removed from this Movie Render Queue."
    )
    response = editor_dialog.show_message(
        "Send Render Queue to Farm",
        message,
        app_message_type.YES_NO,
    )
    yes_value = app_return_type.YES
    return response == yes_value or _safe_text(response).upper().endswith("YES")


def _job_name_from_live_queue(job: Any) -> str:
    getter = getattr(job, "get_editor_property", None)
    if callable(getter):
        try:
            return _safe_text(getter("job_name")).strip()
        except Exception:
            pass
    return _safe_text(getattr(job, "job_name", "")).strip()


def _remove_published_jobs_from_queue(
    packages: list[dict[str, Any]],
    expected_job_count: int,
) -> int:
    """Remove the just-published jobs from the live editor MRQ safely."""
    queue_subsystem = unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem)
    if queue_subsystem is None:
        raise RuntimeError(
            "Jobs were published, but MoviePipelineQueueSubsystem was unavailable "
            "so they could not be removed from the editor queue."
        )

    queue = queue_subsystem.get_queue()
    if queue is None:
        raise RuntimeError(
            "Jobs were published, but the live Movie Render Queue was unavailable "
            "so they could not be removed."
        )

    live_jobs = list(queue.get_jobs() or [])
    if len(live_jobs) != expected_job_count:
        raise RuntimeError(
            "Jobs were published, but the Movie Render Queue changed during "
            "submission. No queue jobs were removed."
        )

    targets: list[tuple[int, str, Any]] = []
    seen_indexes: set[int] = set()
    for package in packages:
        snapshot = package.get("mrq_snapshot") or {}
        queue_index = snapshot.get("queue_index") if isinstance(snapshot, dict) else None
        expected_name = (
            _safe_text(snapshot.get("job_name")).strip()
            if isinstance(snapshot, dict)
            else ""
        )
        if (
            not isinstance(queue_index, int)
            or isinstance(queue_index, bool)
            or queue_index < 0
            or queue_index >= len(live_jobs)
            or queue_index in seen_indexes
        ):
            raise RuntimeError(
                "Jobs were published, but their original queue positions could not "
                "be verified. No queue jobs were removed."
            )

        live_job = live_jobs[queue_index]
        live_name = _job_name_from_live_queue(live_job)
        if not expected_name or live_name != expected_name:
            raise RuntimeError(
                "Jobs were published, but the Movie Render Queue changed during "
                f"submission at index {queue_index}. No queue jobs were removed."
            )

        seen_indexes.add(queue_index)
        targets.append((queue_index, expected_name, live_job))

    delete_job = getattr(queue, "delete_job", None)
    if not callable(delete_job):
        raise RuntimeError(
            "Jobs were published, but this Unreal version does not expose the "
            "Movie Render Queue delete-job API."
        )

    removed_count = 0
    for _, job_name, live_job in sorted(targets, key=lambda item: item[0], reverse=True):
        delete_job(live_job)
        removed_count += 1
        _log(f"Removed published job from Movie Render Queue: {job_name}")

    remaining_count = len(list(queue.get_jobs() or []))
    expected_remaining_count = expected_job_count - removed_count
    if remaining_count != expected_remaining_count:
        raise RuntimeError(
            f"Published {len(packages)} job(s), but Unreal reports that only "
            f"{expected_job_count - remaining_count} were removed from the Movie "
            "Render Queue."
        )
    return removed_count


def _clean_summary_value(value: Any) -> str:
    return _safe_text(value).replace(";", ",").replace("\r", " ").replace("\n", " ")


def _format_summary(
    success: bool,
    cancelled: bool = False,
    jobs_found: int = 0,
    jobs_publishable: int = 0,
    jobs_published: int = 0,
    farm_root: str = "",
    batch_id: str = "",
    message: str = "",
) -> str:
    return (
        f"success={1 if success else 0};"
        f"cancelled={1 if cancelled else 0};"
        f"jobs_found={jobs_found};"
        f"jobs_publishable={jobs_publishable};"
        f"jobs_published={jobs_published};"
        f"farm_root={_clean_summary_value(farm_root)};"
        f"batch_id={_clean_summary_value(batch_id)};"
        f"message={_clean_summary_value(message)}"
    )


def run(
    priority: int = DEFAULT_PRIORITY,
    require_confirmation: bool = True,
    use_v2: bool = False,
) -> str:
    """Validate and publish all enabled, unconsumed jobs in the editor MRQ."""
    jobs_found = 0
    packages: list[dict[str, Any]] = []
    farm_root = ""
    batch_id = ""
    submitted_job_ids: list[str] = []
    dispatcher_api_url = ""
    dispatcher_submit_token = ""

    try:
        if not isinstance(priority, int) or isinstance(priority, bool):
            raise ValueError("priority must be an integer.")
        _log("Starting Movie Render Queue farm-publication preflight...")
        document = _inspect_current_queue()
        queue = document.get("queue") or {}
        jobs = queue.get("jobs") or [] if isinstance(queue, dict) else []
        jobs_found = len(jobs) if isinstance(jobs, list) else 0

        show_root = _load_show_file_server_root()
        farm_root = os.path.normpath(os.path.join(show_root, "renderFarm"))
        dispatcher_api_url, dispatcher_submit_token = (
            _load_dispatcher_submit_connection(use_v2=use_v2)
        )
        _verify_dispatcher_health(dispatcher_api_url)
        packages, batch_id, _ = _validate_and_build_packages(
            document,
            priority,
            show_root,
        )

        for package in packages:
            _log(
                "Preflight OK: {shot} v{version:03d}, frames=[{start},{end}), "
                "MP4={mp4}, EXR={exr}, overwrite_mp4={overwrite_mp4}, "
                "overwrite_exr={overwrite_exr}, "
                "graph='{graph}', output='{output}'".format(
                    shot=package["shot_name"],
                    version=package["render_version"],
                    start=package["frame_start"],
                    end=package["frame_end"],
                    mp4=package["outputs"]["mp4"],
                    exr=package["outputs"]["exr"],
                    overwrite_mp4=package[OVERWRITE_EXISTING_MP4_FIELD],
                    overwrite_exr=package[OVERWRITE_EXISTING_EXR_FIELD],
                    graph=package["render_config"],
                    output=package["output_directory"],
                )
            )

        _log(
            f"Preflight passed for {len(packages)} job(s). Farm root: {farm_root}"
        )
        if require_confirmation and not _show_confirmation(packages, farm_root, use_v2=use_v2):
            message = "Farm submission cancelled by user; nothing was published."
            _log(message)
            return _format_summary(
                success=False,
                cancelled=True,
                jobs_found=jobs_found,
                jobs_publishable=len(packages),
                farm_root=farm_root,
                batch_id=batch_id,
                message=message,
            )

        for package in packages:
            submitted_job_ids.append(
                _submit_job_to_dispatcher(
                    package,
                    dispatcher_api_url,
                    dispatcher_submit_token,
                )
            )
        removed_count = _remove_published_jobs_from_queue(packages, jobs_found)

        message = (
            f"Submitted {len(submitted_job_ids)} Unreal render job(s) directly "
            "to the Cloud Dispatcher and removed "
            f"{removed_count} from the Movie Render Queue."
        )
        _log(message)
        _log(f"Batch ID: {batch_id}")
        return _format_summary(
            success=True,
            jobs_found=jobs_found,
            jobs_publishable=len(packages),
            jobs_published=len(submitted_job_ids),
            farm_root=farm_root,
            batch_id=batch_id,
            message=message,
        )

    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        _log_error(message)
        _log_error(traceback.format_exc())
        return _format_summary(
            success=False,
            jobs_found=jobs_found,
            jobs_publishable=len(packages),
            jobs_published=len(submitted_job_ids),
            farm_root=farm_root,
            batch_id=batch_id,
            message=message,
        )


if __name__ == "__main__":
    run()
