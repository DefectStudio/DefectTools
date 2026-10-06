"""
Attach Snap Stage One wrapper.

Runs the proven real-bake tool, then performs the next flatten prep stage:
- clear Blueprint Actor transform keys
- clear global_ctrl transform keys
- move Sequencer to the first animation frame
- copy recorder_sphere's baked first-frame location/rotation to the Blueprint Actor
- force Blueprint Actor scale to 1,1,1

Selection workflow is the same as the real bake wrapper:
- Select the Blueprint Actor binding/actor.
- Select the Skeletal Mesh binding/component under that Blueprint Actor.
- Select the Control Rig global_ctrl channels/keys so the ANM subsequence can be resolved.
"""

import importlib
import traceback

import unreal

import flatten_world_position_to_global_ctrl_attach_snap_method as attach_base
import flatten_world_position_to_global_ctrl_attach_snap_real_bake as real_bake


LOG_PREFIX = "[AttachSnapStageOne]"
TRANSFORM_KEYS = (
    "location_x", "location_y", "location_z",
    "rotation_x", "rotation_y", "rotation_z",
    "scale_x", "scale_y", "scale_z",
)


def _log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


def _log_warning(message):
    unreal.log_warning(f"{LOG_PREFIX} Warning: {message}")


def _log_error(message):
    unreal.log_error(f"{LOG_PREFIX} Error: {message}")


def _safe_call(obj, function_name, *args):
    if obj is None:
        return None
    function = getattr(obj, function_name, None)
    if function is None:
        return None
    try:
        return function(*args)
    except Exception:
        return None


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [value]
    try:
        return list(value)
    except Exception:
        return [value]


def _compact_text(value, max_length=240):
    try:
        text = str(value)
    except Exception:
        try:
            text = repr(value)
        except Exception:
            text = "<unprintable>"
    text = text.replace("\r", " ").replace("\n", " ").strip()
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text


def _binding_name(binding):
    return _safe_call(attach_base, "_binding_name", binding) or _compact_text(binding, 120)


def _class_name(obj):
    return _safe_call(attach_base, "_class_name", obj) or str(type(obj))


def _binding_key(binding):
    value = _safe_call(binding, "get_id") or _safe_call(binding, "get_binding_id")
    return _compact_text(value or binding, 160)


def _base_module():
    return getattr(attach_base, "base", None)


def _default_transform_values():
    return {
        "location_x": 0.0,
        "location_y": 0.0,
        "location_z": 0.0,
        "rotation_x": 0.0,
        "rotation_y": 0.0,
        "rotation_z": 0.0,
        "scale_x": 1.0,
        "scale_y": 1.0,
        "scale_z": 1.0,
    }


def _selected_global_ctrl_section():
    base_module = _base_module()
    if base_module is None:
        return None, "flatten_world_position_to_global_ctrl base module unavailable"
    getter = getattr(base_module, "_get_selected_global_ctrl_section", None)
    if getter is None:
        return None, "base._get_selected_global_ctrl_section unavailable"
    try:
        section, channel_names, asset_path = getter()
    except Exception as exc:
        return None, f"selected global_ctrl section lookup failed: {exc}"
    if section is None:
        return None, f"no selected global_ctrl section; channels={channel_names} asset_path={asset_path}"
    return section, f"channels={channel_names} asset_path={asset_path}"


def _track_is_attach(track):
    return "Attach" in _class_name(track)


def _track_is_transform(track):
    return "TransformTrack" in _class_name(track) or "3DTransformTrack" in _class_name(track)


def _binding_has_attach_track(binding):
    for track in _as_list(_safe_call(binding, "get_tracks")):
        if _track_is_attach(track):
            return True
    return False


def _binding_has_transform_track(binding):
    for track in _as_list(_safe_call(binding, "get_tracks")):
        if _track_is_transform(track):
            return True
    return False


def _iter_all_bindings(sequence):
    iterator = getattr(attach_base, "_iter_all_bindings", None)
    if iterator is not None:
        try:
            for binding in iterator(sequence):
                yield binding
            return
        except Exception:
            pass
    for binding in _as_list(_safe_call(sequence, "get_bindings")):
        yield binding


def _get_selected_bindings():
    getter = getattr(attach_base, "_get_selected_bindings", None)
    if getter is not None:
        return _as_list(getter())
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    return _as_list(_safe_call(library, "get_selected_bindings"))


