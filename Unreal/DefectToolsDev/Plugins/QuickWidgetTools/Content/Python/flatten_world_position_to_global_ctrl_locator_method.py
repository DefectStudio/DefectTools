"""
Two-pass Sequencer attach locator workflow for MetaHuman global_ctrl flatten.

This script intentionally uses real Sequencer Attach tracks instead of copying
socket/root values for the first locator step.

Pass A creates the attach and stops:

    locator_flatten.run(
        bp_actor_name="chr_Assassin_S1_v001",
        skeletal_mesh_name="Bungie_Char",
        root_bone_name="root",
        setup_attach_only=True,
    )

Then scrub/play the sequence manually and confirm TMP_global_ctrl_sampled_locator
is actually attached to the skeletal mesh/root in Sequencer.

Pass B samples the already-attached locator and bakes a normal Transform track:

    locator_flatten.run(
        bp_actor_name="chr_Assassin_S1_v001",
        skeletal_mesh_name="Bungie_Char",
        root_bone_name="root",
        bake_existing_attached_locator=True,
        keep_debug_locator=True,
    )

Final global_ctrl rebuild is still optional/experimental:

    locator_flatten.run(
        bp_actor_name="chr_Assassin_S1_v001",
        skeletal_mesh_name="Bungie_Char",
        root_bone_name="root",
        bake_existing_attached_locator=True,
        perform_final_rebuild=True,
        dry_run=False,
    )
"""

import traceback

import unreal

import flatten_world_position_to_global_ctrl as base

LOG_PREFIX = "[FlattenGlobalCtrlLocatorMethod]"
LOCATOR_LABEL = "TMP_global_ctrl_sampled_locator"


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


def _safe_set_editor_property(obj, property_name, value):
    if obj is None:
        return False
    try:
        obj.set_editor_property(property_name, value)
        return True
    except Exception:
        return False


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


def _compact_text(value, max_length=260):
    try:
        text = str(value)
    except Exception:
        text = repr(value)
    text = text.replace("\r", " ").replace("\n", " ").strip()
    if len(text) > max_length:
        text = text[:max_length] + "..."
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


def _match_name(obj, target_name):
    target = _normalize(target_name)
    if not target:
        return False
    for name in (_object_name(obj), _safe_call(obj, "get_name"), _safe_call(obj, "get_actor_label")):
        normalized = _normalize(name)
        if normalized and (normalized == target or target in normalized or normalized in target):
            return True
    return False


def _make_frame_number(frame_value):
    try:
        return unreal.FrameNumber(int(frame_value))
    except Exception:
        return int(frame_value)


def _set_sequencer_time(frame):
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    frame_number = _make_frame_number(frame)
    for function_name, value in (
        ("set_current_time", frame_number),
        ("set_current_time", int(frame)),
        ("set_global_time", frame_number),
        ("set_global_time", int(frame)),
    ):
        ok, _ = _call_ok(library, function_name, value)
        if ok:
            return True
    return False


def _force_sequence_evaluate():
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    for function_name in (
        "refresh_current_level_sequence",
        "refresh_current_level_sequence_editor",
        "update_current_time",
    ):
        _safe_call(library, function_name)
    editor_subsystem_class = getattr(unreal, "UnrealEditorSubsystem", None)
    if editor_subsystem_class is not None:
        subsystem = _safe_call(unreal, "get_editor_subsystem", editor_subsystem_class)
        _safe_call(subsystem, "redraw_all_viewports")


def _get_all_level_actors():
    editor_level_library = getattr(unreal, "EditorLevelLibrary", None)
    actors = _safe_call(editor_level_library, "get_all_level_actors")
    if actors is not None:
        return _as_list(actors)
    editor_actor_subsystem_class = getattr(unreal, "EditorActorSubsystem", None)
    subsystem = _safe_call(unreal, "get_editor_subsystem", editor_actor_subsystem_class) if editor_actor_subsystem_class is not None else None
    return _as_list(_safe_call(subsystem, "get_all_level_actors"))


