"""
Attach Snap Bake Diagnostic.

Read-only probe of the recorder_sphere state. It writes NO keys, creates NO tracks,
and never touches global_ctrl or the Blueprint Actor.

Run it with the same Sequencer selection as the safe stage-two run (Blueprint Actor
binding + Bungie_Char binding + global_ctrl channels selected) so context resolves
the same way.

Socket sampling strategy (v2):
The first version sampled the SkeletalMeshComponent reference resolved ONCE at
startup from the editor-level actor lookup. That reference can go stale across
sequencer re-evaluations, and space-enum lookup failures were skipped silently,
which produced <none> for every socket read. This version resolves the evaluated
component PER FRAME through three routes, in order:

1. attach-parent: the sphere's root component's get_attach_parent() and
   get_attach_socket_name(). This is literally the component/socket the live
   Attach track attached the sphere to at evaluation time - ground truth.
2. bound-objects: the Blueprint Actor binding's Sequencer bound objects, then
   SkeletalMeshComponents on that runtime actor matched by name.
3. context: the startup-resolved skeletal component (may be stale; kept last).

Every attempt is logged with the exception text on failure - nothing is
swallowed silently anymore.

Per probe frame it prints:
- sequencer time readback (root + local)
- helper world transform and its live attach parent
- root socket world transform + which route/component produced it
- distance between helper and root (should be ~0 while the attach is live)
- helper transform RELATIVE to the socket (should be ~identity with
  SNAP_TO_TARGET location/rotation)
- resolved runtime actor and SkeletalMeshComponent names/classes

Optional: deactivate_attach_for_comparison=True temporarily sets the attach
sections inactive, re-samples the same frames (so the sphere is driven only by
whatever transform keys exist), prints per-frame deltas against the live socket
samples, then RESTORES the attach sections. Only meaningful after a bake has
written keys; in the setup-only state the sphere will just sit at identity.
"""

import importlib
import traceback

import unreal

import flatten_world_position_to_global_ctrl_attach_snap_method as attach_base


LOG_PREFIX = "[AttachSnapBakeDiag]"


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
    try:
        return list(value)
    except Exception:
        return [value]


def _class_name(obj):
    cls = _safe_call(obj, "get_class")
    return str(_safe_call(cls, "get_name") or type(obj))


def _sequence_label(sequence):
    if sequence is None:
        return "<none>"
    return f"{_safe_call(sequence, 'get_name')} path={_safe_call(sequence, 'get_path_name')}"


def _fmt_vec(vec):
    if vec is None:
        return "<none>"
    return f"({float(vec.x):.4f}, {float(vec.y):.4f}, {float(vec.z):.4f})"


def _fmt_rot(rot):
    if rot is None:
        return "<none>"
    return f"(roll={float(rot.roll):.4f}, pitch={float(rot.pitch):.4f}, yaw={float(rot.yaw):.4f})"


# unreal.Transform is a plain script struct: properties translation (Vector),
# rotation (Quat), scale3d (Vector). It has NO get_translation()/rotator() methods,
# which is why the v2 extractor printed <none> for everything except scale.
_TRANSFORM_SHAPE_LOGGED = [False]


def _log_transform_shape_once(transform):
    if _TRANSFORM_SHAPE_LOGGED[0] or transform is None:
        return
    _TRANSFORM_SHAPE_LOGGED[0] = True
    _log(f"transform raw: type={type(transform)} repr={transform!r}")
    members = [name for name in dir(transform) if not name.startswith("_")]
    _log(f"transform members: {members}")


def _quat_to_rotator(quat):
    if quat is None:
        return None
    rotator = _safe_call(quat, "rotator")
    if rotator is not None:
        return rotator
    return _safe_call(getattr(unreal, "MathLibrary", None), "quat_rotator", quat)


def _transform_parts(transform):
    """Return (location Vector, rotation Rotator, scale Vector) from an unreal.Transform."""
    if transform is None:
        return None, None, None
    _log_transform_shape_once(transform)

    # Preferred: KismetMathLibrary BreakTransform -> (Location, Rotation(Rotator), Scale).
    parts = _safe_call(getattr(unreal, "MathLibrary", None), "break_transform", transform)
    if parts is not None:
        try:
            location, rotation, scale = parts
            if location is not None and rotation is not None:
                return location, rotation, scale
        except Exception:
            pass

    # Fallback: struct properties. rotation is a Quat and needs Rotator conversion.
    location = _safe_get_editor_property(transform, "translation")
    if location is None:
        location = _safe_get_editor_property(transform, "location")
    rotation = _quat_to_rotator(_safe_get_editor_property(transform, "rotation"))
    scale = _safe_get_editor_property(transform, "scale3d")
    if scale is None:
        scale = _safe_get_editor_property(transform, "scale")
    return location, rotation, scale


