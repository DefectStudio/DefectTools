"""Exercise the packaged OnlyClouds tools in an isolated receiving project.

Run with UnrealEditor-Cmd.exe <ValidationHost.uproject> -unattended -nullrhi
-ExecutePythonScript=<this file> (not the Python commandlet: Undo needs an editor).
The only accepted host is I:/AICache/onlyclouds-fx-migration/ValidationHost.
Copy QuickWidgetTools into that host; never junction it to a working checkout.
The launcher must put its logs, user directory, temporary files and DDC in the
same task scratch directory. This script saves only scratch /Game/Validation
assets and the JSON report; it does not save any plugin assets.

Set ONLYCLOUDS_SKIP_WIDGET=1 only for the early, pre-wiring native-action pass.
That run reports native_actions_passed_widget_not_checked, never full success.
"""

import gc
import hashlib
import json
import math
import os
from pathlib import Path
import traceback

import unreal


HOST = Path("I:/AICache/onlyclouds-fx-migration/ValidationHost")
MOUNT = "/QuickWidgetTools/OnlyClouds"
WORLD_BP = MOUNT + "/WorldClouds/BP_UDSOnlyClouds"
PLACED_BP = MOUNT + "/PlacedClouds/BP_CloudPreset"
WIDGET = "/QuickWidgetTools/EditorWidgets/WBP_08_FX_Tools"
MAP = "/Game/Validation/OnlyCloudsRoundTrip"
PRESETS = MOUNT + "/PlacedClouds/Presets/"
BUTTONS = (
    ("Add_Basic_Light_Rigg_Button", "AddBasicLightRigg", 6),
    ("Add_Layered_World_Clouds_Button", "AddLayeredWorldClouds", 1),
    ("Add_Cloud_Preset_Button", "AddCloudPreset", 7),
)
RIG_CLASSES = {
    "/Script/Engine.DirectionalLight", "/Script/Engine.SkyLight",
    "/Script/Engine.SkyAtmosphere", "/Script/Engine.ExponentialHeightFog",
    "/Script/Engine.StaticMeshActor", "/Script/Engine.PostProcessVolume",
}
RESULT = {
    "status": "running", "checks": [], "observations": {},
    "limitations": [
        "NullRHI checks actor state, asset references, Blueprint routes and Undo; "
        "it does not establish rendered appearance or Movie Render Queue output.",
    ],
}


def check(name, passed, detail=None):
    RESULT["checks"].append({"name": name, "passed": bool(passed), "detail": detail})
    if not passed:
        raise AssertionError("%s: %s" % (name, detail))


def prop(obj, name):
    return obj.get_editor_property(name)


def close(a, b):
    return math.isclose(float(a), float(b), abs_tol=1e-4, rel_tol=1e-5)


def ids(sub):
    return {actor.get_path_name() for actor in sub.get_all_level_actors()}


def plugin_hashes(project):
    root = project / "Plugins" / "QuickWidgetTools"
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.suffix.lower() in (".uasset", ".umap")}


def guard():
    # Guard before creating files, modifying an editor world, or calling Quit.
    project = Path(unreal.Paths.project_dir()).resolve()
    if project != HOST.resolve():
        raise RuntimeError("Refusing to run outside designated scratch ValidationHost: " + str(project))
    plugin = project / "Plugins" / "QuickWidgetTools"
    if not plugin.resolve().is_relative_to(project):
        raise RuntimeError("Validation plugin resolves outside scratch host; do not use a junction.")
    if not (plugin / "QuickWidgetTools.uplugin").is_file():
        raise RuntimeError("Missing packaged QuickWidgetTools test copy.")
    for path in plugin.rglob("*"):
        if not path.resolve().is_relative_to(project):
            raise RuntimeError("Validation plugin has a link outside scratch host: " + str(path))
    return project