def _get_selected_level_actors():
    editor_level_library = getattr(unreal, "EditorLevelLibrary", None)
    actors = _safe_call(editor_level_library, "get_selected_level_actors")
    if actors is not None:
        return _as_list(actors)
    editor_actor_subsystem_class = getattr(unreal, "EditorActorSubsystem", None)
    subsystem = _safe_call(unreal, "get_editor_subsystem", editor_actor_subsystem_class) if editor_actor_subsystem_class is not None else None
    return _as_list(_safe_call(subsystem, "get_selected_level_actors"))


def _find_level_actor_by_name(actor_name):
    selected_matches = [actor for actor in _get_selected_level_actors() if _match_name(actor, actor_name)]
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
    if skeletal_mesh_name:
        target = _normalize(skeletal_mesh_name)
        exact = []
        contains = []
        for component in components:
            names = [_normalize(_object_name(component)), _normalize(_safe_call(component, "get_name"))]
            if target in names:
                exact.append(component)
            elif any(target in name or name in target for name in names if name):
                contains.append(component)
        matches = exact if exact else contains
        if len(matches) == 1:
            return matches[0], ""
        if len(matches) > 1:
            _log_warning(f"Multiple skeletal mesh components matched {skeletal_mesh_name!r}; using first: {_object_name(matches[0])}")
            return matches[0], ""
        names = [_object_name(component) for component in components]
        return None, f"No SkeletalMeshComponent matched {skeletal_mesh_name!r}. Available: {names}"
    if len(components) == 1:
        return components[0], ""
    names = [_object_name(component) for component in components]
    return None, f"Multiple SkeletalMeshComponents found. Pass skeletal_mesh_name. Available: {names}"


def _find_binding_by_name(sequence, target_name):
    if sequence is None or not target_name:
        return None
    target = _normalize(target_name)
    exact = []
    contains = []
    for binding in base._iter_all_bindings(sequence):
        binding_name = _normalize(base._binding_name(binding))
        if binding_name == target:
            exact.append(binding)
        elif target in binding_name or binding_name in target:
            contains.append(binding)
    matches = exact if exact else contains
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        _log_warning(f"Multiple Sequencer bindings matched {target_name!r}; using first: {base._binding_name(matches[0])}")
        return matches[0]
    return None


def _find_locator_actor():
    for actor in _get_all_level_actors():
        if _object_name(actor) == LOCATOR_LABEL:
            return actor
    return None


def _delete_existing_debug_locators():
    deleted = 0
    for actor in list(_get_all_level_actors()):
        if _object_name(actor) == LOCATOR_LABEL:
            _destroy_actor(actor)
            deleted += 1
    if deleted:
        _log(f"Deleted {deleted} existing debug locator actor(s) named {LOCATOR_LABEL}.")


def _set_component_movable(component):
    enum_type = getattr(unreal, "ComponentMobility", None)
    movable = getattr(enum_type, "MOVABLE", None) if enum_type is not None else None
    if movable is None or component is None:
        return False
    ok, _ = _call_ok(component, "set_mobility", movable)
    return ok or _safe_set_editor_property(component, "mobility", movable)


def _spawn_locator(label=LOCATOR_LABEL):
    editor_level_library = getattr(unreal, "EditorLevelLibrary", None)
    static_mesh_actor_class = getattr(unreal, "StaticMeshActor", None)
    actor_class = static_mesh_actor_class or getattr(unreal, "Actor", None)
    if actor_class is None:
        return None, "Could not find an Actor class to spawn."
    locator = _safe_call(editor_level_library, "spawn_actor_from_class", actor_class, unreal.Vector(0.0, 0.0, 0.0), unreal.Rotator(0.0, 0.0, 0.0))
    if locator is None:
        editor_actor_subsystem_class = getattr(unreal, "EditorActorSubsystem", None)
        subsystem = _safe_call(unreal, "get_editor_subsystem", editor_actor_subsystem_class) if editor_actor_subsystem_class is not None else None
        locator = _safe_call(subsystem, "spawn_actor_from_class", actor_class, unreal.Vector(0.0, 0.0, 0.0), unreal.Rotator(0.0, 0.0, 0.0))
    if locator is None:
        return None, "Could not spawn TMP locator actor."
    _safe_call(locator, "set_actor_label", label)
    _safe_call(locator, "set_actor_scale3d", unreal.Vector(0.12, 0.12, 0.12))
    _set_component_movable(_safe_call(locator, "get_root_component"))
    static_mesh_component_class = getattr(unreal, "StaticMeshComponent", None)
    mesh_component = _safe_call(locator, "get_component_by_class", static_mesh_component_class) if static_mesh_component_class is not None else None
    if mesh_component is not None:
        _set_component_movable(mesh_component)
        sphere = _safe_call(getattr(unreal, "EditorAssetLibrary", None), "load_asset", "/Engine/BasicShapes/Sphere.Sphere")
        if sphere is not None:
            _safe_call(mesh_component, "set_static_mesh", sphere)
    return locator, ""


