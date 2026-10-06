"""
Attach Snap Method

Creates a spawnable recorder_sphere in the selected global_ctrl ANM subsequence,
attaches it to the selected Blueprint Actor's selected SkeletalMeshComponent root
bone/socket, and can optionally bake the attached sphere onto transform keys.

Default behavior is setup-only so the live Attach track can be inspected first.

Selection workflow:
- Select the Blueprint Actor binding/actor.
- Select the Skeletal Mesh binding/component under that Blueprint Actor.
- Select the Control Rig global_ctrl channels/keys so the ANM subsequence can be resolved.
"""

import traceback
import unreal

try:
    import flatten_world_position_to_global_ctrl as base
except Exception:
    base = None

LOG_PREFIX = "[AttachSnapMethod]"
DEFAULT_SPHERE_NAME = "recorder_sphere"
LOCATION_KEYS = ("location_x", "location_y", "location_z")
ROTATION_KEYS = ("rotation_x", "rotation_y", "rotation_z")
SCALE_KEYS = ("scale_x", "scale_y", "scale_z")
TRANSFORM_KEYS = LOCATION_KEYS + ROTATION_KEYS + SCALE_KEYS


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


def _call_ok(obj, function_name, *args):
    if obj is None:
        return False, "object is None"
    function = getattr(obj, function_name, None)
    if function is None:
        return False, "missing"
    try:
        function(*args)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _safe_get_editor_property(obj, property_name):
    if obj is None:
        return None
    try:
        return obj.get_editor_property(property_name)
    except Exception:
        return None


def _safe_set_editor_property(obj, property_name, value):
    if obj is None:
        return False
    try:
        obj.set_editor_property(property_name, value)
        return True
    except Exception:
        return False


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [value]
    try:
        return list(value)
    except Exception:
        return [value]


def _compact_text(value, max_length=300):
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
    if obj is None:
        return ""
    for function_name in ("get_actor_label", "get_name", "get_display_name"):
        value = _safe_call(obj, function_name)
        if value:
            return str(value)
    for property_name in ("name", "display_name"):
        value = _safe_get_editor_property(obj, property_name)
        if value:
            return str(value)
    return _compact_text(obj, 120)


def _class_name(obj):
    if obj is None:
        return ""
    unreal_class = _safe_call(obj, "get_class")
    class_name = _safe_call(unreal_class, "get_name")
    return str(class_name or type(obj))


