"""
Place debug spheres at the world location of the current Unreal editor selection.

Supports the common cases first:
- selected level actors
- selected actor components
- selected Sequencer / Control Rig controls when Unreal exposes them to Python

Blueprint / Python usage:

    import sphere_at_selected
    import importlib

    importlib.reload(sphere_at_selected)

    # Default sphere radius is 10 cm.
    success = sphere_at_selected.run()

    # Optional custom radius in centimeters.
    success = sphere_at_selected.run(25.0)

Returns:
    "true" when at least one sphere is created, or "" on failure/no supported selection.
"""

import traceback

import unreal


LOG_PREFIX = "[SphereAtSelected]"
DEFAULT_RADIUS_CM = 10.0
DEFAULT_LABEL_PREFIX = "LOC_Sphere"
ENGINE_SPHERE_MESH_PATH = "/Engine/BasicShapes/Sphere.Sphere"


try:
    _RIG_ELEMENT_TYPE_CONTROL = unreal.RigElementType.CONTROL
except Exception:
    _RIG_ELEMENT_TYPE_CONTROL = None


# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------


def _log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


def _log_warning(message):
    unreal.log_warning(f"{LOG_PREFIX} Warning: {message}")


def _log_error(message):
    unreal.log_error(f"{LOG_PREFIX} Error: {message}")


# -----------------------------------------------------------------------------
# Small helpers
# -----------------------------------------------------------------------------


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


def _to_float(value, fallback):
    try:
        return float(value)
    except Exception:
        return fallback


def _clean_name(value):
    text = str(value or "").strip()
    if not text:
        return "Selection"

    # Control names can arrive as RigElementKey string forms. Keep actor labels readable.
    for prefix in ("RigElementKey(type=Control, name=", "RigElementKey(type=CONTROL, name="):
        if text.startswith(prefix) and text.endswith(")"):
            text = text[len(prefix):-1]

    for char in " \\/:;,.[]{}()<>|?*\"'`~!@#$%^&+=":
        text = text.replace(char, "_")

    while "__" in text:
        text = text.replace("__", "_")

    return text.strip("_") or "Selection"


def _get_location_from_transform(transform):
    if transform is None:
        return None

    if isinstance(transform, unreal.Vector):
        return transform

    location = getattr(transform, "translation", None)
    if location is not None:
        return location

    location = _safe_call(transform, "get_location")
    if location is not None:
        return location

    return None


def _get_actor_location(actor):
    location = _safe_call(actor, "get_actor_location")
    if isinstance(location, unreal.Vector):
        return location
    return None


def _get_component_location(component):
    for function_name in ("get_world_location", "get_component_location"):
        location = _safe_call(component, function_name)
        if isinstance(location, unreal.Vector):
            return location

    transform = _safe_call(component, "get_world_transform")
    location = _get_location_from_transform(transform)
    if isinstance(location, unreal.Vector):
        return location

    return None


def _make_unique_points(points):
    unique = []
    seen = set()

    for label, location in points:
        if not isinstance(location, unreal.Vector):
            continue

        key = (
            round(float(location.x), 3),
            round(float(location.y), 3),
            round(float(location.z), 3),
            _clean_name(label),
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append((label, location))

    return unique


# -----------------------------------------------------------------------------
# Editor selection support
# -----------------------------------------------------------------------------


def _get_editor_actor_subsystem():
    try:
        return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    except Exception:
        return None


def _get_selected_level_actors():
    actor_subsystem = _get_editor_actor_subsystem()
    actors = _safe_call(actor_subsystem, "get_selected_level_actors")

    if actors is not None:
        return list(actors)

    actors = _safe_call(unreal.EditorLevelLibrary, "get_selected_level_actors")
    if actors is not None:
        return list(actors)

    return []


def _get_selected_components():
    # Component selection support varies by Unreal version, so this stays defensive.
    component_editor_subsystem_class = getattr(unreal, "EditorComponentSubsystem", None)
    if component_editor_subsystem_class is not None:
        try:
            component_subsystem = unreal.get_editor_subsystem(component_editor_subsystem_class)
            components = _safe_call(component_subsystem, "get_selected_components")
            if components is not None:
                return list(components)
        except Exception:
            pass

    editor_utility_library = getattr(unreal, "EditorUtilityLibrary", None)
    components = _safe_call(editor_utility_library, "get_selected_assets")
    if components is not None:
        return [item for item in list(components) if isinstance(item, unreal.ActorComponent)]

    return []


def _collect_actor_points():
    points = []

    for actor in _get_selected_level_actors():
        location = _get_actor_location(actor)
        if location is None:
            continue

        label = _safe_call(actor, "get_actor_label") or _safe_call(actor, "get_name") or "Actor"
        points.append((label, location))

    for component in _get_selected_components():
        location = _get_component_location(component)
        if location is None:
            continue

        label = _safe_call(component, "get_name") or "Component"
        owner = _safe_call(component, "get_owner")
        owner_label = _safe_call(owner, "get_actor_label") if owner else ""
        if owner_label:
            label = f"{owner_label}_{label}"

        points.append((label, location))

    return _make_unique_points(points)


# -----------------------------------------------------------------------------
# Sequencer / Control Rig support
# -----------------------------------------------------------------------------


def _get_current_level_sequence():
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    sequence = _safe_call(library, "get_current_level_sequence")
    return sequence


def _get_current_frame_number():
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)

    current_time = _safe_call(library, "get_current_time")
    if current_time is None:
        return None

    # UE versions differ here: some return FrameNumber, some return SequencerScriptingRange-ish objects.
    frame_number = getattr(current_time, "frame_number", None)
    if frame_number is not None:
        return frame_number

    value = getattr(current_time, "value", None)
    if value is not None:
        try:
            return unreal.FrameNumber(int(value))
        except Exception:
            return None

    try:
        return unreal.FrameNumber(int(current_time))
    except Exception:
        return None