def _destroy_actor(actor):
    if actor is None:
        return
    editor_level_library = getattr(unreal, "EditorLevelLibrary", None)
    ok, _ = _call_ok(editor_level_library, "destroy_actor", actor)
    if ok:
        return
    editor_actor_subsystem_class = getattr(unreal, "EditorActorSubsystem", None)
    subsystem = _safe_call(unreal, "get_editor_subsystem", editor_actor_subsystem_class) if editor_actor_subsystem_class is not None else None
    _call_ok(subsystem, "destroy_actor", actor)


def _set_section_range(section, start_frame, end_frame):
    for args in ((start_frame, end_frame), (_make_frame_number(start_frame), _make_frame_number(end_frame))):
        ok, _ = _call_ok(section, "set_range", *args)
        if ok:
            return True
    _call_ok(section, "set_start_frame", start_frame)
    _call_ok(section, "set_end_frame", end_frame)
    return True


def _make_object_binding_id_from_guid(guid):
    binding_id_class = getattr(unreal, "MovieSceneObjectBindingID", None)
    if binding_id_class is None:
        return None
    attempts = []
    object_binding_space = getattr(unreal, "MovieSceneObjectBindingSpace", None)
    local_space = getattr(object_binding_space, "LOCAL", None) if object_binding_space is not None else None
    root_space = getattr(object_binding_space, "ROOT", None) if object_binding_space is not None else None

    for constructor_args in ((guid,), (guid, local_space), (guid, root_space)):
        constructor_args = tuple(arg for arg in constructor_args if arg is not None)
        try:
            value = binding_id_class(*constructor_args)
            attempts.append(f"MovieSceneObjectBindingID{constructor_args} -> OK")
            return value, attempts
        except Exception as exc:
            attempts.append(f"MovieSceneObjectBindingID{constructor_args} -> {exc}")

    for space in (local_space, root_space):
        try:
            value = binding_id_class()
            for prop_name, prop_value in (
                ("guid", guid),
                ("space", space),
                ("sequence_id", 0),
                ("resolve_parent_index", 0),
            ):
                if prop_value is not None:
                    _safe_set_editor_property(value, prop_name, prop_value)
            attempts.append(f"MovieSceneObjectBindingID property fill space={space} -> OK")
            return value, attempts
        except Exception as exc:
            attempts.append(f"MovieSceneObjectBindingID property fill -> {exc}")
    return None, attempts


def _get_binding_id_for_attach(sequence, binding):
    attempts = []
    object_binding_space = getattr(unreal, "MovieSceneObjectBindingSpace", None)
    for space_name in ("LOCAL", "ROOT"):
        space = getattr(object_binding_space, space_name, None) if object_binding_space is not None else None
        if space is not None:
            value = _safe_call(sequence, "make_binding_id", binding, space)
            attempts.append(f"sequence.make_binding_id(binding, {space_name}) -> {_compact_text(value)}")
            if value is not None and "MovieSceneObjectBindingID" in _class_name(value):
                return value, attempts

    guid = _safe_call(binding, "get_id") or _safe_call(binding, "get_binding_id")
    attempts.append(f"binding guid -> {_compact_text(guid)}")
    if guid is not None:
        value, sub_attempts = _make_object_binding_id_from_guid(guid)
        attempts.extend(sub_attempts)
        if value is not None:
            return value, attempts
    return None, attempts


def _method_hints(obj):
    try:
        names = dir(obj)
    except Exception:
        return []
    needles = ("bind", "constraint", "attach", "socket", "component", "parent")
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
    for function_name in function_names:
        for arg in (name_value, str(value or "")):
            ok, _ = _call_ok(section, function_name, arg)
            if ok:
                return True
    for property_name in property_names:
        if _safe_set_editor_property(section, property_name, name_value):
            return True
        if _safe_set_editor_property(section, property_name, str(value or "")):
            return True
    return False