def _normalize(value):
    text = str(value or "").lower().strip()
    for char in " \\/:;,.[]{}()<>|?*\"'`~!@#$%^&+=-":
        text = text.replace(char, "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


def _name_matches(value, target):
    left = _normalize(value)
    right = _normalize(target)
    return bool(left and right and (left == right or left in right or right in left))


def _get_selected_bindings():
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    return _as_list(_safe_call(library, "get_selected_bindings"))


def _get_selected_objects():
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    return _as_list(_safe_call(library, "get_selected_objects"))


def _get_selected_level_actors():
    editor_level_library = getattr(unreal, "EditorLevelLibrary", None)
    actors = _safe_call(editor_level_library, "get_selected_level_actors")
    if actors is not None:
        return _as_list(actors)
    subsystem_class = getattr(unreal, "EditorActorSubsystem", None)
    subsystem = _safe_call(unreal, "get_editor_subsystem", subsystem_class) if subsystem_class is not None else None
    return _as_list(_safe_call(subsystem, "get_selected_level_actors"))


def _get_all_level_actors():
    editor_level_library = getattr(unreal, "EditorLevelLibrary", None)
    actors = _safe_call(editor_level_library, "get_all_level_actors")
    if actors is not None:
        return _as_list(actors)
    subsystem_class = getattr(unreal, "EditorActorSubsystem", None)
    subsystem = _safe_call(unreal, "get_editor_subsystem", subsystem_class) if subsystem_class is not None else None
    return _as_list(_safe_call(subsystem, "get_all_level_actors"))


def _sequence_from_selected_global_ctrl():
    if base is None:
        return None, "base helper unavailable"
    get_section = getattr(base, "_get_selected_global_ctrl_section", None)
    load_sequence = getattr(base, "_load_sequence_from_asset_path", None)
    if get_section is None or load_sequence is None:
        return None, "base selected-section helpers unavailable"
    try:
        _section, selected_channel_names, asset_path = get_section()
    except Exception as exc:
        return None, f"selected global_ctrl lookup failed: {exc}"
    if not asset_path:
        return None, "no selected global_ctrl sequence asset path"
    sequence = load_sequence(asset_path)
    if sequence is None:
        return None, f"could not load selected global_ctrl sequence: {asset_path}"
    return sequence, f"selected_global_ctrl_sequence asset={asset_path} channels={selected_channel_names or []}"


def _get_target_level_sequence(prefer_selected_global_ctrl_sequence=True):
    if prefer_selected_global_ctrl_sequence:
        sequence, reason = _sequence_from_selected_global_ctrl()
        if sequence is not None:
            return sequence, reason
        _log_warning(f"Could not resolve selected global_ctrl subsequence; fallback will use current editor sequence. Reason: {reason}")
    sequence = _safe_call(base, "_get_current_level_sequence") if base is not None else None
    if sequence is None:
        library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
        sequence = _safe_call(library, "get_current_level_sequence")
    if sequence is not None:
        return sequence, "current_editor_sequence fallback"
    return None, "no target sequence found"


def _iter_all_bindings(sequence):
    if sequence is None:
        return
    if base is not None:
        try:
            for binding in base._iter_all_bindings(sequence):
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


def _binding_name(binding):
    if binding is None:
        return ""
    if base is not None:
        try:
            return str(base._binding_name(binding))
        except Exception:
            pass
    for function_name in ("get_name", "get_display_name"):
        value = _safe_call(binding, function_name)
        if value:
            return str(value)
    return _compact_text(binding, 120)


def _binding_guid(binding):
    for function_name in ("get_id", "get_binding_id"):
        value = _safe_call(binding, function_name)
        if value is not None:
            return value
    return None


def _binding_id_details(binding_id):
    details = []
    for property_name in ("guid", "Guid", "space", "Space", "resolve_parent_index", "ResolveParentIndex"):
        value = _safe_get_editor_property(binding_id, property_name)
        if value is not None:
            details.append(f"{property_name}={_compact_text(value)}")
    return details


def _make_movie_scene_object_binding_id(sequence, binding):
    attempts = [f"binding name={_binding_name(binding)!r} guid={_compact_text(_binding_guid(binding))}"]
    extensions = getattr(unreal, "MovieSceneSequenceExtensions", None)
    if extensions is not None:
        methods = [name for name in dir(extensions) if "binding" in name.lower()]
        attempts.append(f"MovieSceneSequenceExtensions binding methods={methods}")
        get_binding_id = getattr(extensions, "get_binding_id", None)
        if get_binding_id is not None:
            for label, args in (("binding", (binding,)), ("sequence,binding", (sequence, binding))):
                try:
                    value = get_binding_id(*args)
                    attempts.append(f"MovieSceneSequenceExtensions.get_binding_id({label}) -> {type(value)} {_compact_text(value)}")
                    if value is not None and "MovieSceneObjectBindingID" in _compact_text(type(value)):
                        return value, attempts
                except Exception as exc:
                    attempts.append(f"MovieSceneSequenceExtensions.get_binding_id({label}) -> {exc}")
    guid = _binding_guid(binding)
    if guid is None:
        return None, attempts
    binding_id_class = getattr(unreal, "MovieSceneObjectBindingID", None)
    if binding_id_class is None:
        attempts.append("unreal.MovieSceneObjectBindingID unavailable")
        return None, attempts
    try:
        binding_id = binding_id_class()
    except Exception as exc:
        attempts.append(f"MovieSceneObjectBindingID() -> {exc}")
        return None, attempts
    for property_name in ("guid", "Guid"):
        if _safe_set_editor_property(binding_id, property_name, guid):
            attempts.append(f"MovieSceneObjectBindingID.{property_name}={_compact_text(guid)} -> OK")
            return binding_id, attempts
        attempts.append(f"MovieSceneObjectBindingID.{property_name}={_compact_text(guid)} -> failed")
    return None, attempts


def _find_binding_by_name(sequence, target_name, prefer_selected=True):
    if sequence is None or not target_name:
        return None
    selected = _get_selected_bindings() if prefer_selected else []
    selected_matches = [binding for binding in selected if _name_matches(_binding_name(binding), target_name)]
    if len(selected_matches) == 1:
        return selected_matches[0]
    if len(selected_matches) > 1:
        _log_warning(f"Multiple selected bindings matched {target_name!r}; using first: {_binding_name(selected_matches[0])}")
        return selected_matches[0]
    exact = []
    contains = []
    target = _normalize(target_name)
    for binding in _iter_all_bindings(sequence):
        name = _normalize(_binding_name(binding))
        if name == target:
            exact.append(binding)
        elif target and (target in name or name in target):
            contains.append(binding)
    matches = exact if exact else contains
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        _log_warning(f"Multiple Sequencer bindings matched {target_name!r}; using first: {_binding_name(matches[0])}")
        return matches[0]
    return None


def _binding_has_child(parent_binding, child_binding):
    if parent_binding is None or child_binding is None:
        return False
    child_guid = _compact_text(_binding_guid(child_binding))
    stack = []
    stack.extend(_as_list(_safe_call(parent_binding, "get_child_possessables")))
    stack.extend(_as_list(_safe_call(parent_binding, "get_child_spawnables")))
    seen = set()
    while stack:
        binding = stack.pop(0)
        key = _compact_text(_binding_guid(binding))
        if key in seen:
            continue
        seen.add(key)
        if key == child_guid:
            return True
        stack.extend(_as_list(_safe_call(binding, "get_child_possessables")))
        stack.extend(_as_list(_safe_call(binding, "get_child_spawnables")))
    return False


def _selected_parent_child_binding_pair():
    selected = [binding for binding in _get_selected_bindings() if binding is not None]
    for parent in selected:
        for child in selected:
            if parent is not child and _binding_has_child(parent, child):
                return parent, child
    return None, None


def _find_level_actor_by_name(actor_name):
    selected = _get_selected_level_actors()
    if not actor_name:
        return selected[0] if len(selected) == 1 else None
    selected_matches = [
        actor for actor in selected
        if _name_matches(_object_name(actor), actor_name) or _name_matches(_safe_call(actor, "get_name"), actor_name)
    ]
    if selected_matches:
        return selected_matches[0]
    exact = []
    contains = []
    target = _normalize(actor_name)
    for actor in _get_all_level_actors():
        names = [_normalize(_object_name(actor)), _normalize(_safe_call(actor, "get_name"))]
        if target in names:
            exact.append(actor)
        elif any(target in name or name in target for name in names if name):
            contains.append(actor)
    matches = exact if exact else contains
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        _log_warning(f"Multiple level actors matched {actor_name!r}; using first: {_object_name(matches[0])}")
        return matches[0]
    return None


def _get_actor_components(actor, component_class):
    components = _safe_call(actor, "get_components_by_class", component_class)
    if components is not None:
        return _as_list(components)
    output = []
    for component in _as_list(_safe_call(actor, "get_components")):
        try:
            if isinstance(component, component_class):
                output.append(component)
        except Exception:
            pass
    return output


def _find_skeletal_mesh_component(bp_actor, skeletal_mesh_name):
    skeletal_class = getattr(unreal, "SkeletalMeshComponent", None)
    if skeletal_class is None:
        return None, "unreal.SkeletalMeshComponent is unavailable."
    components = _get_actor_components(bp_actor, skeletal_class)
    if not components:
        return None, f"No SkeletalMeshComponent found under actor {_object_name(bp_actor)}."
    for selected in _get_selected_objects():
        try:
            is_skeletal = isinstance(selected, skeletal_class)
        except Exception:
            is_skeletal = False
        if is_skeletal and selected in components:
            if not skeletal_mesh_name or _name_matches(_object_name(selected), skeletal_mesh_name) or _name_matches(_safe_call(selected, "get_name"), skeletal_mesh_name):
                return selected, ""
    if skeletal_mesh_name:
        matches = [
            component for component in components
            if _name_matches(_object_name(component), skeletal_mesh_name) or _name_matches(_safe_call(component, "get_name"), skeletal_mesh_name)
        ]
        if len(matches) == 1:
            return matches[0], ""
        if len(matches) > 1:
            _log_warning(f"Multiple SkeletalMeshComponents matched {skeletal_mesh_name!r}; using first: {_object_name(matches[0])}")
            return matches[0], ""
        return None, f"No SkeletalMeshComponent matched {skeletal_mesh_name!r}. Available: {[_object_name(component) for component in components]}"
    if len(components) == 1:
        return components[0], ""
    return None, f"Multiple SkeletalMeshComponents found. Select one in Sequencer or pass skeletal_mesh_name. Available: {[_object_name(component) for component in components]}"


def _binding_matches_component(binding, component):
    if binding is None or component is None:
        return False
    binding_name = _binding_name(binding)
    return _name_matches(binding_name, _object_name(component)) or _name_matches(binding_name, _safe_call(component, "get_name"))


def _find_binding_for_component(sequence, component, preferred_name=""):
    selected_matches = [binding for binding in _get_selected_bindings() if _binding_matches_component(binding, component)]
    if len(selected_matches) == 1:
        return selected_matches[0]
    if len(selected_matches) > 1:
        _log_warning(f"Multiple selected bindings matched skeletal component; using first: {_binding_name(selected_matches[0])}")
        return selected_matches[0]
    return _find_binding_by_name(sequence, preferred_name or _object_name(component), prefer_selected=True)


def _find_blueprint_actor_binding(sequence, bp_actor_name, bp_actor, skeletal_binding):
    selected_parent, selected_child = _selected_parent_child_binding_pair()
    if selected_parent is not None and (skeletal_binding is None or _binding_has_child(selected_parent, skeletal_binding) or selected_child == skeletal_binding):
        return selected_parent
    target_names = [bp_actor_name, _object_name(bp_actor), _safe_call(bp_actor, "get_name")]
    candidates = []
    for binding in _get_selected_bindings():
        if any(_name_matches(_binding_name(binding), name) for name in target_names):
            candidates.append(binding)
    for binding in _iter_all_bindings(sequence):
        if any(_name_matches(_binding_name(binding), name) for name in target_names) and binding not in candidates:
            candidates.append(binding)
    if not candidates:
        return None
    child_matches = [binding for binding in candidates if _binding_has_child(binding, skeletal_binding)]
    if len(child_matches) == 1:
        return child_matches[0]
    if len(child_matches) > 1:
        _log_warning(f"Multiple Blueprint Actor bindings contain skeletal mesh binding; using first: {_binding_name(child_matches[0])}")
        return child_matches[0]
    if len(candidates) > 1:
        _log_warning(f"Multiple Blueprint Actor bindings matched; using first: {_binding_name(candidates[0])}")
    return candidates[0]


def _resolve_selected_names(_sequence, bp_actor_name, skeletal_mesh_name):
    selected_parent, selected_child = _selected_parent_child_binding_pair()
    selected_bindings = _get_selected_bindings()
    _log(f"Selected Sequencer bindings: {[_binding_name(binding) for binding in selected_bindings]}")
    _log(f"Selected Sequencer objects: {[_object_name(obj) for obj in _get_selected_objects()]}")
    _log(f"Selected level actors: {[_object_name(actor) for actor in _get_selected_level_actors()]}")
    inferred_bp_name = bp_actor_name or (_binding_name(selected_parent) if selected_parent is not None else "")
    inferred_skeletal_name = skeletal_mesh_name or (_binding_name(selected_child) if selected_child is not None else "")
    if not inferred_bp_name:
        child_guids = set()
        for parent in selected_bindings:
            for child in _as_list(_safe_call(parent, "get_child_possessables")) + _as_list(_safe_call(parent, "get_child_spawnables")):
                child_guids.add(_compact_text(_binding_guid(child)))
        for binding in selected_bindings:
            if _compact_text(_binding_guid(binding)) not in child_guids:
                children = _as_list(_safe_call(binding, "get_child_possessables")) + _as_list(_safe_call(binding, "get_child_spawnables"))
                if children:
                    inferred_bp_name = _binding_name(binding)
                    break
    if not inferred_skeletal_name:
        for binding in selected_bindings:
            name = _binding_name(binding)
            norm = _normalize(name)
            if inferred_bp_name and _name_matches(name, inferred_bp_name):
                continue
            if "controlrig" in norm or "control_rig" in norm or "global_ctrl" in norm:
                continue
            inferred_skeletal_name = name
            break
    return inferred_bp_name, inferred_skeletal_name


def _delete_actor(actor):
    if actor is None:
        return False
    editor_level_library = getattr(unreal, "EditorLevelLibrary", None)
    ok, _error = _call_ok(editor_level_library, "destroy_actor", actor)
    if ok:
        return True
    subsystem_class = getattr(unreal, "EditorActorSubsystem", None)
    subsystem = _safe_call(unreal, "get_editor_subsystem", subsystem_class) if subsystem_class else None
    ok, _error = _call_ok(subsystem, "destroy_actor", actor)
    return ok


def _delete_existing_level_actor_named(actor_name):
    deleted = 0
    for actor in list(_get_all_level_actors()):
        if _object_name(actor) == actor_name and _delete_actor(actor):
            deleted += 1
    if deleted:
        _log(f"Deleted {deleted} existing level actor(s) named {actor_name}.")


def _try_remove_binding(sequence, binding):
    if sequence is None or binding is None:
        return False
    binding_id = _safe_call(binding, "get_id")
    attempts = []
    for function_name, args in (
        ("remove_binding", (binding,)),
        ("remove_binding", (binding_id,)),
        ("remove_spawnable", (binding_id,)),
        ("remove_possessable", (binding_id,)),
    ):
        ok, error = _call_ok(sequence, function_name, *args)
        attempts.append(f"{function_name} -> {'OK' if ok else error}")
        if ok:
            return True
    _log_warning(f"Could not remove existing binding {_binding_name(binding)!r}; attempts={attempts}")
    return False


def _delete_existing_sequence_bindings_named(sequence, binding_name):
    removed = 0
    for binding in list(_iter_all_bindings(sequence)):
        if _binding_name(binding) == binding_name and _try_remove_binding(sequence, binding):
            removed += 1
    if removed:
        _log(f"Removed {removed} existing sequence binding(s) named {binding_name} from {_object_name(sequence)}.")


def _set_component_movable(component):
    enum_type = getattr(unreal, "ComponentMobility", None)
    movable = getattr(enum_type, "MOVABLE", None) if enum_type else None
    if movable is None or component is None:
        return False
    ok, _error = _call_ok(component, "set_mobility", movable)
    return ok or _safe_set_editor_property(component, "mobility", movable)


def _spawn_temp_sphere_actor(sphere_name, visual_scale=0.12):
    static_mesh_actor_class = getattr(unreal, "StaticMeshActor", None)
    if static_mesh_actor_class is None:
        return None, "unreal.StaticMeshActor is unavailable."
    editor_level_library = getattr(unreal, "EditorLevelLibrary", None)
    actor = _safe_call(editor_level_library, "spawn_actor_from_class", static_mesh_actor_class, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
    if actor is None:
        subsystem_class = getattr(unreal, "EditorActorSubsystem", None)
        subsystem = _safe_call(unreal, "get_editor_subsystem", subsystem_class) if subsystem_class else None
        actor = _safe_call(subsystem, "spawn_actor_from_class", static_mesh_actor_class, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
    if actor is None:
        return None, "Could not spawn temporary StaticMeshActor for recorder sphere."

    _safe_call(actor, "set_actor_label", sphere_name)
    _safe_call(actor, "set_actor_location", unreal.Vector(0, 0, 0), False, False)
    _safe_call(actor, "set_actor_rotation", unreal.Rotator(0, 0, 0), False)
    _safe_call(actor, "set_actor_scale3d", unreal.Vector(1.0, 1.0, 1.0))
    _set_component_movable(_safe_call(actor, "get_root_component"))

    static_mesh_component_class = getattr(unreal, "StaticMeshComponent", None)
    mesh_component = _safe_call(actor, "get_component_by_class", static_mesh_component_class) if static_mesh_component_class else None
    if mesh_component is not None:
        _set_component_movable(mesh_component)
        sphere_asset = _safe_call(getattr(unreal, "EditorAssetLibrary", None), "load_asset", "/Engine/BasicShapes/Sphere.Sphere")
        if sphere_asset is not None:
            _safe_call(mesh_component, "set_static_mesh", sphere_asset)
        # Important: keep the ACTOR transform identity. Put display size on the mesh component.
        # This avoids writing sampled world values into a spawnable transform with a scaled object template.
        _safe_call(mesh_component, "set_relative_scale3d", unreal.Vector(visual_scale, visual_scale, visual_scale))

    return actor, ""


def _set_binding_display_name(binding, display_name):
    attempts = []
    for function_name in ("set_display_name", "set_name"):
        ok, error = _call_ok(binding, function_name, display_name)
        attempts.append(f"{function_name}({display_name!r}) -> {'OK' if ok else error}")
        if ok:
            return True, attempts
    for property_name in ("display_name", "name"):
        ok = _safe_set_editor_property(binding, property_name, display_name)
        attempts.append(f"set_editor_property({property_name!r}) -> {'OK' if ok else 'failed'}")
        if ok:
            return True, attempts
    return False, attempts


def _create_spawnable_sphere(sequence, sphere_name, visual_scale=0.12):
    temp_actor, error = _spawn_temp_sphere_actor(sphere_name, visual_scale=visual_scale)
    if error:
        return None, error
    binding = None
    attempts = []
    for function_name in ("add_spawnable_from_instance", "add_spawnable_from_class"):
        args = (temp_actor,) if function_name == "add_spawnable_from_instance" else (temp_actor.get_class(),)
        try:
            binding = getattr(sequence, function_name)(*args)
            attempts.append(f"{function_name} -> OK")
            if binding is not None:
                break
        except Exception as exc:
            attempts.append(f"{function_name} -> {exc}")
    _delete_actor(temp_actor)
    if binding is None:
        return None, f"Could not create spawnable recorder sphere in {_object_name(sequence)}. Attempts: {attempts}"
    ok, display_attempts = _set_binding_display_name(binding, sphere_name)
    if ok:
        _log(f"Set spawnable sphere binding display name to {sphere_name!r}.")
    else:
        _log_warning(f"Could not set spawnable binding display name to {sphere_name!r}. Attempts: {display_attempts}")
    _log(f"Created identity-transform spawnable sphere binding in sequence {_object_name(sequence)} using attempts: {attempts}")
    _log(f"Recorder sphere actor transform is identity; visual size is stored on the mesh component at scale={visual_scale}.")
    return binding, ""


def _get_sequence_frame_range(sequence):
    if base is not None:
        try:
            start, end = base._get_sequence_frame_range(sequence)
            if start is not None and end is not None:
                return int(start), int(end)
        except Exception:
            pass
    playback_range = _safe_call(sequence, "get_playback_range")
    start = _safe_call(playback_range, "get_start_frame")
    end = _safe_call(playback_range, "get_end_frame")
    if start is not None and end is not None:
        try:
            return int(start.value), int(end.value)
        except Exception:
            return int(start), int(end)
    return _safe_call(sequence, "get_playback_start"), _safe_call(sequence, "get_playback_end")


def _make_frame_number(frame):
    try:
        return unreal.FrameNumber(int(frame))
    except Exception:
        return int(frame)


def _set_section_range(section, start_frame, end_frame):
    for args in ((start_frame, end_frame), (_make_frame_number(start_frame), _make_frame_number(end_frame))):
        ok, _error = _call_ok(section, "set_range", *args)
        if ok:
            return True
    _call_ok(section, "set_start_frame", start_frame)
    _call_ok(section, "set_end_frame", end_frame)
    return True


def _method_hints(obj):
    try:
        names = dir(obj)
    except Exception:
        return []
    needles = ("bind", "constraint", "attach", "socket", "component", "parent", "bake", "transform", "channel")
    return [name for name in names if not name.startswith("_") and any(needle in name.lower() for needle in needles)]


def _property_names(obj):
    names = []
    cls = _safe_call(obj, "get_class")
    for prop in _as_list(_safe_call(cls, "get_properties")):
        name = _safe_call(prop, "get_name")
        if name:
            names.append(str(name))
    return names


def _set_section_name(section, function_names, property_names, value):
    name_value = unreal.Name(value or "")
    attempts = []
    for function_name in function_names:
        for arg in (name_value, str(value or "")):
            ok, error = _call_ok(section, function_name, arg)
            attempts.append(f"{function_name}({_compact_text(arg)}) -> {'OK' if ok else error}")
            if ok:
                return True, attempts
    for property_name in property_names:
        if _safe_set_editor_property(section, property_name, name_value):
            attempts.append(f"set_editor_property({property_name!r}, Name) -> OK")
            return True, attempts
        if _safe_set_editor_property(section, property_name, str(value or "")):
            attempts.append(f"set_editor_property({property_name!r}, str) -> OK")
            return True, attempts
        attempts.append(f"set_editor_property({property_name!r}) -> failed")
    return False, attempts


def _set_section_rule(section, function_names, property_names, rule_name):
    attachment_rule = getattr(unreal, "AttachmentRule", None)
    rule = getattr(attachment_rule, rule_name, None) if attachment_rule else None
    if rule is None:
        return False
    for function_name in function_names:
        ok, _error = _call_ok(section, function_name, rule)
        if ok:
            return True
    for property_name in property_names:
        if _safe_set_editor_property(section, property_name, rule):
            return True
    return False


def _assign_attach_parent(section, parent_binding_id):
    attempts = []
    success = False
    for function_name in ("set_constraint_binding_id", "set_constraint_binding", "set_binding_id", "set_parent_binding_id", "set_parent"):
        ok, error = _call_ok(section, function_name, parent_binding_id)
        attempts.append(f"{function_name}(parent_binding_id) -> {'OK' if ok else error}")
        success = success or ok
    for property_name in ("constraint_binding_id", "constraint_binding", "binding_id", "parent_binding_id", "parent"):
        ok = _safe_set_editor_property(section, property_name, parent_binding_id)
        attempts.append(f"set_editor_property({property_name!r}) -> {'OK' if ok else 'failed'}")
        success = success or ok
    return success, attempts


def _configure_attach_section(section, component_name, root_bone_name):
    socket_ok, socket_attempts = _set_section_name(section, ("set_attach_socket_name", "set_socket_name", "set_parent_socket_name"), ("attach_socket_name", "socket_name", "parent_socket_name"), root_bone_name or "")
    component_ok, component_attempts = _set_section_name(section, ("set_attach_component_name", "set_component_name", "set_parent_component_name"), ("attach_component_name", "component_name", "parent_component_name"), component_name or "")
    _set_section_rule(section, ("set_attachment_location_rule", "set_attach_location_rule", "set_location_rule"), ("attachment_location_rule", "attach_location_rule", "location_rule"), "SNAP_TO_TARGET")
    _set_section_rule(section, ("set_attachment_rotation_rule", "set_attach_rotation_rule", "set_rotation_rule"), ("attachment_rotation_rule", "attach_rotation_rule", "rotation_rule"), "SNAP_TO_TARGET")
    _set_section_rule(section, ("set_attachment_scale_rule", "set_attach_scale_rule", "set_scale_rule"), ("attachment_scale_rule", "attach_scale_rule", "scale_rule"), "KEEP_WORLD")
    _set_section_rule(section, ("set_detachment_location_rule", "set_detach_location_rule"), ("detachment_location_rule", "detach_location_rule"), "KEEP_WORLD")
    _set_section_rule(section, ("set_detachment_rotation_rule", "set_detach_rotation_rule"), ("detachment_rotation_rule", "detach_rotation_rule"), "KEEP_WORLD")
    _set_section_rule(section, ("set_detachment_scale_rule", "set_detach_scale_rule"), ("detachment_scale_rule", "detach_scale_rule"), "KEEP_WORLD")
    _log(f"Attach socket set attempts: {socket_attempts}")
    _log(f"Attach component set attempts: {component_attempts}")
    return socket_ok, component_ok


def _attach_section_readback(section):
    output = []
    constraint = _safe_call(section, "get_constraint_binding_id")
    output.append(f"get_constraint_binding_id()={_compact_text(constraint)} details={_binding_id_details(constraint)}")
    output.append(f"get_attach_socket_name()={_compact_text(_safe_call(section, 'get_attach_socket_name'))}")
    output.append(f"get_attach_component_name()={_compact_text(_safe_call(section, 'get_attach_component_name'))}")
    for property_name in ("constraint_binding_id", "attach_socket_name", "attach_component_name", "attachment_location_rule", "attachment_rotation_rule", "attachment_scale_rule"):
        output.append(f"property {property_name}={_compact_text(_safe_get_editor_property(section, property_name))}")
    output.append(f"method_hints={_method_hints(section)}")
    output.append(f"available_props={_property_names(section)}")
    return output


def _create_attach_track(sequence, child_binding, parent_binding, component_name, root_bone_name, start_frame, end_frame):
    track_class = getattr(unreal, "MovieScene3DAttachTrack", None)
    if track_class is None:
        return None, None, "unreal.MovieScene3DAttachTrack is unavailable."
    track = _safe_call(child_binding, "add_track", track_class)
    if track is None:
        return None, None, "Could not add MovieScene3DAttachTrack to recorder_sphere binding."
    section = _safe_call(track, "add_section")
    if section is None:
        return track, None, "Could not add MovieScene3DAttachSection to recorder_sphere attach track."
    _set_section_range(section, start_frame, end_frame)
    parent_binding_id, binding_id_attempts = _make_movie_scene_object_binding_id(sequence, parent_binding)
    _log(f"Parent binding id attempts: {binding_id_attempts}")
    if parent_binding_id is None:
        return track, section, "Could not create MovieSceneObjectBindingID for attach parent binding."
    _log(f"Created parent binding id for attach: {type(parent_binding_id)} {_compact_text(parent_binding_id)} details={_binding_id_details(parent_binding_id)}")
    parent_ok, parent_attempts = _assign_attach_parent(section, parent_binding_id)
    _log(f"Attach parent assignment attempts: {parent_attempts}")
    if not parent_ok:
        return track, section, "Could not assign parent binding id to MovieScene3DAttachSection."
    socket_ok, component_ok = _configure_attach_section(section, component_name, root_bone_name)
    _log(f"Configured attach target component={component_name!r} socket={root_bone_name!r} socket_ok={socket_ok} component_ok={component_ok}")
    _log(f"Attach section readback: {_attach_section_readback(section)}")
    return track, section, ""


def _verify_root_bone(skeletal_component, root_bone_name):
    root_name = root_bone_name or "root"
    bone_index = _safe_call(skeletal_component, "get_bone_index", root_name)
    socket_exists = _safe_call(skeletal_component, "does_socket_exist", root_name)
    _log(f"Root bone/socket diagnostics: name={root_name!r} does_socket_exist={socket_exists!r} bone_index={bone_index!r}")
    if bone_index is not None:
        try:
            if int(bone_index) >= 0:
                return True
        except Exception:
            pass
    return bool(socket_exists)


def _print_context(context, sphere_name, root_bone_name):
    _log("==================================================")
    _log(f"Target Level Sequence: {_object_name(context['sequence'])}")
    _log(f"Target sequence source: {context['sequence_source']}")
    _log(f"Playback frame range: {context['start_frame']} to {context['end_frame']} end-exclusive")
    _log(f"Blueprint Actor var: {_object_name(context['bp_actor'])} class={_class_name(context['bp_actor'])}")
    _log(f"Blueprint Actor Sequencer binding: {_binding_name(context['bp_actor_binding'])}")
    _log(f"Skeletal Mesh var: {_object_name(context['skeletal_component'])} class={_class_name(context['skeletal_component'])}")
    _log(f"Skeletal Mesh component name for attach: {context['skeletal_component_name']}")
    _log(f"Skeletal Mesh Sequencer binding: {_binding_name(context['skeletal_binding'])}")
    _log(f"global_ctrl selected binding/context: {_binding_name(context['global_binding']) if context['global_binding'] else '<not resolved; selection only>'}")
    _log(f"Recorder sphere name: {sphere_name}")
    _log(f"Root bone/socket for attach: {root_bone_name}")
    _log("==================================================")


def _resolve_context(bp_actor_name, skeletal_mesh_name, global_ctrl_name, prefer_selected_global_ctrl_sequence):
    sequence, sequence_source = _get_target_level_sequence(prefer_selected_global_ctrl_sequence)
    if sequence is None:
        return None, f"No target Level Sequence found. {sequence_source}"
    start_frame, end_frame = _get_sequence_frame_range(sequence)
    if start_frame is None or end_frame is None:
        return None, f"Could not read Level Sequence playback range for {_object_name(sequence)}."
    inferred_bp_name, inferred_skeletal_name = _resolve_selected_names(sequence, bp_actor_name, skeletal_mesh_name)
    if not bp_actor_name and inferred_bp_name:
        _log(f"Resolved bp_actor_name from selection: {inferred_bp_name}")
    if not skeletal_mesh_name and inferred_skeletal_name:
        _log(f"Resolved skeletal_mesh_name from selection: {inferred_skeletal_name}")
    bp_actor = _find_level_actor_by_name(inferred_bp_name)
    if bp_actor is None:
        return None, f"Could not resolve Blueprint Actor from selection/name. bp_actor_name={bp_actor_name!r} inferred_bp_name={inferred_bp_name!r}. Select the Blueprint Actor binding/actor or pass bp_actor_name."
    skeletal_component, skeletal_error = _find_skeletal_mesh_component(bp_actor, inferred_skeletal_name)
    if skeletal_error:
        return None, skeletal_error
    skeletal_component_name = _object_name(skeletal_component) or _safe_call(skeletal_component, "get_name") or inferred_skeletal_name
    skeletal_binding = _find_binding_for_component(sequence, skeletal_component, skeletal_component_name)
    if skeletal_binding is None:
        return None, f"Could not find a Sequencer binding for skeletal component {skeletal_component_name!r} in target sequence {_object_name(sequence)}. Select/add the skeletal mesh component binding in the ANM subsequence before running."
    bp_actor_binding = _find_blueprint_actor_binding(sequence, inferred_bp_name, bp_actor, skeletal_binding)
    if bp_actor_binding is None:
        return None, f"Could not find Blueprint Actor binding for {_object_name(bp_actor)!r} in target sequence {_object_name(sequence)}. Select the Blueprint Actor binding along with the Skeletal Mesh binding."
    return {
        "sequence": sequence,
        "sequence_source": sequence_source,
        "start_frame": int(start_frame),
        "end_frame": int(end_frame),
        "bp_actor": bp_actor,
        "bp_actor_binding": bp_actor_binding,
        "skeletal_component": skeletal_component,
        "skeletal_component_name": skeletal_component_name,
        "skeletal_binding": skeletal_binding,
        "global_binding": _find_binding_by_name(sequence, global_ctrl_name, prefer_selected=True) if global_ctrl_name else None,
    }, ""


def _select_binding_for_bake(binding):
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    attempts = []
    for function_name, args in (("select_binding", (binding,)), ("select_bindings", ([binding],)), ("set_selected_bindings", ([binding],))):
        ok, error = _call_ok(library, function_name, *args)
        attempts.append(f"{function_name} -> {'OK' if ok else error}")
        if ok:
            return True, attempts
    return False, attempts


def _try_builtin_bake_transform(sequence, binding, start_frame, end_frame, frame_increment):
    attempts = []
    _ok, select_attempts = _select_binding_for_bake(binding)
    attempts.append(f"select binding attempts={select_attempts}")
    for name, container in (
        ("LevelSequenceEditorBlueprintLibrary", getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)),
        ("SequencerTools", getattr(unreal, "SequencerTools", None)),
        ("MovieSceneToolHelpers", getattr(unreal, "MovieSceneToolHelpers", None)),
    ):
        if container is None:
            attempts.append(f"{name} unavailable")
            continue
        methods = [method_name for method_name in dir(container) if "bake" in method_name.lower() and "transform" in method_name.lower()]
        attempts.append(f"{name} bake/transform methods={methods}")
        for method_name in methods:
            method = getattr(container, method_name, None)
            if method is None:
                continue
            for args in ((start_frame, end_frame, frame_increment), (sequence, start_frame, end_frame, frame_increment), (binding, start_frame, end_frame, frame_increment), (sequence, binding, start_frame, end_frame, frame_increment), ()): 
                try:
                    result = method(*args)
                    attempts.append(f"{name}.{method_name}{args} -> OK result={_compact_text(result)}")
                    return True, attempts
                except Exception as exc:
                    attempts.append(f"{name}.{method_name}{args} -> {exc}")
    return False, attempts


def _set_current_frame(frame):
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    frame_number = _make_frame_number(frame)
    attempts = []
    for function_name, args in (("set_current_time", (frame,)), ("set_current_time", (frame_number,)), ("set_current_frame", (frame,)), ("set_current_frame", (frame_number,)), ("set_global_position", (frame,)), ("set_global_time", (frame,))):
        ok, error = _call_ok(library, function_name, *args)
        attempts.append(f"{function_name} -> {'OK' if ok else error}")
        if ok:
            return True, attempts
    return False, attempts


def _refresh_sequencer():
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    attempts = []
    for function_name in ("refresh_current_level_sequence", "refresh_current_level_sequence_editor", "refresh_current_level_sequence_player"):
        ok, error = _call_ok(library, function_name)
        attempts.append(f"{function_name} -> {'OK' if ok else error}")
        if ok:
            return True, attempts
    return False, attempts


def _flatten_bound_object_result(value):
    output = []
    for item in _as_list(value):
        nested = False
        for property_name in ("bound_objects", "BoundObjects", "objects", "Objects"):
            prop_value = _safe_get_editor_property(item, property_name)
            if prop_value:
                output.extend(_as_list(prop_value))
                nested = True
        for function_name in ("get_bound_objects", "get_objects"):
            result = _safe_call(item, function_name)
            if result:
                output.extend(_as_list(result))
                nested = True
        if not nested:
            output.append(item)
    return output


def _resolve_bound_objects(sequence, binding):
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    attempts = []
    binding_id, binding_attempts = _make_movie_scene_object_binding_id(sequence, binding)
    attempts.append(f"binding_id_attempts={binding_attempts}")
    if binding_id is not None:
        attempts.append(f"binding_id={_compact_text(binding_id)} details={_binding_id_details(binding_id)}")
        for function_name in ("get_bound_objects", "get_bound_object"):
            method = getattr(library, function_name, None)
            if method is None:
                attempts.append(f"{function_name}(binding_id) -> missing")
                continue
            for args in ((binding_id,), ([binding_id],)):
                try:
                    result = method(*args)
                    attempts.append(f"{function_name}(binding_id args={len(args)}) -> {_compact_text(result)}")
                    objects = _flatten_bound_object_result(result)
                    if objects:
                        return objects, attempts
                except Exception as exc:
                    attempts.append(f"{function_name}(binding_id args={len(args)}) -> {exc}")
    return [], attempts


def _get_actor_transform_values(actor):
    location = _safe_call(actor, "get_actor_location")
    rotation = _safe_call(actor, "get_actor_rotation")
    scale = _safe_call(actor, "get_actor_scale3d")
    if location is None or rotation is None or scale is None:
        return None
    return {
        "location_x": float(location.x),
        "location_y": float(location.y),
        "location_z": float(location.z),
        "rotation_x": float(rotation.roll),
        "rotation_y": float(rotation.pitch),
        "rotation_z": float(rotation.yaw),
        "scale_x": float(scale.x),
        "scale_y": float(scale.y),
        "scale_z": float(scale.z),
    }


def _find_transform_track(binding):
    track_class = getattr(unreal, "MovieScene3DTransformTrack", None)
    if track_class is None:
        return None
    for track in _as_list(_safe_call(binding, "get_tracks")):
        if "MovieScene3DTransformTrack" in _class_name(track):
            return track
    return _safe_call(binding, "add_track", track_class)


def _remove_track(binding, track):
    if binding is None or track is None:
        return False
    ok, _error = _call_ok(binding, "remove_track", track)
    if ok:
        return True
    for section in list(_as_list(_safe_call(track, "get_sections"))):
        _call_ok(track, "remove_section", section)
    return True


def _clear_sections(track):
    for section in list(_as_list(_safe_call(track, "get_sections"))):
        _call_ok(track, "remove_section", section)


def _channel_name(channel):
    for function_name in ("get_name", "get_display_name"):
        value = _safe_call(channel, function_name)
        if value:
            return str(value)
    return _compact_text(channel, 120)


def _enable_transform_channels(section):
    # Best-effort only. UE versions expose different APIs/properties for transform masks.
    attempts = []
    for function_name in ("set_channels_mask", "set_mask", "set_transform_mask"):
        fn = getattr(section, function_name, None)
        if fn is None:
            attempts.append(f"{function_name} -> missing")
            continue
        for arg in (None, True):
            try:
                if arg is None:
                    fn()
                else:
                    fn(arg)
                attempts.append(f"{function_name} -> OK")
                return attempts
            except Exception as exc:
                attempts.append(f"{function_name} -> {exc}")
    return attempts


def _section_channels(section):
    channels = []
    attempts = []
    for function_name in ("get_channels", "get_all_channels"):
        result = _safe_call(section, function_name)
        attempts.append(f"{function_name} -> {len(_as_list(result)) if result is not None else 'None'}")
        channels.extend(_as_list(result))
    for channel_class_name in ("MovieSceneScriptingDoubleChannel", "MovieSceneScriptingFloatChannel"):
        channel_class = getattr(unreal, channel_class_name, None)
        if channel_class is None:
            attempts.append(f"get_channels_by_type({channel_class_name}) -> class unavailable")
            continue
        result = _safe_call(section, "get_channels_by_type", channel_class)
        attempts.append(f"get_channels_by_type({channel_class_name}) -> {len(_as_list(result)) if result is not None else 'None'}")
        channels.extend(_as_list(result))
    deduped = []
    seen = set()
    for channel in channels:
        key = id(channel)
        if key not in seen:
            seen.add(key)
            deduped.append(channel)
    return deduped, attempts


def _map_transform_channels(section):
    _enable_transform_channels(section)
    channels, attempts = _section_channels(section)
    ordered = list(TRANSFORM_KEYS)
    result = {key: channel for key, channel in zip(ordered, channels[:9])}
    for channel in channels:
        name = _normalize(_channel_name(channel))
        for key in ordered:
            axis = key[-1]
            group = key[:-2]
            if group in name and axis in name:
                result[key] = channel
    _log(f"Transform channel lookup attempts: {attempts}")
    _log(f"Transform channel names: {[_channel_name(channel) for channel in channels]}")
    return result, channels


def _add_key(channel, frame, value):
    frame_number = _make_frame_number(frame)
    for args in ((frame_number, float(value)), (frame, float(value))):
        ok, _error = _call_ok(channel, "add_key", *args)
        if ok:
            return True
    return False


def _write_transform_keys(binding, samples, start_frame, end_frame, write_scale_keys=False):
    track = _find_transform_track(binding)
    if track is None:
        return "Could not create/find MovieScene3DTransformTrack on recorder_sphere."
    _clear_sections(track)
    section = _safe_call(track, "add_section")
    if section is None:
        return "Could not add transform section to recorder_sphere."
    _set_section_range(section, start_frame, end_frame)
    channels, raw_channels = _map_transform_channels(section)
    keys_to_write = LOCATION_KEYS + ROTATION_KEYS + (SCALE_KEYS if write_scale_keys else ())
    missing = [key for key in keys_to_write if key not in channels]
    if missing:
        return f"Transform section is missing channels: {missing}. Available={[_channel_name(channel) for channel in raw_channels]}"
    failed = []
    for frame, values in samples:
        values_to_write = dict(values)
        # The spawnable actor template is identity. Leave scale unkeyed by default so the mesh-component visual scale stays clean.
        for key in keys_to_write:
            if not _add_key(channels[key], frame, values_to_write[key]):
                failed.append((frame, key))
    if failed:
        return f"Failed to add {len(failed)} transform key(s). First failures={failed[:10]}"
    if not write_scale_keys:
        _log("Wrote Location/Rotation keys only. Scale keys were intentionally skipped; sphere display size lives on the mesh component.")
    return ""


def _manual_bake_by_sampling(sequence, binding, attach_track, start_frame, end_frame, frame_increment, remove_attach_after_bake=True, write_scale_keys=False):
    samples = []
    resolve_attempts = []
    time_attempts = []
    refresh_attempts = []
    for frame in range(int(start_frame), int(end_frame), int(frame_increment)):
        ok, time_attempts = _set_current_frame(frame)
        if not ok:
            return False, f"Could not set Sequencer time. Attempts={time_attempts}"
        _ok, refresh_attempts = _refresh_sequencer()
        objects, resolve_attempts = _resolve_bound_objects(sequence, binding)
        actor = None
        for obj in objects:
            if _safe_call(obj, "get_actor_location") is not None:
                actor = obj
                break
        if actor is None:
            return False, f"Could not resolve spawned recorder_sphere actor while sampling frame {frame}. Time attempts={time_attempts} Refresh attempts={refresh_attempts} Resolve attempts={resolve_attempts}"
        values = _get_actor_transform_values(actor)
        if values is None:
            return False, f"Could not read recorder_sphere actor transform at frame {frame}. Actor={_compact_text(actor)}"
        samples.append((frame, values))
    _log(f"Sampled attached recorder_sphere for {len(samples)} frame(s). First={samples[0] if samples else None} Last={samples[-1] if samples else None}")

    error = _write_transform_keys(binding, samples, start_frame, end_frame, write_scale_keys=write_scale_keys)
    if error:
        return False, error

    if remove_attach_after_bake and _remove_track(binding, attach_track):
        _log("Removed recorder_sphere Attach track after transform keys were written successfully.")
    else:
        _log("Kept recorder_sphere Attach track after bake because remove_attach_after_bake=False or track removal failed.")

    _log(f"Manual identity-spawnable bake wrote transform keys for {len(samples)} frame(s). Time attempts={time_attempts} Refresh attempts={refresh_attempts} Resolve attempts={resolve_attempts}")
    return True, ""


def _bake_recorder_sphere_transform(sequence, binding, attach_track, start_frame, end_frame, frame_increment, remove_attach_after_bake=True, write_scale_keys=False):
    _log(f"Bake recorder_sphere transform requested: start={start_frame} end={end_frame} increment={frame_increment} key_settings=All Frames")
    builtin_ok, builtin_attempts = _try_builtin_bake_transform(sequence, binding, start_frame, end_frame, frame_increment)
    _log(f"Built-in bake transform attempts: {builtin_attempts}")
    if builtin_ok:
        _log("SUCCESS: Built-in Sequencer bake transform call completed for recorder_sphere.")
        return True, ""
    _log_warning("Built-in bake transform API was not available/successful. Trying identity-spawnable manual sampling fallback.")
    return _manual_bake_by_sampling(sequence, binding, attach_track, start_frame, end_frame, frame_increment, remove_attach_after_bake=remove_attach_after_bake, write_scale_keys=write_scale_keys)


def run(
    bp_actor_name="",
    skeletal_mesh_name="",
    global_ctrl_name="global_ctrl",
    root_bone_name="root",
    sphere_name=DEFAULT_SPHERE_NAME,
    delete_existing=True,
    prefer_selected_global_ctrl_sequence=True,
    bake_recorder_sphere=False,
    frame_increment=1,
    remove_attach_after_bake=True,
    sphere_visual_scale=0.12,
    write_scale_keys=False,
):
    try:
        _log("----- attach snap setup run() called -----")
        _log(
            f"bp_actor_name={bp_actor_name!r} skeletal_mesh_name={skeletal_mesh_name!r} "
            f"global_ctrl_name={global_ctrl_name!r} root_bone_name={root_bone_name!r} "
            f"sphere_name={sphere_name!r} delete_existing={delete_existing!r} "
            f"prefer_selected_global_ctrl_sequence={prefer_selected_global_ctrl_sequence!r} "
            f"bake_recorder_sphere={bake_recorder_sphere!r} frame_increment={frame_increment!r} "
            f"remove_attach_after_bake={remove_attach_after_bake!r} sphere_visual_scale={sphere_visual_scale!r} "
            f"write_scale_keys={write_scale_keys!r}"
        )
        context, error = _resolve_context(bp_actor_name, skeletal_mesh_name, global_ctrl_name, prefer_selected_global_ctrl_sequence)
        if error:
            _log_error(error)
            return ""

        sequence = context["sequence"]
        skeletal_component = context["skeletal_component"]
        skeletal_component_name = context["skeletal_component_name"]
        bp_actor_binding = context["bp_actor_binding"]
        skeletal_binding = context["skeletal_binding"]
        start_frame = context["start_frame"]
        end_frame = context["end_frame"]

        _print_context(context, sphere_name, root_bone_name)

        if not _verify_root_bone(skeletal_component, root_bone_name):
            _log_error(f"Skeletal mesh {_object_name(skeletal_component)!r} does not appear to have bone/socket {root_bone_name!r}.")
            return ""

        if delete_existing:
            _delete_existing_level_actor_named(sphere_name)
            _delete_existing_sequence_bindings_named(sequence, sphere_name)

        if _find_binding_by_name(sequence, sphere_name, prefer_selected=False) is not None:
            _log_error(f"A Sequencer binding named {sphere_name!r} already exists in {_object_name(sequence)}. Delete it or rerun with delete_existing=True.")
            return ""

        sphere_binding, sphere_error = _create_spawnable_sphere(sequence, sphere_name, visual_scale=sphere_visual_scale)
        if sphere_error:
            _log_error(sphere_error)
            return ""

        attach_track, _attach_section, attach_error = _create_attach_track(sequence, sphere_binding, bp_actor_binding, skeletal_component_name, root_bone_name, start_frame, end_frame)
        if attach_error:
            _log_error(attach_error)
            return ""

        _log("SUCCESS: Created spawnable recorder_sphere and left the Sequencer Attach track in place.")
        _log(f"Target sequence: {_object_name(sequence)}")
        _log(f"Attach parent binding: {_binding_name(bp_actor_binding)}")
        _log(f"Attach component/socket: {skeletal_component_name}.{root_bone_name}")
        _log(f"Reference skeletal mesh binding selected/found: {_binding_name(skeletal_binding)}")

        if bake_recorder_sphere:
            ok, bake_error = _bake_recorder_sphere_transform(
                sequence,
                sphere_binding,
                attach_track,
                start_frame,
                end_frame,
                frame_increment,
                remove_attach_after_bake=remove_attach_after_bake,
                write_scale_keys=write_scale_keys,
            )
            if not ok:
                _log_error(f"Attach was created, but recorder_sphere bake failed: {bake_error}")
                _log_warning("Attach track was preserved because bake failed before confirmed key writing/removal.")
                return ""
            _log("SUCCESS: recorder_sphere transform bake step completed.")
            _log("Next test: inspect recorder_sphere transform keys and confirm baked motion lines up with the live attach result.")
        else:
            _log("Bake step skipped. Scrub the ANM subsequence and verify recorder_sphere follows the selected skeletal mesh root bone.")

        return "true"
    except Exception:
        _log_error(traceback.format_exc())
        return ""
