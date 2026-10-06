"""Verify the saved widget and actual V2 Send button without publishing a job."""

import importlib
from unittest.mock import patch

import unreal
import publish_render_queue_to_farm as publisher


def verify_saved():
    asset = unreal.load_asset("/QuickWidgetTools/EditorWidgets/WBP_03_RenderingTool")
    prefix = asset.get_path_name() + ":WidgetTree."
    for name in ("FarmVersionV1", "FarmVersionV2", "FarmVersionSelector"):
        control = unreal.find_object(None, prefix + name)
        assert control is None or control.get_parent() is None, name + " is still in the widget layout"
    graph = unreal.BlueprintGraphEditor.get_graph_editor_by_name(asset, "EventGraph")
    submit = next(n for n in graph.list_all_nodes() if n.get_name() == "K2Node_ExecutePythonScript_1")
    script = submit.find_input_pin("PythonScript").get_pin_value()
    assert "run(use_v2=True)" in script and "v1_checkbox" not in script, script
    assert not graph.list_nodes_with_errors()
    unreal.log("[FarmV2OnlyTest] PASS: saved layout and explicit V2 submission wiring.")
    return asset


def verify():
    asset = verify_saved()
    widget = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem).spawn_and_register_tab(asset)
    button = widget.get_editor_property("SendRenderQueuetoFarmButton")
    calls = []
    original_reload = importlib.reload
    with patch.object(publisher, "run", side_effect=lambda **kwargs: calls.append(kwargs) or "test only"), patch.object(
        importlib, "reload", side_effect=lambda module: module if module is publisher else original_reload(module)
    ):
        button.on_clicked.broadcast()
    assert calls == [{"use_v2": True}], calls
    unreal.log("[FarmV2OnlyTest] PASS: actual Send button routes only to V2. No jobs published.")


if __name__ == "__main__":
    try:
        verify()
    finally:
        if "FarmV2OnlyVerifyAndExit" in unreal.SystemLibrary.get_command_line():
            unreal.SystemLibrary.quit_editor()