def dependency_check(project):
    descriptor = json.loads((project / "Plugins/QuickWidgetTools/QuickWidgetTools.uplugin").read_text(encoding="utf-8-sig"))
    modules = {item["Name"]: item["Type"] for item in descriptor["Modules"]}
    check("One plugin contains both cloud modules", modules.get("CloudGeneratorTools") == "Runtime"
          and modules.get("OnlyCloudsEditor") == "Editor", modules)
    check("No separate OnlyClouds plugin installed", not list((project / "Plugins").rglob("OnlyClouds.uplugin")))
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    registry.scan_paths_synchronous([MOUNT], force_rescan=True)
    assets = registry.get_assets_by_path(MOUNT, recursive=True)
    check("All 32 cloud assets migrated", len(assets) == 32, len(assets))
    options = unreal.AssetRegistryDependencyOptions(
        include_soft_package_references=True, include_hard_package_references=True,
        include_searchable_names=False, include_soft_management_references=False,
        include_hard_management_references=False)
    graph, invalid = {}, []
    for asset in assets:
        package = str(asset.package_name)
        dependencies = sorted(str(dep) for dep in registry.get_dependencies(package, options))
        graph[package] = dependencies
        invalid.extend({"asset": package, "dependency": dep} for dep in dependencies
                       if not dep.startswith((MOUNT + "/", "/Engine/", "/Script/")))
    RESULT["observations"]["dependencies"] = graph
    check("Cloud content has no old mount or project-content dependency", not invalid, invalid)
    for required in (WORLD_BP, PLACED_BP, MOUNT + "/Templates/LVL_BasicLiteRigg",
                     PRESETS + "CP_Cumulus", PRESETS + "CP_Cumulonimbus", PRESETS + "CP_Cirrus"):
        check("Required package present: " + required, required in graph)
    for path in (WORLD_BP, PLACED_BP):
        blueprint = unreal.load_asset(path)
        check("Cloud Blueprint loads: " + path, blueprint is not None)
        check("Cloud Blueprint compiles: " + path, unreal.BlueprintEditorLibrary.compile_blueprint(blueprint))


def action(method, label):
    result = method()
    check(label + ": native action succeeds", prop(result, "bSuccess"), str(prop(result, "Message")))
    return result


def undo_redo(label, sub, before, after):
    check(label + ": Undo succeeds", unreal.OnlyCloudsEditorLibrary.undo_last_editor_transaction())
    check(label + ": one Undo removes complete actor batch", ids(sub) == before,
          {"expected": sorted(before), "actual": sorted(ids(sub))})
    check(label + ": Redo succeeds", unreal.OnlyCloudsEditorLibrary.redo_last_editor_transaction())
    check(label + ": one Redo restores complete actor batch", ids(sub) == after,
          {"expected": sorted(after), "actual": sorted(ids(sub))})


def find_cloud(sub):
    matches = [actor for actor in sub.get_all_level_actors()
               if actor.get_class().get_path_name() == PLACED_BP + ".BP_CloudPreset_C"]
    check("Exactly one placed cloud generator", len(matches) == 1, len(matches))
    return matches[0]


def cvars():
    names = ("r.VolumetricRenderTarget", "r.VolumetricRenderTarget.Mode",
             "r.VolumetricCloud.ViewRaySampleMaxCount", "r.VolumetricCloud.StepSizeOnZeroConservativeDensity",
             "r.EyeAdaptationQuality", "r.DefaultFeature.AutoExposure", "r.Fog", "r.VolumetricFog",
             "r.SkyAtmosphere", "r.Lumen.DiffuseIndirect.Allow")
    return {name: unreal.SystemLibrary.get_console_variable_float_value(name) for name in names}


