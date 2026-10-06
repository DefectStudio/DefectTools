"""
Attach Snap Stage Two Snapper Probe.

This is a discovery/helper script for the next pipeline stage:
- global_ctrl should be the Snapper child.
- recorder_sphere should be the Snapper parent.
- Snapper should bake All Frames over the shot range.

It does not perform the destructive Snap Animation operation yet. It logs the
available Unreal Python API/classes/menu entries so we can wire the real Snapper
call the same way we found LevelSequenceEditorSubsystem.bake_transform_with_settings.
"""

import importlib
import traceback

import unreal

import flatten_world_position_to_global_ctrl_attach_snap_method as attach_base
import flatten_world_position_to_global_ctrl_attach_snap_stage_one as stage_one


LOG_PREFIX = "[AttachSnapStageTwoSnapperProbe]"


def _log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


def _log_warning(message):
    unreal.log_warning(f"{LOG_PREFIX} Warning: {message}")


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


def _call_result(obj, function_name, *args):
    if obj is None:
        return False, "object is None"
    fn = getattr(obj, function_name, None)
    if fn is None:
        return False, "missing"
    try:
        return True, fn(*args)
    except Exception as exc:
        return False, str(exc)


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


def _binding_name(binding):
    return _safe_call(attach_base, "_binding_name", binding) or _compact_text(binding, 120)


def _class_name(obj):
    return _safe_call(attach_base, "_class_name", obj) or str(type(obj))


def _get_selected_bindings():
    getter = getattr(attach_base, "_get_selected_bindings", None)
    if getter is not None:
        return _as_list(getter())
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    return _as_list(_safe_call(library, "get_selected_bindings"))


def _get_selected_objects():
    getter = getattr(attach_base, "_get_selected_objects", None)
    if getter is not None:
        return _as_list(getter())
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    return _as_list(_safe_call(library, "get_selected_objects"))


def _get_selected_channel_names():
    base_module = getattr(attach_base, "base", None)
    if base_module is not None:
        getter = getattr(base_module, "_get_selected_channel_names", None)
        if getter is not None:
            return _as_list(getter())
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    channels = _as_list(_safe_call(library, "get_selected_channels"))
    names = []
    for channel in channels:
        for attr_name in ("channel_name", "name", "display_name"):
            value = None
            try:
                value = getattr(channel, attr_name)
            except Exception:
                pass
            if value:
                names.append(str(value))
                break
        else:
            value = _safe_call(channel, "get_name") or _safe_call(channel, "get_display_name")
            names.append(str(value or _compact_text(channel, 200)))
    return names


def _get_current_sequence():
    sequence_getter = getattr(attach_base, "_get_target_level_sequence", None)
    if sequence_getter is not None:
        try:
            sequence, reason = sequence_getter(True)
            if sequence is not None:
                return sequence, reason
        except Exception as exc:
            _log_warning(f"attach_base._get_target_level_sequence failed: {exc}")
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    return _safe_call(library, "get_current_level_sequence"), "current editor sequence"


def _track_is_attach(track):
    return "Attach" in _class_name(track)


def _track_is_transform(track):
    class_name = _class_name(track)
    return "TransformTrack" in class_name or "3DTransformTrack" in class_name


def _binding_has_tracks(binding, want_attach=False, want_transform=False):
    has_attach = False
    has_transform = False
    for track in _as_list(_safe_call(binding, "get_tracks")):
        has_attach = has_attach or _track_is_attach(track)
        has_transform = has_transform or _track_is_transform(track)
    if want_attach and not has_attach:
        return False
    if want_transform and not has_transform:
        return False
    return True


def _iter_all_bindings(sequence):
    iterator = getattr(attach_base, "_iter_all_bindings", None)
    if iterator is not None:
        try:
            for binding in iterator(sequence):
                yield binding
            return
        except Exception:
            pass
    stack = list(_as_list(_safe_call(sequence, "get_bindings")))
    seen = set()
    while stack:
        binding = stack.pop(0)
        key = _compact_text(_safe_call(binding, "get_id") or binding)
        if key in seen:
            continue
        seen.add(key)
        yield binding
        stack.extend(_as_list(_safe_call(binding, "get_child_possessables")))
        stack.extend(_as_list(_safe_call(binding, "get_child_spawnables")))