def _set_section_rule(section, function_names, property_names, rule_name):
    attachment_rule = getattr(unreal, "AttachmentRule", None)
    rule = getattr(attachment_rule, rule_name, None) if attachment_rule is not None else None
    if rule is None:
        return False
    for function_name in function_names:
        ok, _ = _call_ok(section, function_name, rule)
        if ok:
            return True
    for property_name in property_names:
        if _safe_set_editor_property(section, property_name, rule):
            return True
    return False


def _assign_attach_parent(section, parent_binding_id):
    attempts = []
    for function_name in ("set_constraint_binding_id", "set_constraint_binding", "set_binding_id", "set_parent_binding_id", "set_parent"):
        ok, error = _call_ok(section, function_name, parent_binding_id)
        attempts.append(f"{function_name}(parent_binding_id) -> {'OK' if ok else error}")
        if ok:
            return True, attempts
    for property_name in ("constraint_binding_id", "constraint_binding", "binding_id", "parent_binding_id", "parent"):
        ok = _safe_set_editor_property(section, property_name, parent_binding_id)
        attempts.append(f"set_editor_property({property_name!r}) -> {'OK' if ok else 'failed'}")
        if ok:
            return True, attempts
    return False, attempts


def _configure_attach_section(section, root_bone_name):
    _set_section_name(section, ("set_attach_socket_name", "set_socket_name", "set_parent_socket_name"), ("attach_socket_name", "socket_name", "parent_socket_name"), root_bone_name or "")
    _set_section_name(section, ("set_attach_component_name", "set_component_name", "set_parent_component_name"), ("attach_component_name", "component_name", "parent_component_name"), "")
    _set_section_rule(section, ("set_attachment_location_rule", "set_attach_location_rule", "set_location_rule"), ("attachment_location_rule", "attach_location_rule", "location_rule"), "SNAP_TO_TARGET")
    _set_section_rule(section, ("set_attachment_rotation_rule", "set_attach_rotation_rule", "set_rotation_rule"), ("attachment_rotation_rule", "attach_rotation_rule", "rotation_rule"), "SNAP_TO_TARGET")
    _set_section_rule(section, ("set_attachment_scale_rule", "set_attach_scale_rule", "set_scale_rule"), ("attachment_scale_rule", "attach_scale_rule", "scale_rule"), "KEEP_WORLD")
    _set_section_rule(section, ("set_detachment_location_rule", "set_detach_location_rule"), ("detachment_location_rule", "detach_location_rule"), "KEEP_WORLD")
    _set_section_rule(section, ("set_detachment_rotation_rule", "set_detach_rotation_rule"), ("detachment_rotation_rule", "detach_rotation_rule"), "KEEP_WORLD")
    _set_section_rule(section, ("set_detachment_scale_rule", "set_detach_scale_rule"), ("detachment_scale_rule", "detach_scale_rule"), "KEEP_WORLD")


def _create_sequencer_possessable(sequence, actor):
    binding = _safe_call(sequence, "add_possessable", actor)
    if binding is None:
        return None, "Could not add TMP locator as a possessable to the selected sequence."
    return binding, ""


def _create_sequencer_attach_track(sequence, locator_binding, parent_binding, root_bone_name, start_frame, end_frame):
    attach_track_class = getattr(unreal, "MovieScene3DAttachTrack", None)
    if attach_track_class is None:
        return None, None, "unreal.MovieScene3DAttachTrack is unavailable."
    attach_track = _safe_call(locator_binding, "add_track", attach_track_class)
    if attach_track is None:
        return None, None, "Could not add MovieScene3DAttachTrack to TMP locator binding."
    attach_section = _safe_call(attach_track, "add_section")
    if attach_section is None:
        return attach_track, None, "Could not add MovieScene3DAttachSection to TMP locator attach track."
    _set_section_range(attach_section, start_frame, end_frame)

    parent_binding_id, binding_id_attempts = _get_binding_id_for_attach(sequence, parent_binding)
    if parent_binding_id is None:
        return attach_track, attach_section, f"Could not create a MovieSceneObjectBindingID for the skeletal mesh parent binding. binding_id_attempts={binding_id_attempts}"
    _log(f"Created parent binding id for attach: {_class_name(parent_binding_id)} {_compact_text(parent_binding_id)}")
    _log(f"Parent binding id attempts: {binding_id_attempts}")

    binding_id_set, parent_attempts = _assign_attach_parent(attach_section, parent_binding_id)
    if not binding_id_set:
        return attach_track, attach_section, (
            "Could not assign parent binding id to MovieScene3DAttachSection. "
            f"parent_binding_id={_compact_text(parent_binding_id)} "
            f"Attach section class={_class_name(attach_section)} "
            f"attempts={parent_attempts} "
            f"method_hints={_method_hints(attach_section)[:120]} "
            f"available_props={_property_names(attach_section)[:120]}"
        )
    _log(f"Assigned attach parent binding id using one of: {parent_attempts}")
    _configure_attach_section(attach_section, root_bone_name)
    return attach_track, attach_section, ""


