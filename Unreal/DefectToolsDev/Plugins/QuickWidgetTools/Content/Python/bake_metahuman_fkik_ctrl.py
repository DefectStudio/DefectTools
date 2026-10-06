"""
Bake MetaHuman FK/IK switch attributes on the selected global control.

Workflow:
- Open a Level Sequence in Sequencer.
- Select the Control Rig control named global_ctrl in Sequencer / Anim Outliner.
- Run this script from an Editor Utility Widget or the Unreal Python console.

Blueprint / Python usage:

    import bake_metahuman_fkik_ctrl
    import importlib

    importlib.reload(bake_metahuman_fkik_ctrl)

    success = bake_metahuman_fkik_ctrl.run()

Returns:
    "true" on success, or "" on failure.
"""

import re
import traceback

import unreal


LOG_PREFIX = "[BakeMetaHumanFKIKCtrl]"
REQUIRED_SELECTED_CONTROL = "global_ctrl"
TARGET_ATTRIBUTES = (
    "arm_l_fk_ik_switch",
    "arm_r_fk_ik_switch",
)
DEBUG_MAX_ITEMS = 40

try:
    _RIG_ELEMENT_TYPE_CONTROL = unreal.RigElementType.CONTROL
except Exception:
    _RIG_ELEMENT_TYPE_CONTROL = None


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
        value = getattr(obj, name, None)
        if value is not None:
            return value

    for name in names:
        value = _safe_get_editor_property(obj, name)
        if value is not None:
            return value

    return None


def _compact_text(value, max_length=220):
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


def _normalize_name(value):
    text = str(value or "").strip()

    for prefix in (
        "RigElementKey(type=Control, name=",
        "RigElementKey(type=CONTROL, name=",
    ):
        if text.startswith(prefix) and text.endswith(")"):
            text = text[len(prefix):-1]
            break

    return text.strip()


