"""Unreal commandlet smoke test for the Render Farm Viewer Editor Utility Widget."""

import unreal


ASSET_PATH = "/QuickWidgetTools/EditorWidgets/WBP_09_Render_Farm_Viewer"
RUNTIME_TEST = "-RenderFarmViewerRuntimeTest" in unreal.SystemLibrary.get_command_line()
DESIGNER_CONTRACTS = {
    "/QuickWidgetTools/EditorWidgets/RenderFarm/WBP_RenderFarmJobsTable": ("JobName", "Status"),
    "/QuickWidgetTools/EditorWidgets/RenderFarm/WBP_RenderFarmWorkersTable": ("WorkerName", "Status"),
}
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
JOB_SORT_BUTTONS = {
    field: f"{field}SortButton" for field in JOB_RICH_TEXT_WIDGETS
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
JOB_SORT_LABEL_FONT_SCALE = 0.70
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
JOB_STYLE_TABLE_PATH = (
    "/QuickWidgetTools/EditorWidgets/RenderFarm/DT_RenderFarmJobStatusStyles"
)
WORKER_STYLE_TABLE_PATH = (
    "/QuickWidgetTools/EditorWidgets/RenderFarm/DT_RenderFarmWorkerStatusStyles"
)


def verify() -> None:
    asset = unreal.load_asset(ASSET_PATH)
    if asset is None:
        raise AssertionError(f"Viewer asset was not found: {ASSET_PATH}")

    events = unreal.BlueprintEditorLibrary.list_events(asset)
    construct = next((event for event in events if str(event.name) == "Construct"), None)
    if construct is None or not construct.is_implemented:
        raise AssertionError("The viewer widget must implement Construct")

    generated_class = asset.generated_class()
    if generated_class is None:
        raise AssertionError("The viewer widget did not compile a generated class")

    default_object = unreal.get_default_object(generated_class)
    try:
        default_object.get_editor_property("FarmViewerRoot")
    except Exception as error:
        raise AssertionError("FarmViewerRoot is not a generated widget variable") from error

    for designer_path, fields in DESIGNER_CONTRACTS.items():
        designer_asset = unreal.load_asset(designer_path)
        if designer_asset is None or designer_asset.generated_class() is None:
            raise AssertionError(f"Designer widget is missing: {designer_path}")
        designer_default = unreal.get_default_object(designer_asset.generated_class())
        for field in fields:
            try:
                designer_default.get_editor_property(field)
            except Exception as error:
                raise AssertionError(
                    f"Designer widget {designer_path} is missing Data field {field}"
                ) from error

        if designer_path.endswith("WBP_RenderFarmJobsTable"):
            reference_button = unreal.EditorUtilityLibrary.find_source_widget_by_name(
                asset,
                "FarmViewerRefreshButton",
            )
            if not isinstance(reference_button, unreal.Button):
                raise AssertionError("The Refresh style reference button is missing")
            reference_label = reference_button.get_child_at(0)
            if not isinstance(reference_label, unreal.TextBlock):
                raise AssertionError("The Refresh button label is missing")
            expected_sort_font = reference_label.get_editor_property("font").copy()
            reference_font_size = float(
                expected_sort_font.get_editor_property("size")
            )
            expected_sort_font.set_editor_property(
                "size",
                max(1.0, reference_font_size * JOB_SORT_LABEL_FONT_SCALE),
            )
            style_table = unreal.load_asset(JOB_STYLE_TABLE_PATH)
            if not isinstance(style_table, unreal.DataTable):
                raise AssertionError("The job RichText style table is missing")
            style_rows = {
                str(name)
                for name in unreal.DataTableFunctionLibrary.get_data_table_row_names(
                    style_table
                )
            }
            if style_rows != {"queued", "rendering", "done", "failed"}:
                raise AssertionError(f"Unexpected job RichText styles: {style_rows}")
            for widget_name in JOB_RICH_TEXT_WIDGETS.values():
                rich_text = unreal.EditorUtilityLibrary.find_source_widget_by_name(
                    designer_asset,
                    widget_name,
                )
                if not isinstance(rich_text, unreal.RichTextBlock):
                    raise AssertionError(f"Missing job RichText column {widget_name}")
                if rich_text.get_editor_property("text_style_set") != style_table:
                    raise AssertionError(f"{widget_name} does not use the job style table")
            for field, button_name in JOB_SORT_BUTTONS.items():
                button = unreal.EditorUtilityLibrary.find_source_widget_by_name(
                    designer_asset,
                    button_name,
                )
                label = unreal.EditorUtilityLibrary.find_source_widget_by_name(
                    designer_asset,
                    f"{field}SortLabel",
                )
                rich_text = unreal.EditorUtilityLibrary.find_source_widget_by_name(
                    designer_asset,
                    JOB_RICH_TEXT_WIDGETS[field],
                )
                if not isinstance(button, unreal.Button):
                    raise AssertionError(f"Missing job sort button {button_name}")
                if not isinstance(label, unreal.TextBlock):
                    raise AssertionError(f"Missing job sort label {field}SortLabel")
                if str(label.get_text()) != JOB_SORT_HEADINGS[field]:
                    raise AssertionError(f"Unexpected heading text for {button_name}")
                if button.get_parent() != rich_text.get_parent():
                    raise AssertionError(
                        f"{button_name} must share a column with "
                        f"{JOB_RICH_TEXT_WIDGETS[field]}"
                    )
                if button.get_editor_property("widget_style").export_text() != (
                    reference_button.get_editor_property("widget_style").export_text()
                ):
                    raise AssertionError(f"{button_name} does not match Refresh style")
                if label.get_editor_property("font").export_text() != (
                    expected_sort_font.export_text()
                ):
                    raise AssertionError(
                        f"{button_name} does not use scaled Refresh typography"
                    )
                if label.get_editor_property("color_and_opacity").export_text() != (
                    reference_label.get_editor_property(
                        "color_and_opacity"
                    ).export_text()
                ):
                    raise AssertionError(f"{button_name} does not match Refresh text color")

        if designer_path.endswith("WBP_RenderFarmWorkersTable"):
            style_table = unreal.load_asset(WORKER_STYLE_TABLE_PATH)
            if not isinstance(style_table, unreal.DataTable):
                raise AssertionError("The worker RichText style table is missing")
            style_rows = {
                str(name)
                for name in unreal.DataTableFunctionLibrary.get_data_table_row_names(
                    style_table
                )
            }
            if style_rows != {"waiting", "rendering", "stopping", "stale"}:
                raise AssertionError(f"Unexpected worker RichText styles: {style_rows}")
            for widget_name in WORKER_RICH_TEXT_WIDGETS.values():
                rich_text = unreal.EditorUtilityLibrary.find_source_widget_by_name(
                    designer_asset,
                    widget_name,
                )
                if not isinstance(rich_text, unreal.RichTextBlock):
                    raise AssertionError(f"Missing worker RichText column {widget_name}")
                if rich_text.get_editor_property("text_style_set") != style_table:
                    raise AssertionError(f"{widget_name} does not use the worker style table")

    subsystem = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem)
    widget = subsystem.spawn_and_register_tab(asset)
    if widget is None:
        if RUNTIME_TEST:
            raise AssertionError("Unreal could not spawn the viewer tab")
        unreal.log_warning(
            "[RenderFarmViewerWidgetTest] Static checks passed; "
            "tab spawn is unavailable in commandlet mode"
        )
        return

    import render_farm_viewer

    if render_farm_viewer.run() != "true":
        raise AssertionError("The Python viewer did not attach")

    controller = render_farm_viewer._ACTIVE_CONTROLLERS.get(widget.get_path_name())
    if controller is None:
        raise AssertionError("The spawned widget has no read-only viewer controller")

    root = widget.get_editor_property("FarmViewerRoot")
    if root is None or root.get_children_count() < 5:
        raise AssertionError("The Blueprint-owned UMG shell is incomplete")

    for variable_name in ("FarmViewerList",):
        panel = widget.get_editor_property(variable_name)
        if not isinstance(panel, unreal.VerticalBox):
            raise AssertionError(f"{variable_name} must be a designer-owned VerticalBox")
        if not isinstance(panel.get_parent(), unreal.ScrollBox):
            raise AssertionError(f"{variable_name} must be inside a ScrollBox")
        panel_slot = panel.get_editor_property("slot")
        if not isinstance(panel_slot, unreal.ScrollBoxSlot):
            raise AssertionError(f"{variable_name} must have a ScrollBoxSlot")
        if (
            panel_slot.get_editor_property("horizontal_alignment")
            != unreal.HorizontalAlignment.H_ALIGN_FILL
        ):
            raise AssertionError(f"{variable_name} must fill the ScrollBox width")

    try:
        widget.get_editor_property("FarmViewerDetails")
    except Exception:
        pass
    else:
        raise AssertionError("The list-only viewer must not expose FarmViewerDetails")

    controller.jobs = [
        {
            "job_id": "job-beta",
            "job_name": "Beta",
            "status": "queued",
            "progress": 0,
            "submitted_utc": "2026-08-25T20:00:00Z",
        },
        {
            "job_id": "job-alpha",
            "job_name": "Alpha",
            "status": "queued",
            "progress": 0,
            "submitted_utc": "2026-08-25T19:00:00Z",
        },
        {
            "job_id": "job-gamma",
            "job_name": "Gamma",
            "status": "queued",
            "progress": 0,
            "submitted_utc": "2026-08-25T21:00:00Z",
        },
    ]
    controller.workers = render_farm_viewer.normalize_workers(
        [
            {
                "id": "smoke-worker",
                "display_name": "SMOKE-NODE",
                "status": "waiting",
                "last_seen_at": "2099-01-01T00:00:00Z",
                "capabilities_json": '{"project":"smoke"}',
            }
        ],
        controller.jobs,
    )
    controller._set_mode("jobs")
    if controller.list_scroll.get_children_count() != 1:
        raise AssertionError("The viewer must render jobs as one aggregate table widget")
    if (
        controller.list_scroll.get_child_at(0).get_class()
        != controller.designer_classes["jobs_table"]
    ):
        raise AssertionError("Jobs must render through WBP_RenderFarmJobsTable")
    jobs_table = controller.list_scroll.get_child_at(0)
    expected_initial_jobs = render_farm_viewer.sort_jobs(
        controller.jobs,
        "Submitted",
        descending=True,
    )
    expected_job_markup = render_farm_viewer.job_rich_columns(expected_initial_jobs)
    if str(jobs_table.get_editor_property("JobName")) != "Gamma\nBeta\nAlpha":
        raise AssertionError("Jobs must initially show newest submissions first")
    for property_name, widget_name in JOB_RICH_TEXT_WIDGETS.items():
        rich_text = jobs_table.get_editor_property(widget_name)
        if not isinstance(rich_text, unreal.RichTextBlock):
            raise AssertionError(f"Runtime table is missing {widget_name}")
        expected_markup = expected_job_markup[property_name]
        actual_markup = str(rich_text.get_text())
        if actual_markup != expected_markup:
            raise AssertionError(
                f"{widget_name} did not receive queued job markup: "
                f"expected {expected_markup!r}, got {actual_markup!r}"
            )
    if len(controller._job_sort_callbacks) != len(JOB_SORT_BUTTONS):
        raise AssertionError("Every job header must register one sort callback")
    for field, button_name in JOB_SORT_BUTTONS.items():
        button = jobs_table.get_editor_property(button_name)
        if not isinstance(button, unreal.Button):
            raise AssertionError(f"Runtime table is missing {button_name}")
        label = button.get_child_at(0)
        if not isinstance(label, unreal.TextBlock):
            raise AssertionError(f"{button_name} is missing its label")
        expected_heading = JOB_SORT_HEADINGS[field]
        if field == "Submitted":
            expected_heading += " ▼"
        if str(label.get_text()) != expected_heading:
            raise AssertionError(f"{button_name} starts with an unexpected marker")

    controller._job_sort_callbacks[0]()
    jobs_table = controller.list_scroll.get_child_at(0)
    if str(jobs_table.get_editor_property("JobName")) != "Alpha\nBeta\nGamma":
        raise AssertionError("The first Job Name click must sort ascending")
    job_name_button = jobs_table.get_editor_property("JobNameSortButton")
    if str(job_name_button.get_child_at(0).get_text()) != "Job Name ▲":
        raise AssertionError("Ascending Job Name sort marker is missing")

    controller._job_sort_callbacks[0]()
    jobs_table = controller.list_scroll.get_child_at(0)
    if str(jobs_table.get_editor_property("JobName")) != "Gamma\nBeta\nAlpha":
        raise AssertionError("The second Job Name click must sort descending")
    job_name_button = jobs_table.get_editor_property("JobNameSortButton")
    if str(job_name_button.get_child_at(0).get_text()) != "Job Name ▼":
        raise AssertionError("Descending Job Name sort marker is missing")
    controller._set_mode("workers")
    if controller.list_scroll.get_children_count() != 1:
        raise AssertionError("The viewer must render workers as one aggregate table widget")
    workers_table = controller.list_scroll.get_child_at(0)
    if workers_table.get_class() != controller.designer_classes["workers_table"]:
        raise AssertionError("Workers must render through WBP_RenderFarmWorkersTable")
    expected_worker_table_data = {
        "WorkerName": "smoke-worker",
        "Project": "smoke",
        "Status": "Waiting",
        "CurrentJob": "—",
        "LastSeen": "0 sec ago",
        "Commit": "Unknown",
    }
    for property_name, expected_value in expected_worker_table_data.items():
        actual_value = str(workers_table.get_editor_property(property_name))
        if actual_value != expected_value:
            raise AssertionError(
                f"The aggregate workers table did not receive {property_name} data: "
                f"expected {expected_value!r}, got {actual_value!r}"
            )
        rich_text = workers_table.get_editor_property(
            WORKER_RICH_TEXT_PROPERTIES[property_name]
        )
        if not isinstance(rich_text, unreal.RichTextBlock):
            raise AssertionError(
                f"Runtime table is missing {WORKER_RICH_TEXT_WIDGETS[property_name]}"
            )
        expected_markup = f"<waiting>{expected_value}</>"
        actual_markup = str(rich_text.get_text())
        if actual_markup != expected_markup:
            raise AssertionError(
                f"{WORKER_RICH_TEXT_WIDGETS[property_name]} did not receive status markup: "
                f"expected {expected_markup!r}, got {actual_markup!r}"
            )
    worker_slot = workers_table.get_editor_property("slot")
    if not isinstance(worker_slot, unreal.VerticalBoxSlot):
        raise AssertionError("Worker rows must be children of the designer-owned VerticalBox")
    if (
        worker_slot.get_editor_property("horizontal_alignment")
        != unreal.HorizontalAlignment.H_ALIGN_FILL
    ):
        raise AssertionError("Worker rows must fill the available list width")
    public_client_methods = {
        name
        for name in dir(render_farm_viewer.ReadOnlyFarmClient)
        if not name.startswith("_")
    }
    if public_client_methods != {"list_jobs", "list_workers"}:
        raise AssertionError(
            f"Viewer client gained a non-read operation: {sorted(public_client_methods)}"
        )

    controller.dispose()
    tab_id = subsystem.get_tab_id_from_blueprint(asset)
    if tab_id:
        subsystem.close_tab_by_id(tab_id)


try:
    verify()
except Exception as error:
    unreal.log_error(f"[RenderFarmViewerWidgetTest] FAIL: {error}")
    if RUNTIME_TEST:
        unreal.SystemLibrary.quit_editor()
    raise
else:
    unreal.log_warning("[RenderFarmViewerWidgetTest] PASS")
    if RUNTIME_TEST:
        unreal.SystemLibrary.quit_editor()
