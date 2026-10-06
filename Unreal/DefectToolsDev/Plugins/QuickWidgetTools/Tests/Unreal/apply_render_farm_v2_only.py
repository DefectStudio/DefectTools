"""Remove both version controls and make the saved Rendering Tool submit to V2."""

import unreal


ASSET_PATH = "/QuickWidgetTools/EditorWidgets/WBP_03_RenderingTool"
SUBMIT_SCRIPT = (
    "import importlib\n"
    "import publish_render_queue_to_farm\n"
    "importlib.reload(publish_render_queue_to_farm)\n"
    "result_summary = publish_render_queue_to_farm.run(use_v2=True)"
)


def apply():
    asset = unreal.load_asset(ASSET_PATH)
    if asset is None:
        raise RuntimeError("Rendering Tool asset is missing")
    asset.modify()
    tree = unreal.load_object(None, asset.get_path_name() + ":WidgetTree")
    tree.modify()
    prefix = tree.get_path_name() + "."
    graph = unreal.BlueprintGraphEditor.get_graph_editor_by_name(asset, "EventGraph")
    nodes = graph.list_all_nodes()
    submit = next(n for n in nodes if n.get_name() == "K2Node_ExecutePythonScript_1")
    initializers = [
        n for n in nodes
        if n.get_class().get_name() == "K2Node_ExecutePythonScript"
        and "render_farm_version_selector.initialize" in n.find_input_pin("PythonScript").get_pin_value()
    ]
    for init in initializers:
        incoming = list(init.find_execute_pin().list_connected_pins())
        following = list(init.find_then_pin().list_connected_pins())
        init.find_execute_pin().break_pin_links()
        init.find_then_pin().break_pin_links()
        for source in incoming:
            for target in following:
                if not source.try_create_connection(target):
                    raise RuntimeError("Could not reconnect widget construction")

    submit.modify()
    for old_input in submit.get_editor_property("inputs"):
        submit.find_input_pin(old_input).break_pin_links()
    submit.set_editor_property("inputs", [])
    if not submit.find_input_pin("PythonScript").set_pin_value(SUBMIT_SCRIPT):
        raise RuntimeError("Could not update farm submission node")

    version_getters = [
        n for n in nodes
        if n.get_class().get_name() == "K2Node_VariableGet"
        and any(name in n.get_node_title().replace(" ", "") for name in ("FarmVersionV1", "FarmVersionV2"))
    ]
    if initializers or version_getters:
        graph.remove_nodes(initializers + version_getters)

    for name in ("FarmVersionV1", "FarmVersionV2", "FarmVersionSelector"):
        control = unreal.find_object(None, prefix + name)
        if control is not None:
            control.modify()
            control.remove_from_parent()

    unreal.BlueprintEditorLibrary.compile_blueprint(asset)
    errors = graph.list_nodes_with_errors()
    if errors:
        raise RuntimeError("Rendering Tool compilation errors: " + str(errors))
    if not unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
        raise RuntimeError("Could not save Rendering Tool")
    unreal.log("[FarmV2Only] PASS: saved Rendering Tool without version checkboxes; submission is explicitly V2.")


if __name__ == "__main__":
    try:
        apply()
        import runpy
        from pathlib import Path

        runpy.run_path(str(Path(__file__).with_name("verify_render_farm_v2_only.py")))["verify_saved"]()
    finally:
        if "FarmV2OnlyApplyAndExit" in unreal.SystemLibrary.get_command_line():
            unreal.SystemLibrary.quit_editor()
