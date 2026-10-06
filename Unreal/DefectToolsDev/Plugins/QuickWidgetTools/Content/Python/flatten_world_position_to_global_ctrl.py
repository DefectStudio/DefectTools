"""
Flatten Blueprint Actor transform motion onto selected global_ctrl channels.

Preferred workflow:
- Open the shot Level Sequence in Sequencer.
- In Sequencer, select the Blueprint Actor binding, for example chr_Assassin_S1_v001.
- Also select the Control Rig control global_ctrl.
- Run this script first in dry-run mode.
- If the diagnostic chooses the correct Blueprint Actor binding and global_ctrl section,
  run with dry_run=False.

Important:
- The selected global_ctrl channels identify the exact Control Rig section to edit.
- The selected Blueprint Actor binding identifies the exact actor transform track to flatten.
- If no Blueprint Actor binding is selected, the script falls back to bp_actor_name.
- The script searches the Level Sequence asset that owns the selected global_ctrl section
  before the parent/current sequence. This handles ANM sub-sequences correctly.
- Scale is not flattened; actor/global_ctrl scale keys are left alone.
- Source channels are sampled every display frame. If Unreal's Python channel evaluator
  is not available, source values are linearly interpolated between sparse keys instead
  of being treated as stepped/held values.

Blueprint / Python usage:

    import flatten_world_position_to_global_ctrl
    import importlib

    importlib.reload(flatten_world_position_to_global_ctrl)

    # Safe diagnostic pass. If both actor + global_ctrl are selected, bp_actor_name
    # is used as an extra safety check.
    flatten_world_position_to_global_ctrl.run(
        bp_actor_name="chr_Assassin_S1_v001"
    )

    # Destructive pass after dry-run diagnostics look correct.
    flatten_world_position_to_global_ctrl.run(
        dry_run=False,
        bp_actor_name="chr_Assassin_S1_v001"
    )

Returns:
    "true" on success, or "" on failure.
"""

import math
import traceback

import unreal


LOG_PREFIX = "[FlattenWorldPositionToGlobalCtrl]"
REQUIRED_SELECTED_CONTROL = "global_ctrl"
DEBUG_MAX_ITEMS = 120

TRANSFORM_KEYS = (
    "location_x",
    "location_y",
    "location_z",
    "rotation_x",
    "rotation_y",
    "rotation_z",
    "scale_x",
    "scale_y",
    "scale_z",
)
LOCATION_KEYS = ("location_x", "location_y", "location_z")
ROTATION_KEYS = ("rotation_x", "rotation_y", "rotation_z")
SCALE_KEYS = ("scale_x", "scale_y", "scale_z")
KEYS_TO_FLATTEN = LOCATION_KEYS + ROTATION_KEYS

