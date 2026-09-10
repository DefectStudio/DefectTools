"""Create a three-frame render fixture inside an explicitly isolated checkout.

Run with UnrealEditor-Cmd -run=pythonscript -script=<this file>. Set
RENDER_WORKER_V2_VALIDATION_ROOT to the directory containing runtime-smoke.
The script refuses other projects and creates no production callbacks.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import traceback
from uuid import uuid4

import unreal


def create_fixture() -> dict:
    configured = os.environ.get("RENDER_WORKER_V2_VALIDATION_ROOT")
    if not configured:
        raise RuntimeError("RENDER_WORKER_V2_VALIDATION_ROOT is required")
    root = Path(configured).resolve()
    project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
    if project != root / "runtime-smoke" or not (root / ".render-worker-v2-validation").is_file():
        raise RuntimeError(f"Refusing to create smoke assets in {project}")

    asset_root = "/Game/RenderWorkerV2Smoke/Run_" + uuid4().hex[:8]
    paths = {name: f"{asset_root}/{name}" for name in ("Map", "Sequence", "Graph")}
    if any(unreal.EditorAssetLibrary.does_asset_exist(path) for path in paths.values()):
        raise RuntimeError("Smoke assets already exist; preserve them and use a fresh checkout for another run")

    world = unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    cube = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0, 0, 50))
    cube.static_mesh_component.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Cube"))
    camera = actors.spawn_actor_from_class(unreal.CineCameraActor, unreal.Vector(-350, 0, 50))
    actors.spawn_actor_from_class(
        unreal.DirectionalLight, unreal.Vector(0, 0, 300), unreal.Rotator(-35, -45, 0)
    )
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, paths["Map"]):
        raise RuntimeError("Could not save smoke map")

    assets = unreal.AssetToolsHelpers.get_asset_tools()
    sequence = assets.create_asset("Sequence", asset_root, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    sequence.set_display_rate(unreal.FrameRate(24, 1))
    sequence.set_playback_start(0)
    sequence.set_playback_end(3)
    binding = sequence.add_possessable(camera)
    cut = sequence.add_track(unreal.MovieSceneCameraCutTrack).add_section()
    cut.set_range(0, 3)
    camera_binding = unreal.MovieSceneObjectBindingID()
    camera_binding.set_editor_property("guid", binding.get_id())
    cut.set_camera_binding_id(camera_binding)

    # Use the engine's basic graph construction pattern, with no Execute Script
    # nodes, external assets, MP4 encoder, ClickUp, or show-folder callbacks.
    graph = assets.create_asset("Graph", asset_root, unreal.MovieGraphConfig, None)
    output = graph.create_node_by_class(unreal.MovieGraphGlobalOutputSettingNode)
    output.override_output_resolution = True
    output.output_resolution = unreal.MovieGraphLibrary.named_resolution_from_size(256, 144)
    output.override_output_directory = True
    output.output_directory = unreal.DirectoryPath(str(root / "output"))
    writer = graph.create_node_by_class(unreal.MovieGraphImageSequenceOutputNode_EXR)
    writer.override_file_name_format = True
    writer.file_name_format = "smoke.{frame_number}"
    preview = graph.create_node_by_class(unreal.MovieGraphImageSequenceOutputNode_PNG)
    preview.override_file_name_format = True
    preview.file_name_format = "smoke.{frame_number}"
    graph.add_labeled_edge(graph.get_input_node(), "Globals", output, "")
    graph.add_labeled_edge(output, "", writer, "")
    graph.add_labeled_edge(writer, "", preview, "")
    graph.add_labeled_edge(preview, "", graph.get_output_node(), "Globals")
    graph.add_input().set_member_name("Main")
    graph.add_output().set_member_name("Main")
    renderer = graph.create_node_by_class(unreal.MovieGraphDeferredRenderPassNode)
    layer = graph.create_node_by_class(unreal.MovieGraphRenderLayerNode)
    layer.override_layer_name = True
    layer.layer_name = "Main"
    graph.add_labeled_edge(graph.get_input_node(), "Main", renderer, "")
    graph.add_labeled_edge(renderer, "", layer, "")
    graph.add_labeled_edge(layer, "", graph.get_output_node(), "Main")
    variable = graph.add_variable("SmokeTest")
    variable.set_value_type(unreal.MovieGraphValueType.BOOL)
    variable.set_value_serialized_string("True")
    for name in ("Sequence", "Graph"):
        if not unreal.EditorAssetLibrary.save_asset(paths[name]):
            raise RuntimeError(f"Could not save smoke {name}")

    job = {
        "schema_version": 1,
        "job_type": "unreal_movie_render_graph",
        "job_id": "render-worker-v2-runtime-smoke",
        "shot_name": "RenderWorkerV2Smoke",
        "status": "rendering",
        "project": "s3bishop",
        "uproject": str(project / "s3bishop.uproject"),
        "level": paths["Map"] + ".Map",
        "sequence": paths["Sequence"] + ".Sequence",
        "render_config": paths["Graph"] + ".Graph",
        "output_directory": str(root / "output"),
        "output_relative_directory": "output",
        "submitted_show_file_server_path": str(root),
        "worker_output_directory": str(root / "output"),
        "output_file_name_format": "smoke.{frame_number}",
        "frame_count": 3,
        "outputs": {"exr": True, "mp4": False},
        "graph_variable_overrides": {
            "SmokeTest": {"enabled": True, "serialized_value": "True"},
        },
    }
    folder = root / "job"
    folder.mkdir(exist_ok=True)
    (folder / "job.json").write_text(json.dumps(job, indent=2), encoding="utf-8")
    return {"success": True, "project": str(project), "job": str(folder / "job.json")}


try:
    result = create_fixture()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
else:
    unreal.log("WORKER_V2_FIXTURE " + json.dumps(result))
