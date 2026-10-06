"""
Attach Snap Real Bake wrapper.

This keeps the proven attach-snap setup from
flatten_world_position_to_global_ctrl_attach_snap_method, but replaces the
manual bake fallback with Unreal's real Sequencer bake API:

    LevelSequenceEditorSubsystem.bake_transform_with_settings

Selection workflow is the same as the attach snap method:
- Select the Blueprint Actor binding/actor.
- Select the Skeletal Mesh binding/component under that Blueprint Actor.
- Select the Control Rig global_ctrl channels/keys so the ANM subsequence can be resolved.
"""

import importlib
import traceback

import unreal

import flatten_world_position_to_global_ctrl_attach_snap_method as attach_base


LOG_PREFIX = "[AttachSnapRealBake]"


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


def _call_result(obj, function_name, *args):
    if obj is None:
        return False, "object is None"
    function = getattr(obj, function_name, None)
    if function is None:
        return False, "missing"
    try:
        return True, function(*args)
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


def _binding_name(binding):
    return _safe_call(attach_base, "_binding_name", binding) or _compact_text(binding, 120)


def _class_name(obj):
    return _safe_call(attach_base, "_class_name", obj) or str(type(obj))


def _make_frame_number(value):
    frame_value = int(value)
    frame_number_class = getattr(unreal, "FrameNumber", None)
    if frame_number_class is None:
        return frame_value
    try:
        return frame_number_class(frame_value)
    except Exception:
        try:
            frame_number = frame_number_class()
            frame_number.value = frame_value
            return frame_number
        except Exception:
            return frame_value


def _set_property_with_attempts(obj, prop, values, attempts):
    for label, value in values:
        if _safe_set_editor_property(obj, prop, value):
            attempts.append(f"set {prop}={label} -> OK")
            return True
        attempts.append(f"set {prop}={label} -> failed")
    return False


def _read_properties(obj, names):
    output = []
    for name in names:
        try:
            value = obj.get_editor_property(name)
            output.append(f"{name}={_compact_text(value, 120)}")
        except Exception:
            pass
    return output


def _make_baking_settings(start_frame, end_frame_exclusive, frame_increment=1):
    """Create BakingAnimationKeySettings that matches Wrench > Bake Transforms > All Frames.

    Unreal's BakingAnimationKeySettings uses inclusive start/end frames. The ANM playback
    range from the base script is end-exclusive, so bake_end is end_frame_exclusive - step.
    """
    attempts = []
    settings_class = getattr(unreal, "BakingAnimationKeySettings", None)
    if settings_class is None:
        return None, ["unreal.BakingAnimationKeySettings unavailable"]

    try:
        settings = settings_class()
        attempts.append(f"BakingAnimationKeySettings() -> OK {settings}")
    except Exception as exc:
        return None, [f"BakingAnimationKeySettings() -> {exc}"]

    step = max(1, int(frame_increment))
    bake_start = int(start_frame)
    bake_end = int(end_frame_exclusive) - step
    if bake_end < bake_start:
        bake_end = bake_start

    prop_names = ["baking_key_settings", "start_frame", "end_frame", "frame_increment", "reduce_keys", "tolerance", "time_warp"]
    attempts.append(f"initial settings values={_read_properties(settings, prop_names)}")
    attempts.append(f"requested bake frame range inclusive: {bake_start} to {bake_end} step={step}")

    key_enum = getattr(unreal, "BakingKeySettings", None)
    all_frames = getattr(key_enum, "ALL_FRAMES", None) if key_enum is not None else None
    if all_frames is not None:
        _set_property_with_attempts(settings, "baking_key_settings", [("BakingKeySettings.ALL_FRAMES", all_frames)], attempts)
    else:
        _set_property_with_attempts(settings, "baking_key_settings", [("string:ALL_FRAMES", "ALL_FRAMES"), ("string:All Frames", "All Frames")], attempts)

    _set_property_with_attempts(settings, "start_frame", [(f"FrameNumber({bake_start})", _make_frame_number(bake_start)), (f"int({bake_start})", bake_start)], attempts)
    _set_property_with_attempts(settings, "end_frame", [(f"FrameNumber({bake_end})", _make_frame_number(bake_end)), (f"int({bake_end})", bake_end)], attempts)
    _set_property_with_attempts(settings, "frame_increment", [(f"int({step})", step)], attempts)
    _set_property_with_attempts(settings, "reduce_keys", [("False", False)], attempts)

    attempts.append(f"final settings values={_read_properties(settings, prop_names)}")
    return settings, attempts


