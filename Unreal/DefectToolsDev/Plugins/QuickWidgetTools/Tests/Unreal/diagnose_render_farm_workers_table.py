"""Trace worker data from the Python controller into the aggregate table's visuals."""

import unreal


VIEWER_PATH = "/QuickWidgetTools/EditorWidgets/WBP_09_Render_Farm_Viewer"
JOBS_TABLE_PATH = "/QuickWidgetTools/EditorWidgets/RenderFarm/WBP_RenderFarmJobsTable"
TABLE_PATH = "/QuickWidgetTools/EditorWidgets/RenderFarm/WBP_RenderFarmWorkersTable"
TEXT_NAMES = ("TextBlock",) + tuple(f"TextBlock_{index}" for index in range(16))
FIELDS = ("WorkerName", "Project", "Status", "CurrentJob", "LastSeen", "Commit")
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


def _log(message: str) -> None:
    unreal.log_warning(f"[WorkersTableDiagnostic] {message}")


def diagnose() -> None:
    table_asset = unreal.load_asset(TABLE_PATH)
    if not isinstance(table_asset, unreal.WidgetBlueprint):
        raise AssertionError(f"Missing table asset: {TABLE_PATH}")

    source_text_names = []
    for name in TEXT_NAMES:
        text = unreal.EditorUtilityLibrary.find_source_widget_by_name(table_asset, name)
        if isinstance(text, unreal.TextBlock):
            source_text_names.append(name)
            _log(
                f"source {name}: text={str(text.get_text())!r}, "
                f"visibility={text.get_visibility()}, opacity={text.get_render_opacity()}"
            )
    _log(f"source visible TextBlocks={source_text_names}")

    viewer_asset = unreal.load_asset(VIEWER_PATH)
    subsystem = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem)
    widget = subsystem.spawn_and_register_tab(viewer_asset)
    if widget is None:
        raise AssertionError("Could not spawn the Render Farm Viewer")

    import render_farm_viewer

    active = render_farm_viewer._ACTIVE_CONTROLLERS.pop(widget.get_path_name(), None)
    if active is not None:
        active.dispose()

    controller = render_farm_viewer.RenderFarmViewerController(widget)
    controller.jobs = [
        {
            "shot_name": "SH010",
            "render_version": 1,
            "status": "queued",
            "progress": 0,
        },
        {
            "shot_name": "SH020",
            "render_version": 2,
            "worker": "DIAGNOSTIC-NODE-B",
            "status": "rendering",
            "progress": 50,
        },
    ]
    controller.workers = [
        {
            "worker_name": "DIAGNOSTIC-NODE-A",
            "project": "diagnostic-project",
            "status": "waiting",
            "last_heartbeat_utc": "2099-01-01T00:00:00Z",
            "worker_git_commit": "12345678abcdef00",
        },
        {
            "worker_name": "DIAGNOSTIC-NODE-B",
            "project": "diagnostic-project",
            "status": "rendering",
            "shot_name": "SH999",
            "render_version": "v001",
            "last_heartbeat_utc": "2099-01-01T00:00:00Z",
            "worker_git_commit": "abcdef0012345678",
        },
    ]
    controller._set_mode("jobs")

    jobs_table_asset = unreal.load_asset(JOBS_TABLE_PATH)
    job_text_names = []
    for name in TEXT_NAMES:
        text = unreal.EditorUtilityLibrary.find_source_widget_by_name(
            jobs_table_asset,
            name,
        )
        if isinstance(text, unreal.TextBlock):
            job_text_names.append(name)
    jobs_table = controller.list_scroll.get_child_at(0)
    _log(f"jobs spawned class={jobs_table.get_class().get_name()}")
    for field in JOB_FIELDS:
        _log(f"jobs data {field}={str(jobs_table.get_editor_property(field))!r}")
    jobs_table.force_layout_prepass()
    for name in job_text_names:
        try:
            text = jobs_table.get_editor_property(name)
        except Exception:
            continue
        if isinstance(text, unreal.TextBlock):
            _log(f"jobs runtime {name}: text={str(text.get_text())!r}")

    controller._set_mode("workers")

    child_count = controller.list_scroll.get_children_count()
    _log(f"FarmViewerList children={child_count}")
    if child_count != 1:
        raise AssertionError(f"Expected one workers table, found {child_count}")

    table = controller.list_scroll.get_child_at(0)
    _log(f"spawned class={table.get_class().get_name()}")
    for field in FIELDS:
        _log(f"data {field}={str(table.get_editor_property(field))!r}")

    table.force_layout_prepass()
    runtime_text_names = []
    for name in source_text_names:
        try:
            text = table.get_editor_property(name)
        except Exception as error:
            _log(f"runtime {name}: unavailable ({error})")
            continue
        if not isinstance(text, unreal.TextBlock):
            _log(f"runtime {name}: property is {text!r}")
            continue
        runtime_text_names.append(name)
        _log(
            f"runtime {name}: text={str(text.get_text())!r}, "
            f"visibility={text.get_visibility()}, opacity={text.get_render_opacity()}, "
            f"desired_size={text.get_desired_size()}"
        )
    _log(f"runtime accessible TextBlocks={runtime_text_names}")

    controller.dispose()
    tab_id = subsystem.get_tab_id_from_blueprint(viewer_asset)
    if tab_id:
        subsystem.close_tab_by_id(tab_id)


try:
    diagnose()
except Exception as error:
    unreal.log_error(f"[WorkersTableDiagnostic] FAIL: {error}")
    unreal.SystemLibrary.quit_editor()
    raise
else:
    _log("PASS")
    unreal.SystemLibrary.quit_editor()