def _transform_loc_rot(transform):
    location, rotation, _scale = _transform_parts(transform)
    return location, rotation


def _fmt_transform(transform):
    if transform is None:
        return "<none>"
    location, rotation, scale = _transform_parts(transform)
    return f"loc={_fmt_vec(location)} rot={_fmt_rot(rotation)} scale={_fmt_vec(scale)}"


def _describe_component(component):
    if component is None:
        return "<none>"
    owner = _safe_call(component, "get_owner")
    return (
        f"{_safe_call(component, 'get_name')} class={_class_name(component)} "
        f"owner={attach_base._object_name(owner)} owner_class={_class_name(owner)}"
    )


def _describe_actor(actor):
    if actor is None:
        return "<none>"
    return f"{attach_base._object_name(actor)} class={_class_name(actor)}"


def _binding_kind(sequence, binding):
    guid_text = str(_safe_call(binding, "get_id"))
    for spawnable in _as_list(_safe_call(sequence, "get_spawnables")):
        if str(_safe_call(spawnable, "get_id")) == guid_text:
            return "spawnable"
    for possessable in _as_list(_safe_call(sequence, "get_possessables")):
        if str(_safe_call(possessable, "get_id")) == guid_text:
            return "possessable"
    return "unknown"


def _find_sphere_binding(sequence, sphere_name):
    bindings = list(attach_base._iter_all_bindings(sequence))
    exact = [b for b in bindings if attach_base._binding_name(b) == sphere_name]
    if exact:
        return exact[-1], "exact name"
    contains = [b for b in bindings if sphere_name.lower() in attach_base._binding_name(b).lower()]
    if contains:
        return contains[-1], "contains name"
    with_attach = [
        b for b in bindings
        if any("Attach" in _class_name(t) for t in _as_list(_safe_call(b, "get_tracks")))
    ]
    if with_attach:
        return with_attach[-1], "binding with Attach track"
    return None, "not found"


def _channel_name(channel):
    value = _safe_get_editor_property(channel, "channel_name")
    if value:
        return str(value)
    for fn in ("get_name", "get_display_name"):
        value = _safe_call(channel, fn)
        if value:
            return str(value)
    return _class_name(channel)


def _key_frame_and_value(key):
    frame = None
    time_unit = getattr(unreal, "MovieSceneTimeUnit", None)
    display_rate = getattr(time_unit, "DISPLAY_RATE", None) if time_unit else None
    for args in ((display_rate,), ()) if display_rate is not None else ((),):
        try:
            t = key.get_time(*args)
        except Exception:
            continue
        frame_number = getattr(t, "frame_number", None)
        if frame_number is not None:
            frame = int(getattr(frame_number, "value", frame_number))
            break
        try:
            frame = int(getattr(t, "value", t))
            break
        except Exception:
            pass
    value = _safe_call(key, "get_value")
    try:
        value = float(value)
    except Exception:
        pass
    return frame, value


def _transform_track_summary(binding):
    lines = []
    tracks = [t for t in _as_list(_safe_call(binding, "get_tracks")) if "TransformTrack" in _class_name(t)]
    lines.append(f"transform tracks on binding: {len(tracks)}")
    for track_index, track in enumerate(tracks):
        sections = _as_list(_safe_call(track, "get_sections"))
        lines.append(f"track[{track_index}] {_class_name(track)} sections={len(sections)}")
        for section_index, section in enumerate(sections):
            start = _safe_call(section, "get_start_frame")
            end = _safe_call(section, "get_end_frame")
            active = _safe_call(section, "is_active")
            blend = _safe_call(section, "get_blend_type")
            channels_all = _as_list(_safe_call(section, "get_all_channels"))
            lines.append(
                f"  section[{section_index}] range=[{start},{end}) active={active} blend={blend} "
                f"channels={len(channels_all)}"
            )
            true_total = 0
            for channel in channels_all:
                keys = _as_list(_safe_call(channel, "get_keys"))
                true_total += len(keys)
                if keys:
                    first_frame, first_value = _key_frame_and_value(keys[0])
                    last_frame, last_value = _key_frame_and_value(keys[-1])
                    lines.append(
                        f"    channel {_channel_name(channel)}: keys={len(keys)} "
                        f"first=({first_frame}, {first_value}) last=({last_frame}, {last_value})"
                    )
                else:
                    lines.append(f"    channel {_channel_name(channel)}: keys=0")
            lines.append(f"  section[{section_index}] TRUE total keys={true_total}")
    return lines