def _find_recorder_sphere_binding(sequence, sphere_name="recorder_sphere"):
    # Prefer a selected binding with the baked sphere's shape.
    for binding in _get_selected_bindings():
        if _binding_has_tracks(binding, want_attach=True, want_transform=True):
            return binding, "selected binding with Attach + Transform tracks"

    candidates = []
    for binding in _iter_all_bindings(sequence):
        if _binding_has_tracks(binding, want_attach=True, want_transform=True):
            candidates.append(binding)

    if not candidates:
        return None, "no binding with Attach + Transform tracks"

    named = [binding for binding in candidates if str(sphere_name).lower() in _binding_name(binding).lower()]
    if named:
        return named[0], "name-matched binding with Attach + Transform tracks"

    return candidates[0], "first binding with Attach + Transform tracks"


def _method_hits(obj, tokens=("snap", "constraint", "constrain", "bake", "parent", "child")):
    hits = []
    try:
        names = dir(obj)
    except Exception:
        return hits
    for name in names:
        if name.startswith("_"):
            continue
        lower = name.lower()
        if any(token in lower for token in tokens):
            hits.append(name)
    return hits


def _log_doc(obj, method_name):
    fn = getattr(obj, method_name, None)
    if fn is None:
        return
    doc = getattr(fn, "__doc__", None)
    if doc:
        _log(f"    DOC {method_name}: {_compact_text(doc, 900)}")


def _object_from_unreal_name(name):
    obj = getattr(unreal, name, None)
    if obj is None:
        return None, "missing"

    # Try editor subsystem instance first for subsystem classes.
    if "Subsystem" in name:
        try:
            subsystem = unreal.get_editor_subsystem(obj)
            if subsystem is not None:
                return subsystem, f"editor subsystem instance of unreal.{name}"
        except Exception as exc:
            return obj, f"class only; get_editor_subsystem failed: {exc}"

    # Try default object for BlueprintFunctionLibrary-style classes.
    try:
        default_object = obj.get_default_object()
        if default_object is not None:
            return default_object, f"default object of unreal.{name}"
    except Exception:
        pass

    return obj, f"unreal.{name}"


def _log_unreal_snapper_api_candidates():
    _log("=" * 72)
    _log("Unreal classes/objects containing snap/constraint/constrain:")
    names = []
    for name in dir(unreal):
        lower = name.lower()
        if "snap" in lower or "constraint" in lower or "constrain" in lower:
            names.append(name)
    _log(f"Found {len(names)} names: {names}")

    known_names = [
        "ConstraintsScriptingLibrary",
        "ConstraintsManager",
        "ConstraintsSubsystem",
        "ConstraintsActor",
        "ConstraintSubsystem",
        "SequencerTools",
        "LevelSequenceEditorSubsystem",
        "LevelSequenceEditorBlueprintLibrary",
        "ControlRigSequencerEditorLibrary",
        "ControlRigSequencerLibrary",
        "ControlRigBlueprintLibrary",
        "ControlRig",
        "TransformableHandle",
        "TransformableControlHandle",
        "TransformableComponentHandle",
        "TransformableActorHandle",
        "TickableTransformConstraint",
        "ParentConstraint",
        "PositionConstraint",
        "RotationConstraint",
        "ScaleConstraint",
    ]

    for name in names + known_names:
        obj, reason = _object_from_unreal_name(name)
        if obj is None:
            continue
        hits = _method_hits(obj)
        if not hits:
            continue
        _log(f"API {name}: {reason} type={type(obj)} hits={hits}")
        for method_name in hits:
            lower = method_name.lower()
            if "snap" in lower or "constraint" in lower or "bake" in lower:
                _log_doc(obj, method_name)


