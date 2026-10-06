"""
Probe the Control Rig Snapper helper structs needed by Stage Two.

Run from Unreal Python after Stage One has succeeded. This script is diagnostic only.
"""

import importlib
import traceback

import unreal

import flatten_world_position_to_global_ctrl_attach_snap_method as attach_base
import flatten_world_position_to_global_ctrl_attach_snap_stage_one as stage_one


LOG_PREFIX = "[SnapperStructProbe]"


def _log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


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


def _compact_text(value, max_length=280):
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


def _safe_get_editor_property(obj, prop_name):
    if obj is None:
        return None
    try:
        return obj.get_editor_property(prop_name)
    except Exception:
        return None


def _try_set_editor_property(obj, prop_name, value):
    if obj is None:
        return False, "object is None"
    try:
        obj.set_editor_property(prop_name, value)
        readback = _safe_get_editor_property(obj, prop_name)
        return True, f"OK readback={_compact_text(readback, 180)}"
    except Exception as exc:
        return False, str(exc)


def _binding_name(binding):
    return _safe_call(attach_base, "_binding_name", binding) or _compact_text(binding, 120)


def _binding_key(binding):
    value = _safe_call(binding, "get_id") or _safe_call(binding, "get_binding_id")
    return _compact_text(value or binding, 180)


def _class_name(obj):
    return _safe_call(attach_base, "_class_name", obj) or str(type(obj))


def _track_is_attach(track):
    return "Attach" in _class_name(track)


def _track_is_transform(track):
    name = _class_name(track)
    return "TransformTrack" in name or "3DTransformTrack" in name


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


def _find_recorder_sphere_binding(sequence, sphere_name, excluded_bindings=()):
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
        return candidates[0], "single binding with Attach + Transform tracks"
    if len(candidates) > 1:
        name_matches = [binding for binding in candidates if str(sphere_name).lower() in _binding_name(binding).lower()]
        if name_matches:
            return name_matches[0], "name matched binding with Attach + Transform tracks"
        return candidates[0], "first binding with Attach + Transform tracks"
    return None, "no recorder sphere style binding found"


def _resolve_sequence_and_context(global_ctrl_name, sphere_name):
    resolver = getattr(attach_base, "_resolve_context", None)
    context = None
    if resolver is not None:
        try:
            context, context_error = resolver("", "", global_ctrl_name, True)
            if context_error:
                _log(f"resolve_context warning: {context_error}")
        except Exception as exc:
            _log(f"resolve_context failed: {exc}")
            context = None
    sequence = context.get("sequence") if context else None
    if sequence is None:
        sequence = _safe_call(getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None), "get_current_level_sequence")
    return sequence, context


def _try_construct(class_name):
    cls = getattr(unreal, class_name, None)
    _log("=" * 74)
    _log(f"{class_name}: {cls}")
    if cls is None:
        return None
    try:
        obj = cls()
        _log(f"constructed: {_compact_text(obj, 500)}")
    except Exception as exc:
        _log(f"construct failed: {exc}")
        obj = None
    try:
        _log("__doc__:")
        _log(cls.__doc__)
    except Exception as exc:
        _log(f"doc failed: {exc}")
    if obj is not None:
        _log("dir hits:")
        for name in dir(obj):
            low = name.lower()
            if any(token in low for token in [
                "actor", "control", "rig", "binding", "handle", "component", "object",
                "socket", "name", "transform", "world", "parent", "child", "selection"
            ]):
                _log("  " + name)
        for prop_name in ("actor", "component", "control_rig", "control_names", "control_name", "binding", "binding_id", "constraint_binding_id", "object_binding", "socket_name"):
            value = _safe_get_editor_property(obj, prop_name)
            if value is not None:
                _log(f"property readback {prop_name}={_compact_text(value)}")
    return obj


def _get_bound_objects(sequence, binding):
    output = []
    binding_id = None
    extensions = getattr(unreal, "MovieSceneSequenceExtensions", None)
    if extensions is not None:
        for args in ((sequence, binding), (binding,)):
            try:
                binding_id = extensions.get_binding_id(*args)
                break
            except Exception:
                pass
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    if library is not None:
        for args in ((binding_id,), (binding,)):
            if args[0] is None:
                continue
            try:
                result = library.get_bound_objects(*args)
                if result:
                    output.extend(_as_list(result))
            except Exception as exc:
                _log(f"get_bound_objects{args} failed: {exc}")
    return output, binding_id