def _remove_binding_track(binding, track):
    if binding is None or track is None:
        return False
    ok, _ = _call_ok(binding, "remove_track", track)
    if ok:
        return True
    ok, _ = _call_ok(binding, "remove", track)
    return ok


def _find_locator_binding(sequence):
    return _find_binding_by_name(sequence, LOCATOR_LABEL)


def _find_locator_attach_track(locator_binding):
    if locator_binding is None:
        return None
    attach_track_class = getattr(unreal, "MovieScene3DAttachTrack", None)
    tracks = _as_list(_safe_call(locator_binding, "get_tracks"))
    for track in tracks:
        if attach_track_class is not None:
            try:
                if isinstance(track, attach_track_class):
                    return track
            except Exception:
                pass
        if "Attach" in _class_name(track):
            return track
    return None


def _create_locator_transform_bundle(locator_binding, start_frame, end_frame):
    track_class = getattr(unreal, "MovieScene3DTransformTrack", None)
    if track_class is None:
        return None, "MovieScene3DTransformTrack is unavailable."
    track = _safe_call(locator_binding, "add_track", track_class)
    if track is None:
        return None, "Could not add transform track to TMP locator binding."
    section = _safe_call(track, "add_section")
    if section is None:
        return None, "Could not add transform section to TMP locator track."
    _set_section_range(section, start_frame, end_frame)
    bundle = {key: [] for key in base.TRANSFORM_KEYS}
    for channel in base._get_section_channels(section):
        channel_name = base._get_channel_name(channel)
        transform_key = base._classify_transform_channel(channel_name)
        if transform_key:
            bundle[transform_key].append(channel)
    missing = [key for key in base.KEYS_TO_FLATTEN if not bundle.get(key)]
    if missing:
        return None, f"TMP locator transform track is missing channels: {missing}"
    return bundle, ""


def _key_locator_samples(locator_bundle, samples):
    for key in base.KEYS_TO_FLATTEN:
        channel = base._first_channel(locator_bundle, key)
        if channel is None:
            return f"TMP locator missing channel {key}."
        if not base._remove_all_keys(channel):
            return f"Could not clear TMP locator keys for {key}."
    for sample in samples:
        frame = sample["frame"]
        values = sample["values"]
        for key in base.KEYS_TO_FLATTEN:
            channel = base._first_channel(locator_bundle, key)
            if not base._add_channel_key(channel, frame, values[key]):
                return f"Could not key TMP locator {key} at frame {frame}."
    return ""


def _sample_locator_driven_by_attach(start_frame, end_frame, locator):
    samples = []
    zeroish_count = 0
    for frame in range(start_frame, max(start_frame + 1, end_frame)):
        if not _set_sequencer_time(frame):
            return None, "Could not set Sequencer current time from Python."
        _force_sequence_evaluate()
        transform = _safe_call(locator, "get_actor_transform")
        values = base._transform_to_values(transform)
        if values is None:
            return None, f"Could not read TMP locator world transform at frame {frame}."
        if abs(values["location_x"]) < 0.0001 and abs(values["location_y"]) < 0.0001 and abs(values["location_z"]) < 0.0001:
            zeroish_count += 1
        samples.append({"frame": frame, "transform": transform, "values": values})
    if samples and zeroish_count == len(samples):
        return None, "Sequencer attach track did not move TMP locator; every sampled locator transform remained at origin. Leave the attach track in place, scrub manually, then run with bake_existing_attached_locator=True."
    return samples, ""


