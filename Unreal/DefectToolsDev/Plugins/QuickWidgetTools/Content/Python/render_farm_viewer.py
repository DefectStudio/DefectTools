"""Read-only Unreal Editor viewer for the Defect V2 render farm.

The matching Editor Utility Widget is intentionally a very small shell.  Its
Construct event calls :func:`run`, and this module builds the temporary UMG
controls, fetches Cloudflare data on a background thread, and updates the UI on
Unreal's Slate tick.  Nothing in this module can submit, mutate, stop, retry, or
delete farm data.
"""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import json
import threading
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    import unreal
except ImportError:  # Allows ordinary CPython unit tests of the data boundary.
    unreal = None  # type: ignore[assignment]


LOG_PREFIX = "[RenderFarmViewer]"
WIDGET_ASSET_PATH = "/QuickWidgetTools/EditorWidgets/WBP_09_Render_Farm_Viewer"
WIDGET_ROOT_NAME = "FarmViewerRoot"
DESIGNER_WIDGET_PATHS = {
    "jobs_table": "/QuickWidgetTools/EditorWidgets/RenderFarm/WBP_RenderFarmJobsTable",
    "workers_table": "/QuickWidgetTools/EditorWidgets/RenderFarm/WBP_RenderFarmWorkersTable",
}

JOB_FIELDS = (
    "JobName",
    "Worker",
    "User",
    "Status",
    "Time",
    "Errors",
    "Progress",
    "Submitted",
    "Completed",
)

JOB_RICH_TEXT_WIDGETS = {
    "JobName": "JobNameRichText",
    "Worker": "WorkerRichText",
    "User": "UserRichText",
    "Status": "StatusRichText",
    "Time": "TimeRichText",
    "Errors": "ErrorsRichText",
    "Progress": "ProgressRichText",
    "Submitted": "SubmittedRichText",
    "Completed": "CompletedRichText",
}
JOB_RICH_TEXT_PROPERTIES = {
    field: widget_name for field, widget_name in JOB_RICH_TEXT_WIDGETS.items()
}

JOB_SORT_BUTTONS = {
    field: f"{field}SortButton" for field in JOB_FIELDS
}
JOB_SORT_HEADINGS = {
    "JobName": "Job Name",
    "Worker": "Worker",
    "User": "User",
    "Status": "Status",
    "Time": "Time",
    "Errors": "Errors",
    "Progress": "Progress",
    "Submitted": "Submitted",
    "Completed": "Completed",
}
JOB_SORT_DEFAULT_DESCENDING = frozenset(
    {"Time", "Errors", "Progress", "Submitted", "Completed"}
)
JOB_DEFAULT_SORT_FIELD = "Submitted"
JOB_DEFAULT_SORT_DESCENDING = True

# These names and colors intentionally mirror FarmRenderManagerApp's job
# Treeview tags in the standalone manager.
JOB_STATUS_STYLE_COLORS = {
    "queued": "#d6d7d9",
    "rendering": "#74d680",
    "done": "#70aee8",
    "failed": "#ff7777",
}

WORKER_FIELDS = (
    "WorkerName",
    "Project",
    "Status",
    "CurrentJob",
    "LastSeen",
    "Commit",
)

WORKER_RICH_TEXT_WIDGETS = {
    "WorkerName": "WorkerNameRichText",
    "Project": "ProjectRichText",
    "Status": "StatusRichText",
    "CurrentJob": "CurrentJobRichText",
    "LastSeen": "LastSeenRichText",
    "Commit": "CommitRichText",
}
WORKER_RICH_TEXT_PROPERTIES = {
    field: widget_name
    for field, widget_name in WORKER_RICH_TEXT_WIDGETS.items()
}

# These names and colors intentionally mirror FarmRenderManagerApp's worker
# Treeview tags in the standalone manager.
WORKER_STATUS_STYLE_COLORS = {
    "waiting": "#74d680",
    "rendering": "#74d680",
    "stopping": "#e6c56c",
    "stale": "#ff7777",
}

# Company V2 read-only connection, independent of the V1/V2 submit selector.
# The service retains /api/v1 routes as its wire protocol version.
VIEWER_API_URL = "https://defect-farm-api-v2.twilight-tooth-7b7c.workers.dev"
VIEWER_TOKEN = "defect_v2_viewer_a03K2bPEMKFt0DTRZ_numXWyJVue8uD7QwDbpyf4AjIk5eN29gJOpt4n4VBOktoj"
REQUEST_TIMEOUT_SECONDS = 15.0
AUTO_REFRESH_SECONDS = 60.0
WORKER_STALE_AFTER_SECONDS = 180.0
MAX_JOBS = 1_000