def _make_scripting_params():
    attempts = []
    params_class = getattr(unreal, "MovieSceneScriptingParams", None)
    if params_class is None:
        return None, ["unreal.MovieSceneScriptingParams unavailable"]
    try:
        params = params_class()
        attempts.append(f"MovieSceneScriptingParams() -> OK {params}")
    except Exception as exc:
        return None, [f"MovieSceneScriptingParams() -> {exc}"]

    time_unit_enum = getattr(unreal, "MovieSceneTimeUnit", None)
    display_rate = getattr(time_unit_enum, "DISPLAY_RATE", None) if time_unit_enum else None
    if display_rate is not None:
        _set_property_with_attempts(params, "time_unit", [("MovieSceneTimeUnit.DISPLAY_RATE", display_rate)], attempts)
    attempts.append(f"final params values={_read_properties(params, ['time_unit'])}")
    return params, attempts


def _clear_sequencer_selection():
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    attempts = []
    for function_name, args in (
        ("empty_selection", ()),
        ("clear_selection", ()),
        ("clear_selected_bindings", ()),
        ("select_bindings", ([],)),
        ("set_selected_bindings", ([],)),
    ):
        ok, result = _call_result(library, function_name, *args)
        attempts.append(f"{function_name} -> {'OK' if ok else result}")
    return attempts


def _select_binding(binding):
    attempts = []
    attempts.append(f"clear attempts={_clear_sequencer_selection()}")
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    for function_name, args in (
        ("select_binding", (binding,)),
        ("select_bindings", ([binding],)),
        ("set_selected_bindings", ([binding],)),
    ):
        ok, result = _call_result(library, function_name, *args)
        attempts.append(f"{function_name} -> {'OK' if ok else result}")
        if ok:
            return True, attempts
    return False, attempts


def _refresh_sequencer():
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    attempts = []
    for function_name in ("refresh_current_level_sequence", "refresh_current_level_sequence_editor", "refresh_current_level_sequence_player"):
        ok, result = _call_result(library, function_name)
        attempts.append(f"{function_name} -> {'OK' if ok else result}")
        if ok:
            return True, attempts
    return False, attempts


def _track_is_attach(track):
    return "Attach" in _class_name(track)


def _track_is_transform(track):
    return "TransformTrack" in _class_name(track) or "3DTransformTrack" in _class_name(track)


def _key_frame_number(key):
    time_unit_enum = getattr(unreal, "MovieSceneTimeUnit", None)
    display_rate = getattr(time_unit_enum, "DISPLAY_RATE", None) if time_unit_enum else None
    args_to_try = []
    if display_rate is not None:
        args_to_try.append((display_rate,))
    args_to_try.append(())

    for args in args_to_try:
        try:
            value = key.get_time(*args)
        except Exception:
            continue
        for attr in ("value", "Value"):
            if hasattr(value, attr):
                try:
                    return int(getattr(value, attr))
                except Exception:
                    pass
        frame_number = getattr(value, "frame_number", None) or getattr(value, "FrameNumber", None)
        if frame_number is not None:
            for attr in ("value", "Value"):
                if hasattr(frame_number, attr):
                    try:
                        return int(getattr(frame_number, attr))
                    except Exception:
                        pass
        try:
            return int(value)
        except Exception:
            pass
    return None


def _attach_track_status(binding):
    output = []
    for track in _as_list(_safe_call(binding, "get_tracks")):
        if not _track_is_attach(track):
            continue
        values = []
        for prop in ("b_is_eval_disabled", "is_eval_disabled", "bIsEvalDisabled", "eval_disabled"):
            value = _safe_get_editor_property(track, prop)
            if value is not None:
                values.append(f"{prop}={value}")
        output.append(f"{_class_name(track)} {values or '<no disabled-property readback>'}")
    return output