def _attach_sections(binding):
    sections = []
    for track in _as_list(_safe_call(binding, "get_tracks")):
        if "Attach" not in _class_name(track):
            continue
        for section in _as_list(_safe_call(track, "get_sections")):
            sections.append((track, section))
    return sections


def _attach_summary(binding):
    lines = []
    pairs = _attach_sections(binding)
    lines.append(f"attach tracks/sections on binding: {len(pairs)}")
    for index, (track, section) in enumerate(pairs):
        start = _safe_call(section, "get_start_frame")
        end = _safe_call(section, "get_end_frame")
        active = _safe_call(section, "is_active")
        socket = _safe_get_editor_property(section, "attach_socket_name")
        component = _safe_get_editor_property(section, "attach_component_name")
        constraint = _safe_call(section, "get_constraint_binding_id")
        lines.append(
            f"  attach[{index}] {_class_name(track)} range=[{start},{end}) active={active} "
            f"socket={socket} component={component} constraint_binding={constraint}"
        )
    return lines


def _set_time_and_report(frame):
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    ok = True
    try:
        library.set_current_time(int(frame))
    except Exception as exc:
        ok = False
        _log_warning(f"set_current_time({frame}) failed: {exc}")
    _safe_call(library, "refresh_current_level_sequence")
    current = _safe_call(library, "get_current_time")
    local = _safe_call(library, "get_current_local_time")
    return ok, current, local


def _resolve_sphere_actor(sequence, sphere_binding):
    objects, attempts = attach_base._resolve_bound_objects(sequence, sphere_binding)
    for obj in objects:
        if _safe_call(obj, "get_actor_location") is not None:
            return obj, attempts
    return None, attempts


def _get_root_component(actor):
    component = _safe_get_editor_property(actor, "root_component")
    if component is not None:
        return component
    return _safe_call(actor, "get_root_component")


def _is_valid_object(obj):
    return bool(_safe_call(getattr(unreal, "SystemLibrary", None), "is_valid", obj))


def _resolve_skeletal_candidates(sequence, context, sphere_actor, attempts):
    """Return ordered [(route_label, component, socket_name_or_None)] resolved fresh this frame."""
    candidates = []

    # Route 1: read the live attachment straight off the sphere. Ground truth.
    if sphere_actor is not None:
        sphere_root = _get_root_component(sphere_actor)
        attempts.append(f"route1 sphere root_component: {_describe_component(sphere_root)}")
        parent_component = _safe_call(sphere_root, "get_attach_parent")
        parent_socket = _safe_call(sphere_root, "get_attach_socket_name")
        attempts.append(
            f"route1 get_attach_parent(): {_describe_component(parent_component)} "
            f"get_attach_socket_name(): {parent_socket}"
        )
        if parent_component is not None:
            candidates.append(("attach-parent", parent_component, parent_socket))
    else:
        attempts.append("route1 skipped: sphere actor unresolved")

    # Route 2: Sequencer bound objects of the Blueprint Actor binding -> skeletal components.
    bp_binding = context.get("bp_actor_binding")
    bound_objects, resolve_attempts = attach_base._resolve_bound_objects(sequence, bp_binding)
    attempts.append(f"route2 bp binding bound objects: {[_describe_actor(obj) for obj in bound_objects]}")
    if not bound_objects:
        attempts.append(f"route2 resolve attempts: {resolve_attempts}")
    skeletal_class = getattr(unreal, "SkeletalMeshComponent", None)
    preferred = str(context.get("skeletal_component_name") or "")
    for obj in bound_objects:
        components = _as_list(_safe_call(obj, "get_components_by_class", skeletal_class)) if skeletal_class else []
        attempts.append(
            f"route2 skeletal components on {_describe_actor(obj)}: "
            f"{[_describe_component(component) for component in components]}"
        )
        named = [c for c in components if attach_base._name_matches(_safe_call(c, "get_name"), preferred)]
        for component in named + [c for c in components if c not in named]:
            candidates.append(("bound-objects", component, None))

    # Route 3: the startup-resolved component (may be stale by now; kept last on purpose).
    startup_component = context.get("skeletal_component")
    attempts.append(
        f"route3 startup component: {_describe_component(startup_component)} "
        f"is_valid={_is_valid_object(startup_component)}"
    )
    if startup_component is not None:
        candidates.append(("context-startup", startup_component, None))

    return candidates


