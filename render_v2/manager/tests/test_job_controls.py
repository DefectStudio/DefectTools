from __future__ import annotations

from dataclasses import replace
from io import BytesIO
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch
from urllib.error import URLError
from uuid import UUID

from portable_pipe_tools.apps.farm_render_manager_app import FarmRenderManagerApp
from portable_pipe_tools.render_farm.cloud_dispatch import (
    DispatcherClient,
    DispatcherConnection,
    DispatcherError,
)
from portable_pipe_tools.render_farm.cloud_manager import _render_job_from_cloud_payload
from portable_pipe_tools.render_farm.manage_render_jobs import control_cloud_render_job
from portable_pipe_tools.render_farm.manager_settings import save_auto_refresh_enabled


APP_MODULE = "portable_pipe_tools.apps.farm_render_manager_app."
DISPATCH_MODULE = "portable_pipe_tools.render_farm.cloud_dispatch."


def cloud_job(status: str = "rendering", *, job_id: str = "job/with space"):
    return _render_job_from_cloud_payload(
        {
            "job_id": job_id,
            "project": "show",
            "shot_name": "SHOT_020",
            "render_version": 3,
            "status": status,
            "attempt": 2,
            "revision": 99,
            "blacklisted_workers": ["OLD-WORKER"],
        },
        Path("D:/AICache/render-manager-requeue-clear-blacklist/manager-tests/jobs"),
    )


class JobControlClientTests(unittest.TestCase):
    def test_actions_encode_job_id_and_keep_one_request_id_across_transport_retry(self):
        for action in ("stop", "requeue"):
            with self.subTest(action=action):
                client = DispatcherClient(
                    DispatcherConnection("https://dispatcher.example.test", "manager", "token"),
                    retry_delays_seconds=(0,),
                )
                with patch(
                    DISPATCH_MODULE + "urlopen",
                    side_effect=[URLError("reply lost"), BytesIO(b'{"ok": true}')],
                ) as transport:
                    result = getattr(client, action + "_job")(
                        "job/with space", expected_attempt=2, expected_status="rendering"
                    )
                self.assertEqual({"ok": True}, result)
                self.assertEqual(2, transport.call_count)
                first, retried = [entry.args[0] for entry in transport.call_args_list]
                self.assertEqual(
                    "https://dispatcher.example.test/api/v1/jobs/job%2Fwith%20space/" + action,
                    first.full_url,
                )
                self.assertEqual("POST", first.method)
                self.assertEqual(first.data, retried.data)
                body = json.loads(first.data)
                self.assertEqual(2, body["expected_attempt"])
                self.assertEqual("rendering", body["expected_status"])
                self.assertEqual(4, UUID(body["request_id"]).version)

    def test_caller_can_replay_explicit_request_id(self):
        client = DispatcherClient(
            DispatcherConnection("https://dispatcher.example.test", "manager", "token")
        )
        with patch.object(client, "_request", return_value={"ok": True}) as request:
            client.requeue_job(
                "job", expected_attempt=3, expected_status="canceled", request_id="stable-id"
            )
        self.assertEqual("stable-id", request.call_args.kwargs["body"]["request_id"])


class JobControlHelperTests(unittest.TestCase):
    def test_actions_send_selected_attempt_and_status_without_revision(self):
        dispatcher = Mock()
        for action, status in (("stop", "rendering"), ("requeue", "canceled")):
            with self.subTest(action=action):
                selected = cloud_job(status)
                result = control_cloud_render_job(selected, dispatcher, action=action)
                operation = getattr(dispatcher, action + "_job")
                operation.assert_called_once_with(
                    selected.job_id, expected_attempt=2, expected_status=status
                )
                self.assertIs(result, operation.return_value)

    def test_rejects_invalid_or_noncloud_selection_before_mutating(self):
        selected = cloud_job()
        cases = [
            (replace(selected, control_source="filesystem"), "stop"),
            (cloud_job("complete"), "requeue"),
            (cloud_job("canceled"), "stop"),
            (selected, "delete"),
        ]
        for job, action in cases:
            with self.subTest(status=job.status, source=job.control_source, action=action):
                dispatcher = Mock()
                with self.assertRaises(ValueError):
                    control_cloud_render_job(job, dispatcher, action=action)
                self.assertEqual([], dispatcher.mock_calls)

    def test_requires_manager_connection_and_valid_attempt(self):
        with self.assertRaises(DispatcherError) as error:
            control_cloud_render_job(cloud_job(), None, action="stop")
        self.assertEqual("dispatcher_not_configured", error.exception.code)
        for value in (None, -1, True, "2"):
            with self.subTest(attempt=value):
                dispatcher = Mock()
                job = cloud_job()
                job.job_data["attempt"] = value
                with self.assertRaises(ValueError):
                    control_cloud_render_job(job, dispatcher, action="stop")
                self.assertEqual([], dispatcher.mock_calls)

    def test_stale_selection_conflict_is_preserved(self):
        dispatcher = Mock()
        stale = DispatcherError("Refresh the Manager", status=409, code="job_changed")
        dispatcher.stop_job.side_effect = stale
        with self.assertRaises(DispatcherError) as error:
            control_cloud_render_job(cloud_job(), dispatcher, action="stop")
        self.assertIs(stale, error.exception)


