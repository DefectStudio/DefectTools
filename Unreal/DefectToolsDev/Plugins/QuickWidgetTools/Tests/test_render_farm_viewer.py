from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType
import unittest
from urllib.parse import parse_qs, urlparse


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "Content"
    / "Python"
    / "render_farm_viewer.py"
)


class UnrealBoundary(ModuleType):
    def __init__(self) -> None:
        super().__init__("unreal")

    @staticmethod
    def log(_message: str) -> None:
        pass

    @staticmethod
    def log_error(_message: str) -> None:
        pass


def load_viewer():
    sys.modules["unreal"] = UnrealBoundary()
    spec = importlib.util.spec_from_file_location("render_farm_viewer_under_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        pass

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class RecordingOpener:
    def __init__(self) -> None:
        self.requests = []

    def __call__(self, request, *, timeout):
        self.requests.append((request, timeout))
        parsed = urlparse(request.full_url)
        if parsed.path == "/api/v1/jobs":
            offset = int(parse_qs(parsed.query).get("offset", [0])[0])
            jobs = [{"job_id": str(index)} for index in range(100)] if offset == 0 else [{"job_id": "last"}]
            return FakeResponse({"jobs": jobs})
        if parsed.path == "/api/v1/workers":
            return FakeResponse({"workers": [{"worker_id": "worker-a"}]})
        return FakeResponse({"job_id": "shot/one", "status": "rendering"})


class FakeDesignerWidget:
    def __init__(self) -> None:
        self.properties = {}

    def set_editor_property(self, name, value) -> None:
        self.properties[name] = value


class ReadOnlyClientTests(unittest.TestCase):
    def test_sql_worker_fields_reach_display(self) -> None:
        viewer = load_viewer()
        raw = {
            "id": "worker-v2", "display_name": "Render PC", "status": "waiting",
            "last_seen_at": "2026-09-30T20:00:00Z", "current_job_id": None,
            "capabilities_json": json.dumps({"registered_projects": ["spectrum", "ironwidow"],
                                             "git_commit": "1234567890abcdef"}),
        }
        client = viewer.ReadOnlyFarmClient(opener=lambda *a, **k: FakeResponse({"workers": [raw]}))
        worker = client.list_workers()[0]
        now = datetime(2026, 9, 30, 20, 0, 30, tzinfo=timezone.utc)
        self.assertEqual(("Render PC", "spectrum, ironwidow", "Waiting", "—", "30 sec ago", "12345678"),
                         viewer.worker_row(worker, now=now))
        self.assertEqual("waiting", viewer.worker_status_style(worker, now=now))
        raw.update(status="offline", current_job_id="shot-job", capabilities_json="invalid")
        row = viewer.worker_row(client.list_workers()[0], now=now)
        self.assertEqual("Stale", row[2])
        self.assertEqual("shot-job", row[3])
        self.assertEqual("Unknown", row[5])

    def test_every_request_is_get_and_uses_bearer_viewer_auth(self) -> None:
        viewer = load_viewer()
        opener = RecordingOpener()
        client = viewer.ReadOnlyFarmClient(opener=opener)

        self.assertEqual(101, len(client.list_jobs()))
        self.assertEqual("worker-a", client.list_workers()[0]["worker_id"])
        self.assertTrue(opener.requests)
        for request, timeout in opener.requests:
            self.assertEqual("GET", request.get_method())
            self.assertEqual(
                "defect-farm-api-v2.twilight-tooth-7b7c.workers.dev",
                urlparse(request.full_url).netloc,
            )
            self.assertEqual(f"Bearer {viewer.VIEWER_TOKEN}", request.headers["Authorization"])
            self.assertEqual(viewer.REQUEST_TIMEOUT_SECONDS, timeout)

    def test_client_exposes_no_mutating_operations(self) -> None:
        viewer = load_viewer()
        public_methods = {
            name
            for name in dir(viewer.ReadOnlyFarmClient)
            if not name.startswith("_")
        }
        self.assertEqual({"list_jobs", "list_workers"}, public_methods)

    def test_rejects_non_https_endpoint(self) -> None:
        viewer = load_viewer()
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            viewer.ReadOnlyFarmClient(api_url="http://example.test", token="viewer")


class FarmFormattingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.viewer = load_viewer()
        self.now = datetime(2026, 8, 25, 20, 0, tzinfo=timezone.utc)

    def test_job_row_matches_manager_columns(self) -> None:
        row = self.viewer.job_row(
            {
                "job_id": "j1",
                "shot_name": "SH010",
                "render_version": 4,
                "worker": "node-1",
                "submitted_user": "Kat",
                "status": "rendering",
                "render_started_utc": "2026-08-25T19:58:30Z",
                "progress": 37.5,
                "submitted_utc": "2026-08-25T19:50:00Z",
            },
            now=self.now,
        )
        self.assertEqual(9, len(row))
        self.assertEqual("SH010_v004", row[0])
        self.assertEqual("node-1", row[1])
        self.assertEqual("Rendering", row[3])
        self.assertEqual("00:01:30", row[4])
        self.assertEqual("37.5%", row[6])

    def test_jobs_are_packed_into_aligned_multiline_columns(self) -> None:
        jobs = [
            {
                "shot_name": "SH010",
                "render_version": 1,
                "status": "queued",
                "progress": 0,
            },
            {
                "shot_name": "SH020",
                "render_version": 2,
                "worker": "node-2",
                "status": "rendering",
                "progress": 50,
            },
        ]

        columns = self.viewer.job_columns(jobs, now=self.now)

        self.assertEqual(set(self.viewer.JOB_FIELDS), set(columns))
        self.assertEqual("SH010_v001\nSH020_v002", columns["JobName"])
        self.assertEqual("\nnode-2", columns["Worker"])
        self.assertEqual("Queued\nRendering", columns["Status"])
        self.assertTrue(all(value.count("\n") == 1 for value in columns.values()))

    def test_job_rich_columns_match_manager_status_aliases_and_colors(self) -> None:
        jobs = [
            {"job_name": "queued<&>", "status": "pending"},
            {"job_name": "rendering", "status": "active"},
            {"job_name": "complete", "status": "success"},
            {"job_name": "failed", "status": "error"},
            {"job_name": "unknown", "status": "cancelled"},
        ]

        columns = self.viewer.job_rich_columns(jobs, now=self.now)

        self.assertEqual(
            "<queued>queued&lt;&amp;&gt;</>\n"
            "<rendering>rendering</>\n"
            "<done>complete</>\n"
            "<failed>failed</>\n"
            "unknown",
            columns["JobName"],
        )
        self.assertTrue(
            all(value.count("\n") == len(jobs) - 1 for value in columns.values())
        )

    def test_job_status_style_matches_standalone_colors(self) -> None:
        self.assertEqual(
            {
                "queued": "#d6d7d9",
                "rendering": "#74d680",
                "done": "#70aee8",
                "failed": "#ff7777",
            },
            self.viewer.JOB_STATUS_STYLE_COLORS,
        )

    def test_job_sort_defaults_match_standalone_manager(self) -> None:
        self.assertEqual(
            {"Time", "Errors", "Progress", "Submitted", "Completed"},
            set(self.viewer.JOB_SORT_DEFAULT_DESCENDING),
        )
        self.assertEqual("Submitted", self.viewer.JOB_DEFAULT_SORT_FIELD)
        self.assertTrue(self.viewer.JOB_DEFAULT_SORT_DESCENDING)

    def test_jobs_sort_case_insensitively_with_blanks_always_last(self) -> None:
        jobs = [
            {"job_id": "blank", "submitted_user": ""},
            {"job_id": "zed", "submitted_user": "Zed"},
            {"job_id": "ana", "submitted_user": "ana"},
        ]

        ascending = self.viewer.sort_jobs(jobs, "User")
        descending = self.viewer.sort_jobs(jobs, "User", descending=True)

        self.assertEqual(["ana", "zed", "blank"], [job["job_id"] for job in ascending])
        self.assertEqual(["zed", "ana", "blank"], [job["job_id"] for job in descending])

    def test_jobs_sort_timestamps_and_running_duration_numerically(self) -> None:
        jobs = [
            {
                "job_id": "short",
                "status": "rendering",
                "render_started_utc": "2026-08-25T19:59:00Z",
                "render_finished_utc": "",
            },
            {
                "job_id": "long",
                "status": "done",
                "render_started_utc": "2026-08-25T19:50:00Z",
                "render_finished_utc": "2026-08-25T19:55:00Z",
            },
            {"job_id": "blank", "status": "queued"},
        ]

        result = self.viewer.sort_jobs(jobs, "Time", descending=True, now=self.now)

        self.assertEqual(["long", "short", "blank"], [job["job_id"] for job in result])

    def test_worker_row_marks_stale_and_matches_manager_columns(self) -> None:
        row = self.viewer.worker_row(
            {
                "worker_name": "node-1",
                "project": "ironwidow",
                "status": "rendering",
                "last_heartbeat_utc": "2026-08-25T19:55:00Z",
                "worker_git_commit": "1234567890abcdef",
            },
            now=self.now,
        )
        self.assertEqual(6, len(row))
        self.assertEqual("Stale", row[2])
        self.assertEqual("5 min ago", row[4])
        self.assertEqual("12345678", row[5])

    def test_workers_are_packed_into_aligned_multiline_columns(self) -> None:
        workers = [
            {
                "worker_name": "node-1",
                "project": "ironwidow",
                "status": "waiting",
                "last_heartbeat_utc": "2026-08-25T19:59:30Z",
                "worker_git_commit": "11111111aaaaaaaa",
            },
            {
                "worker_name": "node-2",
                "project": "ironwidow",
                "status": "rendering",
                "shot_name": "SH020",
                "render_version": "v002",
                "last_heartbeat_utc": "2026-08-25T19:59:00Z",
                "worker_git_commit": "22222222bbbbbbbb",
            },
        ]

        columns = self.viewer.worker_columns(workers, now=self.now)

        self.assertEqual(set(self.viewer.WORKER_FIELDS), set(columns))
        self.assertEqual("node-1\nnode-2", columns["WorkerName"])
        self.assertEqual("Waiting\nRendering", columns["Status"])
        self.assertEqual("—\nSH020 v002", columns["CurrentJob"])
        self.assertTrue(all(value.count("\n") == 1 for value in columns.values()))

    def test_worker_rich_columns_match_manager_status_color_precedence(self) -> None:
        workers = [
            {
                "worker_name": "rendering<&>",
                "status": "rendering",
                "last_heartbeat_utc": "2026-08-25T19:59:30Z",
            },
            {
                "worker_name": "waiting",
                "status": "waiting",
                "last_heartbeat_utc": "2026-08-25T19:59:30Z",
            },
            {
                "worker_name": "stopping",
                "status": "rendering",
                "stop_requested": True,
                "last_heartbeat_utc": "2026-08-25T19:59:30Z",
            },
            {
                "worker_name": "stale",
                "status": "rendering",
                "stop_requested": True,
                "last_heartbeat_utc": "2026-08-25T19:55:00Z",
            },
        ]

        columns = self.viewer.worker_rich_columns(workers, now=self.now)

        self.assertEqual(
            "<rendering>rendering&lt;&amp;&gt;</>\n"
            "<waiting>waiting</>\n"
            "<stopping>stopping</>\n"
            "<stale>stale</>",
            columns["WorkerName"],
        )
        self.assertTrue(
            all(value.count("\n") == len(workers) - 1 for value in columns.values())
        )

    def test_worker_status_style_matches_standalone_colors(self) -> None:
        self.assertEqual(
            {
                "waiting": "#74d680",
                "rendering": "#74d680",
                "stopping": "#e6c56c",
                "stale": "#ff7777",
            },
            self.viewer.WORKER_STATUS_STYLE_COLORS,
        )

    def test_raw_d1_worker_is_normalized_like_the_manager(self) -> None:
        workers = self.viewer.normalize_workers(
            [
                {
                    "id": "worker-1",
                    "display_name": "NODE-01",
                    "status": "rendering",
                    "current_job_id": "job-1",
                    "last_seen_at": "2026-08-25T19:59:30Z",
                    "capabilities_json": json.dumps(
                        {
                            "project": "ironwidow",
                            "git_branch": "main",
                            "git_commit": "abcdef0123456789",
                        }
                    ),
                }
            ],
            [
                {
                    "job_id": "job-1",
                    "project": "ironwidow",
                    "shot_name": "SH020",
                    "render_version": 7,
                    "render_config": "/Game/MRG/Final.Final",
                }
            ],
            now=self.now,
        )
        self.assertEqual(1, len(workers))
        self.assertEqual("worker-1", workers[0]["worker_name"])
        self.assertEqual("NODE-01", workers[0]["machine_name"])
        self.assertEqual("SH020", workers[0]["shot_name"])
        self.assertEqual("v007", workers[0]["render_version"])
        self.assertFalse(workers[0]["stale"])
        self.assertEqual(
            ("worker-1", "ironwidow", "Rendering", "SH020 v007", "30 sec ago", "abcdef01"),
            self.viewer.worker_row(workers[0], now=self.now),
        )

class DesignerWidgetBoundaryTests(unittest.TestCase):
    def test_designer_widget_contracts_are_separate_assets(self) -> None:
        viewer = load_viewer()
        self.assertEqual(
            {
                "jobs_table",
                "workers_table",
            },
            set(viewer.DESIGNER_WIDGET_PATHS),
        )

    def test_controller_only_assigns_data_to_designer_widget(self) -> None:
        viewer = load_viewer()
        widget = FakeDesignerWidget()

        viewer.RenderFarmViewerController._set_widget_data(
            widget,
            {"Status": "Rendering", "Progress": 42},
        )

        self.assertEqual(
            {"Status": "Rendering", "Progress": "42"}, widget.properties
        )

    def test_controller_contains_no_layout_construction_or_sizing(self) -> None:
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        for forbidden in (
            "unreal.TextBlock",
            "unreal.Button",
            "unreal.ScaleBox",
            "SlateChildSize",
            "set_stretch",
            "set_visibility",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