def _read_socket_world_transform(component, socket_name, attempts, route_label):
    """Try hard to read one socket/bone world transform. Logs every attempt."""
    if component is None:
        attempts.append(f"[{route_label}] component is None")
        return None
    valid = _is_valid_object(component)
    exists = _safe_call(component, "does_socket_exist", str(socket_name))
    bone_index = _safe_call(component, "get_bone_index", str(socket_name))
    attempts.append(
        f"[{route_label}] {_describe_component(component)} is_valid={valid} "
        f"does_socket_exist({socket_name!r})={exists} get_bone_index={bone_index}"
    )

    space_enum = getattr(unreal, "RelativeTransformSpace", None)
    if space_enum is None:
        attempts.append(f"[{route_label}] unreal.RelativeTransformSpace MISSING")
    world_space = None
    for member in ("RTS_WORLD", "WORLD", "RTS_World"):
        world_space = getattr(space_enum, member, None) if space_enum else None
        if world_space is not None:
            attempts.append(f"[{route_label}] world space enum member: {member}")
            break
    if world_space is None and space_enum is not None:
        members = [name for name in dir(space_enum) if not name.startswith("_")]
        attempts.append(f"[{route_label}] no world member found; RelativeTransformSpace members={members}")

    call_variants = []
    if world_space is not None:
        call_variants.append((f"get_socket_transform(Name({socket_name}), WORLD)", (unreal.Name(str(socket_name)), world_space)))
        call_variants.append((f"get_socket_transform({socket_name!r}, WORLD)", (str(socket_name), world_space)))
    call_variants.append((f"get_socket_transform(Name({socket_name}))", (unreal.Name(str(socket_name)),)))
    call_variants.append((f"get_socket_transform({socket_name!r})", (str(socket_name),)))

    for label, args in call_variants:
        try:
            transform = component.get_socket_transform(*args)
        except Exception as exc:
            attempts.append(f"[{route_label}] {label} -> EXCEPTION {exc}")
            continue
        if transform is None:
            attempts.append(f"[{route_label}] {label} -> None")
            continue
        attempts.append(f"[{route_label}] {label} -> OK {_fmt_transform(transform)}")
        return transform

    location = _safe_call(component, "get_socket_location", str(socket_name))
    rotation = _safe_call(component, "get_socket_rotation", str(socket_name))
    attempts.append(f"[{route_label}] get_socket_location/rotation -> loc={_fmt_vec(location)} rot={_fmt_rot(rotation)}")
    if location is not None and rotation is not None:
        try:
            return unreal.Transform(location=location, rotation=rotation, scale=unreal.Vector(1.0, 1.0, 1.0))
        except Exception as exc:
            attempts.append(f"[{route_label}] Transform(loc, rot) -> EXCEPTION {exc}")
    return None


def _sample_root_world(sequence, context, sphere_actor, root_bone_name, attempts):
    """Returns (socket_world_transform, route_label, component) using the first route that works."""
    candidates = _resolve_skeletal_candidates(sequence, context, sphere_actor, attempts)
    if not candidates:
        attempts.append("no skeletal component candidates resolved this frame")
        return None, "<none>", None
    for route_label, component, route_socket in candidates:
        socket_name = route_socket if route_socket and str(route_socket) not in ("", "None") else root_bone_name
        transform = _read_socket_world_transform(component, socket_name, attempts, route_label)
        if transform is not None:
            return transform, f"{route_label} socket={socket_name}", component
    return None, "<all routes failed>", None


def _relative_to_socket(sphere_transform, socket_transform):
    if sphere_transform is None or socket_transform is None:
        return None
    math_library = getattr(unreal, "MathLibrary", None)
    relative = _safe_call(math_library, "make_relative_transform", sphere_transform, socket_transform)
    return relative


def _delta(vec_a, vec_b):
    if vec_a is None or vec_b is None:
        return None
    try:
        diff = unreal.Vector(vec_a.x - vec_b.x, vec_a.y - vec_b.y, vec_a.z - vec_b.z)
        return diff.length()
    except Exception:
        return None