def native_actions(sub):
    world = unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
    api = unreal.OnlyCloudsEditorLibrary
    baseline = cvars()
    before = ids(sub)
    result = action(api.add_basic_light_rigg, "Lighting rig")
    actors = list(prop(result, "Actors"))
    after = ids(sub)
    check("Rig creates exactly six actors", prop(result, "bCreated") and len(actors) == 6 and len(after - before) == 6)
    check("Rig has the six original light/environment classes", {a.get_class().get_path_name() for a in actors} == RIG_CLASSES)
    check("Rig actors use BasicLiteRigg folder", all(str(a.get_folder_path()) == "BasicLiteRigg" for a in actors))
    check("Rig preserves the active editor world", world == unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world())
    check("Rig leaves rendering globals unchanged", cvars() == baseline)
    undo_redo("Rig", sub, before, after)

    before = ids(sub)
    result = action(api.add_layered_world_clouds, "World clouds")
    actors = list(prop(result, "Actors"))
    after = ids(sub)
    check("World action creates one controller", prop(result, "bCreated") and len(actors) == 1 and len(after - before) == 1)
    world_class = unreal.load_class(None, WORLD_BP + ".BP_UDSOnlyClouds_C")
    check("World controller is the migrated Blueprint", actors[0].get_class() == world_class)
    component = actors[0].get_component_by_class(unreal.VolumetricCloudComponent)
    check("World cloud has its material", component is not None and prop(component, "Material") is not None)
    current = cvars()
    check("World action preserves exposure, fog and lighting globals",
          all(current[key] == value for key, value in baseline.items()
              if not key.startswith(("r.VolumetricCloud.", "r.VolumetricRenderTarget"))))
    check("World Undo succeeds", api.undo_last_editor_transaction())
    check("World Undo removes controller and restores cloud quality", ids(sub) == before and cvars() == baseline,
          {"expected_cvars": baseline, "actual_cvars": cvars()})
    check("World Redo succeeds", api.redo_last_editor_transaction())
    check("World Redo restores controller and quality", ids(sub) == after and cvars() == current)
    controller = next(a for a in sub.get_all_level_actors() if a.get_class() == world_class)
    for hidden in (False, True):
        controller.set_is_temporarily_hidden_in_editor(hidden)
        repeated = action(api.add_layered_world_clouds, "Repeated world clouds, hidden=" + str(hidden))
        check("Repeated world action reuses existing controller, hidden=" + str(hidden),
              not prop(repeated, "bCreated") and list(prop(repeated, "Actors")) == [controller] and ids(sub) == after)
    controller.set_is_temporarily_hidden_in_editor(False)

    before = ids(sub)
    result = action(api.add_cloud_preset, "Cloud preset")
    after = ids(sub)
    cloud = find_cloud(sub)
    check("Preset creates generator plus six guides", prop(result, "bCreated") and len(after - before) == 7
          and len(prop(cloud, "Guides")) == 6 and prop(cloud, "ActiveGuideCount") == 6)
    check("Preset uses migrated Cumulus recipe", prop(cloud, "Preset").get_path_name().startswith(PRESETS + "CP_Cumulus."))
    check("Preset has exactly one material-bound render volume", len(cloud.get_components_by_class(unreal.HeterogeneousVolumeComponent)) == 1
          and prop(cloud, "CloudVolume").get_material(0) is not None)
    undo_redo("Preset", sub, before, after)
    return world, find_cloud(sub)


def save_edited_preset_map(world, cloud, sub):
    for family in ("Cumulonimbus", "Cirrus", "Cumulus"):
        preset = unreal.load_asset(PRESETS + "CP_" + family)
        recipe_guides = list(prop(prop(preset, "Recipe"), "Guides"))
        expected_enabled = [bool(prop(guide, "bEnabled")) for guide in recipe_guides]
        cloud.set_editor_property("Preset", preset)
        cloud.load_preset()
        actual_guides = list(prop(cloud, "Guides"))
        # Cirrus intentionally retains ten guides, with five disabled. The
        # active render count must follow the enabled flags, not total guides.
        check("Editable preset loads: " + family,
              len(actual_guides) == len(recipe_guides)
              and [bool(prop(guide, "bEnabled")) for guide in actual_guides] == expected_enabled
              and prop(cloud, "ActiveGuideCount") == sum(expected_enabled),
              {"expected_total": len(recipe_guides), "actual_total": len(actual_guides),
               "expected_active": sum(expected_enabled), "actual_active": prop(cloud, "ActiveGuideCount"),
               "workflow": str(prop(cloud, "WorkflowStatus")), "preview": str(prop(cloud, "PreviewStatus"))})
    cloud.set_editor_properties({"bAnimated": False, "Density": 1.375,
                                 "PresetName": "MigrationEditedCloud", "PresetSaveDirectory": "/Game/Validation/Presets"})
    guide = list(prop(cloud, "Guides"))[0]
    original = guide.get_actor_location()
    guide.set_actor_location(unreal.Vector(original.x + 123.0, original.y, original.z), False, False)
    cloud.refresh_cloud()
    expected = cloud.capture_recipe()
    expected_x = prop(list(prop(expected, "Guides"))[0], "LocalTransform").translation.x
    cloud.save_preset()
    saved = prop(cloud, "Preset")
    check("Artist preset saves into scratch project Content", saved.get_path_name().startswith("/Game/Validation/Presets/CP_MigrationEditedCloud"), str(prop(cloud, "WorkflowStatus")))
    check("Saved preset records edited density", close(prop(prop(saved, "Recipe"), "Density"), 1.375))
    cloud.set_editor_property("Density", 0.25)
    guide.set_actor_location(original, False, False)
    cloud.load_preset()
    check("Loading saved preset restores density and edited guide",
          close(prop(cloud, "Density"), 1.375)
          and close(prop(list(prop(cloud.capture_recipe(), "Guides"))[0], "LocalTransform").translation.x, expected_x))
    actor_count = len(ids(sub))
    check("Scratch test map saves", unreal.EditorLoadingAndSavingUtils.save_map(world, MAP))
    # Return primitive expectations only. The caller must release the world,
    # generator and this function's guide wrappers before replacing the map.
    return {"actor_count": actor_count, "guide_local_x": expected_x}