def _get_control_rig_from_proxy(proxy):
    for attribute_name in ("control_rig", "rig"):
        rig = getattr(proxy, attribute_name, None)
        if rig is not None:
            return rig

    for function_name in ("get_control_rig", "get_rig"):
        rig = _safe_call(proxy, function_name)
        if rig is not None:
            return rig

    return None


def _get_control_rig_binding_object_from_proxy(proxy):
    for attribute_name in (
        "bound_object",
        "object",
        "component",
        "skeletal_mesh_component",
        "skel_mesh_component",
    ):
        value = getattr(proxy, attribute_name, None)
        if value is not None:
            return value

    for function_name in (
        "get_bound_object",
        "get_object",
        "get_component",
        "get_skeletal_mesh_component",
    ):
        value = _safe_call(proxy, function_name)
        if value is not None:
            return value

    return None


def _get_control_rig_proxies(sequence):
    library = getattr(unreal, "ControlRigSequencerLibrary", None)
    proxies = _safe_call(library, "get_control_rigs", sequence)

    if proxies is None:
        return []

    return list(proxies)


def _normalize_control_name(value):
    name = getattr(value, "name", None)
    if name:
        return str(name)

    return str(value)


def _get_selected_control_names(control_rig):
    candidates = []

    for function_name in (
        "current_control_selection",
        "get_current_control_selection",
        "get_selected_controls",
        "get_control_selection",
        "selected_controls",
    ):
        selection = _safe_call(control_rig, function_name)
        if selection:
            candidates.extend(list(selection))

    hierarchy = _safe_call(control_rig, "get_hierarchy")
    if hierarchy is not None:
        for function_name in (
            "get_selected_keys",
            "get_current_selection",
            "current_selection",
            "get_selection",
        ):
            selection = _safe_call(hierarchy, function_name)
            if selection:
                candidates.extend(list(selection))

    names = []
    seen = set()

    for item in candidates:
        item_type = getattr(item, "type", None)
        if _RIG_ELEMENT_TYPE_CONTROL is not None and item_type is not None and item_type != _RIG_ELEMENT_TYPE_CONTROL:
            continue

        name = _normalize_control_name(item).strip()
        if not name:
            continue

        if name not in seen:
            seen.add(name)
            names.append(name)

    return names


def _try_get_control_world_transform_from_sequencer(sequence, control_rig, control_name):
    library = getattr(unreal, "ControlRigSequencerLibrary", None)
    if library is None:
        return None

    frame_number = _get_current_frame_number()

    call_patterns = []
    if frame_number is not None:
        call_patterns.extend([
            ("get_control_rig_world_transform", sequence, control_rig, control_name, frame_number),
            ("get_control_world_transform", sequence, control_rig, control_name, frame_number),
            ("get_control_rig_transform", sequence, control_rig, control_name, frame_number),
            ("get_control_transform", sequence, control_rig, control_name, frame_number),
        ])

    call_patterns.extend([
        ("get_control_rig_world_transform", sequence, control_rig, control_name),
        ("get_control_world_transform", sequence, control_rig, control_name),
        ("get_control_rig_transform", sequence, control_rig, control_name),
        ("get_control_transform", sequence, control_rig, control_name),
    ])

    for pattern in call_patterns:
        function_name = pattern[0]
        args = pattern[1:]
        transform = _safe_call(library, function_name, *args)
        if transform is not None:
            return transform

    return None


def _try_get_control_global_transform_from_rig(control_rig, control_name):
    for function_name in (
        "get_control_global_transform",
        "get_global_transform",
        "get_control_transform",
        "get_control_global_transform_by_name",
    ):
        transform = _safe_call(control_rig, function_name, control_name)
        if transform is not None:
            return transform

    hierarchy = _safe_call(control_rig, "get_hierarchy")
    if hierarchy is None:
        return None

    key = None
    if _RIG_ELEMENT_TYPE_CONTROL is not None:
        try:
            key = unreal.RigElementKey(type=_RIG_ELEMENT_TYPE_CONTROL, name=control_name)
        except Exception:
            key = None

    if key is not None:
        for function_name in ("get_global_transform", "get_transform"):
            for args in ((key, False), (key,)):
                transform = _safe_call(hierarchy, function_name, *args)
                if transform is not None:
                    return transform

    return None