def _build_global_ctrl_samples_from_locator(locator_samples, base_actor_values):
    base_actor_transform = base._make_transform(base_actor_values)
    output = []
    for sample in locator_samples:
        local_transform = base._make_relative_transform(sample["transform"], base_actor_transform)
        if local_transform is None:
            return None, f"Could not convert TMP locator to local global_ctrl at frame {sample['frame']}."
        values = base._transform_to_values(local_transform)
        if values is None:
            return None, f"Could not extract local global_ctrl values at frame {sample['frame']}."
        output.append({"frame": sample["frame"], "values": values})
    return output, ""


def _find_context(bp_actor_name, actor_binding_index, dry_run, skeletal_mesh_name):
    current_sequence = base._get_current_level_sequence()
    if current_sequence is None:
        return None, "No current Level Sequence is open in Sequencer."
    current_sequence_name = _safe_call(current_sequence, "get_name") or str(current_sequence)
    start_frame, end_frame = base._get_sequence_frame_range(current_sequence)
    if start_frame is None or end_frame is None:
        return None, "Could not read the current Level Sequence playback range."
    global_section, selected_global_names, selected_sequence_asset_path = base._get_selected_global_ctrl_section()
    if global_section is None:
        return None, "Select global_ctrl channels/keys in Sequencer before running this tool."
    selected_sequence = base._load_sequence_from_asset_path(selected_sequence_asset_path)
    selected_sequence_name = _safe_call(selected_sequence, "get_name") or ""
    if selected_sequence is None:
        return None, "Could not load the Level Sequence that owns selected global_ctrl."
    global_bundle = base._find_global_ctrl_channels_from_section(global_section)
    missing = base._missing_required_channels(global_bundle)
    if missing:
        return None, f"Selected global_ctrl section is missing required channels: {missing}"
    selected_actor_candidates = base._find_selected_actor_candidates()
    sequence_entries = [(f"selected_global_ctrl_sequence:{selected_sequence_name}", selected_sequence), (f"current_sequence:{current_sequence_name}", current_sequence)]
    searched_actor_candidates = base._find_actor_candidates_in_sequences(sequence_entries)
    chosen_candidate, candidates_to_use = base._choose_actor_candidate(selected_actor_candidates, searched_actor_candidates, bp_actor_name, actor_binding_index, dry_run)
    if chosen_candidate is None:
        return None, "Could not choose a Blueprint Actor candidate."
    actor_name = bp_actor_name or base._binding_name(chosen_candidate["binding"])
    bp_actor = _find_level_actor_by_name(actor_name)
    if bp_actor is None:
        return None, f"Could not find a level actor matching {actor_name!r}. Select the actor in the level or pass bp_actor_name."
    skeletal_component, skeletal_error = _find_skeletal_mesh_component(bp_actor, skeletal_mesh_name)
    if skeletal_error:
        return None, skeletal_error
    skeletal_binding = _find_binding_by_name(selected_sequence, skeletal_mesh_name or _object_name(skeletal_component))
    if skeletal_binding is None:
        return None, f"Could not find a Sequencer binding for skeletal_mesh_name={skeletal_mesh_name!r}. Select/add the skeletal mesh component binding in the ANM sequence before running."
    return {
        "current_sequence_name": current_sequence_name,
        "selected_sequence": selected_sequence,
        "selected_sequence_name": selected_sequence_name,
        "selected_sequence_asset_path": selected_sequence_asset_path,
        "start_frame": start_frame,
        "end_frame": end_frame,
        "selected_global_names": selected_global_names,
        "global_bundle": global_bundle,
        "chosen_candidate": chosen_candidate,
        "candidates_to_use": candidates_to_use,
        "bp_actor": bp_actor,
        "skeletal_component": skeletal_component,
        "skeletal_binding": skeletal_binding,
    }, ""