def _remove_attach_track_after_bake(binding, attach_track):
    attempts = []
    if binding is None or attach_track is None:
        return False, ["binding or attach_track is None"]

    remover = getattr(attach_base, "_remove_track", None)
    if remover is not None:
        try:
            if remover(binding, attach_track):
                attempts.append("attach_base._remove_track(binding, attach_track) -> OK")
                return True, attempts
            attempts.append("attach_base._remove_track(binding, attach_track) -> returned False")
        except Exception as exc:
            attempts.append(f"attach_base._remove_track(binding, attach_track) -> {exc}")

    for function_name, args in (
        ("remove_track", (attach_track,)),
        ("remove_movie_scene_track", (attach_track,)),
    ):
        ok, result = _call_result(binding, function_name, *args)
        attempts.append(f"binding.{function_name}(attach_track) -> {'OK' if ok else result}")
        if ok:
            return True, attempts

    # Last resort: remove the attach sections so the baked transform keys do not double-evaluate with the live attach.
    removed_sections = 0
    for section in list(_as_list(_safe_call(attach_track, "get_sections"))):
        ok, result = _call_result(attach_track, "remove_section", section)
        attempts.append(f"attach_track.remove_section(section) -> {'OK' if ok else result}")
        if ok:
            removed_sections += 1
    if removed_sections:
        attempts.append(f"removed {removed_sections} attach section(s) as fallback")
        return True, attempts

    return False, attempts


def _transform_key_summary(binding, start_frame=None, end_frame_exclusive=None):
    summary = []
    total_keys = 0
    keys_in_range = 0
    for track in _as_list(_safe_call(binding, "get_tracks")):
        if not _track_is_transform(track):
            continue
        for section in _as_list(_safe_call(track, "get_sections")):
            channels = []
            for getter in ("get_channels", "get_all_channels"):
                channels.extend(_as_list(_safe_call(section, getter)))
            channel_class = getattr(unreal, "MovieSceneScriptingDoubleChannel", None)
            if channel_class is not None:
                channels.extend(_as_list(_safe_call(section, "get_channels_by_type", channel_class)))

            seen = set()
            channel_summaries = []
            for channel in channels:
                key = id(channel)
                if key in seen:
                    continue
                seen.add(key)
                name = _safe_call(channel, "get_name") or _safe_call(channel, "get_display_name") or _compact_text(channel, 80)
                keys = _as_list(_safe_call(channel, "get_keys"))
                total_keys += len(keys)

                frames = []
                for key_obj in keys:
                    frame = _key_frame_number(key_obj)
                    if frame is not None:
                        frames.append(frame)
                        if start_frame is not None and end_frame_exclusive is not None:
                            if int(start_frame) <= frame < int(end_frame_exclusive):
                                keys_in_range += 1

                if frames:
                    channel_summaries.append(f"{name}:{len(keys)} min={min(frames)} max={max(frames)}")
                else:
                    channel_summaries.append(f"{name}:{len(keys)}")
            summary.append(f"{_class_name(track)} section={_compact_text(section, 80)} channels={channel_summaries}")
    return total_keys, keys_in_range, summary


def _try_real_sequencer_bake_transform(sequence, binding, start_frame, end_frame, frame_increment):
    attempts = []
    attempts.append(f"target binding for bake={_binding_name(binding)!r}")

    before_total, before_in_range, before_summary = _transform_key_summary(binding, start_frame, end_frame)
    attempts.append(f"transform key summary before bake total={before_total} in_range={before_in_range} summary={before_summary}")

    selected_ok, selected_attempts = _select_binding(binding)
    attempts.append(f"select binding attempts={selected_attempts}")
    _ok, refresh_attempts = _refresh_sequencer()
    attempts.append(f"refresh attempts before bake={refresh_attempts}")

    subsystem_class = getattr(unreal, "LevelSequenceEditorSubsystem", None)
    subsystem = _safe_call(unreal, "get_editor_subsystem", subsystem_class) if subsystem_class is not None else None
    if subsystem is None:
        attempts.append("LevelSequenceEditorSubsystem unavailable")
        return False, attempts

    bake_method = getattr(subsystem, "bake_transform_with_settings", None)
    if bake_method is None:
        attempts.append("LevelSequenceEditorSubsystem.bake_transform_with_settings missing")
        return False, attempts

    settings, settings_attempts = _make_baking_settings(start_frame=start_frame, end_frame_exclusive=end_frame, frame_increment=frame_increment)
    attempts.append(f"settings attempts={settings_attempts}")
    if settings is None:
        return False, attempts

    params, params_attempts = _make_scripting_params()
    attempts.append(f"params attempts={params_attempts}")

    arg_sets = []
    if params is not None:
        arg_sets.append(("[binding], settings, params", ([binding], settings, params)))
    arg_sets.append(("[binding], settings", ([binding], settings)))

    for label, args in arg_sets:
        try:
            result = bake_method(*args)
            attempts.append(f"bake_transform_with_settings({label}) -> OK result={result}")
            _ok, refresh_after = _refresh_sequencer()
            attempts.append(f"refresh attempts after bake={refresh_after}")
            after_total, after_in_range, after_summary = _transform_key_summary(binding, start_frame, end_frame)
            attempts.append(f"transform key summary after bake total={after_total} in_range={after_in_range} summary={after_summary}")
            attempts.append(f"attach track status after bake={_attach_track_status(binding)}")

            expected_frames = max(1, int((int(end_frame) - int(start_frame)) / max(1, int(frame_increment))))
            expected_range_keys = expected_frames * 9
            if bool(result) and after_in_range >= expected_range_keys:
                return True, attempts

            attempts.append(
                "bake returned true but did not create enough keys inside the requested shot range; "
                f"expected at least {expected_range_keys} in-range keys, got {after_in_range}"
            )
            return False, attempts
        except Exception as exc:
            attempts.append(f"bake_transform_with_settings({label}) -> {exc}")

    attempts.append(f"attach track status after failed bake={_attach_track_status(binding)}")
    return False, attempts