def _find_recorder_sphere_binding(sequence, sphere_name, excluded_bindings):
    excluded_keys = {_binding_key(binding) for binding in excluded_bindings if binding is not None}

    for binding in _get_selected_bindings():
        if _binding_key(binding) in excluded_keys:
            continue
        if _binding_has_attach_track(binding) and _binding_has_transform_track(binding):
            return binding, "selected binding with Attach + Transform tracks"

    candidates = []
    for binding in _iter_all_bindings(sequence):
        if _binding_key(binding) in excluded_keys:
            continue
        if _binding_has_attach_track(binding) and _binding_has_transform_track(binding):
            candidates.append(binding)

    if len(candidates) == 1:
        return candidates[0], "single sequence binding with Attach + Transform tracks"
    if len(candidates) > 1:
        name_matches = [binding for binding in candidates if str(sphere_name).lower() in _binding_name(binding).lower()]
        if name_matches:
            return name_matches[0], "name-matched binding with Attach + Transform tracks"
        return candidates[0], "first binding with Attach + Transform tracks"
    return None, "no binding with Attach + Transform tracks was found"


def _get_transform_values_from_binding(binding, frame):
    base_module = _base_module()
    if base_module is None:
        return None, "flatten_world_position_to_global_ctrl base module unavailable"

    bundle = _safe_call(base_module, "_find_actor_transform_channels_for_binding", binding)
    if not bundle:
        return None, f"Could not find transform channels on {_binding_name(binding)!r}."

    snapshot = _safe_call(base_module, "_snapshot_bundle", bundle)
    if not snapshot:
        return None, f"Could not snapshot transform channels on {_binding_name(binding)!r}."

    values = _safe_call(base_module, "_evaluate_transform_values", snapshot, int(frame))
    if not values:
        return None, f"Could not evaluate transform channels on {_binding_name(binding)!r} at frame {frame}."

    return values, ""


def _actor_values_from_recorder_values(recorder_values):
    values_to_write = dict(_default_transform_values())
    values_to_write.update(recorder_values or {})

    # Important: the recorder_sphere is visually scaled to 0.12, but the Blueprint Actor
    # should stay at normal scene scale. Copy only location/rotation from recorder_sphere.
    values_to_write["scale_x"] = 1.0
    values_to_write["scale_y"] = 1.0
    values_to_write["scale_z"] = 1.0
    return values_to_write


def _write_actor_first_frame_transform(binding, first_frame, end_frame, recorder_values):
    writer = getattr(attach_base, "_write_transform_keys", None)
    if writer is None:
        return "attach_base._write_transform_keys unavailable"

    values_to_write = _actor_values_from_recorder_values(recorder_values)
    _log(f"Blueprint Actor first-frame transform to write: {_format_values(values_to_write)}")

    error = writer(
        binding,
        [(int(first_frame), values_to_write)],
        int(first_frame),
        int(end_frame),
        write_scale_keys=True,
    )
    return error or ""


def _clear_global_ctrl_and_write_zero(global_section, first_frame):
    base_module = _base_module()
    if base_module is None:
        return "flatten_world_position_to_global_ctrl base module unavailable"

    find_channels = getattr(base_module, "_find_global_ctrl_channels_from_section", None)
    first_channel = getattr(base_module, "_first_channel", None)
    remove_all_keys = getattr(base_module, "_remove_all_keys", None)
    set_default = getattr(base_module, "_set_channel_default", None)
    add_key = getattr(base_module, "_add_channel_key", None)

    if None in (find_channels, first_channel, remove_all_keys, set_default, add_key):
        return "Required global_ctrl channel helpers are unavailable."

    bundle = find_channels(global_section)
    values = _default_transform_values()
    missing = [key for key in TRANSFORM_KEYS if first_channel(bundle, key) is None]
    if missing:
        return f"global_ctrl section is missing transform channels: {missing}"

    for key in TRANSFORM_KEYS:
        channel = first_channel(bundle, key)
        value = values[key]
        if not remove_all_keys(channel):
            return f"Could not remove all global_ctrl keys for {key}."
        set_default(channel, value)
        if not add_key(channel, int(first_frame), value):
            return f"Could not add global_ctrl {key} reset key at frame {first_frame}."
    return ""


def _set_current_frame(frame):
    setter = getattr(attach_base, "_set_current_frame", None)
    if setter is None:
        return False, ["attach_base._set_current_frame unavailable"]
    return setter(int(frame))


def _refresh_sequencer():
    refresher = getattr(attach_base, "_refresh_sequencer", None)
    if refresher is not None:
        return refresher()
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    ok = _safe_call(library, "refresh_current_level_sequence")
    return bool(ok), ["refresh_current_level_sequence"]


def _format_values(values):
    return (
        "loc=({location_x:.3f}, {location_y:.3f}, {location_z:.3f}) "
        "rot=({rotation_x:.3f}, {rotation_y:.3f}, {rotation_z:.3f}) "
        "scale=({scale_x:.3f}, {scale_y:.3f}, {scale_z:.3f})"
    ).format(**values)