def _print_context(context, bp_actor_name, skeletal_mesh_name, root_bone_name):
    chosen_candidate = context["chosen_candidate"]
    try:
        chosen_index = context["candidates_to_use"].index(chosen_candidate)
    except Exception:
        chosen_index = 0
    _log("==================================================")
    _log(f"Current Level Sequence: {context['current_sequence_name']}")
    _log(f"Playback frame range: {context['start_frame']} to {context['end_frame']} end-exclusive")
    _log(f"Selected global_ctrl channels: {context['selected_global_names']}")
    _log(f"Selected global_ctrl sequence asset path: {context['selected_sequence_asset_path']}")
    _log(f"Loaded selected global_ctrl sequence: {context['selected_sequence_name']}")
    _log(f"Blueprint Actor object: {_object_name(context['bp_actor'])} class={_class_name(context['bp_actor'])}")
    _log(f"Skeletal Mesh Component object: {_object_name(context['skeletal_component'])} class={_class_name(context['skeletal_component'])}")
    _log(f"Skeletal Mesh Sequencer binding: {base._binding_name(context['skeletal_binding'])}")
    _log(f"Root bone/socket used for Sequencer attach: {root_bone_name}")
    if bp_actor_name:
        _log(f"Required Blueprint Actor name filter: {bp_actor_name}")
    if skeletal_mesh_name:
        _log(f"Required Skeletal Mesh name filter: {skeletal_mesh_name}")
    _log(f"Actor search chose source: {chosen_candidate['source']}")
    _log(f"Actor search chose sequence: {chosen_candidate['sequence_label']}")
    base._print_actor_candidates(context["candidates_to_use"], chosen_index, label="Usable actor transform candidates")
    base._print_bundle("Chosen Blueprint Actor", chosen_candidate["bundle"])
    base._print_bundle("Selected global_ctrl", context["global_bundle"])
    _log("==================================================")


def _setup_attach_pass(context, root_bone_name, keep_existing_locator=False):
    if not keep_existing_locator:
        _delete_existing_debug_locators()
    locator = _find_locator_actor()
    if locator is None:
        locator, locator_error = _spawn_locator(LOCATOR_LABEL)
        if locator_error:
            return None, None, locator_error
        _log(f"Created movable debug locator actor: {_object_name(locator)} class={_class_name(locator)}")
    else:
        _log(f"Using existing debug locator actor: {_object_name(locator)} class={_class_name(locator)}")

    locator_binding, binding_error = _create_sequencer_possessable(context["selected_sequence"], locator)
    if binding_error:
        return locator, None, binding_error
    _log("Added TMP locator possessable. No transform track is created in setup pass.")

    attach_track, attach_section, attach_error = _create_sequencer_attach_track(
        context["selected_sequence"],
        locator_binding,
        context["skeletal_binding"],
        root_bone_name,
        context["start_frame"],
        context["end_frame"],
    )
    if attach_error:
        return locator, locator_binding, attach_error
    _log(f"Created Sequencer attach section: TMP locator -> {base._binding_name(context['skeletal_binding'])}.{root_bone_name}")
    _log("Setup pass complete. Scrub/play the sequence manually now and confirm TMP locator follows the skeletal root.")
    return locator, locator_binding, ""


