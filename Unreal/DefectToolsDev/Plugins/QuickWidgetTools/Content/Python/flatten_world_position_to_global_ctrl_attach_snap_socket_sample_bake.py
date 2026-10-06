"""
Attach Snap Socket Sample Bake.

This avoids both problematic bake routes discovered during testing:
- Unreal LevelSequenceEditorSubsystem.bake_transform_with_settings creates offset keys for this case.
- Sampling the recorder_sphere actor after an Attach track only reads the spawnable actor/local state in this case.

Instead, this script:
1. Creates the proven live recorder_sphere Attach track.
2. Scrubs the shot frame-by-frame.
3. Samples Bungie_Char.root directly in WORLD space.
4. Writes those world-space samples onto recorder_sphere transform keys.
5. Removes the live Attach track so only the baked transform keys drive recorder_sphere.

It does not edit the Blueprint Actor or global_ctrl.
"""

import importlib
import traceback

import unreal

import flatten_world_position_to_global_ctrl_attach_snap_method as attach_snap


LOG_PREFIX = "[AttachSnapSocketSampleBake]"


def _log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


def _log_error(message):
    unreal.log_error(f"{LOG_PREFIX} Error: {message}")


def _safe_call(obj, function_name, *args):
    if obj is None:
        return None
    fn = getattr(obj, function_name, None)
    if fn is None:
        return None
    try:
        return fn(*args)
    except Exception:
        return None


def _safe_get_editor_property(obj, property_name):
    if obj is None:
        return None
    try:
        return obj.get_editor_property(property_name)
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


def _compact(value, max_length=240):
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


def _object_name(obj):
    return _safe_call(attach_snap, "_object_name", obj) or _safe_call(obj, "get_name") or _compact(obj, 120)


def _binding_name(binding):
    return _safe_call(attach_snap, "_binding_name", binding) or _compact(binding, 120)


def _class_name(obj):
    cls = _safe_call(obj, "get_class")
    return str(_safe_call(cls, "get_name") or type(obj))


def _refresh_sequencer():
    refresher = getattr(attach_snap, "_refresh_sequencer", None)
    if refresher:
        return refresher()
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    attempts = []
    for fn_name in ("refresh_current_level_sequence", "refresh_current_level_sequence_editor", "refresh_current_level_sequence_player"):
        fn = getattr(library, fn_name, None) if library else None
        if fn is None:
            attempts.append(f"{fn_name} -> missing")
            continue
        try:
            fn()
            attempts.append(f"{fn_name} -> OK")
            return True, attempts
        except Exception as exc:
            attempts.append(f"{fn_name} -> {exc}")
    return False, attempts


def _set_current_frame(frame):
    setter = getattr(attach_snap, "_set_current_frame", None)
    if setter:
        return setter(frame)
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    attempts = []
    frame_number = _make_frame_number(frame)
    for fn_name, args in (
        ("set_current_time", (frame,)),
        ("set_current_time", (frame_number,)),
        ("set_current_frame", (frame,)),
        ("set_current_frame", (frame_number,)),
    ):
        fn = getattr(library, fn_name, None) if library else None
        if fn is None:
            attempts.append(f"{fn_name} -> missing")
            continue
        try:
            fn(*args)
            attempts.append(f"{fn_name} -> OK")
            return True, attempts
        except Exception as exc:
            attempts.append(f"{fn_name} -> {exc}")
    return False, attempts


def _make_frame_number(frame):
    try:
        return unreal.FrameNumber(int(frame))
    except Exception:
        return int(frame)


def _rotator_to_values(rotator):
    if rotator is None:
        return None
    return {
        "rotation_x": float(getattr(rotator, "roll", 0.0)),
        "rotation_y": float(getattr(rotator, "pitch", 0.0)),
        "rotation_z": float(getattr(rotator, "yaw", 0.0)),
    }


def _vector_to_location_values(vector):
    if vector is None:
        return None
    return {
        "location_x": float(getattr(vector, "x", 0.0)),
        "location_y": float(getattr(vector, "y", 0.0)),
        "location_z": float(getattr(vector, "z", 0.0)),
    }


def _vector_to_scale_values(vector):
    if vector is None:
        return {"scale_x": 1.0, "scale_y": 1.0, "scale_z": 1.0}
    return {
        "scale_x": float(getattr(vector, "x", 1.0)),
        "scale_y": float(getattr(vector, "y", 1.0)),
        "scale_z": float(getattr(vector, "z", 1.0)),
    }