def _probe_frame(sequence, context, sphere_binding, root_bone_name, frame):
    ok, current, local = _set_time_and_report(frame)
    attempts = []
    row = {"frame": int(frame), "set_ok": ok, "current_time": current, "local_time": local, "attempts": attempts}

    sphere_actor, sphere_resolve_attempts = _resolve_sphere_actor(sequence, sphere_binding)
    if sphere_actor is None:
        attempts.append(f"sphere resolve attempts: {sphere_resolve_attempts}")
    row["sphere_actor_desc"] = _describe_actor(sphere_actor)
    sphere_transform = _safe_call(sphere_actor, "get_actor_transform")
    row["sphere_transform"] = sphere_transform
    row["sphere_loc"], row["sphere_rot"] = _transform_loc_rot(sphere_transform)
    # Belt and braces: direct actor reads in case Transform decomposition ever regresses.
    if row["sphere_loc"] is None:
        row["sphere_loc"] = _safe_call(sphere_actor, "get_actor_location")
    if row["sphere_rot"] is None:
        row["sphere_rot"] = _safe_call(sphere_actor, "get_actor_rotation")
    row["sphere_attach_parent_actor"] = _describe_actor(_safe_call(sphere_actor, "get_attach_parent_actor"))

    bp_actor = context.get("bp_actor")
    row["bp_loc"] = _safe_call(bp_actor, "get_actor_location")
    row["bp_rot"] = _safe_call(bp_actor, "get_actor_rotation")

    socket_transform, route, component = _sample_root_world(sequence, context, sphere_actor, root_bone_name, attempts)
    row["socket_transform"] = socket_transform
    row["socket_loc"], row["socket_rot"] = _transform_loc_rot(socket_transform)
    row["socket_route"] = route
    row["socket_component_desc"] = _describe_component(component)
    row["relative"] = _relative_to_socket(sphere_transform, socket_transform)
    row["distance"] = _delta(row.get("sphere_loc"), row.get("socket_loc"))
    return row


def _log_probe_row(row, label, verbose_attempts):
    _log(
        f"[{label}] frame={row['frame']} set_ok={row['set_ok']} "
        f"current_time={row['current_time']} local_time={row['local_time']}"
    )
    _log(
        f"[{label}]   helper {row.get('sphere_actor_desc')} "
        f"world loc={_fmt_vec(row.get('sphere_loc'))} rot={_fmt_rot(row.get('sphere_rot'))} "
        f"attach_parent_actor={row.get('sphere_attach_parent_actor')}"
    )
    _log(
        f"[{label}]   root  via {row.get('socket_route')} on {row.get('socket_component_desc')} "
        f"world loc={_fmt_vec(row.get('socket_loc'))} rot={_fmt_rot(row.get('socket_rot'))}"
    )
    distance = row.get("distance")
    distance_text = f"{distance:.4f}" if distance is not None else "<n/a>"
    _log(f"[{label}]   helper-vs-root distance={distance_text}")
    _log(f"[{label}]   helper relative-to-socket: {_fmt_transform(row.get('relative'))}")
    _log(f"[{label}]   bp_actor loc={_fmt_vec(row.get('bp_loc'))} rot={_fmt_rot(row.get('bp_rot'))}")
    failed = row.get("socket_transform") is None
    if verbose_attempts or failed:
        for line in row.get("attempts", []):
            _log(f"[{label}]     attempt: {line}")


def _set_attach_active(binding, active):
    changed = []
    for _track, section in _attach_sections(binding):
        try:
            section.set_is_active(bool(active))
            changed.append(section)
        except Exception as exc:
            _log_warning(f"set_is_active({active}) failed on attach section: {exc}")
    _safe_call(getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None), "refresh_current_level_sequence")
    return changed