def _combine_component_and_control_locations(binding_object, control_transform):
    control_location = _get_location_from_transform(control_transform)
    if control_location is None:
        return None

    if binding_object is None:
        return control_location

    # If Sequencer gives a true world transform, returning the control location is already correct.
    # If the ControlRig only gives rig/component space, this binding transform gets it close enough for markers.
    binding_transform = None
    if isinstance(binding_object, unreal.Actor):
        binding_transform = _safe_call(binding_object, "get_actor_transform")
    elif isinstance(binding_object, unreal.SceneComponent):
        binding_transform = _safe_call(binding_object, "get_world_transform")

    if binding_transform is None:
        return control_location

    try:
        return binding_transform.transform_position(control_location)
    except Exception:
        return control_location


def _collect_control_rig_points():
    sequence = _get_current_level_sequence()
    if sequence is None:
        return []

    points = []

    for proxy in _get_control_rig_proxies(sequence):
        control_rig = _get_control_rig_from_proxy(proxy)
        if control_rig is None:
            continue

        selected_control_names = _get_selected_control_names(control_rig)
        if not selected_control_names:
            continue

        binding_object = _get_control_rig_binding_object_from_proxy(proxy)

        for control_name in selected_control_names:
            transform = _try_get_control_world_transform_from_sequencer(sequence, control_rig, control_name)
            if transform is not None:
                location = _get_location_from_transform(transform)
            else:
                transform = _try_get_control_global_transform_from_rig(control_rig, control_name)
                location = _combine_component_and_control_locations(binding_object, transform)

            if not isinstance(location, unreal.Vector):
                _log_warning(f"Could not resolve world location for Control Rig control: {control_name}")
                continue

            points.append((control_name, location))

    return _make_unique_points(points)


# -----------------------------------------------------------------------------
# Sphere creation
# -----------------------------------------------------------------------------


def _load_sphere_mesh():
    mesh = unreal.load_object(None, ENGINE_SPHERE_MESH_PATH)
    if mesh is None:
        _log_error(f"Could not load sphere mesh: {ENGINE_SPHERE_MESH_PATH}")
    return mesh


def _spawn_actor_from_object(asset, location):
    actor_subsystem = _get_editor_actor_subsystem()
    rotation = unreal.Rotator(0.0, 0.0, 0.0)

    actor = _safe_call(actor_subsystem, "spawn_actor_from_object", asset, location, rotation)
    if actor is not None:
        return actor

    actor = _safe_call(unreal.EditorLevelLibrary, "spawn_actor_from_object", asset, location, rotation)
    if actor is not None:
        return actor

    return None


def _set_actor_label(actor, label):
    safe_label = _clean_name(label)
    final_label = f"{DEFAULT_LABEL_PREFIX}_{safe_label}"
    _safe_call(actor, "set_actor_label", final_label)


def _set_sphere_scale(actor, radius_cm):
    radius = max(_to_float(radius_cm, DEFAULT_RADIUS_CM), 0.1)

    # /Engine/BasicShapes/Sphere is roughly 100 cm across at scale 1.0.
    uniform_scale = (radius * 2.0) / 100.0
    _safe_call(actor, "set_actor_scale3d", unreal.Vector(uniform_scale, uniform_scale, uniform_scale))


def _create_sphere_at_location(label, location, radius_cm):
    mesh = _load_sphere_mesh()
    if mesh is None:
        return None

    actor = _spawn_actor_from_object(mesh, location)
    if actor is None:
        _log_error(f"Could not spawn sphere actor at {location}")
        return None

    _set_actor_label(actor, label)
    _set_sphere_scale(actor, radius_cm)

    return actor


# -----------------------------------------------------------------------------
# Public entry point
# -----------------------------------------------------------------------------


def run(radius_cm=DEFAULT_RADIUS_CM):
    try:
        radius = _to_float(radius_cm, DEFAULT_RADIUS_CM)
        points = []

        # Level actors/components are the most reliable case, including many Sequencer-spawned actors.
        points.extend(_collect_actor_points())

        # Control Rig selections are exposed differently across UE versions, so this is best-effort.
        points.extend(_collect_control_rig_points())

        points = _make_unique_points(points)

        if not points:
            _log_warning(
                "No supported selection found. Select a level actor/component, or a Control Rig control "
                "that Unreal exposes to Python in the active Level Sequence."
            )
            return ""

        created = []
        for label, location in points:
            actor = _create_sphere_at_location(label, location, radius)
            if actor is not None:
                created.append(actor)

        if not created:
            _log_error("Found selection points, but no spheres were created.")
            return ""

        _log(f"Created {len(created)} sphere(s).")
        return "true"

    except Exception:
        _log_error(traceback.format_exc())
        return ""


if __name__ == "__main__":
    run()