def _transform_to_values(transform):
    if transform is None:
        return None

    location = None
    rotation = None
    scale = None

    for getter in ("get_location", "get_translation"):
        location = _safe_call(transform, getter)
        if location is not None:
            break
    if location is None:
        location = _safe_get_editor_property(transform, "translation") or _safe_get_editor_property(transform, "location")

    rotation = _safe_call(transform, "rotator") or _safe_call(transform, "get_rotation")
    if rotation is not None and "Quat" in _compact(type(rotation)):
        rotation = _safe_call(rotation, "rotator")
    if rotation is None:
        rotation = _safe_get_editor_property(transform, "rotation")
        if rotation is not None and "Quat" in _compact(type(rotation)):
            rotation = _safe_call(rotation, "rotator")

    for getter in ("get_scale3d", "get_scale_3d", "get_scale"):
        scale = _safe_call(transform, getter)
        if scale is not None:
            break
    if scale is None:
        scale = _safe_get_editor_property(transform, "scale3d") or _safe_get_editor_property(transform, "scale")

    location_values = _vector_to_location_values(location)
    rotation_values = _rotator_to_values(rotation)
    scale_values = _vector_to_scale_values(scale)
    if location_values is None or rotation_values is None:
        return None
    result = {}
    result.update(location_values)
    result.update(rotation_values)
    result.update(scale_values)
    return result


def _sample_socket_world_values(skeletal_component, root_bone_name):
    root_name = root_bone_name or "root"
    attempts = []

    space_enum = getattr(unreal, "RelativeTransformSpace", None)
    world_spaces = []
    if space_enum is not None:
        for attr in ("RTS_WORLD", "WORLD", "RTS_World"):
            value = getattr(space_enum, attr, None)
            if value is not None:
                world_spaces.append(value)
    world_spaces.append(None)

    for space in world_spaces:
        for socket_arg in (unreal.Name(root_name), str(root_name)):
            try:
                if space is None:
                    transform = skeletal_component.get_socket_transform(socket_arg)
                    attempts.append(f"get_socket_transform({socket_arg}) -> {_compact(transform)}")
                else:
                    transform = skeletal_component.get_socket_transform(socket_arg, space)
                    attempts.append(f"get_socket_transform({socket_arg}, {space}) -> {_compact(transform)}")
                values = _transform_to_values(transform)
                if values is not None:
                    return values, attempts
            except Exception as exc:
                attempts.append(f"get_socket_transform({socket_arg}, {space}) -> {exc}")

    for socket_arg in (unreal.Name(root_name), str(root_name)):
        location = _safe_call(skeletal_component, "get_socket_location", socket_arg)
        rotation = _safe_call(skeletal_component, "get_socket_rotation", socket_arg)
        attempts.append(f"get_socket_location/rotation({socket_arg}) -> loc={_compact(location)} rot={_compact(rotation)}")
        location_values = _vector_to_location_values(location)
        rotation_values = _rotator_to_values(rotation)
        if location_values is not None and rotation_values is not None:
            result = {}
            result.update(location_values)
            result.update(rotation_values)
            result.update({"scale_x": 1.0, "scale_y": 1.0, "scale_z": 1.0})
            return result, attempts

    return None, attempts


def _iter_all_bindings(sequence):
    iterator = getattr(attach_snap, "_iter_all_bindings", None)
    if iterator is not None:
        try:
            for binding in iterator(sequence):
                yield binding
            return
        except Exception as exc:
            _log(f"attach_snap._iter_all_bindings failed; fallback to top-level get_bindings. Error={exc}")
    for binding in _as_list(_safe_call(sequence, "get_bindings")):
        yield binding


def _binding_tracks(binding):
    return _as_list(_safe_call(binding, "get_tracks"))


def _track_is_attach(track):
    text = f"{_class_name(track)} {_compact(track, 240)}"
    return "Attach" in text or "3DAttach" in text


def _track_is_transform(track):
    text = f"{_class_name(track)} {_compact(track, 240)}"
    return "TransformTrack" in text or "3DTransformTrack" in text


def _binding_has_attach_track(binding):
    return any(_track_is_attach(track) for track in _binding_tracks(binding))


def _binding_track_summary(binding):
    return [_class_name(track) for track in _binding_tracks(binding)]


def _remove_attach_tracks(binding):
    attempts = []
    removed = 0
    remover = getattr(attach_snap, "_remove_track", None)
    for track in list(_binding_tracks(binding)):
        class_name = _class_name(track)
        if not _track_is_attach(track):
            continue
        if remover is not None and remover(binding, track):
            attempts.append(f"attach_snap._remove_track({class_name}) -> OK")
            removed += 1
            continue
        fn = getattr(binding, "remove_track", None)
        if fn is None:
            attempts.append(f"binding.remove_track({class_name}) -> missing")
            continue
        try:
            fn(track)
            attempts.append(f"binding.remove_track({class_name}) -> OK")
            removed += 1
        except Exception as exc:
            attempts.append(f"binding.remove_track({class_name}) -> {exc}")
    return removed, attempts