def reload_edited_preset_map(sub, expected):
    unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
    check("Scratch test map reloads", unreal.EditorLoadingAndSavingUtils.load_map(MAP) is not None)
    cloud = find_cloud(sub)
    check("Created actor batch survives map reload", len(ids(sub)) == expected["actor_count"])
    check("Edited preset and guides survive map reload", close(prop(cloud, "Density"), 1.375)
          and len(prop(cloud, "Guides")) == 6
          and close(prop(list(prop(cloud.capture_recipe(), "Guides"))[0], "LocalTransform").translation.x, expected["guide_local_x"]))


def normalized_title(node):
    return "".join(c.lower() for c in str(unreal.BlueprintEditorLibrary.get_node_title(node)) if c.isalnum())


def connected(source, target):
    return source.is_valid() and target.is_valid() and any(pin.is_same_native_pin(target) for pin in source.list_connected_pins())


def widget_check(sub):
    asset = unreal.load_asset(WIDGET)
    check("FX widget loads", asset is not None)
    check("FX widget remains a Designer EditorUtilityWidget", asset.get_blueprint_parent_class() == unreal.EditorUtilityWidget.static_class())
    graph = unreal.BlueprintGraphEditor.get_graph_editor_by_name(asset, "EventGraph")
    nodes = graph.list_all_nodes()
    routes = []
    for button, function, _ in BUTTONS:
        events = [node for node in nodes if str(unreal.BlueprintEditorLibrary.get_node_title(node)) == "On Clicked (" + button + ")"]
        check("Exactly one button event: " + button, len(events) == 1)
        linked = events[0].find_then_pin().list_connected_pins()
        check("Button directly invokes native action: " + button, len(linked) == 1
              and normalized_title(linked[0].get_owning_node()) == function.lower())
        action_node = linked[0].get_owning_node()
        report_links = action_node.find_then_pin().list_connected_pins()
        check("Action reports result: " + function, len(report_links) == 1
              and normalized_title(report_links[0].get_owning_node()) in ("reportactionresult", "reportonlycloudsactionresult"))
        report_node = report_links[0].get_owning_node()
        check("Report receives this action's result: " + function,
              connected(action_node.find_output_pin("ReturnValue"), report_node.find_input_pin("Result")))
        routes.append({"button": button, "native_action": function, "reports_result": True})
    check("FX widget compiles", unreal.BlueprintEditorLibrary.compile_blueprint(asset))
    check("FX graph has no errors", not graph.list_nodes_with_errors())
    check("FX graph has no warnings", not graph.list_nodes_with_warnings())
    RESULT["observations"]["widget_routes"] = routes
    unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
    widget = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem).spawn_and_register_tab(asset)
    check("FX widget instantiates", widget is not None)
    for name, _, count in BUTTONS:
        button = widget.get_editor_property(name)
        check("Runtime button has click binding: " + name, button.on_clicked.is_bound())
        before = ids(sub)
        button.on_clicked.broadcast()
        check("Actual button creates expected actor batch: " + name, len(ids(sub) - before) == count, len(ids(sub) - before))
    # No spawned test actor is retained in an unsaved open level at exit.
    unreal.EditorLoadingAndSavingUtils.new_blank_map(False)


def main():
    project = guard()
    report = project / "Saved/Tests/OnlyClouds/integration-results.json"
    before_hashes = plugin_hashes(project)
    try:
        dependency_check(project)
        sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        world, cloud = native_actions(sub)
        saved_expectations = save_edited_preset_map(world, cloud, sub)
        del world, cloud
        gc.collect()
        reload_edited_preset_map(sub, saved_expectations)
        gc.collect()
        if os.environ.get("ONLYCLOUDS_SKIP_WIDGET") == "1":
            RESULT["status"] = "native_actions_passed_widget_not_checked"
            RESULT["limitations"].append("Widget routes were explicitly skipped for a pre-wiring native-action pass.")
        else:
            widget_check(sub)
            RESULT["status"] = "passed"
        check("Plugin assets were never saved or modified on disk", plugin_hashes(project) == before_hashes)
    except Exception as error:
        RESULT["status"] = "failed"
        RESULT["error"] = str(error)
        RESULT["traceback"] = traceback.format_exc()
        unreal.log_error(RESULT["traceback"])
    finally:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(RESULT, indent=2), encoding="utf-8")
        unreal.log("ONLYCLOUDS_INTEGRATION " + RESULT["status"] + " " + str(report))
        unreal.SystemLibrary.quit_editor()


if __name__ == "__main__":
    main()