def _bake_existing_locator_pass(context, keep_debug_locator, perform_final_rebuild, dry_run):
    locator = _find_locator_actor()
    if locator is None:
        return "Could not find TMP_global_ctrl_sampled_locator. Run setup_attach_only=True first."
    locator_binding = _find_locator_binding(context["selected_sequence"])
    if locator_binding is None:
        return "Could not find TMP locator binding in the selected sequence. Run setup_attach_only=True first."
    attach_track = _find_locator_attach_track(locator_binding)
    if attach_track is None:
        return "Could not find an Attach track on TMP locator binding. Run setup_attach_only=True first."

    locator_samples, sample_error = _sample_locator_driven_by_attach(context["start_frame"], context["end_frame"], locator)
    if sample_error:
        return sample_error

    if not _remove_binding_track(locator_binding, attach_track):
        _log_warning("Could not remove the Sequencer attach track from TMP locator. Locator may continue to be driven by the attach section.")
    else:
        _log("Removed Sequencer attach track from TMP locator after sampling.")

    locator_bundle, locator_track_error = _create_locator_transform_bundle(locator_binding, context["start_frame"], context["end_frame"])
    if locator_track_error:
        return locator_track_error
    _log("Created locator Transform track after attachment sampling, then baking sampled world transforms onto it.")

    key_error = _key_locator_samples(locator_bundle, locator_samples)
    if key_error:
        return key_error

    first_locator_values = locator_samples[0]["values"]
    new_global_samples, conversion_error = _build_global_ctrl_samples_from_locator(locator_samples, first_locator_values)
    if conversion_error:
        return conversion_error

    _log(f"First Sequencer-attached TMP locator frame {locator_samples[0]['frame']}: {base._format_values(locator_samples[0]['values'])}")
    _log(f"Last Sequencer-attached TMP locator frame {locator_samples[-1]['frame']}: {base._format_values(locator_samples[-1]['values'])}")
    _log(f"First rebuilt local global_ctrl frame {new_global_samples[0]['frame']}: {base._format_values(new_global_samples[0]['values'])}")
    _log(f"Last rebuilt local global_ctrl frame {new_global_samples[-1]['frame']}: {base._format_values(new_global_samples[-1]['values'])}")

    if dry_run or not perform_final_rebuild:
        _log("LOCATOR BAKE ONLY. BP actor/global_ctrl keys were not changed.")
        _log("TMP locator now has normal transform keys. Inspect it before final rebuild.")
        return ""

    transaction_class = getattr(unreal, "ScopedEditorTransaction", None)
    if transaction_class is not None:
        with transaction_class("Sequencer Attach Locator Flatten World Position To Global Ctrl"):
            apply_error = base._clear_and_write(
                context["chosen_candidate"]["bundle"],
                context["global_bundle"],
                context["start_frame"],
                first_locator_values,
                new_global_samples,
            )
    else:
        apply_error = base._clear_and_write(
            context["chosen_candidate"]["bundle"],
            context["global_bundle"],
            context["start_frame"],
            first_locator_values,
            new_global_samples,
        )
    if apply_error:
        return apply_error

    if keep_debug_locator:
        _log(f"Sequencer-attach locator flatten complete. Kept debug locator: {LOCATOR_LABEL}")
    else:
        _destroy_actor(locator)
        _log("Sequencer-attach locator flatten complete. Deleted debug locator.")
    _log(f"Wrote {len(new_global_samples)} frame(s) to global_ctrl and keyed actor base at frame {context['start_frame']}.")
    _log("Review animation before saving.")
    return ""


def run(
    dry_run=True,
    bp_actor_name="",
    skeletal_mesh_name="",
    root_bone_name="root",
    actor_binding_index=0,
    keep_debug_locator=True,
    perform_final_rebuild=False,
    setup_attach_only=True,
    bake_existing_attached_locator=False,
):
    try:
        _log("----- Sequencer attach locator method run() called -----")
        _log(
            f"dry_run={dry_run!r} bp_actor_name={bp_actor_name!r} skeletal_mesh_name={skeletal_mesh_name!r} "
            f"root_bone_name={root_bone_name!r} actor_binding_index={actor_binding_index!r} "
            f"keep_debug_locator={keep_debug_locator!r} perform_final_rebuild={perform_final_rebuild!r} "
            f"setup_attach_only={setup_attach_only!r} bake_existing_attached_locator={bake_existing_attached_locator!r}"
        )

        context, error = _find_context(bp_actor_name, actor_binding_index, dry_run, skeletal_mesh_name)
        if error:
            _log_error(error)
            return ""
        _print_context(context, bp_actor_name, skeletal_mesh_name, root_bone_name)

        if bake_existing_attached_locator:
            bake_error = _bake_existing_locator_pass(context, keep_debug_locator, perform_final_rebuild, dry_run)
            if bake_error:
                _log_error(bake_error)
                return ""
            return "true"

        locator, locator_binding, setup_error = _setup_attach_pass(context, root_bone_name, keep_existing_locator=False)
        if setup_error:
            _log_error(setup_error)
            if locator is not None and not keep_debug_locator:
                _destroy_actor(locator)
            return ""

        if setup_attach_only:
            _log("SETUP ONLY. The real Sequencer attach track was left in the sequence.")
            _log("Next: scrub the sequence manually. If TMP locator follows correctly, run again with bake_existing_attached_locator=True.")
            return "true"

        bake_error = _bake_existing_locator_pass(context, keep_debug_locator, perform_final_rebuild, dry_run)
        if bake_error:
            _log_error(bake_error)
            return ""
        return "true"

    except Exception:
        _log_error(traceback.format_exc())
        return ""