def _try_set_object_properties(label, obj, candidates):
    if obj is None:
        return
    _log(f"Trying property assignments for {label}:")
    for prop_name, value in candidates:
        ok, result = _try_set_editor_property(obj, prop_name, value)
        _log(f"  set {prop_name}={_compact_text(value, 120)} -> {'OK' if ok else 'failed'} {result}")


def run(global_ctrl_name="global_ctrl", sphere_name="recorder_sphere"):
    try:
        global attach_base, stage_one
        attach_base = importlib.reload(attach_base)
        stage_one = importlib.reload(stage_one)

        sequence, context = _resolve_sequence_and_context(global_ctrl_name, sphere_name)
        if sequence is None:
            _log_error("No Level Sequence could be resolved.")
            return ""

        bp_binding = context.get("bp_actor_binding") if context else None
        skeletal_binding = context.get("skeletal_binding") if context else None
        sphere_binding, sphere_reason = _find_recorder_sphere_binding(sequence, sphere_name, [bp_binding, skeletal_binding])

        _log("=" * 74)
        _log(f"Sequence: {sequence}")
        _log(f"Blueprint binding: {_binding_name(bp_binding) if bp_binding else '<none>'}")
        _log(f"Skeletal binding: {_binding_name(skeletal_binding) if skeletal_binding else '<none>'}")
        _log(f"Recorder sphere binding: {_binding_name(sphere_binding) if sphere_binding else '<none>'} reason={sphere_reason}")

        bound_objects, sphere_binding_id = _get_bound_objects(sequence, sphere_binding) if sphere_binding is not None else ([], None)
        _log(f"Recorder sphere binding id: {_compact_text(sphere_binding_id, 400)}")
        _log(f"Recorder sphere bound objects: {[ _compact_text(obj, 180) for obj in bound_objects ]}")
        sphere_actor = bound_objects[0] if bound_objects else None
        root_component = _safe_call(sphere_actor, "get_root_component") if sphere_actor is not None else None
        _log(f"Recorder sphere actor object: {_compact_text(sphere_actor, 400)}")
        _log(f"Recorder sphere root component: {_compact_text(root_component, 400)}")

        actor_struct = _try_construct("ActorForWorldTransforms")
        control_rig_struct = _try_construct("ControlRigForWorldTransforms")
        _try_construct("ControlRigSnapperSelection")
        _try_construct("ControlRigSnapSettings")

        if actor_struct is not None:
            _try_set_object_properties(
                "ActorForWorldTransforms",
                actor_struct,
                [
                    ("actor", sphere_actor),
                    ("object", sphere_actor),
                    ("component", root_component),
                    ("binding", sphere_binding),
                    ("binding_id", sphere_binding_id),
                    ("constraint_binding_id", sphere_binding_id),
                ],
            )

        # Try to locate the selected global_ctrl's ControlRig object from the selected section.
        control_rig = None
        global_section = None
        base_module = getattr(attach_base, "base", None)
        getter = getattr(base_module, "_get_selected_global_ctrl_section", None) if base_module else None
        if getter is not None:
            try:
                global_section, channel_names, asset_path = getter()
                _log(f"Selected global_ctrl section: {global_section} channels={channel_names} asset_path={asset_path}")
                control_rig = _safe_get_editor_property(global_section, "control_rig") or _safe_get_editor_property(global_section, "ControlRig")
            except Exception as exc:
                _log(f"selected global_ctrl section/control rig lookup failed: {exc}")
        _log(f"Resolved global_ctrl ControlRig: {_compact_text(control_rig, 400)}")

        if control_rig_struct is not None:
            _try_set_object_properties(
                "ControlRigForWorldTransforms",
                control_rig_struct,
                [
                    ("control_rig", control_rig),
                    ("control_name", unreal.Name(global_ctrl_name)),
                    ("control_names", [unreal.Name(global_ctrl_name)]),
                    ("name", unreal.Name(global_ctrl_name)),
                    ("names", [unreal.Name(global_ctrl_name)]),
                ],
            )

        _log("Probe complete. Paste this output so Stage Two can construct the Snapper selections safely.")
        return "true"
    except Exception:
        _log_error(traceback.format_exc())
        return ""


def reload_and_run(**kwargs):
    return run(**kwargs)
