"""Editor smoke test for a level-independent Render Farm Viewer dock tab."""

import unreal


LEVELS = (
    "/Game/LVL_Startup",
    "/Game/_defecttoolsdev/Assets/env_testWorld/env_testWorld",
)


def assert_table_owned_by_viewer(controller) -> None:
    controller._render()
    if controller.list_scroll.get_children_count() != 1:
        raise AssertionError("Viewer did not render one table")
    table_path = controller.list_scroll.get_child_at(0).get_path_name()
    widget_path = controller.widget.get_path_name()
    if not any(
        table_path.startswith(widget_path + separator + "WidgetTree_")
        for separator in (".", ":")
    ):
        raise AssertionError(f"Viewer table is not widget-owned: {table_path}")


def verify():
    import render_farm_viewer

    class EmptyFarmClient:
        def list_jobs(self):
            return []

        def list_workers(self):
            return []

    render_farm_viewer.ReadOnlyFarmClient = EmptyFarmClient
    native_tab = unreal.QuickWidgetToolsRenderFarmViewerLibrary
    if not native_tab.open_viewer():
        raise AssertionError("Could not open the native viewer tab")
    widget = native_tab.get_active_viewer()
    if widget is None:
        raise AssertionError("Native viewer tab has no designer widget")
    if not widget.get_path_name().startswith("/Engine/Transient."):
        raise AssertionError("Viewer is still owned by an editor level")
    render_farm_viewer.run()
    controller = render_farm_viewer._ACTIVE_CONTROLLERS[widget.get_path_name()]
    controller._set_mode("workers")
    controller.job_sort_field = "JobName"
    assert_table_owned_by_viewer(controller)

    levels_to_check = () if "-RenderFarmSkipLevelSwitch" in unreal.SystemLibrary.get_command_line() else LEVELS * 2
    for level in levels_to_check:
        if not unreal.EditorAssetLibrary.does_asset_exist(level):
            raise AssertionError(f"Missing test level: {level}")
        unreal.EditorLevelLibrary.load_level(level)
        current = native_tab.get_active_viewer()
        if current != widget:
            raise AssertionError(f"Level switch reconstructed the viewer in {level}")
        if render_farm_viewer._ACTIVE_CONTROLLERS.get(widget.get_path_name()) is not controller:
            raise AssertionError(f"Level switch replaced the viewer controller in {level}")
        if controller.mode != "workers" or controller.job_sort_field != "JobName":
            raise AssertionError(f"Level switch reset viewer state in {level}")
        if not controller._widget_is_open():
            raise AssertionError(f"Viewer tab was not registered after loading {level}")
        assert_table_owned_by_viewer(controller)
        if len(render_farm_viewer._ACTIVE_CONTROLLERS) != 1:
            raise AssertionError("Level switch created another viewer controller")

    return native_tab, controller, render_farm_viewer


try:
    native_tab, controller, render_farm_viewer = verify()
except Exception as error:
    unreal.log_error(f"[RenderFarmViewerLevelSwitchTest] FAIL: {error}")
    unreal.SystemLibrary.quit_editor()
    raise
else:
    if "-RenderFarmSkipClose" in unreal.SystemLibrary.get_command_line():
        unreal.log_warning("[RenderFarmViewerLevelSwitchTest] PASS")
        unreal.SystemLibrary.quit_editor()
    else:
        ticks = 0
        close_handle = None
        unreal.EditorPythonScripting.set_keep_python_script_alive(True)

        def finish_after_ticks(_delta_seconds):
            global ticks, close_handle
            ticks += 1
            try:
                if ticks == 5 and not native_tab.close_viewer():
                    raise AssertionError("Could not close the native viewer tab")
                if ticks < 10:
                    return
                for _ in range(3):
                    controller._widget_is_open()
                if not controller._disposed or render_farm_viewer._ACTIVE_CONTROLLERS:
                    raise AssertionError("Closing the viewer left an active controller")
                unreal.log_warning("[RenderFarmViewerLevelSwitchTest] PASS")
            except Exception as error:
                unreal.log_error(f"[RenderFarmViewerLevelSwitchTest] FAIL: {error}")
                unreal.unregister_slate_post_tick_callback(close_handle)
                unreal.EditorPythonScripting.set_keep_python_script_alive(False)
                unreal.SystemLibrary.quit_editor()
                return
            if ticks >= 10:
                unreal.unregister_slate_post_tick_callback(close_handle)
                unreal.EditorPythonScripting.set_keep_python_script_alive(False)
                unreal.SystemLibrary.quit_editor()

        close_handle = unreal.register_slate_post_tick_callback(finish_after_ticks)