class JobControlMenuTests(unittest.TestCase):
    def test_real_context_menu_disables_ineligible_and_readonly_selections(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Path(directory) / "manager.json"
            save_auto_refresh_enabled(False, settings)
            with patch(APP_MODULE + "load_dispatcher_connection", return_value=None):
                app = FarmRenderManagerApp(settings_path=settings, prompt_on_startup=False)
            app.root.withdraw()
            try:
                self.assertEqual(
                    "Stop Job", app.job_context_menu.entrycget(app._stop_job_menu_index, "label")
                )
                self.assertEqual(
                    "Requeue Job", app.job_context_menu.entrycget(app._requeue_job_menu_index, "label")
                )
                app.job_tree.identify_row = Mock(return_value="first")
                app.job_context_menu.tk_popup = Mock()
                app.job_context_menu.grab_release = Mock()
                app.job_tree.insert("", "end", iid="first")
                app.job_tree.insert("", "end", iid="second")
                event = SimpleNamespace(y=30, x_root=0, y_root=0)
                for statuses, writable, expected in (
                    (("queued",), True, ("normal", "normal")),
                    (("rendering",), True, ("normal", "normal")),
                    (("canceled",), True, ("disabled", "normal")),
                    (("failed",), True, ("disabled", "normal")),
                    (("complete",), True, ("disabled", "disabled")),
                    (("rendering", "canceled"), True, ("disabled", "normal")),
                    (("rendering",), False, ("disabled", "disabled")),
                ):
                    with self.subTest(statuses=statuses, writable=writable):
                        ids = ("first", "second")[:len(statuses)]
                        app._jobs_by_item = {
                            item: cloud_job(status) for item, status in zip(ids, statuses)
                        }
                        app.job_tree.selection_set(ids)
                        app.dispatcher_client = Mock() if writable else None
                        self.assertEqual("break", app._show_job_context_menu(event))
                        actual = tuple(
                            app.job_context_menu.entrycget(index, "state")
                            for index in (app._stop_job_menu_index, app._requeue_job_menu_index)
                        )
                        self.assertEqual(expected, actual)
                app._jobs_by_item = {
                    "first": replace(cloud_job(), control_source="filesystem")
                }
                app.job_tree.selection_set("first")
                app.dispatcher_client = Mock()
                app._show_job_context_menu(event)
                self.assertEqual(
                    "disabled", app.job_context_menu.entrycget(app._stop_job_menu_index, "state")
                )
            finally:
                app._on_close()


class JobControlActionTests(unittest.TestCase):
    def make_app(self, jobs):
        app = FarmRenderManagerApp.__new__(FarmRenderManagerApp)
        app._selected_jobs = Mock(return_value=jobs)
        app.dispatcher_client = Mock()
        app.root = Mock()
        app.status_var = Mock()
        app.auto_refresh_worker = Mock(running=True)
        app.auto_refresh_var = Mock()
        app.auto_refresh_var.get.return_value = True
        app._refresh_jobs = Mock()
        return app

    def test_declining_confirmation_does_not_change_jobs_or_refresh(self):
        app = self.make_app([cloud_job()])
        with (
            patch(APP_MODULE + "messagebox.askyesno", return_value=False) as confirm,
            patch(APP_MODULE + "control_cloud_render_job") as control,
        ):
            app._stop_selected_jobs()
        self.assertIn("Every currently active farm worker", confirm.call_args.args[1])
        control.assert_not_called()
        app.auto_refresh_worker.stop.assert_not_called()
        app._refresh_jobs.assert_not_called()

    def test_requeue_confirmation_explains_clear_blacklist_and_worker_eligibility(self):
        app = self.make_app([cloud_job("canceled")])
        with (
            patch(APP_MODULE + "messagebox.askyesno", return_value=False) as confirm,
            patch(APP_MODULE + "control_cloud_render_job") as control,
        ):
            app._requeue_selected_jobs()
        title, prompt = confirm.call_args.args
        self.assertEqual("Requeue Job", title)
        self.assertIn("black list", prompt.lower())
        self.assertIn("clear", prompt.lower())
        self.assertIn("any eligible worker", prompt.lower())
        self.assertNotIn("Every currently active farm worker", prompt)
        self.assertNotIn("until you use Clear Black List", prompt)
        self.assertIn("continue listening", prompt)
        control.assert_not_called()

    def test_success_status_describes_each_actions_blacklist_effect(self):
        for action in ("stop", "requeue"):
            with self.subTest(action=action):
                app = self.make_app([cloud_job()])
                with (
                    patch(APP_MODULE + "messagebox.askyesno", return_value=True),
                    patch(APP_MODULE + "control_cloud_render_job") as control,
                ):
                    app._control_selected_jobs(action=action)
                control.assert_called_once_with(
                    app._selected_jobs.return_value[0], app.dispatcher_client, action=action
                )
                status = app.status_var.set.call_args.args[0]
                if action == "stop":
                    self.assertIn("Stopped 1", status)
                    self.assertIn("all active farm workers blacklisted", status)
                    self.assertNotIn("black lists cleared", status)
                else:
                    self.assertIn("Requeued 1", status)
                    self.assertIn("black lists cleared", status)
                    self.assertNotIn("workers blacklisted", status)

    def test_failed_actions_do_not_claim_blacklist_was_changed(self):
        for action in ("stop", "requeue"):
            with self.subTest(action=action):
                app = self.make_app([cloud_job()])
                with (
                    patch(APP_MODULE + "messagebox.askyesno", return_value=True),
                    patch(APP_MODULE + "messagebox.showerror"),
                    patch(
                        APP_MODULE + "control_cloud_render_job",
                        side_effect=DispatcherError("Job changed; refresh", status=409),
                    ),
                ):
                    app._control_selected_jobs(action=action)
                status = app.status_var.set.call_args.args[0]
                self.assertIn("0 render job", status)
                self.assertIn("1 error", status)
                self.assertNotIn("workers blacklisted", status)
                self.assertNotIn("black lists cleared", status)

    def test_partial_failure_refreshes_and_restores_automatic_refresh(self):
        first = cloud_job(job_id="first")
        second = cloud_job(job_id="second")
        app = self.make_app([first, second])
        order = Mock()
        order.attach_mock(app.auto_refresh_worker.stop, "pause")
        order.attach_mock(app._refresh_jobs, "refresh")
        order.attach_mock(app.auto_refresh_worker.start, "resume")
        with (
            patch(APP_MODULE + "messagebox.askyesno", return_value=True),
            patch(APP_MODULE + "messagebox.showerror") as show_error,
            patch(
                APP_MODULE + "control_cloud_render_job",
                side_effect=[DispatcherError("Job changed; refresh", status=409), {"ok": True}],
            ) as control,
        ):
            order.attach_mock(control, "control")
            app._requeue_selected_jobs()
        self.assertEqual(
            [
                call.pause(),
                call.control(first, app.dispatcher_client, action="requeue"),
                call.control(second, app.dispatcher_client, action="requeue"),
                call.refresh(),
                call.resume(),
            ],
            order.mock_calls,
        )
        self.assertIn("Job changed; refresh", show_error.call_args.args[1])
        self.assertIn("Requeued 1", app.status_var.set.call_args.args[0])
        self.assertIn("1 error", app.status_var.set.call_args.args[0])

    def test_refresh_exception_still_restores_automatic_refresh(self):
        app = self.make_app([cloud_job()])
        app._refresh_jobs.side_effect = RuntimeError("refresh failed")
        with (
            patch(APP_MODULE + "messagebox.askyesno", return_value=True),
            patch(APP_MODULE + "control_cloud_render_job"),
            self.assertRaisesRegex(RuntimeError, "refresh failed"),
        ):
            app._stop_selected_jobs()
        app.auto_refresh_worker.start.assert_called_once()

    def test_readonly_selection_reports_error_without_confirmation(self):
        app = self.make_app([cloud_job()])
        app.dispatcher_client = None
        with (
            patch(APP_MODULE + "messagebox.askyesno") as confirm,
            patch(APP_MODULE + "messagebox.showerror") as show_error,
            patch(APP_MODULE + "control_cloud_render_job") as control,
        ):
            app._stop_selected_jobs()
        show_error.assert_called_once()
        confirm.assert_not_called()
        control.assert_not_called()


if __name__ == "__main__":
    unittest.main()