def _normalize_for_match(value):
    text = _normalize_name(value).lower().strip()
    for char in " \\/:;,.[]{}()<>|?*\"'`~!@#$%^&+=-":
        text = text.replace(char, "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


def _extract_channel_name_from_text(value):
    text = _compact_text(value, 1000)
    match = re.search(r'channel_name:\s*"([^"]+)"', text)
    if match:
        return match.group(1)
    return ""


def _get_channel_name(channel_or_proxy):
    value = _get_value(channel_or_proxy, "channel_name")
    if value:
        return str(value)

    for function_name in ("get_name", "get_display_name"):
        value = _safe_call(channel_or_proxy, function_name)
        if value:
            return str(value)

    value = _get_value(channel_or_proxy, "name")
    if value:
        return str(value)

    value = _extract_channel_name_from_text(channel_or_proxy)
    if value:
        return value

    return _compact_text(channel_or_proxy)


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


def _as_list(value):
    if value is None:
        return []

    if isinstance(value, (str, bytes)):
        return [value]

    try:
        return list(value)
    except Exception:
        return [value]


def _get_current_level_sequence():
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    return _safe_call(library, "get_current_level_sequence")


def _get_selected_channel_proxies():
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    return _as_list(_safe_call(library, "get_selected_channels"))


def _get_selected_channel_names():
    names = []
    seen = set()

    for channel_proxy in _get_selected_channel_proxies():
        name = _get_channel_name(channel_proxy)
        if not name:
            continue

        if name in seen:
            continue

        seen.add(name)
        names.append(name)

    return names


def _get_control_rig_from_proxy(proxy):
    rig = _get_value(proxy, "control_rig", "rig")
    if rig is not None:
        return rig

    for function_name in ("get_control_rig", "get_rig"):
        rig = _safe_call(proxy, function_name)
        if rig is not None:
            return rig

    return None


def _get_control_rig_proxies(sequence):
    library = getattr(unreal, "ControlRigSequencerLibrary", None)
    proxies = _safe_call(library, "get_control_rigs", sequence)
    return _as_list(proxies)


def _get_selected_control_names_from_control_rig(control_rig):
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
            candidates.extend(_as_list(selection))

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
                candidates.extend(_as_list(selection))

    names = []
    seen = set()

    for item in candidates:
        item_type = getattr(item, "type", None)
        if _RIG_ELEMENT_TYPE_CONTROL is not None and item_type is not None:
            if item_type != _RIG_ELEMENT_TYPE_CONTROL:
                continue

        name = getattr(item, "name", None)
        if name is None:
            name = item

        name = _normalize_name(name)
        if not name or name in seen:
            continue

        seen.add(name)
        names.append(name)

    return names


def _selection_name_matches_required_control(name):
    normalized_name = _normalize_for_match(name)
    normalized_required = _normalize_for_match(REQUIRED_SELECTED_CONTROL)

    return (
        normalized_name == normalized_required
        or normalized_name.startswith(normalized_required + "_")
    )


def _validate_selected_global_control(sequence):
    selected_channel_names = _get_selected_channel_names()

    for channel_name in selected_channel_names:
        if _selection_name_matches_required_control(channel_name):
            _log(f"Selected Sequencer channels include {REQUIRED_SELECTED_CONTROL}: {channel_name}")
            return True

    wrong_selected_controls = []

    for proxy in _get_control_rig_proxies(sequence):
        control_rig = _get_control_rig_from_proxy(proxy)
        selected_control_names = _get_selected_control_names_from_control_rig(control_rig)

        for control_name in selected_control_names:
            if _normalize_for_match(control_name) == _normalize_for_match(REQUIRED_SELECTED_CONTROL):
                _log(f"Selected Control Rig controller: {REQUIRED_SELECTED_CONTROL}")
                return True
            wrong_selected_controls.append(control_name)

    if selected_channel_names:
        _log_error(
            "wrong controller. Selected Sequencer channel names: "
            + ", ".join(selected_channel_names[:DEBUG_MAX_ITEMS])
        )
    elif wrong_selected_controls:
        _log_error(
            "wrong controller. Selected Control Rig controls: "
            + ", ".join(wrong_selected_controls[:DEBUG_MAX_ITEMS])
        )
    else:
        _log_error(
            "wrong controller. Select the Control Rig controller named "
            f"{REQUIRED_SELECTED_CONTROL} in Sequencer."
        )

    return False


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


def _iter_bindings(sequence):
    bindings = []

    for function_name in ("get_bindings", "get_possessables", "get_spawnables"):
        result = _safe_call(sequence, function_name)
        if result:
            bindings.extend(_as_list(result))

    index = 0
    while index < len(bindings):
        binding = bindings[index]
        index += 1
        yield binding

        children = _safe_call(binding, "get_child_possessables")
        if children:
            bindings.extend(_as_list(children))


def _iter_tracks(sequence):
    seen = set()

    for binding in _iter_bindings(sequence):
        tracks = _safe_call(binding, "get_tracks")
        if not tracks:
            continue

        for track in _as_list(tracks):
            key = id(track)
            if key in seen:
                continue
            seen.add(key)
            yield track

    master_tracks = _safe_call(sequence, "get_master_tracks")
    if master_tracks:
        for track in _as_list(master_tracks):
            key = id(track)
            if key in seen:
                continue
            seen.add(key)
            yield track


def _iter_sections(sequence):
    seen = set()

    for track in _iter_tracks(sequence):
        sections = _safe_call(track, "get_sections")
        if not sections:
            continue

        for section in _as_list(sections):
            key = id(section)
            if key in seen:
                continue
            seen.add(key)
            yield section

    for channel_proxy in _get_selected_channel_proxies():
        section = _get_value(channel_proxy, "section")
        if section is None:
            continue

        key = id(section)
        if key in seen:
            continue
        seen.add(key)
        yield section


def _get_section_channels(section):
    channels = _safe_call(section, "get_channels")
    if channels is None:
        channels = _safe_call(section, "get_all_channels")
    return _as_list(channels)


def _channel_matches_target(channel, attribute_name):
    channel_name = _get_channel_name(channel)
    normalized_channel_name = _normalize_for_match(channel_name)
    normalized_attribute_name = _normalize_for_match(attribute_name)

    return (
        normalized_channel_name == normalized_attribute_name
        or normalized_channel_name.endswith("_" + normalized_attribute_name)
    )


def _find_target_channels(sequence):
    found = {attribute_name: [] for attribute_name in TARGET_ATTRIBUTES}
    seen = set()

    for section in _iter_sections(sequence):
        section_name = _safe_call(_safe_call(section, "get_class"), "get_name") or _compact_text(type(section))
        channels = _get_section_channels(section)

        for channel in channels:
            for attribute_name in TARGET_ATTRIBUTES:
                if not _channel_matches_target(channel, attribute_name):
                    continue

                key = (attribute_name, id(channel))
                if key in seen:
                    continue

                seen.add(key)
                found[attribute_name].append((section, channel, section_name, _get_channel_name(channel)))

    return found


def _get_channel_default(channel):
    for function_name in ("get_default", "get_default_value"):
        value = _safe_call(channel, function_name)
        if value is not None:
            return value
    return None


def _get_key_time(key):
    display_rate_unit = _get_display_rate_time_unit()

    if display_rate_unit is not None:
        time_value = _safe_call(key, "get_time", display_rate_unit)
        frame = _to_int_frame(time_value)
        if frame is not None:
            return frame

    time_value = _safe_call(key, "get_time")
    frame = _to_int_frame(time_value)
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


def _get_channel_keys(channel):
    for function_name in ("get_keys", "get_all_keys"):
        keys = _safe_call(channel, function_name)
        if keys is not None:
            return _as_list(keys)
    return []


def _snapshot_channel_values(channel):
    key_values = []

    for key in _get_channel_keys(channel):
        frame = _get_key_time(key)
        value = _get_key_value(key)

        if frame is None or value is None:
            continue

        key_values.append((frame, value))

    key_values.sort(key=lambda item: item[0])
    return key_values, _get_channel_default(channel)


def _evaluate_channel(channel, frame_number):
    time = _make_frame_number(frame_number)

    for args in ((time,), (frame_number,)):
        value = _safe_call(channel, "evaluate", *args)
        if value is not None:
            return value

    return _get_channel_default(channel)


def _value_from_snapshot(frame_number, key_values, default_value, fallback_channel):
    if key_values:
        value = default_value
        if value is None:
            value = key_values[0][1]

        for key_frame, key_value in key_values:
            if key_frame > frame_number:
                break
            value = key_value

        return value

    value = _evaluate_channel(fallback_channel, frame_number)
    if value is not None:
        return value

    return default_value


def _looks_bool_channel(channel):
    try:
        class_name = str(channel.get_class().get_name()).lower()
    except Exception:
        class_name = str(type(channel)).lower()

    return "bool" in class_name


def _coerce_bool(value):
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    text = str(value).strip().lower()
    if text in ("false", "0", "no", "off", "unchecked", "none", ""):
        return False

    return True


def _coerce_value_for_channel(channel, value):
    class_name = ""
    try:
        class_name = str(channel.get_class().get_name()).lower()
    except Exception:
        class_name = str(type(channel)).lower()

    if "bool" in class_name:
        return _coerce_bool(value)

    if "integer" in class_name or "int" in class_name or "byte" in class_name:
        try:
            return int(value)
        except Exception:
            return 0

    try:
        return float(value)
    except Exception:
        return value


def _add_channel_key(channel, frame_number, value):
    time = _make_frame_number(frame_number)
    value = _coerce_value_for_channel(channel, value)
    display_rate_unit = _get_display_rate_time_unit()

    call_patterns = []
    if display_rate_unit is not None:
        call_patterns.append((time, value, 0.0, display_rate_unit))
    call_patterns.extend((
        (time, value, 0.0),
        (time, value),
        (frame_number, value),
    ))

    for args in call_patterns:
        try:
            channel.add_key(*args)
            return True
        except Exception:
            pass

    return False


def _bake_channel_every_frame(channel, start_frame, end_frame):
    keyed_count = 0
    failed_frames = []
    stop_frame = max(start_frame + 1, end_frame)

    key_values, default_value = _snapshot_channel_values(channel)
    _log(f"Original key snapshot count: {len(key_values)}")

    if key_values:
        preview = ", ".join([f"{frame}:{value}" for frame, value in key_values[:10]])
        _log(f"Original key snapshot preview: {preview}")
        if len(key_values) > 10:
            _log(f"Original key snapshot skipped: {len(key_values) - 10}")

    for frame in range(start_frame, stop_frame):
        value = _value_from_snapshot(frame, key_values, default_value, channel)
        if value is None:
            failed_frames.append(frame)
            continue

        if _add_channel_key(channel, frame, value):
            keyed_count += 1
        else:
            failed_frames.append(frame)

    return keyed_count, failed_frames


def _debug_print_selected_channels():
    selected_channel_names = _get_selected_channel_names()
    _log(f"Selected Sequencer channels: {len(selected_channel_names)}")

    for index, channel_name in enumerate(selected_channel_names[:DEBUG_MAX_ITEMS]):
        _log(f"  SelectedChannel[{index}]: {channel_name}")

    if len(selected_channel_names) > DEBUG_MAX_ITEMS:
        _log(f"  ... skipped {len(selected_channel_names) - DEBUG_MAX_ITEMS} more selected channel(s)")


def run(debug_selection=True):
    """
    Bake keys on every playback frame for global_ctrl arm FK/IK switch attrs.

    Args:
        debug_selection (bool): Print selected Sequencer channel info before baking.

    Returns:
        str: "true" on success, or "" on failure.
    """
    try:
        sequence = _get_current_level_sequence()
        if sequence is None:
            _log_error("No current Level Sequence is open in Sequencer.")
            return ""

        sequence_name = _safe_call(sequence, "get_name") or str(sequence)
        _log(f"Current Level Sequence: {sequence_name}")

        start_frame, end_frame = _get_sequence_frame_range(sequence)
        if start_frame is None or end_frame is None:
            _log_error("Could not read the Level Sequence playback frame range.")
            return ""

        _log(f"Playback frame range: {start_frame} to {end_frame} end-exclusive")
        _log(f"Frames to key: {max(1, end_frame - start_frame)}")

        if debug_selection:
            _debug_print_selected_channels()

        if not _validate_selected_global_control(sequence):
            return ""

        target_channels = _find_target_channels(sequence)
        missing_attributes = [
            attribute_name
            for attribute_name, channels in target_channels.items()
            if not channels
        ]

        if missing_attributes:
            for attribute_name in missing_attributes:
                _log_error(f"Could not find keyable Sequencer channel: {attribute_name}")
            return ""

        total_keyed = 0
        total_failures = 0

        for attribute_name in TARGET_ATTRIBUTES:
            channels = target_channels.get(attribute_name, [])
            _log(f"Found {len(channels)} channel(s) for {attribute_name}")

            for section, channel, section_name, channel_name in channels:
                _log(f"Baking channel: {channel_name}  Section: {section_name}")
                keyed_count, failed_frames = _bake_channel_every_frame(channel, start_frame, end_frame)
                total_keyed += keyed_count
                total_failures += len(failed_frames)

                _log(f"Keyed {keyed_count} frame(s) for channel: {channel_name}")
                if failed_frames:
                    _log_warning(
                        f"Failed frame count for {channel_name}: {len(failed_frames)}. "
                        f"First few: {failed_frames[:10]}"
                    )

        if total_failures:
            _log_error(f"Bake finished with failed frame writes: {total_failures}")
            return ""

        _log(f"Bake complete. Total keys written: {total_keyed}")
        return "true"

    except Exception:
        _log_error(traceback.format_exc())
        return ""