def run(
    bp_actor_name="",
    skeletal_mesh_name="",
    global_ctrl_name="global_ctrl",
    root_bone_name="root",
    sphere_name="recorder_sphere",
    prefer_selected_global_ctrl_sequence=True,
    probe_frames=None,
    deactivate_attach_for_comparison=False,
):
    try:
        global attach_base
        attach_base = importlib.reload(attach_base)

        _log("================ bake diagnostic v3 start ================")
        _TRANSFORM_SHAPE_LOGGED[0] = False
        context, error = attach_base._resolve_context(
            bp_actor_name, skeletal_mesh_name, global_ctrl_name, prefer_selected_global_ctrl_sequence
        )
        if error:
            _log_error(error)
            return ""

        sequence = context["sequence"]
        start_frame = int(context["start_frame"])
        end_frame = int(context["end_frame"])

        library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
        current_sequence = _safe_call(library, "get_current_level_sequence")
        focused_sequence = _safe_call(library, "get_focused_level_sequence")
        original_time = _safe_call(library, "get_current_time")

        _log(f"target sequence:  {_sequence_label(sequence)}")
        _log(f"open (root) seq:  {_sequence_label(current_sequence)}")
        _log(f"focused seq:      {_sequence_label(focused_sequence)}")
        target_path = str(_safe_call(sequence, "get_path_name"))
        open_paths = {str(_safe_call(current_sequence, "get_path_name")), str(_safe_call(focused_sequence, "get_path_name"))}
        if target_path not in open_paths:
            _log_warning(
                "TARGET SEQUENCE IS NOT THE OPEN/FOCUSED SEQUENCER SEQUENCE. "
                "set_current_time drives the open sequencer, so every sampled frame below may be "
                "evaluated in a different time space than the target asset's playback range. "
                "Open/focus the ANM subsequence in Sequencer and re-run."
            )
        display_rate = _safe_call(sequence, "get_display_rate")
        tick_resolution = _safe_call(sequence, "get_tick_resolution")
        _log(f"playback range [{start_frame},{end_frame}) display_rate={display_rate} tick_resolution={tick_resolution}")
        _log(f"startup bp_actor: {_describe_actor(context.get('bp_actor'))}")
        _log(f"startup skeletal component: {_describe_component(context.get('skeletal_component'))}")

        sphere_binding, how = _find_sphere_binding(sequence, sphere_name)
        if sphere_binding is None:
            _log_error(f"Could not find recorder_sphere binding ({how}). Run the safe stage-two setup first.")
            return ""
        _log(
            f"sphere binding: name={attach_base._binding_name(sphere_binding)!r} found_by={how} "
            f"guid={_safe_call(sphere_binding, 'get_id')} kind={_binding_kind(sequence, sphere_binding)}"
        )

        for line in _transform_track_summary(sphere_binding):
            _log(line)
        for line in _attach_summary(sphere_binding):
            _log(line)

        if probe_frames is None:
            mid = start_frame + (end_frame - start_frame) // 2
            probe_frames = sorted({start_frame, start_frame + 1, min(start_frame + 9, end_frame - 1), mid, end_frame - 1})
        _log(f"probe frames: {probe_frames}")

        live_rows = []
        max_distance = None
        for index, frame in enumerate(probe_frames):
            row = _probe_frame(sequence, context, sphere_binding, root_bone_name, frame)
            live_rows.append(row)
            _log_probe_row(row, "LIVE", verbose_attempts=(index == 0))
            if row.get("distance") is not None:
                max_distance = row["distance"] if max_distance is None else max(max_distance, row["distance"])

        if max_distance is None:
            _log_error(
                "Socket sampling failed on every probe frame - helper-vs-root could not be verified. "
                "See the attempt lines above for the exact failure per route."
            )
        else:
            _log(f"RESULT: max helper-vs-root distance across probe frames = {max_distance:.4f}")
            if max_distance < 0.1:
                _log("RESULT: helper matches root at all probe frames (~zero). Safe to proceed to a bake test.")
            else:
                _log_warning(
                    "RESULT: helper does NOT match root within 0.1 units on at least one probe frame. "
                    "Do not bake yet - inspect the per-frame rows above."
                )

        if deactivate_attach_for_comparison:
            _log("---- deactivating attach sections for keys-only comparison ----")
            changed = _set_attach_active(sphere_binding, False)
            if not changed:
                _log_warning("No attach sections were deactivated; comparison skipped.")
            else:
                try:
                    for index, live_row in enumerate(live_rows):
                        frame = live_row["frame"]
                        row = _probe_frame(sequence, context, sphere_binding, root_bone_name, frame)
                        _log_probe_row(row, "KEYS-ONLY", verbose_attempts=(index == 0))
                        dist = _delta(row.get("sphere_loc"), live_row.get("socket_loc"))
                        dist_text = f"{dist:.4f}" if dist is not None else "<n/a>"
                        _log(
                            f"[COMPARE] frame={frame} keys-only helper vs live root-world distance={dist_text} "
                            f"(should be ~0 after a correct bake)"
                        )
                finally:
                    _set_attach_active(sphere_binding, True)
                    _log("---- attach sections restored to active ----")

        if original_time is not None:
            try:
                library.set_current_time(int(original_time))
            except Exception:
                pass
        _log("================ bake diagnostic v3 end ================")
        return "true"
    except Exception:
        _log_error(traceback.format_exc())
        return ""


def reload_and_run(**kwargs):
    return run(**kwargs)