def _log_tool_menu_candidates():
    tool_menus_class = getattr(unreal, "ToolMenus", None)
    if tool_menus_class is None:
        _log("ToolMenus unavailable")
        return
    menus = _safe_call(tool_menus_class, "get")
    if menus is None:
        _log("ToolMenus.get() returned None")
        return

    _log("=" * 72)
    _log(f"ToolMenus methods containing menu/entry/section/execute: {_method_hits(menus, ('menu', 'entry', 'section', 'execute', 'find'))}")

    candidate_menu_names = [
        "LevelSequenceEditor.MainMenu",
        "LevelSequenceEditor.MainMenu.Edit",
        "LevelSequenceEditor.MainMenu.Tools",
        "LevelSequenceEditor.MainMenu.Actions",
        "LevelSequenceEditor.ToolBar",
        "LevelSequenceEditor.ContextMenu",
        "LevelSequenceEditor.ContextMenu.ObjectBinding",
        "LevelSequenceEditor.ContextMenu.ControlRig",
        "LevelSequenceEditor.ContextMenu.Constraint",
        "LevelSequenceEditor.ContextMenu.Snapper",
        "Sequencer.MainMenu",
        "Sequencer.MainMenu.Tools",
        "Sequencer.ContextMenu",
        "Sequencer.ContextMenu.ControlRig",
        "Sequencer.ContextMenu.Constraint",
        "ControlRigEditor.MainMenu",
        "ControlRigEditor.ContextMenu",
        "ControlRigEditor.ContextMenu.Constraint",
    ]

    for menu_name in candidate_menu_names:
        menu = _safe_call(menus, "find_menu", menu_name)
        if menu is None:
            continue
        _log("-" * 72)
        _log(f"MENU FOUND: {menu_name} type={type(menu)}")
        for getter in ("get_sections", "get_entries", "get_menu_entries"):
            result = _safe_call(menu, getter)
            items = _as_list(result)
            if result is None:
                continue
            _log(f"  {getter}: count={len(items)}")
            for item in items:
                text = _compact_text(item, 500)
                lower = text.lower()
                if "snap" in lower or "constraint" in lower or "constrain" in lower or "bake" in lower:
                    _log(f"    POSSIBLE MENU ITEM: {text}")


def _log_context(sequence, sphere_name):
    _log("=" * 72)
    _log(f"Target sequence: {_compact_text(sequence)}")
    selected_bindings = _get_selected_bindings()
    selected_objects = _get_selected_objects()
    selected_channel_names = _get_selected_channel_names()
    _log(f"Selected bindings: {[_binding_name(binding) for binding in selected_bindings]}")
    _log(f"Selected objects: {[ _compact_text(obj, 120) for obj in selected_objects ]}")
    _log(f"Selected channel names: {selected_channel_names}")

    sphere_binding, sphere_reason = _find_recorder_sphere_binding(sequence, sphere_name=sphere_name)
    _log(f"Recorder sphere binding: {_binding_name(sphere_binding) if sphere_binding else '<not found>'} reason={sphere_reason}")

    transform_bindings = []
    for binding in _iter_all_bindings(sequence):
        if _binding_has_tracks(binding, want_transform=True):
            transform_bindings.append(_binding_name(binding))
    _log(f"Transform-capable bindings in sequence: {transform_bindings[:80]}")


def run(run_stage_one_first=False, sphere_name="recorder_sphere"):
    try:
        global attach_base, stage_one
        attach_base = importlib.reload(attach_base)
        stage_one = importlib.reload(stage_one)

        if run_stage_one_first:
            _log("Running Stage One first before Snapper probe.")
            result = stage_one.reload_base_and_run(sphere_name=sphere_name)
            _log(f"Stage One result={result!r}")
            if result != "true":
                _log_error("Stage One failed; continuing with discovery using current Sequencer state.")

        sequence, reason = _get_current_sequence()
        _log(f"Resolved current sequence reason: {reason}")
        if sequence is None:
            _log_error("Could not resolve a target Level Sequence.")
            return ""

        _log_context(sequence, sphere_name)
        _log_unreal_snapper_api_candidates()
        _log_tool_menu_candidates()

        _log("=" * 72)
        _log("Probe complete. Paste this output so the exact Snapper API/command can be wired into Stage Two.")
        return "true"
    except Exception:
        _log_error(traceback.format_exc())
        return ""


def reload_and_run(**kwargs):
    return run(**kwargs)