_MISSING = "--"
_ACTIVE_CONTROLLERS: dict[str, "RenderFarmViewerController"] = {}
_DEFERRED_ATTACH_HANDLE: Any = None


class FarmViewerError(RuntimeError):
    """A safe, user-facing viewer failure."""


class ReadOnlyFarmClient:
    """Tiny Cloudflare client whose complete public surface is GET-only."""

    def __init__(
        self,
        api_url: str = VIEWER_API_URL,
        token: str = VIEWER_TOKEN,
        *,
        timeout_seconds: float = REQUEST_TIMEOUT_SECONDS,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        if not api_url.lower().startswith("https://"):
            raise ValueError("The render-farm viewer requires an HTTPS endpoint.")
        if not token.strip():
            raise ValueError("The render-farm viewer token is empty.")
        self._api_url = api_url.rstrip("/")
        self._token = token.strip()
        self._timeout_seconds = timeout_seconds
        self._opener = opener

    def _get(
        self,
        path: str,
        *,
        query: dict[str, str | int | None] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._api_url}{path}"
        if query:
            encoded = urlencode(
                {key: value for key, value in query.items() if value is not None}
            )
            if encoded:
                url = f"{url}?{encoded}"
        request = Request(
            url,
            method="GET",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._token}",
                "User-Agent": "Defect-Unreal-Render-Farm-Viewer/1",
            },
        )
        try:
            with self._opener(request, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise FarmViewerError(
                f"Cloudflare returned HTTP {error.code} while reading farm data."
            ) from error
        except URLError as error:
            raise FarmViewerError(f"Could not reach the render farm: {error.reason}") from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise FarmViewerError("The render farm returned invalid JSON.") from error
        if not isinstance(payload, dict):
            raise FarmViewerError("The render farm response was not a JSON object.")
        return payload

    def list_jobs(self, *, maximum: int = MAX_JOBS) -> list[dict[str, Any]]:
        jobs: list[dict[str, Any]] = []
        page_size = 100
        while len(jobs) < maximum:
            page = self._get(
                "/api/v1/jobs",
                query={"limit": min(page_size, maximum - len(jobs)), "offset": len(jobs)},
            ).get("jobs")
            if not isinstance(page, list) or not all(isinstance(item, dict) for item in page):
                raise FarmViewerError("The render-farm job list was invalid.")
            jobs.extend(page)
            if len(page) < page_size:
                break
        return jobs

    def list_workers(self) -> list[dict[str, Any]]:
        workers = self._get("/api/v1/workers").get("workers")
        if not isinstance(workers, list) or not all(
            isinstance(item, dict) for item in workers
        ):
            raise FarmViewerError("The render-farm worker list was invalid.")
        return [normalize_worker(worker) for worker in workers]


def normalize_worker(worker: dict[str, Any]) -> dict[str, Any]:
    """Adapt SQL worker records to the viewer's display fields."""
    capabilities = _json_object(worker.get("capabilities_json"))
    projects = capabilities.get("registered_projects")
    project_names = ", ".join(str(p) for p in projects) if isinstance(projects, list) else ""
    return {
        **worker,
        "worker_id": worker.get("id") or worker.get("worker_id"),
        "worker_name": worker.get("display_name") or worker.get("worker_name") or worker.get("id"),
        "last_heartbeat_utc": worker.get("last_seen_at") or worker.get("last_heartbeat_utc"),
        "project": worker.get("project") or capabilities.get("project") or project_names,
        "worker_git_commit": worker.get("worker_git_commit") or capabilities.get("git_commit"),
    }

def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _number(value: Any, default: float = 0.0) -> float:
    if value is None or isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _integer(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _display(value: Any) -> str:
    return _text(value) or _MISSING


def _parse_timestamp(value: Any) -> datetime | None:
    raw = _text(value)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_timestamp(value: Any) -> str:
    parsed = _parse_timestamp(value)
    if parsed is None:
        return _display(value)
    return parsed.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z").rstrip()


def _format_duration(start_value: Any, finish_value: Any, *, now: datetime | None = None) -> str:
    started = _parse_timestamp(start_value)
    finished = _parse_timestamp(finish_value) or now
    if started is None or finished is None:
        return _MISSING
    if finished.tzinfo is None:
        finished = finished.replace(tzinfo=timezone.utc)
    finished = finished.astimezone(timezone.utc)
    if finished < started:
        return _MISSING
    seconds = int((finished - started).total_seconds())
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _job_name(job: dict[str, Any]) -> str:
    shot = _text(job.get("shot_name"))
    version = _integer(job.get("render_version"))
    if shot and version is not None:
        return f"{shot}_v{version:03d}"
    return _text(job.get("job_name") or job.get("job_id")) or "Unknown Job"


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def job_row(job: dict[str, Any], *, now: datetime | None = None) -> tuple[str, ...]:
    status = _text(job.get("status")).casefold() or "unknown"
    finish = job.get("render_finished_utc")
    render_now = now if status == "rendering" else None
    progress = max(0.0, min(100.0, _number(job.get("progress"))))
    user = _text(job.get("submitted_user") or job.get("submitted_by"))
    errors = 1 if status == "failed" else 0
    return (
        _job_name(job),
        _text(job.get("worker")) if status == "rendering" else "",
        user,
        status.replace("_", " ").title(),
        _format_duration(job.get("render_started_utc"), finish, now=render_now),
        str(errors),
        f"{progress:g}%",
        _format_timestamp(job.get("submitted_utc")),
        _format_timestamp(finish),
    )


def job_columns(
    jobs: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, str]:
    """Convert every job into one newline-delimited value per table column."""
    rows = [job_row(job, now=now) for job in jobs]
    return {
        field: "\n".join(row[index] for row in rows)
        for index, field in enumerate(JOB_FIELDS)
    }


def job_status_style(job: dict[str, Any]) -> str:
    """Return the standalone manager's normalized color tag for one job."""
    normalized = _text(job.get("status")).strip().casefold()
    if normalized in {"submitting", "queue", "queued", "pending"}:
        return "queued"
    if normalized in {"rendering", "running", "active"}:
        return "rendering"
    if normalized in {"done", "complete", "completed", "success"}:
        return "done"
    if normalized in {"failed", "failure", "error"}:
        return "failed"
    return ""


def job_rich_columns(
    jobs: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, str]:
    """Return per-column RichText markup with one status-colored line per job."""
    rows = [job_row(job, now=now) for job in jobs]
    styles = [job_status_style(job) for job in jobs]
    return {
        field: "\n".join(
            (
                f"<{styles[row_index]}>"
                f"{escape(row[field_index], quote=False)}"
                f"</>"
                if styles[row_index]
                else escape(row[field_index], quote=False)
            )
            for row_index, row in enumerate(rows)
        )
        for field_index, field in enumerate(JOB_FIELDS)
    }


def _job_duration_seconds(
    job: dict[str, Any],
    *,
    now: datetime | None = None,
) -> float | None:
    started = _parse_timestamp(job.get("render_started_utc"))
    if started is None:
        return None
    finished = _parse_timestamp(job.get("render_finished_utc"))
    if finished is None:
        if _text(job.get("status")).casefold() != "rendering":
            return None
        finished = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return max(0.0, (finished - started).total_seconds())


def _job_sort_value(
    job: dict[str, Any],
    field: str,
    *,
    now: datetime | None = None,
) -> Any:
    status = _text(job.get("status")).casefold()
    if field == "JobName":
        return _job_name(job).casefold()
    if field == "Worker":
        return _text(job.get("worker")).casefold() if status == "rendering" else ""
    if field == "User":
        return _text(job.get("submitted_user") or job.get("submitted_by")).casefold()
    if field == "Status":
        return status
    if field == "Time":
        return _job_duration_seconds(job, now=now)
    if field == "Errors":
        error_count = _integer(job.get("error_count"))
        return error_count if error_count is not None else (1 if status == "failed" else 0)
    if field == "Progress":
        return _number(job.get("progress"))
    if field == "Submitted":
        submitted = _parse_timestamp(job.get("submitted_utc"))
        return submitted.timestamp() if submitted is not None else None
    if field == "Completed":
        completed = _parse_timestamp(job.get("render_finished_utc"))
        return completed.timestamp() if completed is not None else None
    raise ValueError(f"Unsupported render-job sort field: {field}")


def sort_jobs(
    jobs: list[dict[str, Any]],
    field: str,
    descending: bool = False,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Sort like the standalone manager, always leaving blank values last."""
    if field not in JOB_FIELDS:
        raise ValueError(f"Unsupported render-job sort field: {field}")
    populated: list[tuple[Any, dict[str, Any]]] = []
    missing: list[dict[str, Any]] = []
    selected_now = now or datetime.now(timezone.utc)
    for job in jobs:
        value = _job_sort_value(job, field, now=selected_now)
        if value is None or value == "":
            missing.append(job)
        else:
            populated.append((value, job))
    populated.sort(key=lambda item: item[0], reverse=descending)
    return [job for _value, job in populated] + missing


def _worker_is_stale(worker: dict[str, Any], *, now: datetime | None = None) -> bool:
    explicit = worker.get("stale")
    if isinstance(explicit, bool):
        return explicit
    if _text(worker.get("status")).casefold() == "offline":
        return True
    heartbeat = _parse_timestamp(worker.get("last_heartbeat_utc"))
    if heartbeat is None:
        return True
    selected_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return (selected_now - heartbeat).total_seconds() > WORKER_STALE_AFTER_SECONDS


def _worker_status(worker: dict[str, Any], *, now: datetime | None = None) -> str:
    if _worker_is_stale(worker, now=now):
        return "Stale"
    status = _text(worker.get("status"))
    if worker.get("stop_requested") and status != "stopping_after_current_job":
        return "Stop Requested"
    labels = {
        "starting": "Starting",
        "waiting": "Waiting",
        "moving_files": "Moving Files",
        "rendering": "Rendering",
        "finishing": "Finishing",
        "stopping_after_current_job": "Stopping After Job",
    }
    return labels.get(status, status.replace("_", " ").title() or "Unknown")


def _last_seen(worker: dict[str, Any], *, now: datetime | None = None) -> str:
    heartbeat = _parse_timestamp(worker.get("last_heartbeat_utc"))
    if heartbeat is None:
        return "Unknown"
    selected_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    seconds = max(0, int((selected_now - heartbeat).total_seconds()))
    if seconds < 60:
        return f"{seconds} sec ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min ago"
    return f"{minutes // 60} hr ago"


def worker_row(worker: dict[str, Any], *, now: datetime | None = None) -> tuple[str, ...]:
    shot = _text(worker.get("shot_name"))
    version = _text(worker.get("render_version"))
    current = " ".join(part for part in (shot, version) if part)
    return (
        _text(worker.get("worker_name") or worker.get("worker_id")) or "Unknown",
        _text(worker.get("project")),
        _worker_status(worker, now=now),
        current or _text(worker.get("current_job_id")) or "—",
        _last_seen(worker, now=now),
        _text(worker.get("worker_git_commit"))[:8] or "Unknown",
    )


def worker_columns(
    workers: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, str]:
    """Convert every worker into one newline-delimited value per table column."""
    rows = [worker_row(worker, now=now) for worker in workers]
    return {
        field: "\n".join(row[index] for row in rows)
        for index, field in enumerate(WORKER_FIELDS)
    }


def worker_status_style(
    worker: dict[str, Any],
    *,
    now: datetime | None = None,
) -> str:
    """Return the standalone manager's prioritized visual-status tag."""
    if _worker_is_stale(worker, now=now):
        return "stale"
    status = _text(worker.get("status")).casefold()
    if worker.get("stop_requested") or status == "stopping_after_current_job":
        return "stopping"
    if status == "rendering":
        return "rendering"
    return "waiting"


def worker_rich_columns(
    workers: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, str]:
    """Return per-column RichText markup with one status-colored line per worker."""
    rows = [worker_row(worker, now=now) for worker in workers]
    styles = [worker_status_style(worker, now=now) for worker in workers]
    return {
        field: "\n".join(
            f"<{styles[row_index]}>"
            f"{escape(row[field_index], quote=False)}"
            f"</>"
            for row_index, row in enumerate(rows)
        )
        for field_index, field in enumerate(WORKER_FIELDS)
    }


def normalize_workers(
    workers: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Map the raw D1 worker schema to the fields displayed by the manager."""
    selected_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    jobs_by_id = {_text(job.get("job_id")): job for job in jobs}
    normalized: list[dict[str, Any]] = []
    for raw in workers:
        worker_name = _text(raw.get("id") or raw.get("worker_name"))
        if not worker_name:
            continue
        capabilities = _json_object(
            raw.get("capabilities_json") or raw.get("capabilities")
        )
        current_job_id = _text(raw.get("current_job_id"))
        current_job = jobs_by_id.get(current_job_id, {})
        last_seen = _text(
            raw.get("last_seen_at") or raw.get("last_heartbeat_utc")
        )
        heartbeat = _parse_timestamp(last_seen)
        age = (
            max(0.0, (selected_now - heartbeat).total_seconds())
            if heartbeat is not None
            else None
        )
        status = _text(raw.get("status")) or "offline"
        version = _integer(current_job.get("render_version"))
        render_config = _text(current_job.get("render_config"))
        render_setting = (
            render_config.replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0]
            if render_config
            else ""
        )
        normalized.append(
            {
                **raw,
                "worker_name": worker_name,
                "machine_name": _text(raw.get("display_name")) or worker_name,
                "project": _text(capabilities.get("project"))
                or _text(current_job.get("project"))
                or "Cloud",
                "status": status,
                "started_utc": _text(
                    raw.get("first_seen_at") or raw.get("started_utc")
                ),
                "last_heartbeat_utc": last_seen,
                "heartbeat_age_seconds": age,
                "stale": status.casefold() == "offline"
                or age is None
                or age > WORKER_STALE_AFTER_SECONDS,
                "stop_requested": bool(raw.get("stop_requested")),
                "current_job_id": current_job_id,
                "shot_name": _text(current_job.get("shot_name")),
                "render_version": f"v{version:03d}" if version is not None else "",
                "render_setting": render_setting,
                "worker_git_branch": _text(capabilities.get("git_branch")),
                "worker_git_commit": _text(capabilities.get("git_commit")),
                "process_id": capabilities.get("process_id"),
                "capabilities": capabilities,
            }
        )
    return sorted(normalized, key=lambda item: item["worker_name"].casefold())


def _log(message: str) -> None:
    if unreal is not None:
        unreal.log(f"{LOG_PREFIX} {message}")


def _log_error(message: str) -> None:
    if unreal is not None:
        unreal.log_error(f"{LOG_PREFIX} {message}")


class RenderFarmViewerController:
    """Owns one open viewer widget and its background read cycle."""

    def __init__(self, widget: Any, client: ReadOnlyFarmClient | None = None) -> None:
        self.widget = widget
        self.client = client or ReadOnlyFarmClient()
        self.jobs: list[dict[str, Any]] = []
        self.workers: list[dict[str, Any]] = []
        self.mode = "jobs"
        self.job_sort_field: str | None = JOB_DEFAULT_SORT_FIELD
        self.job_sort_descending = JOB_DEFAULT_SORT_DESCENDING
        self._pending: tuple[list[dict[str, Any]], list[dict[str, Any]], str | None] | None = None
        self._pending_lock = threading.Lock()
        self._loading = False
        self._last_refresh = 0.0
        self._tick_handle: Any = None
        self._callbacks: list[Callable[..., Any]] = []
        self._job_sort_callbacks: list[Callable[..., Any]] = []
        self.root = widget.get_editor_property(WIDGET_ROOT_NAME)
        self.status_text = widget.get_editor_property("FarmViewerStatus")
        self.summary_text = widget.get_editor_property("FarmViewerSummary")
        self.list_scroll = widget.get_editor_property("FarmViewerList")
        self.designer_classes = {
            name: self._load_designer_class(path)
            for name, path in DESIGNER_WIDGET_PATHS.items()
        }
        self._bind_toolbar_button("FarmViewerRefreshButton", self.refresh)
        self._bind_toolbar_button(
            "FarmViewerJobsButton", lambda: self._set_mode("jobs")
        )
        self._bind_toolbar_button(
            "FarmViewerWorkersButton", lambda: self._set_mode("workers")
        )

    def _new(self, widget_class: Any, name: str = "") -> Any:
        # ``unreal.new_object`` creates only a raw UserWidget UObject, leaving
        # its WidgetTree and named designer children uninitialized. The normal
        # CreateWidget function is hidden from Unreal's generated Python API,
        # but remains callable through UFunction reflection.
        library_class = unreal.load_class(None, "/Script/UMG.WidgetBlueprintLibrary")
        library = unreal.get_default_object(library_class)
        return library.call_method(
            "Create",
            (unreal.EditorLevelLibrary.get_editor_world(), widget_class, None),
        )

    def _load_designer_class(self, asset_path: str) -> Any:
        asset = unreal.load_asset(asset_path)
        if asset is None or asset.generated_class() is None:
            raise RuntimeError(f"Designer widget is missing or invalid: {asset_path}")
        return asset.generated_class()

    def _designer_widget(self, kind: str, values: dict[str, str]) -> Any:
        instance = self._new(self.designer_classes[kind])
        self._set_widget_data(instance, values)
        return instance

    @staticmethod
    def _set_widget_data(instance: Any, values: dict[str, str]) -> None:
        for property_name, value in values.items():
            instance.set_editor_property(property_name, str(value))

    def _bind_toolbar_button(self, property_name: str, callback: Callable[[], None]) -> None:
        button = self.widget.get_editor_property(property_name)
        button.on_clicked.add_callable(callback)
        self._callbacks.append(callback)

    def start(self) -> None:
        self._tick_handle = unreal.register_slate_post_tick_callback(self._tick)
        self.refresh()

    def dispose(self) -> None:
        if self._tick_handle is not None:
            unreal.unregister_slate_post_tick_callback(self._tick_handle)
            self._tick_handle = None

    def refresh(self) -> None:
        if self._loading:
            return
        self._loading = True
        self.status_text.set_text("Refreshing read-only farm data…")
        threading.Thread(target=self._read_snapshot, daemon=True).start()

    def _read_snapshot(self) -> None:
        try:
            jobs = self.client.list_jobs()
            workers = normalize_workers(self.client.list_workers(), jobs)
            result = (jobs, workers, None)
        except Exception as error:
            result = ([], [], str(error))
        with self._pending_lock:
            self._pending = result

    def _tick(self, _delta_seconds: float) -> None:
        with self._pending_lock:
            pending = self._pending
            self._pending = None
        if pending is not None:
            jobs, workers, error = pending
            self._loading = False
            if error:
                self.status_text.set_text(f"Refresh failed: {error}")
                _log_error(error)
            else:
                self.jobs = jobs
                self.workers = workers
                self._last_refresh = time.monotonic()
                self.status_text.set_text(
                    f"Live • {len(jobs)} jobs • {len(workers)} workers • refreshed {_format_timestamp(datetime.now(timezone.utc).isoformat())}"
                )
                self._render()
        if not self._loading and time.monotonic() - self._last_refresh >= AUTO_REFRESH_SECONDS:
            self.refresh()

    def _set_mode(self, mode: str) -> None:
        self.mode = mode
        self._render()

    def _render(self) -> None:
        self.list_scroll.clear_children()
        if self.mode == "workers":
            self._render_workers()
        else:
            self._render_jobs()

    def _render_jobs(self) -> None:
        counts: dict[str, int] = {}
        for job in self.jobs:
            status = _text(job.get("status")).casefold() or "unknown"
            counts[status] = counts.get(status, 0) + 1
        self.summary_text.set_text(
            "Jobs: " + str(len(self.jobs)) + "    " + "    ".join(
                f"{name.title()}: {count}" for name, count in sorted(counts.items())
            )
        )
        # One aggregate widget owns every job column. Each property is a
        # newline-delimited column, so UMG controls all column widths in one
        # designer hierarchy instead of trying to align independent rows.
        now = datetime.now(timezone.utc)
        visible_jobs = (
            sort_jobs(
                self.jobs,
                self.job_sort_field,
                self.job_sort_descending,
                now=now,
            )
            if self.job_sort_field is not None
            else list(self.jobs)
        )
        job_table = self._designer_widget(
            "jobs_table",
            job_columns(visible_jobs, now=now),
        )
        for field, markup in job_rich_columns(visible_jobs, now=now).items():
            rich_text = job_table.get_editor_property(JOB_RICH_TEXT_PROPERTIES[field])
            if rich_text is None:
                raise RuntimeError(
                    f"Job table is missing {JOB_RICH_TEXT_WIDGETS[field]}"
                )
            rich_text.set_text(markup)
        self._bind_job_sort_buttons(job_table)
        self.list_scroll.add_child(job_table)

    def _bind_job_sort_buttons(self, job_table: Any) -> None:
        self._job_sort_callbacks = []
        for field, button_name in JOB_SORT_BUTTONS.items():
            button = job_table.get_editor_property(button_name)
            if button is None or button.get_class().get_name() != "Button":
                raise RuntimeError(f"Job table is missing {button_name}")
            callback = self._make_job_sort_callback(field)
            button.on_clicked.add_callable(callback)
            self._job_sort_callbacks.append(callback)

            marker = ""
            if field == self.job_sort_field:
                marker = " ▼" if self.job_sort_descending else " ▲"
            label = button.get_child_at(0)
            if label is None or label.get_class().get_name() != "TextBlock":
                raise RuntimeError(f"{button_name} must contain one TextBlock label")
            label.set_text(JOB_SORT_HEADINGS[field] + marker)

    def _make_job_sort_callback(self, field: str) -> Callable[[], None]:
        def callback() -> None:
            self._sort_jobs_by_field(field)

        return callback

    def _sort_jobs_by_field(self, field: str) -> None:
        if field not in JOB_FIELDS:
            raise ValueError(f"Unsupported render-job sort field: {field}")
        if field == self.job_sort_field:
            self.job_sort_descending = not self.job_sort_descending
        else:
            self.job_sort_field = field
            self.job_sort_descending = field in JOB_SORT_DEFAULT_DESCENDING
        self._render()

    def _render_workers(self) -> None:
        now = datetime.now(timezone.utc)
        online = sum(not _worker_is_stale(worker, now=now) for worker in self.workers)
        rendering = sum(_worker_status(worker, now=now) == "Rendering" for worker in self.workers)
        stale = sum(_worker_is_stale(worker, now=now) for worker in self.workers)
        self.summary_text.set_text(
            f"Workers: {len(self.workers)}    Online: {online}    Rendering: {rendering}    Stale: {stale}"
        )
        # Like the jobs view, one aggregate widget owns every worker column so
        # their widths and headers share the same designer hierarchy.
        worker_table_data = worker_columns(self.workers, now=now)
        worker_table = self._designer_widget(
            "workers_table",
            worker_table_data,
        )
        for field, markup in worker_rich_columns(self.workers, now=now).items():
            rich_text = worker_table.get_editor_property(
                WORKER_RICH_TEXT_PROPERTIES[field]
            )
            if rich_text is None:
                raise RuntimeError(
                    f"Worker table is missing {WORKER_RICH_TEXT_WIDGETS[field]}"
                )
            rich_text.set_text(markup)
        self.list_scroll.add_child(worker_table)


def _find_open_widget() -> Any:
    if unreal is None:
        raise RuntimeError("render_farm_viewer.run() must execute inside Unreal Editor")
    asset = unreal.load_asset(WIDGET_ASSET_PATH)
    if asset is None:
        raise RuntimeError(f"Viewer widget asset was not found: {WIDGET_ASSET_PATH}")
    subsystem = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem)
    widget = subsystem.find_utility_widget_from_blueprint(asset)
    if widget is None:
        raise RuntimeError("The Render Farm Viewer widget is not currently open.")
    return widget


def _attach_open_widget() -> None:
    widget = _find_open_widget()
    key = widget.get_path_name()
    previous = _ACTIVE_CONTROLLERS.pop(key, None)
    if previous is not None:
        previous.dispose()
    controller = RenderFarmViewerController(widget)
    _ACTIVE_CONTROLLERS[key] = controller
    controller.start()
    _log("Viewer attached; only Cloudflare GET endpoints are available.")


def _deferred_attach(_delta_seconds: float) -> None:
    global _DEFERRED_ATTACH_HANDLE
    try:
        _attach_open_widget()
    except RuntimeError:
        return
    if _DEFERRED_ATTACH_HANDLE is not None:
        unreal.unregister_slate_post_tick_callback(_DEFERRED_ATTACH_HANDLE)
        _DEFERRED_ATTACH_HANDLE = None


def run() -> str:
    """Attach the read-only controller to the currently open widget."""
    global _DEFERRED_ATTACH_HANDLE
    try:
        _attach_open_widget()
    except RuntimeError:
        # Construct can fire a fraction before the subsystem records its tab.
        if _DEFERRED_ATTACH_HANDLE is None:
            _DEFERRED_ATTACH_HANDLE = unreal.register_slate_post_tick_callback(
                _deferred_attach
            )
    else:
        if _DEFERRED_ATTACH_HANDLE is not None:
            unreal.unregister_slate_post_tick_callback(_DEFERRED_ATTACH_HANDLE)
            _DEFERRED_ATTACH_HANDLE = None
    return "true"