DEFAULT_VALUES = {
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


def _safe_get_editor_property(obj, property_name):
    if obj is None:
        return None
    try:
        return obj.get_editor_property(property_name)
    except Exception:
        return None


def _get_value(obj, *names):
    if obj is None:
        return None
    for name in names:
        try:
            value = getattr(obj, name)
        except Exception:
            value = None
        if value is not None:
            return value
    for name in names:
        value = _safe_get_editor_property(obj, name)
        if value is not None:
            return value
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
        try:
            text = repr(value)
        except Exception:
            text = "<unprintable>"
    text = text.replace("\r", " ").replace("\n", " ").strip()
    if len(text) > max_length:
        text = text[:max_length] + "..."
    return text


def _class_name(obj):
    if obj is None:
        return ""
    unreal_class = _safe_call(obj, "get_class")
    class_name = _safe_call(unreal_class, "get_name")
    if class_name:
        return str(class_name)
    return str(type(obj))


def _object_name(obj):
    if obj is None:
        return ""
    for function_name in ("get_name", "get_display_name"):
        value = _safe_call(obj, function_name)
        if value:
            return str(value)
    value = _get_value(obj, "name", "display_name")
    if value:
        return str(value)
    return _compact_text(obj, 120)


def _normalize_name(value):
    text = str(value or "").strip().lower()
    for char in " \\/:;,.[]{}()<>|?*\"'`~!@#$%^&+=-":
        text = text.replace(char, "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


def _binding_id_text(binding):
    if binding is None:
        return ""
    for function_name in ("get_id", "get_binding_id"):
        value = _safe_call(binding, function_name)
        if value is not None:
            return _compact_text(value, 120)
    value = _get_value(binding, "binding_id", "id")
    if value is not None:
        return _compact_text(value, 120)
    return _object_name(binding)


def _binding_name(binding):
    if binding is None:
        return ""
    for function_name in ("get_name", "get_display_name"):
        value = _safe_call(binding, function_name)
        if value:
            return str(value)
    value = _get_value(binding, "name", "display_name")
    if value:
        return str(value)
    return _binding_id_text(binding)


def _to_int_frame(value):
    if value is None:
        return None
    frame_number = getattr(value, "frame_number", None)
    if frame_number is not None:
        return _to_int_frame(frame_number)
    value_attr = getattr(value, "value", None)
    if value_attr is not None:
        return _to_int_frame(value_attr)
    try:
        return int(value)
    except Exception:
        return None


def _make_frame_number(frame_value):
    try:
        return unreal.FrameNumber(int(frame_value))
    except Exception:
        return int(frame_value)


def _make_frame_time(frame_value):
    frame_number = _make_frame_number(frame_value)
    frame_time_type = getattr(unreal, "FrameTime", None)
    if frame_time_type is None:
        return None
    for args in ((frame_number,), (int(frame_value),), (frame_number, 0.0), (int(frame_value), 0.0)):
        try:
            return frame_time_type(*args)
        except Exception:
            pass
    return None


def _get_display_rate_time_unit():
    for enum_name in ("SequenceTimeUnit", "MovieSceneTimeUnit"):
        enum_type = getattr(unreal, enum_name, None)
        if enum_type is None:
            continue
        for value_name in ("DISPLAY_RATE", "DISPLAYRATE"):
            value = getattr(enum_type, value_name, None)
            if value is not None:
                return value
    return None


def _get_current_level_sequence():
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    return _safe_call(library, "get_current_level_sequence")


def _get_sequence_frame_range(sequence):
    start_candidates = (
        _safe_call(sequence, "get_playback_start"),
        _safe_call(sequence, "get_start_frame"),
    )
    end_candidates = (
        _safe_call(sequence, "get_playback_end"),
        _safe_call(sequence, "get_end_frame"),
    )
    start_frame = None
    end_frame = None
    for value in start_candidates:
        start_frame = _to_int_frame(value)
        if start_frame is not None:
            break
    for value in end_candidates:
        end_frame = _to_int_frame(value)
        if end_frame is not None:
            break
    if start_frame is None or end_frame is None:
        playback_range = _safe_call(sequence, "get_playback_range")
        start_frame = _to_int_frame(getattr(playback_range, "start", None))
        end_frame = _to_int_frame(getattr(playback_range, "end", None))
    if start_frame is None or end_frame is None:
        return None, None
    if end_frame < start_frame:
        start_frame, end_frame = end_frame, start_frame
    return start_frame, end_frame


def _get_selected_channel_proxies():
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    return _as_list(_safe_call(library, "get_selected_channels"))


def _get_selected_binding_proxies():
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    bindings = []
    for function_name in (
        "get_selected_bindings",
        "get_selected_objects",
    ):
        result = _safe_call(library, function_name)
        if result:
            bindings.extend(_as_list(result))
    seen = set()
    output = []
    for binding in bindings:
        if not hasattr(binding, "get_tracks") and _safe_call(binding, "get_tracks") is None:
            continue
        key = str(id(binding))
        if key in seen:
            continue
        seen.add(key)
        output.append(binding)
    return output


def _get_channel_name(channel_or_proxy):
    if channel_or_proxy is None:
        return ""
    for name in ("channel_name", "name", "display_name"):
        value = _get_value(channel_or_proxy, name)
        if value:
            return str(value)
    for function_name in ("get_name", "get_display_name"):
        value = _safe_call(channel_or_proxy, function_name)
        if value:
            return str(value)
    text = _compact_text(channel_or_proxy, 1000)
    marker = 'channel_name: "'
    if marker in text:
        try:
            return text.split(marker, 1)[1].split('"', 1)[0]
        except Exception:
            pass
    return text


def _get_selected_channel_names():
    names = []
    seen = set()
    for proxy in _get_selected_channel_proxies():
        name = _get_channel_name(proxy)
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def _selection_name_matches_global_ctrl(name):
    normalized = _normalize_name(name)
    return normalized == REQUIRED_SELECTED_CONTROL or normalized.startswith(REQUIRED_SELECTED_CONTROL + "_")


def _extract_asset_path_from_text(text):
    text = str(text or "")
    if "'/Game" in text:
        tail = text.split("'/Game", 1)[1]
        path = "/Game" + tail.split("'", 1)[0]
    elif "/Game" in text:
        tail = text.split("/Game", 1)[1]
        path = "/Game" + tail
    else:
        return ""
    path = path.split(":", 1)[0].strip()
    return path


def _load_sequence_from_asset_path(asset_path):
    if not asset_path:
        return None
    loaded = unreal.load_asset(asset_path)
    if loaded is not None:
        return loaded
    if "." in asset_path:
        package_path = asset_path.rsplit(".", 1)[0]
        loaded = unreal.load_asset(package_path)
        if loaded is not None:
            return loaded
    return None


def _get_section_from_proxy(proxy):
    section = _get_value(proxy, "section")
    if section is not None:
        return section
    return _safe_call(proxy, "get_section")


def _get_selected_global_ctrl_section():
    sections = []
    selected_global_names = []
    sequence_asset_path = ""
    for proxy in _get_selected_channel_proxies():
        channel_name = _get_channel_name(proxy)
        if not _selection_name_matches_global_ctrl(channel_name):
            continue
        selected_global_names.append(channel_name)
        section = _get_section_from_proxy(proxy)
        if section is not None and not any(section is existing for existing in sections):
            sections.append(section)
        if not sequence_asset_path:
            sequence_asset_path = _extract_asset_path_from_text(_compact_text(proxy, 2000))

    if not selected_global_names:
        return None, [], ""
    if not sections:
        return None, selected_global_names, sequence_asset_path
    if len(sections) > 1:
        _log_warning(f"Selected global_ctrl channels came from {len(sections)} sections. Using the first section.")
    return sections[0], selected_global_names, sequence_asset_path


def _get_section_channels(section):
    channels = _safe_call(section, "get_channels")
    if channels is None:
        channels = _safe_call(section, "get_all_channels")
    return _as_list(channels)


def _classify_transform_channel(channel_name):
    normalized = _normalize_name(channel_name)
    tokens = [token for token in normalized.split("_") if token]
    axis = ""
    for token in reversed(tokens):
        if token in ("x", "y", "z"):
            axis = token
            break
    if not axis:
        return ""
    if any(token in tokens for token in ("location", "translation", "translate")):
        return f"location_{axis}"
    if any(token in tokens for token in ("rotation", "rotate", "rotator", "euler")):
        return f"rotation_{axis}"
    if "scale" in tokens or "scale3d" in normalized:
        return f"scale_{axis}"
    return ""


def _find_global_ctrl_channels_from_section(section):
    bundle = {key: [] for key in TRANSFORM_KEYS}
    for channel in _get_section_channels(section):
        channel_name = _get_channel_name(channel)
        if "global_ctrl" not in _normalize_name(channel_name):
            continue
        transform_key = _classify_transform_channel(channel_name)
        if transform_key:
            bundle[transform_key].append(channel)
    return bundle


def _iter_root_bindings(sequence):
    bindings = []
    for function_name in ("get_bindings", "get_possessables", "get_spawnables"):
        result = _safe_call(sequence, function_name)
        if result:
            bindings.extend(_as_list(result))
    seen = set()
    for binding in bindings:
        key = _binding_id_text(binding) or str(id(binding))
        if key in seen:
            continue
        seen.add(key)
        yield binding


def _get_child_bindings(binding):
    children = []
    for function_name in ("get_child_possessables", "get_child_spawnables", "get_children"):
        result = _safe_call(binding, function_name)
        if result:
            children.extend(_as_list(result))
    return children


def _iter_all_bindings(sequence):
    stack = list(_iter_root_bindings(sequence))
    seen = set()
    while stack:
        binding = stack.pop(0)
        key = _binding_id_text(binding) or str(id(binding))
        if key in seen:
            continue
        seen.add(key)
        yield binding
        stack.extend(_get_child_bindings(binding))


def _iter_binding_tracks(binding):
    return _as_list(_safe_call(binding, "get_tracks"))


def _iter_track_sections(track):
    return _as_list(_safe_call(track, "get_sections"))


def _find_actor_transform_channels_for_binding(binding):
    bundle = {key: [] for key in TRANSFORM_KEYS}
    for track in _iter_binding_tracks(binding):
        for section in _iter_track_sections(track):
            for channel in _get_section_channels(section):
                channel_name = _get_channel_name(channel)
                transform_key = _classify_transform_channel(channel_name)
                if transform_key:
                    bundle[transform_key].append(channel)
    return bundle


def _missing_required_channels(bundle):
    return [key for key in KEYS_TO_FLATTEN if not bundle.get(key)]


def _make_candidate(source, sequence_label, sequence, binding, bundle):
    return {
        "source": source,
        "sequence_label": sequence_label,
        "sequence": sequence,
        "binding": binding,
        "bundle": bundle,
    }


def _candidate_signature(candidate):
    binding = candidate["binding"]
    bundle = candidate["bundle"]
    channel_signature = []
    for key in TRANSFORM_KEYS:
        channel = _first_channel(bundle, key)
        channel_signature.append((key, _get_channel_name(channel) if channel else "", _count_channel_keys(channel) if channel else -1))
    return (
        candidate.get("source"),
        candidate.get("sequence_label"),
        _normalize_name(_binding_name(binding)),
        tuple(channel_signature),
    )


def _dedupe_candidates(candidates):
    output = []
    seen = set()
    for candidate in candidates:
        key = _candidate_signature(candidate)
        if key in seen:
            continue
        seen.add(key)
        output.append(candidate)
    return output


def _find_actor_transform_candidates(sequence):
    candidates = []
    for binding in _iter_all_bindings(sequence):
        bundle = _find_actor_transform_channels_for_binding(binding)
        if not _missing_required_channels(bundle):
            candidates.append((binding, bundle))
    return candidates


def _find_actor_candidates_in_sequences(sequence_entries):
    all_candidates = []
    for sequence_label, sequence in sequence_entries:
        if sequence is None:
            continue
        for binding, bundle in _find_actor_transform_candidates(sequence):
            all_candidates.append(_make_candidate("searched", sequence_label, sequence, binding, bundle))
    return _dedupe_candidates(all_candidates)


def _find_selected_actor_candidates():
    candidates = []
    for binding in _get_selected_binding_proxies():
        bundle = _find_actor_transform_channels_for_binding(binding)
        if not _missing_required_channels(bundle):
            candidates.append(_make_candidate("selected", "selected_binding", None, binding, bundle))
    return _dedupe_candidates(candidates)


def _filter_actor_candidates_by_name(candidates, bp_actor_name):
    clean_name = str(bp_actor_name or "").strip()
    if not clean_name:
        return candidates
    normalized_target = _normalize_name(clean_name)
    exact_matches = []
    contains_matches = []
    for candidate in candidates:
        binding_name = _binding_name(candidate["binding"])
        normalized_binding_name = _normalize_name(binding_name)
        if normalized_binding_name == normalized_target:
            exact_matches.append(candidate)
        elif normalized_target in normalized_binding_name or normalized_binding_name in normalized_target:
            contains_matches.append(candidate)
    return exact_matches if exact_matches else contains_matches


def _get_channel_keys(channel):
    if channel is None:
        return []
    for function_name in ("get_keys", "get_all_keys"):
        keys = _safe_call(channel, function_name)
        if keys is not None:
            return _as_list(keys)
    return []


def _count_channel_keys(channel):
    return len(_get_channel_keys(channel))


def _get_key_time(key):
    display_rate_unit = _get_display_rate_time_unit()
    if display_rate_unit is not None:
        frame = _to_int_frame(_safe_call(key, "get_time", display_rate_unit))
        if frame is not None:
            return frame
    frame = _to_int_frame(_safe_call(key, "get_time"))
    if frame is not None:
        return frame
    for property_name in ("time", "frame_number", "frame"):
        frame = _to_int_frame(_get_value(key, property_name))
        if frame is not None:
            return frame
    return None


def _get_key_value(key):
    for function_name in ("get_value", "get_key_value"):
        value = _safe_call(key, function_name)
        if value is not None:
            return value
    for property_name in ("value", "key_value"):
        value = _get_value(key, property_name)
        if value is not None:
            return value
    return None


def _get_channel_default(channel):
    for function_name in ("get_default", "get_default_value"):
        value = _safe_call(channel, function_name)
        if value is not None:
            return value
    return None


def _snapshot_channel(channel):
    key_values = []
    for key in _get_channel_keys(channel):
        frame = _get_key_time(key)
        value = _get_key_value(key)
        if frame is None or value is None:
            continue
        key_values.append((frame, _float_or_default(value, 0.0)))
    key_values.sort(key=lambda item: item[0])
    return key_values, _get_channel_default(channel)


def _float_or_default(value, default_value):
    try:
        return float(value)
    except Exception:
        return float(default_value)


def _extract_number(value):
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        pass
    if isinstance(value, (list, tuple)):
        numeric_values = []
        bool_values = []
        for item in value:
            if isinstance(item, bool):
                bool_values.append(item)
                continue
            try:
                numeric_values.append(float(item))
            except Exception:
                pass
        if numeric_values:
            # evaluate() can return (value, success) or (success, value).
            # Prefer the last numeric value when a bool is present.
            return numeric_values[-1]
    for name in ("value", "result", "return_value"):
        item = _get_value(value, name)
        if item is not None and item is not value:
            extracted = _extract_number(item)
            if extracted is not None:
                return extracted
    return None


def _try_evaluate_channel(channel, frame_number):
    if channel is None:
        return None

    frame_number_obj = _make_frame_number(frame_number)
    frame_time_obj = _make_frame_time(frame_number)
    display_rate_unit = _get_display_rate_time_unit()

    call_patterns = []
    if frame_time_obj is not None:
        call_patterns.append((frame_time_obj,))
    call_patterns.append((frame_number_obj,))
    call_patterns.append((int(frame_number),))
    if display_rate_unit is not None:
        call_patterns.append((frame_number_obj, display_rate_unit))
        if frame_time_obj is not None:
            call_patterns.append((frame_time_obj, display_rate_unit))
    call_patterns.append((frame_number_obj, 0.0))
    call_patterns.append((int(frame_number), 0.0))

    for args in call_patterns:
        value = _safe_call(channel, "evaluate", *args)
        extracted = _extract_number(value)
        if extracted is not None:
            return extracted
    return None


def _linear_interpolate_key_values(transform_key, frame, key_values, default_value, fallback):
    if not key_values:
        return _float_or_default(default_value, fallback)

    if len(key_values) == 1:
        return _float_or_default(key_values[0][1], fallback)

    frame = int(frame)
    first_frame, first_value = key_values[0]
    last_frame, last_value = key_values[-1]

    if frame <= first_frame:
        return _float_or_default(first_value, fallback)
    if frame >= last_frame:
        return _float_or_default(last_value, fallback)

    previous_frame, previous_value = key_values[0]
    for next_frame, next_value in key_values[1:]:
        if frame > next_frame:
            previous_frame, previous_value = next_frame, next_value
            continue

        if next_frame == previous_frame:
            return _float_or_default(next_value, fallback)

        alpha = float(frame - previous_frame) / float(next_frame - previous_frame)
        v0 = _float_or_default(previous_value, fallback)
        v1 = _float_or_default(next_value, fallback)

        if transform_key in ROTATION_KEYS:
            # Use the shortest angular path for sparse rotation keys.
            delta = (v1 - v0 + 180.0) % 360.0 - 180.0
            return v0 + (delta * alpha)

        return v0 + ((v1 - v0) * alpha)

    return _float_or_default(last_value, fallback)


def _snapshot_bundle(bundle):
    snapshots = {}
    for key in TRANSFORM_KEYS:
        channel = _first_channel(bundle, key)
        if channel is None:
            snapshots[key] = ([], DEFAULT_VALUES[key], None)
        else:
            key_values, default_value = _snapshot_channel(channel)
            if default_value is None:
                default_value = DEFAULT_VALUES[key]
            snapshots[key] = (key_values, default_value, channel)
    return snapshots


def _value_from_snapshot(transform_key, frame, key_values, default_value, channel, fallback):
    evaluated = _try_evaluate_channel(channel, frame)
    if evaluated is not None:
        return _float_or_default(evaluated, fallback)

    return _linear_interpolate_key_values(transform_key, frame, key_values, default_value, fallback)


def _evaluate_transform_values(snapshots, frame):
    values = {}
    for key in TRANSFORM_KEYS:
        key_values, default_value, channel = snapshots.get(key, ([], DEFAULT_VALUES[key], None))
        values[key] = _value_from_snapshot(key, frame, key_values, default_value, channel, DEFAULT_VALUES[key])
    return values


def _first_channel(bundle, key):
    channels = bundle.get(key) or []
    return channels[0] if channels else None


def _make_vector(x, y, z):
    return unreal.Vector(float(x), float(y), float(z))


def _make_rotator(rotation_x, rotation_y, rotation_z):
    # Sequencer channels are Rotation.X/Y/Z. Unreal Rotator is Pitch/Yaw/Roll.
    return unreal.Rotator(float(rotation_y), float(rotation_z), float(rotation_x))


def _make_transform(values):
    location = _make_vector(values["location_x"], values["location_y"], values["location_z"])
    rotation = _make_rotator(values["rotation_x"], values["rotation_y"], values["rotation_z"])
    scale = _make_vector(values.get("scale_x", 1.0), values.get("scale_y", 1.0), values.get("scale_z", 1.0))
    for kwargs in (
        {"location": location, "rotation": rotation, "scale": scale},
        {"translation": location, "rotation": rotation, "scale3d": scale},
    ):
        try:
            return unreal.Transform(**kwargs)
        except Exception:
            pass
    transform = unreal.Transform()
    for name, value in (("translation", location), ("location", location), ("rotation", rotation), ("scale3d", scale), ("scale", scale)):
        try:
            transform.set_editor_property(name, value)
        except Exception:
            pass
    return transform


def _call_math(function_names, *args):
    for library in (getattr(unreal, "KismetMathLibrary", None), getattr(unreal, "MathLibrary", None)):
        if library is None:
            continue
        for function_name in function_names:
            result = _safe_call(library, function_name, *args)
            if result is not None:
                return result
    return None


def _compose_transforms(parent_transform, child_transform):
    result = _call_math(("compose_transforms", "multiply_transform_transform"), parent_transform, child_transform)
    if result is not None:
        return result
    try:
        return parent_transform * child_transform
    except Exception:
        return None


def _make_relative_transform(world_transform, parent_transform):
    result = _call_math(("make_relative_transform", "make_relative_transform_transform"), world_transform, parent_transform)
    if result is not None:
        return result
    result = _safe_call(world_transform, "get_relative_transform", parent_transform)
    if result is not None:
        return result
    inverse_parent = _safe_call(parent_transform, "inverse") or _call_math(("invert_transform",), parent_transform)
    if inverse_parent is not None:
        return _compose_transforms(inverse_parent, world_transform)
    return None


def _vector_xyz(vector_value):
    if vector_value is None:
        return None
    x = _get_value(vector_value, "x", "X")
    y = _get_value(vector_value, "y", "Y")
    z = _get_value(vector_value, "z", "Z")
    if x is not None and y is not None and z is not None:
        return [float(x), float(y), float(z)]
    try:
        return [float(vector_value[0]), float(vector_value[1]), float(vector_value[2])]
    except Exception:
        return None


def _rotator_xyz(rotation_value):
    if rotation_value is None:
        return None
    for function_name in ("rotator", "to_rotator"):
        candidate = _safe_call(rotation_value, function_name)
        if candidate is not None:
            rotation_value = candidate
            break
    pitch = _get_value(rotation_value, "pitch", "Pitch")
    yaw = _get_value(rotation_value, "yaw", "Yaw")
    roll = _get_value(rotation_value, "roll", "Roll")
    if pitch is not None and yaw is not None and roll is not None:
        return [float(roll), float(pitch), float(yaw)]
    x = _get_value(rotation_value, "x", "X")
    y = _get_value(rotation_value, "y", "Y")
    z = _get_value(rotation_value, "z", "Z")
    if x is not None and y is not None and z is not None:
        return [float(x), float(y), float(z)]
    return None


def _transform_to_values(transform):
    location = None
    for function_name in ("get_location", "get_translation"):
        location = _vector_xyz(_safe_call(transform, function_name))
        if location is not None:
            break
    if location is None:
        location = _vector_xyz(_get_value(transform, "translation", "location"))

    rotation = None
    for function_name in ("rotator", "get_rotation", "get_rotator"):
        rotation = _rotator_xyz(_safe_call(transform, function_name))
        if rotation is not None:
            break
    if rotation is None:
        rotation = _rotator_xyz(_get_value(transform, "rotation", "rotator"))

    scale = None
    for function_name in ("get_scale3d", "get_scale", "get_scale_3d"):
        scale = _vector_xyz(_safe_call(transform, function_name))
        if scale is not None:
            break
    if scale is None:
        scale = _vector_xyz(_get_value(transform, "scale3d", "scale")) or [1.0, 1.0, 1.0]

    if location is None or rotation is None:
        return None

    return {
        "location_x": location[0],
        "location_y": location[1],
        "location_z": location[2],
        "rotation_x": rotation[0],
        "rotation_y": rotation[1],
        "rotation_z": rotation[2],
        "scale_x": scale[0],
        "scale_y": scale[1],
        "scale_z": scale[2],
    }


def _format_values(values):
    return (
        "loc=({location_x:.3f}, {location_y:.3f}, {location_z:.3f}) "
        "rot=({rotation_x:.3f}, {rotation_y:.3f}, {rotation_z:.3f}) "
        "scale=({scale_x:.3f}, {scale_y:.3f}, {scale_z:.3f})"
    ).format(**values)


def _set_channel_default(channel, value):
    for function_name in ("set_default", "set_default_value"):
        function = getattr(channel, function_name, None)
        if function is None:
            continue
        try:
            function(float(value))
            return True
        except Exception:
            pass
    return False


def _try_set_key_interpolation_linear(key):
    if key is None:
        return
    rich_curve_interp_mode = getattr(unreal, "RichCurveInterpMode", None)
    possible_values = []
    if rich_curve_interp_mode is not None:
        for name in ("RCIM_LINEAR", "LINEAR"):
            value = getattr(rich_curve_interp_mode, name, None)
            if value is not None:
                possible_values.append(value)
    for value in possible_values:
        if _safe_call(key, "set_interpolation_mode", value) is not None:
            return


def _add_channel_key(channel, frame_number, value):
    time = _make_frame_number(frame_number)
    value = float(value)
    display_rate_unit = _get_display_rate_time_unit()
    patterns = []
    if display_rate_unit is not None:
        patterns.append((time, value, 0.0, display_rate_unit))
    patterns.extend(((time, value, 0.0), (time, value), (frame_number, value)))
    for args in patterns:
        try:
            key = channel.add_key(*args)
            _try_set_key_interpolation_linear(key)
            return True
        except Exception:
            pass
    return False


def _remove_all_keys(channel):
    failed = 0
    for key in list(_get_channel_keys(channel)):
        removed = False
        for function_name in ("remove_key", "delete_key"):
            function = getattr(channel, function_name, None)
            if function is None:
                continue
            try:
                function(key)
                removed = True
                break
            except Exception:
                pass
        if not removed:
            failed += 1
    return failed == 0


def _print_bundle(label, bundle):
    _log(f"{label} transform channels:")
    for key in TRANSFORM_KEYS:
        channels = bundle.get(key) or []
        if not channels:
            _log(f"  {key}: MISSING")
            continue
        channel = channels[0]
        _log(f"  {key}: {_get_channel_name(channel)} keys={_count_channel_keys(channel)} class={_class_name(channel)}")


def _print_actor_candidates(candidates, chosen_index, label="Actor transform candidates"):
    _log(f"{label}: {len(candidates)}")
    for index, candidate in enumerate(candidates):
        binding = candidate["binding"]
        bundle = candidate["bundle"]
        chosen = " <== CHOSEN" if index == chosen_index else ""
        key_counts = []
        for key in KEYS_TO_FLATTEN:
            channel = _first_channel(bundle, key)
            key_counts.append(f"{key}:{_count_channel_keys(channel) if channel else 'missing'}")
        _log(
            f"  ActorCandidate[{index}] source={candidate['source']} sequence={candidate['sequence_label']} "
            f"binding={_binding_name(binding)} id={_binding_id_text(binding)}{chosen}"
        )
        _log(f"    {', '.join(key_counts)}")


def _build_samples(start_frame, end_frame, actor_bundle, global_bundle):
    actor_snapshots = _snapshot_bundle(actor_bundle)
    global_snapshots = _snapshot_bundle(global_bundle)
    samples = []
    stop_frame = max(start_frame + 1, end_frame)

    for frame in range(start_frame, stop_frame):
        actor_values = _evaluate_transform_values(actor_snapshots, frame)
        global_values = _evaluate_transform_values(global_snapshots, frame)
        actor_transform = _make_transform(actor_values)
        global_transform = _make_transform(global_values)
        world_transform = _compose_transforms(actor_transform, global_transform)
        if world_transform is None:
            return None, f"Could not compose actor/global transforms at frame {frame}."
        world_values = _transform_to_values(world_transform)
        if world_values is None:
            return None, f"Could not extract world transform values at frame {frame}."
        samples.append({"frame": frame, "actor_values": actor_values, "global_values": global_values, "world_transform": world_transform, "world_values": world_values})
    return samples, ""


def _build_new_global_samples(samples, base_actor_values):
    base_actor_transform = _make_transform(base_actor_values)
    output = []
    for sample in samples:
        local_transform = _make_relative_transform(sample["world_transform"], base_actor_transform)
        if local_transform is None:
            return None, f"Could not make relative global_ctrl transform at frame {sample['frame']}."
        values = _transform_to_values(local_transform)
        if values is None:
            return None, f"Could not extract relative global_ctrl values at frame {sample['frame']} ."
        output.append({"frame": sample["frame"], "values": values})
    return output, ""


def _clear_and_write(actor_bundle, global_bundle, start_frame, base_actor_values, new_global_samples):
    for key in KEYS_TO_FLATTEN:
        actor_channel = _first_channel(actor_bundle, key)
        global_channel = _first_channel(global_bundle, key)
        if actor_channel is None or global_channel is None:
            return f"Missing write channel for {key}."
        if not _remove_all_keys(actor_channel):
            return f"Could not remove all actor keys for {key}."
        if not _remove_all_keys(global_channel):
            return f"Could not remove all global_ctrl keys for {key}."
        _set_channel_default(actor_channel, base_actor_values[key])
        if not _add_channel_key(actor_channel, start_frame, base_actor_values[key]):
            return f"Could not key actor base value for {key}."

    for sample in new_global_samples:
        frame = sample["frame"]
        values = sample["values"]
        for key in KEYS_TO_FLATTEN:
            channel = _first_channel(global_bundle, key)
            if not _add_channel_key(channel, frame, values[key]):
                return f"Could not key global_ctrl {key} at frame {frame}."
    return ""


def _choose_actor_candidate(selected_candidates, searched_candidates, bp_actor_name, actor_binding_index, dry_run):
    selected_filtered = _filter_actor_candidates_by_name(selected_candidates, bp_actor_name)

    if selected_candidates and bp_actor_name and not selected_filtered:
        _log_error(
            f"Selected Blueprint Actor binding(s) were found, but none matched bp_actor_name={bp_actor_name!r}. "
            "Refusing to fall back because the explicit selection may be wrong."
        )
        _print_actor_candidates(selected_candidates, -1, label="Selected actor transform candidates")
        _print_actor_candidates(searched_candidates, -1, label="Searched actor transform candidates")
        return None, []

    if selected_filtered:
        candidates_to_use = selected_filtered
        candidate_source_label = "selected actor transform candidates"
    elif selected_candidates:
        candidates_to_use = selected_candidates
        candidate_source_label = "selected actor transform candidates"
    else:
        searched_filtered = _filter_actor_candidates_by_name(searched_candidates, bp_actor_name)
        if bp_actor_name and not searched_filtered:
            _log_error(f"No complete Blueprint Actor transform candidate matched bp_actor_name={bp_actor_name!r}.")
            _print_actor_candidates(searched_candidates, -1, label="Searched actor transform candidates")
            return None, []
        candidates_to_use = searched_filtered if bp_actor_name else searched_candidates
        candidate_source_label = "searched actor transform candidates"

    if not candidates_to_use:
        _log_error("No usable Blueprint Actor transform candidate was found.")
        return None, []

    if not dry_run and len(candidates_to_use) > 1 and not bp_actor_name and not selected_candidates:
        _log_error(
            "Multiple Blueprint Actor transform candidates were found. "
            "For destructive mode, select the Blueprint Actor binding or pass bp_actor_name."
        )
        _print_actor_candidates(candidates_to_use, -1, label=candidate_source_label)
        return None, candidates_to_use

    try:
        chosen_index = int(actor_binding_index)
    except Exception:
        chosen_index = 0

    if chosen_index < 0 or chosen_index >= len(candidates_to_use):
        _log_error(f"actor_binding_index {chosen_index} is out of range. Candidate count: {len(candidates_to_use)}")
        _print_actor_candidates(candidates_to_use, -1, label=candidate_source_label)
        return None, candidates_to_use

    return candidates_to_use[chosen_index], candidates_to_use


def run(dry_run=True, bp_actor_name="", actor_binding_index=0):
    """
    Args:
        dry_run (bool): True prints diagnostics only. False edits keys.
        bp_actor_name (str): Optional expected top Blueprint Actor binding name, e.g. "chr_Assassin_S1_v001".
        actor_binding_index (int): Which matching candidate to use if multiple match.
    """
    try:
        _log("----- run() called -----")
        _log(f"dry_run={dry_run!r} bp_actor_name={bp_actor_name!r} actor_binding_index={actor_binding_index!r}")

        current_sequence = _get_current_level_sequence()
        if current_sequence is None:
            _log_error("No current Level Sequence is open in Sequencer.")
            return ""

        current_sequence_name = _safe_call(current_sequence, "get_name") or str(current_sequence)
        start_frame, end_frame = _get_sequence_frame_range(current_sequence)
        if start_frame is None or end_frame is None:
            _log_error("Could not read the current Level Sequence playback range.")
            return ""

        global_section, selected_global_names, selected_sequence_asset_path = _get_selected_global_ctrl_section()
        if global_section is None:
            _log_error("Select global_ctrl in Sequencer / Anim Outliner before running this tool.")
            _log_error(f"Selected channel names: {_get_selected_channel_names()[:DEBUG_MAX_ITEMS]}")
            return ""

        selected_sequence = _load_sequence_from_asset_path(selected_sequence_asset_path)
        selected_sequence_name = _safe_call(selected_sequence, "get_name") or ""

        global_bundle = _find_global_ctrl_channels_from_section(global_section)
        global_missing = _missing_required_channels(global_bundle)
        if global_missing:
            _log_error(f"Selected global_ctrl section is missing required channels: {global_missing}")
            _print_bundle("global_ctrl", global_bundle)
            return ""

        selected_actor_candidates = _find_selected_actor_candidates()

        sequence_entries = []
        if selected_sequence is not None:
            sequence_entries.append((f"selected_global_ctrl_sequence:{selected_sequence_name}", selected_sequence))
        sequence_entries.append((f"current_sequence:{current_sequence_name}", current_sequence))
        searched_actor_candidates = _find_actor_candidates_in_sequences(sequence_entries)

        chosen_candidate, candidates_to_use = _choose_actor_candidate(
            selected_actor_candidates,
            searched_actor_candidates,
            bp_actor_name,
            actor_binding_index,
            dry_run,
        )
        if chosen_candidate is None:
            return ""

        actor_binding = chosen_candidate["binding"]
        actor_bundle = chosen_candidate["bundle"]
        try:
            chosen_index = candidates_to_use.index(chosen_candidate)
        except Exception:
            chosen_index = int(actor_binding_index or 0)

        _log("==================================================")
        _log(f"Current Level Sequence: {current_sequence_name}")
        _log(f"Playback frame range: {start_frame} to {end_frame} end-exclusive")
        _log(f"Selected global_ctrl channels: {selected_global_names}")
        _log(f"Selected global_ctrl section: {_object_name(global_section)} class={_class_name(global_section)}")
        _log(f"Selected global_ctrl sequence asset path: {selected_sequence_asset_path or '<not parsed>'}")
        _log(f"Loaded selected global_ctrl sequence: {selected_sequence_name or '<not loaded>'}")
        _log(f"Selected Blueprint Actor candidates found: {len(selected_actor_candidates)}")
        _log(f"Actor search chose source: {chosen_candidate['source']}")
        _log(f"Actor search chose sequence: {chosen_candidate['sequence_label']}")
        if bp_actor_name:
            _log(f"Required Blueprint Actor name filter: {bp_actor_name}")
        _print_actor_candidates(candidates_to_use, chosen_index, label="Usable actor transform candidates")
        if selected_actor_candidates:
            _print_actor_candidates(selected_actor_candidates, -1, label="All selected actor transform candidates")
        _print_actor_candidates(searched_actor_candidates, -1, label="All searched actor transform candidates")
        _print_bundle("Chosen Blueprint Actor", actor_bundle)
        _print_bundle("Selected global_ctrl", global_bundle)
        _log("==================================================")

        samples, sample_error = _build_samples(start_frame, end_frame, actor_bundle, global_bundle)
        if sample_error:
            _log_error(sample_error)
            return ""

        if samples:
            _log(f"First sampled world global_ctrl frame {samples[0]['frame']}: {_format_values(samples[0]['world_values'])}")
            _log(f"Last sampled world global_ctrl frame {samples[-1]['frame']}: {_format_values(samples[-1]['world_values'])}")

        base_actor_values = samples[0]["actor_values"]
        new_global_samples, conversion_error = _build_new_global_samples(samples, base_actor_values)
        if conversion_error:
            _log_error(conversion_error)
            return ""

        if new_global_samples:
            _log(f"First new local global_ctrl frame {new_global_samples[0]['frame']}: {_format_values(new_global_samples[0]['values'])}")
            _log(f"Last new local global_ctrl frame {new_global_samples[-1]['frame']}: {_format_values(new_global_samples[-1]['values'])}")

        if dry_run:
            _log("DRY RUN ONLY. No keys changed.")
            _log("If the chosen Blueprint Actor and global_ctrl section are correct, run with dry_run=False using the same selection/arguments.")
            return "true"

        transaction_class = getattr(unreal, "ScopedEditorTransaction", None)
        if transaction_class is not None:
            with transaction_class("Flatten World Position To Global Ctrl"):
                apply_error = _clear_and_write(actor_bundle, global_bundle, start_frame, base_actor_values, new_global_samples)
        else:
            apply_error = _clear_and_write(actor_bundle, global_bundle, start_frame, base_actor_values, new_global_samples)

        if apply_error:
            _log_error(apply_error)
            _log_error("Flatten failed. Use Edit > Undo before saving if any keys changed.")
            return ""

        _log(f"Flatten complete. Wrote {len(new_global_samples)} frame(s) to global_ctrl and keyed actor base at frame {start_frame}.")
        _log("Review animation before saving.")
        return "true"

    except Exception:
        _log_error(traceback.format_exc())
        return ""