def _find_sphere_binding(sequence, sphere_name):
    attempts = []
    bindings = list(_iter_all_bindings(sequence))
    attempts.append(f"all bindings={[ _binding_name(binding) for binding in bindings ]}")

    # First try the display/name path. This is clean when Unreal keeps the requested spawnable name.
    finder = getattr(attach_snap, "_find_binding_by_name", None)
    if finder is not None:
        try:
            binding = finder(sequence, sphere_name, prefer_selected=False)
            attempts.append(f"attach_snap._find_binding_by_name({sphere_name!r}) -> {_binding_name(binding) if binding else '<none>'}")
            if binding is not None:
                return binding, "name lookup", attempts
        except Exception as exc:
            attempts.append(f"attach_snap._find_binding_by_name({sphere_name!r}) -> {exc}")

    exact = [binding for binding in bindings if _binding_name(binding) == sphere_name]
    if exact:
        return exact[-1], "exact binding name", attempts

    contains = [binding for binding in bindings if sphere_name.lower() in _binding_name(binding).lower()]
    if contains:
        return contains[-1], "contains binding name", attempts

    # In UE spawnables can display as Static Mesh Actor even after set_display_name().
    # The reliable signature of the fresh recorder_sphere is that it has the Attach track we just made.
    attach_candidates = [binding for binding in bindings if _binding_has_attach_track(binding)]
    attempts.append(
        "attach candidates=" + str([
            f"{_binding_name(binding)} tracks={_binding_track_summary(binding)}" for binding in attach_candidates
        ])
    )
    if attach_candidates:
        return attach_candidates[-1], "binding with Attach track", attempts

    transform_candidates = [binding for binding in bindings if any(_track_is_transform(track) for track in _binding_tracks(binding))]
    attempts.append(
        "transform candidates=" + str([
            f"{_binding_name(binding)} tracks={_binding_track_summary(binding)}" for binding in transform_candidates
        ])
    )
    return None, "no name/attach-track match", attempts


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
        global attach_snap
        attach_snap = importlib.reload(attach_snap)

        _log("----- socket sample bake called -----")
        _log("This pass creates the proven live Attach setup, then samples the skeletal socket/root directly in WORLD space.")
        _log("It does not edit Blueprint Actor keys, global_ctrl keys, or run Snapper.")

        setup_result = attach_snap.run(
            bp_actor_name=bp_actor_name,
            skeletal_mesh_name=skeletal_mesh_name,
            global_ctrl_name=global_ctrl_name,
            root_bone_name=root_bone_name,
            sphere_name=sphere_name,
            delete_existing=delete_existing,
            prefer_selected_global_ctrl_sequence=prefer_selected_global_ctrl_sequence,
            bake_recorder_sphere=False,
            frame_increment=frame_increment,
            remove_attach_after_bake=True,
            sphere_visual_scale=sphere_visual_scale,
            write_scale_keys=False,
        )
        if setup_result != "true":
            _log_error("Live Attach setup failed; socket sample bake was not run.")
            return ""

        context, context_error = attach_snap._resolve_context(
            bp_actor_name,
            skeletal_mesh_name,
            global_ctrl_name,
            prefer_selected_global_ctrl_sequence,
        )
        if context_error:
            _log_error(context_error)
            return ""

        sequence = context["sequence"]
        skeletal_component = context["skeletal_component"]
        start_frame = int(context["start_frame"])
        end_frame = int(context["end_frame"])
        step = max(1, int(frame_increment))

        sphere_binding, sphere_reason, sphere_attempts = _find_sphere_binding(sequence, sphere_name)
        _log(f"Recorder sphere binding lookup reason={sphere_reason} attempts={sphere_attempts}")
        _log(f"Resolved recorder_sphere binding after setup: {_binding_name(sphere_binding) if sphere_binding else '<none>'}")
        if sphere_binding is None:
            _log_error("Could not find recorder_sphere binding after live Attach setup.")
            return ""

        samples = []
        last_time_attempts = []
        last_refresh_attempts = []
        last_socket_attempts = []
        for frame in range(start_frame, end_frame, step):
            ok, last_time_attempts = _set_current_frame(frame)
            if not ok:
                _log_error(f"Could not set Sequencer frame {frame}. Attempts={last_time_attempts}")
                return ""
            _ok, last_refresh_attempts = _refresh_sequencer()
            values, last_socket_attempts = _sample_socket_world_values(skeletal_component, root_bone_name)
            if values is None:
                _log_error(f"Could not sample {root_bone_name} world transform at frame {frame}. Attempts={last_socket_attempts}")
                return ""
            samples.append((frame, values))

        _log(f"Socket-world sampled {len(samples)} frame(s). First={samples[0] if samples else None} Last={samples[-1] if samples else None}")
        _log(f"Last frame time attempts={last_time_attempts}")
        _log(f"Last refresh attempts={last_refresh_attempts}")
        _log(f"Last socket sample attempts={last_socket_attempts}")

        error = attach_snap._write_transform_keys(
            sphere_binding,
            samples,
            start_frame,
            end_frame,
            write_scale_keys=False,
        )
        if error:
            _log_error(error)
            return ""

        removed, remove_attempts = _remove_attach_tracks(sphere_binding)
        _log(f"Attach track removal after socket-world key write: removed={removed} attempts={remove_attempts}")
        _refresh_sequencer()
        _set_current_frame(start_frame)

        _log("SUCCESS: recorder_sphere was baked from direct skeletal socket/root WORLD samples.")
        _log("Expected state: recorder_sphere has baked Transform keys, live Attach track is removed, Blueprint Actor/global_ctrl are untouched.")
        return "true"
    except Exception:
        _log_error(traceback.format_exc())
        return ""


def reload_and_run(**kwargs):
    return run(**kwargs)
