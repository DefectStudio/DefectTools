"""Read the requested shot and graph in Unreal, without editing project assets."""

from __future__ import annotations

import json
import os
from pathlib import Path
import traceback

import unreal


def object_path(value):
    if hasattr(value, "get_path_name"):
        return value.get_path_name()
    text = str(value)
    if "'" in text:
        text = text.split("'", 2)[1]
    if not text.startswith("/"):
        return ""
    return text


def prepare(request):
    project_dir = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
    if project_dir != Path(request.get("project_directory", request["checkout"])).resolve():
        raise RuntimeError("Unreal opened a different checkout than the worker prepared")
    shot = request["shot"]
    bindings = {"shot": shot, "prefix": shot.split("_", 1)[0]}
    spec = request["render"]
    sequence_path = spec["sequence"].format(**bindings)
    graph_path = spec["graph"].format(**bindings)
    sequence = unreal.load_asset(sequence_path)
    graph = unreal.load_asset(graph_path)
    if not isinstance(sequence, unreal.LevelSequence):
        raise RuntimeError(f"Shot sequence is missing: {sequence_path}")
    if not isinstance(graph, unreal.MovieGraphConfig):
        raise RuntimeError(f"Shot render graph is missing: {graph_path}")
    level_path = spec.get("level", "").format(**bindings)
    if not level_path:
        data_path = spec["shot_data"].format(**bindings)
        data = unreal.load_asset(data_path)
        if data is None:
            raise RuntimeError(f"Shot data is missing: {data_path}")
        for key in [spec.get("level_property", "AssociatedLevel"), "associated_level", "Level", "AssociatedLevelStored", "AssociatedLevelPathString"]:
            try:
                level_path = object_path(data.get_editor_property(key))
                if level_path:
                    break
            except Exception:
                continue
    if not level_path:
        raise RuntimeError("The shot has no associated level")
    variables = {str(v.get_member_name()).casefold(): v for v in graph.get_variables()}
    output = request["output_directory"]
    overrides = {}
    values = {
        "outputdirectory": unreal.DirectoryPath(output).export_text(),
        "filenameformat": "EXR/" + shot + ".{frame_number}",
        "mp4filenameformat": shot,
        "exr": "True",
        "mp4": "False",
        "hero": "False",
    }
    for key, value in values.items():
        if key in variables:
            overrides[str(variables[key].get_member_name())] = {"enabled": True, "serialized_value": value}
    if "outputdirectory" not in variables or "filenameformat" not in variables:
        raise RuntimeError("The graph must expose OutputDirectory and FileNameFormat for portable outputs")
    start = sequence.get_playback_start()
    end = sequence.get_playback_end()
    if end <= start:
        raise RuntimeError("Shot has an empty playback range")
    job = {
        "schema_version": 1, "job_type": "unreal_movie_render_graph", "status": "rendering",
        "job_id": request["job_id"], "shot_name": shot, "project": request["project_name"],
        "project_id": request["project_id"], "uproject": request["uproject"],
        "worker_runtime_version": 2, "disable_project_scripts": False,
        "prepared_git_commit": request["commit"], "worker_sync_policy": "managed_project_fetch",
        "level": level_path, "sequence": sequence_path, "render_config": graph_path,
        "output_directory": output, "output_relative_directory": "output",
        "submitted_show_file_server_path": request["run_root"],
        "output_file_name_format": "EXR/" + shot + ".{frame_number}",
        "mp4_file_name_format": shot, "frame_count": end - start,
        "frame_start": start, "frame_end": end, "outputs": {"exr": True, "mp4": False},
        "graph_variable_overrides": overrides,
    }
    Path(request["job_path"]).write_text(json.dumps(job, indent=2), encoding="utf-8")
    return {"success": True, "job_id": job["job_id"], "frame_count": job["frame_count"],
            "level": level_path, "graph": graph_path, "variables": list(variables)}


request_path = Path(os.environ["RENDER_WORKER_JOB_REQUEST"])
request = json.loads(request_path.read_text(encoding="utf-8"))
try:
    result = prepare(request)
except Exception:
    result = {"success": False, "job_id": request["job_id"], "error": traceback.format_exc()}
Path(request["receipt_path"]).write_text(json.dumps(result, indent=2), encoding="utf-8")
unreal.log("RENDER_WORKER_JOB_PREPARED " + json.dumps(result))
