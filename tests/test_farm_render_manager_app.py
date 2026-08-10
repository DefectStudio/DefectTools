from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from portable_pipe_tools.apps.farm_render_manager_app import (
    FarmRenderManagerApp,
    JOB_COLUMNS,
    WORKER_COLUMNS,
)
from portable_pipe_tools.render_farm.manager_settings import (
    load_saved_auto_refresh_interval_minutes,
    save_auto_refresh_enabled,
    save_auto_refresh_interval_minutes,
)
from portable_pipe_tools.render_farm.queue import (
    create_queue_folders,
    utc_now,
    write_json_atomic,
)
from portable_pipe_tools.render_farm.workers import WorkerRecord


def _click_tree_heading(
    app: FarmRenderManagerApp,
    *,
    x: int,
) -> None:
    app.root.deiconify()
    app.root.update()
    if app.job_tree.identify_region(x, 5) != "heading":
        raise AssertionError("Test click coordinate is not over a tree heading")
    app.job_tree.event_generate("<ButtonPress-1>", x=x, y=5)
    app.job_tree.event_generate("<ButtonRelease-1>", x=x, y=5)
    app.root.update()


class FarmRenderManagerAppTests(unittest.TestCase):
    def test_job_name_is_the_leftmost_column(self) -> None:
        self.assertEqual("job_name", JOB_COLUMNS[0].key)
        self.assertEqual("Job Name", JOB_COLUMNS[0].heading)

    def test_worker_column_is_immediately_left_of_user(self) -> None:
        keys = [column.key for column in JOB_COLUMNS]
        worker_index = keys.index("worker")

        self.assertEqual("Worker", JOB_COLUMNS[worker_index].heading)
        self.assertEqual("user", keys[worker_index + 1])

    def test_worker_name_is_the_leftmost_worker_column(self) -> None:
        self.assertEqual("worker_name", WORKER_COLUMNS[0].key)
        self.assertEqual("Worker", WORKER_COLUMNS[0].heading)

    def test_worker_visual_status_prioritizes_stale_and_stop_requests(self) -> None:
        base_values = {
            "project": "show",
            "farm_root": Path("show/renderFarm"),
            "status_file": Path("WORKER_STATUS.json"),
            "stop_file": Path("WORKER_STOP.json"),
            "worker_name": "WORKER",
            "machine_name": "WORKER",
            "session_id": "session",
            "status": "rendering",
            "started_utc": "",
            "last_heartbeat_utc": "",
            "heartbeat_age_seconds": 2.0,
            "stop_requested": False,
            "current_job_id": "",
            "shot_name": "",
            "render_version": "",
            "render_setting": "",
            "worker_git_branch": "main",
            "worker_git_commit": "a" * 40,
            "process_id": 1,
            "raw_data": {},
        }
        rendering = WorkerRecord(stale=False, **base_values)
        stopping = WorkerRecord(
            stale=False,
            **{**base_values, "stop_requested": True},
        )
        stale = WorkerRecord(stale=True, **base_values)

        self.assertEqual("rendering", FarmRenderManagerApp._worker_status_tag(rendering))
        self.assertEqual("stopping", FarmRenderManagerApp._worker_status_tag(stopping))
        self.assertEqual("stale", FarmRenderManagerApp._worker_status_tag(stale))

    def test_statuses_map_to_the_expected_visual_groups(self) -> None:
        self.assertEqual("queued", FarmRenderManagerApp._status_tag("pending"))
        self.assertEqual(
            "rendering", FarmRenderManagerApp._status_tag("rendering")
        )
        self.assertEqual("done", FarmRenderManagerApp._status_tag("completed"))
        self.assertEqual("failed", FarmRenderManagerApp._status_tag("error"))

    def test_status_matching_ignores_case_and_whitespace(self) -> None:
        self.assertEqual(
            "rendering",
            FarmRenderManagerApp._status_tag("  RENDERING  "),
        )

    def test_refresh_interval_is_restored_and_saved_from_combobox(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "manager.json"
            save_auto_refresh_enabled(False, settings_path)
            save_auto_refresh_interval_minutes(5, settings_path)
            app = FarmRenderManagerApp(
                settings_path=settings_path,
                prompt_on_startup=False,
            )
            app.root.withdraw()

            try:
                self.assertEqual("5 minutes", app.auto_refresh_interval_var.get())
                self.assertEqual(300, app.auto_refresh_worker.interval_seconds)

                app.auto_refresh_interval_var.set("10 minutes")
                app._on_auto_refresh_interval_selected()

                self.assertEqual(600, app.auto_refresh_worker.interval_seconds)
                self.assertEqual(
                    10,
                    load_saved_auto_refresh_interval_minutes(settings_path),
                )
            finally:
                app._on_close()

    def test_refresh_restores_selected_job_after_queue_folder_move(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            settings_path = repository / "manager.json"
            save_auto_refresh_enabled(False, settings_path)
            paths = create_queue_folders(repository / "show" / "renderFarm")
            queued_folder = paths.needs_rendering / "job-package"
            queued_folder.mkdir()
            write_json_atomic(
                queued_folder / "job.json",
                {
                    "job_id": "stable-job-id",
                    "shot_name": "SHOT_010",
                    "render_version": 1,
                },
            )
            (queued_folder / "unreal.log").write_text(
                "Selected job render log",
                encoding="utf-8",
            )
            app = FarmRenderManagerApp(
                settings_path=settings_path,
                prompt_on_startup=False,
            )
            app.root.withdraw()

            try:
                app._set_repository_connected(repository)
                selected_item = app.job_tree.get_children()[0]
                app.job_tree.selection_set(selected_item)
                app._on_job_selected(None)

                detail_sections = app.job_detail_tree.get_children()
                self.assertEqual("General", app.job_detail_tree.item(
                    detail_sections[0], "text"
                ))
                general_details = {
                    app.job_detail_tree.item(item, "text"):
                    app.job_detail_tree.set(item, "value")
                    for item in app.job_detail_tree.get_children(
                        detail_sections[0]
                    )
                }
                self.assertEqual("stable-job-id", general_details["Job ID"])
                self.assertIn("properties", app.detail_count_var.get())

                queued_folder.rename(
                    paths.is_rendering / "job-package__WORKER-01"
                )
                app._refresh_jobs()

                restored_selection = app.job_tree.selection()
                self.assertEqual(1, len(restored_selection))
                restored_job = app._jobs_by_item[restored_selection[0]]
                self.assertEqual("stable-job-id", restored_job.job_id)
                self.assertEqual("rendering", restored_job.status)
                self.assertEqual(
                    "WORKER-01",
                    app.job_tree.set(restored_selection[0], "worker"),
                )
                self.assertEqual(
                    "Selected job render log",
                    app.log_text.get("1.0", "end-1c"),
                )

                app.last_update_var.set("Last update: --")
                app._on_manual_refresh_clicked()

                self.assertEqual("Refreshed  ✓", app.refresh_button.cget("text"))
                self.assertEqual(
                    "RefreshSuccess.TButton",
                    app.refresh_button.cget("style"),
                )
                self.assertNotEqual("Last update: --", app.last_update_var.get())
            finally:
                app._on_close()

    def test_workers_toggle_lists_heartbeats_and_creates_empty_stop_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            settings_path = repository / "manager.json"
            save_auto_refresh_enabled(False, settings_path)
            paths = create_queue_folders(repository / "show" / "renderFarm")
            write_json_atomic(
                paths.workers / "VENGEANCE_STATUS.json",
                {
                    "worker_name": "VENGEANCE",
                    "machine_name": "VENGEANCE",
                    "session_id": "vengeance-session",
                    "status": "rendering",
                    "last_heartbeat_utc": utc_now(),
                    "current_job_id": "job-1",
                    "shot_name": "JNG_000_0330",
                    "render_version": "v011",
                    "render_setting": "beauty_LowHDsRGB",
                },
            )
            app = FarmRenderManagerApp(
                settings_path=settings_path,
                prompt_on_startup=False,
            )
            app.root.withdraw()

            try:
                app._set_repository_connected(repository)
                self.assertEqual("Workers", app.view_toggle_button.cget("text"))

                app._toggle_list_view()

                self.assertEqual("Jobs", app.view_toggle_button.cget("text"))
                self.assertEqual("Workers", app.list_title_var.get())
                worker_items = app.worker_tree.get_children()
                self.assertEqual(1, len(worker_items))
                worker_item = worker_items[0]
                self.assertEqual(
                    "VENGEANCE",
                    app.worker_tree.set(worker_item, "worker_name"),
                )
                self.assertEqual(
                    "Rendering",
                    app.worker_tree.set(worker_item, "status"),
                )

                app.worker_tree.selection_set(worker_item)
                app._on_worker_selected(None)
                self.assertEqual(
                    "Worker Details - VENGEANCE",
                    app.details_title_var.get(),
                )

                with patch(
                    "portable_pipe_tools.apps.farm_render_manager_app."
                    "messagebox.askyesno",
                    return_value=True,
                ):
                    app._stop_selected_worker()

                stop_file = paths.workers / "VENGEANCE_STOP.json"
                self.assertTrue(stop_file.is_file())
                self.assertEqual(0, stop_file.stat().st_size)
                refreshed_item = app.worker_tree.get_children()[0]
                self.assertEqual(
                    "Stop Requested",
                    app.worker_tree.set(refreshed_item, "status"),
                )

                app._toggle_list_view()
                self.assertEqual("Workers", app.view_toggle_button.cget("text"))
                self.assertEqual("Jobs", app.list_title_var.get())
            finally:
                app._on_close()

    def test_delete_prompt_cancels_or_bulk_deletes_selected_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            settings_path = repository / "manager.json"
            save_auto_refresh_enabled(False, settings_path)
            paths = create_queue_folders(repository / "show" / "renderFarm")
            job_folders = []
            for index in range(3):
                destination = (
                    paths.render_failed
                    if index == 2
                    else paths.render_complete
                )
                job_folder = destination / f"job-package-{index}"
                job_folder.mkdir()
                write_json_atomic(
                    job_folder / "job.json",
                    {
                        "job_id": f"delete-test-{index}",
                        "shot_name": f"SHOT_02{index}",
                    },
                )
                job_folders.append(job_folder)
            app = FarmRenderManagerApp(
                settings_path=settings_path,
                prompt_on_startup=False,
            )
            app.root.withdraw()

            try:
                app._set_repository_connected(repository)
                _click_tree_heading(app, x=20)
                ascending_names = [
                    app._jobs_by_item[item].job_name
                    for item in app.job_tree.get_children()
                ]
                self.assertEqual(sorted(ascending_names), ascending_names)
                self.assertTrue(
                    app.job_tree.heading("job_name", "text").endswith("\u25b2")
                )

                _click_tree_heading(app, x=20)
                descending_names = [
                    app._jobs_by_item[item].job_name
                    for item in app.job_tree.get_children()
                ]
                self.assertEqual(
                    sorted(descending_names, reverse=True),
                    descending_names,
                )
                self.assertTrue(
                    app.job_tree.heading("job_name", "text").endswith("\u25bc")
                )

                selected_item = app.job_tree.get_children()[1]
                selected_job_id = app._jobs_by_item[selected_item].job_id
                app.job_tree.selection_set(selected_item)
                app._on_job_selected(None)
                app._sort_jobs_by_column("errors")
                first_item = app.job_tree.get_children()[0]
                self.assertEqual(1, app._jobs_by_item[first_item].error_count)
                restored_item = app.job_tree.selection()[0]
                self.assertEqual(
                    selected_job_id,
                    app._jobs_by_item[restored_item].job_id,
                )
                app._select_all_jobs()
                self.assertEqual(3, len(app.job_tree.selection()))
                self.assertIn("(+2 selected)", app.details_title_var.get())

                with patch(
                    "portable_pipe_tools.apps.farm_render_manager_app."
                    "messagebox.askyesno",
                    return_value=False,
                ) as confirmation:
                    app._delete_selected_jobs()

                self.assertTrue(all(folder.exists() for folder in job_folders))
                self.assertEqual("no", confirmation.call_args.kwargs["default"])
                self.assertIn("3 selected render jobs", confirmation.call_args.args[1])

                with patch(
                    "portable_pipe_tools.apps.farm_render_manager_app."
                    "messagebox.askyesno",
                    return_value=True,
                ):
                    app._delete_selected_jobs()

                self.assertTrue(all(not folder.exists() for folder in job_folders))
                self.assertEqual((), app.job_tree.get_children())
            finally:
                app._on_close()


if __name__ == "__main__":
    unittest.main()