def _real_bake_recorder_sphere_transform(sequence, binding, attach_track, start_frame, end_frame, frame_increment, remove_attach_after_bake=True, write_scale_keys=False):
    _log(f"Real Sequencer bake requested: start={start_frame} end={end_frame} end-exclusive increment={frame_increment} settings=All Frames")
    ok, attempts = _try_real_sequencer_bake_transform(sequence, binding, start_frame, end_frame, frame_increment)
    _log(f"Real Sequencer bake attempts: {attempts}")
    if ok:
        if remove_attach_after_bake:
            removed, removal_attempts = _remove_attach_track_after_bake(binding, attach_track)
            _log(f"Post-bake attach removal attempts: {removal_attempts}")
            if removed:
                _ok, refresh_attempts = _refresh_sequencer()
                _log(f"Refresh after attach removal attempts: {refresh_attempts}")
                _log("Removed recorder_sphere Attach track after real Sequencer bake so baked Transform keys are the only driver.")
            else:
                _log_warning("Real Sequencer bake succeeded, but Attach track could not be removed. The live attach may double-evaluate with the baked transform keys.")
        else:
            _log("Kept recorder_sphere Attach track after real Sequencer bake because remove_attach_after_bake=False.")
        _log("SUCCESS: LevelSequenceEditorSubsystem.bake_transform_with_settings completed for recorder_sphere in the shot frame range.")
        return True, ""
    return False, "Real Sequencer bake did not create a full All Frames transform bake in the requested shot range. Manual fallback is intentionally disabled because it creates an offset. See log attempts above."


def _patch_base_module():
    attach_base._bake_recorder_sphere_transform = _real_bake_recorder_sphere_transform
    return True


def run(
    bp_actor_name="",
    skeletal_mesh_name="",
    global_ctrl_name="global_ctrl",
    root_bone_name="root",
    sphere_name="recorder_sphere",
    delete_existing=True,
    prefer_selected_global_ctrl_sequence=True,
    bake_recorder_sphere=True,
    frame_increment=1,
    remove_attach_after_bake=False,
    sphere_visual_scale=0.12,
    write_scale_keys=True,
):
    try:
        _patch_base_module()
        _log("Using real Sequencer bake path through LevelSequenceEditorSubsystem.bake_transform_with_settings.")
        return attach_base.run(
            bp_actor_name=bp_actor_name,
            skeletal_mesh_name=skeletal_mesh_name,
            global_ctrl_name=global_ctrl_name,
            root_bone_name=root_bone_name,
            sphere_name=sphere_name,
            delete_existing=delete_existing,
            prefer_selected_global_ctrl_sequence=prefer_selected_global_ctrl_sequence,
            bake_recorder_sphere=bake_recorder_sphere,
            frame_increment=frame_increment,
            remove_attach_after_bake=remove_attach_after_bake,
            sphere_visual_scale=sphere_visual_scale,
            write_scale_keys=write_scale_keys,
        )
    except Exception:
        _log_error(traceback.format_exc())
        return ""


def reload_base_and_run(**kwargs):
    global attach_base
    attach_base = importlib.reload(attach_base)
    return run(**kwargs)