def _run_stage_one(context, global_section, sphere_name):
    if context is None:
        return "Missing pre-resolved attach context."
    if global_section is None:
        return "Missing pre-resolved global_ctrl section. Select global_ctrl channels before running."

    sequence = context.get("sequence")
    bp_binding = context.get("bp_actor_binding")
    skeletal_binding = context.get("skeletal_binding")
    first_frame = int(context.get("start_frame"))
    end_frame = int(context.get("end_frame"))

    if sequence is None or bp_binding is None:
        return "Missing sequence or Blueprint Actor binding from pre-resolved context."

    sphere_binding, sphere_reason = _find_recorder_sphere_binding(sequence, sphere_name, [bp_binding, skeletal_binding])
    if sphere_binding is None:
        return f"Could not find baked recorder_sphere binding after bake: {sphere_reason}"

    _log("----- post-bake stage 1 called -----")
    _log(f"Blueprint Actor binding: {_binding_name(bp_binding)}")
    _log(f"Baked recorder_sphere binding: {_binding_name(sphere_binding)} ({sphere_reason})")
    _log(f"First animation frame: {first_frame}")

    ok, time_attempts = _set_current_frame(first_frame)
    _log(f"Set Sequencer current frame attempts: {time_attempts}")
    if not ok:
        return f"Could not set Sequencer to first frame {first_frame}."
    _refresh_sequencer()

    recorder_values, error = _get_transform_values_from_binding(sphere_binding, first_frame)
    if error:
        return error
    _log(f"First-frame recorder_sphere baked transform: {_format_values(recorder_values)}")

    error = _write_actor_first_frame_transform(bp_binding, first_frame, end_frame, recorder_values)
    if error:
        return f"Blueprint Actor transform reset/copy failed: {error}"
    _log("Cleared Blueprint Actor transform keys and wrote recorder_sphere loc/rot with unit scale at the first frame.")

    error = _clear_global_ctrl_and_write_zero(global_section, first_frame)
    if error:
        return f"global_ctrl transform reset failed: {error}"
    _log("Cleared global_ctrl transform keys and wrote zero loc/rot + unit scale at the first frame.")

    ok, time_attempts = _set_current_frame(first_frame)
    _log(f"Returned Sequencer to first frame attempts: {time_attempts}")
    _refresh_sequencer()
    _log("SUCCESS: post-bake stage 1 completed.")
    return ""


def run(
    bp_actor_name="",
    skeletal_mesh_name="",
    global_ctrl_name="global_ctrl",
    root_bone_name="root",
    sphere_name="recorder_sphere",
    delete_existing=True,
    prefer_selected_global_ctrl_sequence=True,
    frame_increment=1,
    sphere_visual_scale=0.12,
):
    try:
        global attach_base, real_bake
        attach_base = importlib.reload(attach_base)
        real_bake = importlib.reload(real_bake)

        resolver = getattr(attach_base, "_resolve_context", None)
        if resolver is None:
            _log_error("attach_base._resolve_context unavailable")
            return ""

        context, context_error = resolver(
            bp_actor_name,
            skeletal_mesh_name,
            global_ctrl_name,
            prefer_selected_global_ctrl_sequence,
        )
        if context_error:
            _log_error(context_error)
            return ""

        global_section, global_section_reason = _selected_global_ctrl_section()
        _log(f"Pre-resolved global_ctrl section: {global_section_reason}")
        if global_section is None:
            _log_error("Could not resolve selected global_ctrl section before bake.")
            return ""

        bake_result = real_bake.reload_base_and_run(
            bp_actor_name=bp_actor_name,
            skeletal_mesh_name=skeletal_mesh_name,
            global_ctrl_name=global_ctrl_name,
            root_bone_name=root_bone_name,
            sphere_name=sphere_name,
            delete_existing=delete_existing,
            prefer_selected_global_ctrl_sequence=prefer_selected_global_ctrl_sequence,
            bake_recorder_sphere=True,
            frame_increment=frame_increment,
            remove_attach_after_bake=False,
            sphere_visual_scale=sphere_visual_scale,
            write_scale_keys=True,
        )
        if bake_result != "true":
            _log_error("Real bake step failed, so post-bake stage 1 was not run.")
            return ""

        error = _run_stage_one(context, global_section, sphere_name)
        if error:
            _log_error(error)
            return ""

        return "true"
    except Exception:
        _log_error(traceback.format_exc())
        return ""


def reload_base_and_run(**kwargs):
    return run(**kwargs)
