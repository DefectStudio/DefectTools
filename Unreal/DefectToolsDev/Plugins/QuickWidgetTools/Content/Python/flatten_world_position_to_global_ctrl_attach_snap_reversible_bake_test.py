"""
Attach Snap Reversible Bake Test (v2 - split commands).

The first version validated inside the same synchronous Python call that
deactivated the Attach section. Sequencer's compiled evaluation graph is NOT
rebuilt mid-call, so every "keys-only" read still came from the old live-attach
evaluation -> numeric pass, visibly wrong result. This version splits the work
into three commands that each run in their own editor evaluation:

COMMAND A - bake_and_detach():
    Pre-flight guards, samples sphere+root world transforms for every display
    frame while the attach is LIVE, writes one transform track
    (location+rotation+scale keys, every frame), deactivates (not deletes) the
    attach section, refreshes, and EXITS. No validation happens here.
    After it returns: let the editor tick, scrub the timeline by hand, then run
    Command B.

COMMAND B - validate_settled():
    Read-only. Run it in a separate call after Unreal has ticked/scrubbed.
    Starts with a frame wiggle (jump to last frame, then first) to force real
    re-evaluations. Requires: attach sections inactive AND the sphere's root
    component no longer attached (get_attach_parent() is None).
    Per frame it compares THREE values:
      keyed   - the values read back from the transform channels (what we wrote)
      evaluated - the sphere's freshly evaluated world transform
      root    - freshly sampled Bungie_Char.root world transform
    evaluated-vs-keyed mismatch  -> Sequencer applies the keys in a different
                                    space than world (space problem).
    keyed-vs-root mismatch       -> the PASS 1 samples were wrong.
    evaluated-vs-root            -> the final correctness verdict.
    Detailed rows are logged at the probe frames; the numeric check covers every
    frame. It never writes anything and never rolls back automatically by
    default (so a failed state can be inspected); pass rollback_on_failure=True
    to auto-restore.

COMMAND R - rollback():
    Removes the transform track(s) on the recorder_sphere binding FIRST, then
    reactivates the attach section(s), refreshes, returns the playhead to the
    shot start. Restores the known-good live-attach state. Touches nothing but
    the recorder_sphere binding.

Nothing here touches global_ctrl, the Control Rig, Snapper, or
chr_Assassin_S1_v001 / its transform keys.
"""

import importlib
import math
import traceback

import unreal

import flatten_world_position_to_global_ctrl_attach_snap_method as attach_base
import flatten_world_position_to_global_ctrl_attach_snap_bake_diagnostic as diag


LOG_PREFIX = "[AttachSnapReversibleBakeTest]"

TRANSFORM_CHANNEL_ORDER = (
    "location_x", "location_y", "location_z",
    "rotation_x", "rotation_y", "rotation_z",
    "scale_x", "scale_y", "scale_z",
)


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


def _reload_dependencies():
    global attach_base, diag
    attach_base = importlib.reload(attach_base)
    diag = importlib.reload(diag)


def _transform_tracks(binding):
    return [t for t in _as_list(_safe_call(binding, "get_tracks")) if "TransformTrack" in _class_name(t)]


def _wrapped_component_rot_error(rot_a, rot_b):
    worst = 0.0
    for attr in ("roll", "pitch", "yaw"):
        delta = float(getattr(rot_a, attr)) - float(getattr(rot_b, attr))
        delta = abs((delta + 180.0) % 360.0 - 180.0)
        worst = max(worst, delta)
    return worst


def _rotation_error_degrees(rot_a, rot_b):
    if rot_a is None or rot_b is None:
        return None
    quat_a = _safe_call(rot_a, "quaternion")
    quat_b = _safe_call(rot_b, "quaternion")
    radians = _safe_call(quat_a, "angular_distance", quat_b)
    if radians is not None:
        try:
            return abs(math.degrees(float(radians)))
        except Exception:
            pass
    return _wrapped_component_rot_error(rot_a, rot_b)


def _location_error(loc_a, loc_b):
    if loc_a is None or loc_b is None:
        return None
    diff = unreal.Vector(loc_a.x - loc_b.x, loc_a.y - loc_b.y, loc_a.z - loc_b.z)
    return float(diff.length())


def _fmt_err(value):
    return f"{value:.6f}" if value is not None else "<n/a>"


def _values_from_parts(location, rotation, scale):
    return {
        "location_x": float(location.x),
        "location_y": float(location.y),
        "location_z": float(location.z),
        "rotation_x": float(rotation.roll),
        "rotation_y": float(rotation.pitch),
        "rotation_z": float(rotation.yaw),
        "scale_x": float(scale.x) if scale is not None else 1.0,
        "scale_y": float(scale.y) if scale is not None else 1.0,
        "scale_z": float(scale.z) if scale is not None else 1.0,
    }


def _sample_sphere_world(sequence, sphere_binding):
    sphere_actor, _attempts = diag._resolve_sphere_actor(sequence, sphere_binding)
    if sphere_actor is None:
        return None, None, None, None
    transform = _safe_call(sphere_actor, "get_actor_transform")
    location, rotation, scale = diag._transform_parts(transform)
    if location is None:
        location = _safe_call(sphere_actor, "get_actor_location")
    if rotation is None:
        rotation = _safe_call(sphere_actor, "get_actor_rotation")
    return sphere_actor, location, rotation, scale


def _resolve_common(bp_actor_name, skeletal_mesh_name, global_ctrl_name, prefer_selected_global_ctrl_sequence, sphere_name):
    context, error = attach_base._resolve_context(
        bp_actor_name, skeletal_mesh_name, global_ctrl_name, prefer_selected_global_ctrl_sequence
    )
    if error:
        return None, None, error
    sequence = context["sequence"]
    sphere_binding, how = diag._find_sphere_binding(sequence, sphere_name)
    if sphere_binding is None:
        return None, None, f"Could not find recorder_sphere binding ({how})."
    _log(
        f"sequence={_safe_call(sequence, 'get_name')} "
        f"range=[{context['start_frame']},{context['end_frame']}) "
        f"binding={attach_base._binding_name(sphere_binding)!r} found_by={how} "
        f"kind={diag._binding_kind(sequence, sphere_binding)}"
    )
    return context, sphere_binding, ""


def _default_probe_frames(start_frame, end_frame):
    mid = start_frame + (end_frame - start_frame) // 2
    return sorted({start_frame, start_frame + 1, min(start_frame + 9, end_frame - 1), mid, end_frame - 1})


def _channel_key_by_name(channel):
    name = str(diag._channel_name(channel)).lower().replace(".", "_").replace(" ", "_")
    for key in TRANSFORM_CHANNEL_ORDER:
        group, axis = key.rsplit("_", 1)
        if group in name and name.endswith(axis):
            return key
    return None


def _keyed_values_by_frame(binding):
    """Read back {frame: {channel_key: value}} from the transform track's channels."""
    tracks = _transform_tracks(binding)
    if not tracks:
        return {}, "no transform track on binding"
    if len(tracks) > 1:
        _log_warning(f"{len(tracks)} transform tracks on binding; reading the first.")
    sections = _as_list(_safe_call(tracks[0], "get_sections"))
    if not sections:
        return {}, "transform track has no sections"
    if len(sections) > 1:
        _log_warning(f"{len(sections)} sections on transform track; reading the first.")
    section = sections[0]
    channels = _as_list(_safe_call(section, "get_all_channels"))
    mapping = {}
    for key, channel in zip(TRANSFORM_CHANNEL_ORDER, channels[:9]):
        mapping[key] = channel
    for channel in channels:
        key = _channel_key_by_name(channel)
        if key is not None:
            mapping[key] = channel
    by_frame = {}
    for key, channel in mapping.items():
        for key_obj in _as_list(_safe_call(channel, "get_keys")):
            frame, value = diag._key_frame_and_value(key_obj)
            if frame is None:
                continue
            by_frame.setdefault(int(frame), {})[key] = value
    return by_frame, ""


def _keyed_loc_rot(values):
    if values is None:
        return None, None
    try:
        location = unreal.Vector(values["location_x"], values["location_y"], values["location_z"])
        rotation = unreal.Rotator(roll=values["rotation_x"], pitch=values["rotation_y"], yaw=values["rotation_z"])
        return location, rotation
    except Exception:
        return None, None


def _remove_transform_tracks(binding):
    attempts = []
    for track in list(_transform_tracks(binding)):
        ok = attach_base._remove_track(binding, track)
        attempts.append(f"remove {_class_name(track)} -> {ok}")
    return attempts


# ---------------------------------------------------------------------------
# COMMAND A - bake and detach (no validation in this call)
# ---------------------------------------------------------------------------

def bake_and_detach(
    bp_actor_name="",
    skeletal_mesh_name="",
    global_ctrl_name="global_ctrl",
    root_bone_name="root",
    sphere_name="recorder_sphere",
    prefer_selected_global_ctrl_sequence=True,
    location_tolerance=0.1,
):
    try:
        _reload_dependencies()
        _log("================ COMMAND A: bake_and_detach start ================")
        _log("Scope: recorder_sphere only. No validation in this call - run validate_settled() separately.")

        context, sphere_binding, error = _resolve_common(
            bp_actor_name, skeletal_mesh_name, global_ctrl_name, prefer_selected_global_ctrl_sequence, sphere_name
        )
        if error:
            _log_error(error)
            return ""
        sequence = context["sequence"]
        start_frame = int(context["start_frame"])
        end_frame = int(context["end_frame"])
        library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)

        attach_pairs = diag._attach_sections(sphere_binding)
        if not attach_pairs:
            _log_error("No attach sections on recorder_sphere binding. Aborting untouched.")
            return ""
        if any(not _safe_call(section, "is_active") for _t, section in attach_pairs):
            _log_error(
                "Attach section(s) are not active; expected the live-attach known-good state. "
                "Run rollback() first if a previous bake left the attach inactive. Aborting untouched."
            )
            return ""
        if _transform_tracks(sphere_binding):
            _log_error(
                "recorder_sphere already has transform track(s). Refusing to clobber. "
                "Run rollback() to clear a previous bake, then retry. Aborting untouched."
            )
            return ""

        frames = list(range(start_frame, end_frame))
        _log(f"PASS 1: sampling {len(frames)} frames with attach LIVE...")
        samples = []
        worst_live = 0.0
        for frame in frames:
            ok, _current, _local = diag._set_time_and_report(frame)
            if not ok:
                _log_error(f"Could not set sequencer time at frame {frame}. Aborting untouched.")
                return ""
            sphere_actor, sphere_loc, sphere_rot, sphere_scale = _sample_sphere_world(sequence, sphere_binding)
            if sphere_actor is None or sphere_loc is None or sphere_rot is None:
                _log_error(f"Could not sample recorder_sphere at frame {frame}. Aborting untouched.")
                return ""
            attempts = []
            socket_transform, route, _component = diag._sample_root_world(
                sequence, context, sphere_actor, root_bone_name, attempts
            )
            root_loc, _root_rot = diag._transform_loc_rot(socket_transform)
            if root_loc is None:
                _log_error(f"Could not sample root at frame {frame} (route={route}). Aborting untouched.")
                for line in attempts:
                    _log(f"  attempt: {line}")
                return ""
            live_distance = _location_error(sphere_loc, root_loc)
            worst_live = max(worst_live, live_distance)
            if live_distance > float(location_tolerance):
                _log_error(
                    f"LIVE sphere-vs-root distance {live_distance:.4f} exceeds tolerance at frame {frame}. "
                    "Aborting before writing anything."
                )
                return ""
            samples.append((frame, _values_from_parts(sphere_loc, sphere_rot, sphere_scale)))
        _log(f"PASS 1 done. max live sphere-vs-root distance={worst_live:.6f}")
        _log(f"first sample: {samples[0]}")
        _log(f"last sample:  {samples[-1]}")

        _log(f"Writing transform keys for {len(samples)} frames (location+rotation+scale)...")
        write_error = attach_base._write_transform_keys(
            sphere_binding, samples, start_frame, end_frame, write_scale_keys=True
        )
        if write_error:
            _log_error(f"Key writing failed: {write_error}")
            cleanup = _remove_transform_tracks(sphere_binding)
            _log(f"Cleanup of partial transform track: {cleanup}")
            return ""
        for line in diag._transform_track_summary(sphere_binding):
            _log(line)

        _log("Deactivating attach section(s) (reversible; rollback() restores them)...")
        changed = diag._set_attach_active(sphere_binding, False)
        if not changed:
            _log_error("Could not deactivate any attach section. Removing baked track and aborting.")
            cleanup = _remove_transform_tracks(sphere_binding)
            _log(f"Cleanup: {cleanup}")
            return ""
        _safe_call(library, "refresh_current_level_sequence")
        diag._set_time_and_report(start_frame)

        _log("COMMAND A done. Keys written, attach section INACTIVE.")
        _log("NOW: let the editor tick, scrub the timeline by hand, look at the sphere,")
        _log("then run validate_settled() as a SEPARATE command. Run rollback() to restore live-attach.")
        _log("================ COMMAND A: bake_and_detach end ================")
        return "true"
    except Exception:
        _log_error(traceback.format_exc())
        return ""


# ---------------------------------------------------------------------------
# COMMAND B - settled-state validation (read-only)
# ---------------------------------------------------------------------------

def validate_settled(
    bp_actor_name="",
    skeletal_mesh_name="",
    global_ctrl_name="global_ctrl",
    root_bone_name="root",
    sphere_name="recorder_sphere",
    prefer_selected_global_ctrl_sequence=True,
    location_tolerance=0.1,
    rotation_tolerance_degrees=0.1,
    probe_frames=None,
    max_failure_rows_logged=15,
    rollback_on_failure=False,
):
    try:
        _reload_dependencies()
        _log("================ COMMAND B: validate_settled start ================")
        _log("Read-only. Run this in a separate call AFTER the editor has ticked/scrubbed since Command A.")

        context, sphere_binding, error = _resolve_common(
            bp_actor_name, skeletal_mesh_name, global_ctrl_name, prefer_selected_global_ctrl_sequence, sphere_name
        )
        if error:
            _log_error(error)
            return ""
        sequence = context["sequence"]
        start_frame = int(context["start_frame"])
        end_frame = int(context["end_frame"])
        library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
        original_time = _safe_call(library, "get_current_time")

        # Requirement: attach sections must be INACTIVE.
        attach_pairs = diag._attach_sections(sphere_binding)
        attach_states = [bool(_safe_call(section, "is_active")) for _t, section in attach_pairs]
        _log(f"attach sections: {len(attach_pairs)} active_states={attach_states}")
        if any(attach_states):
            _log_error("Attach section(s) still ACTIVE - this is not the keys-only state. Aborting validation.")
            return ""

        keyed_by_frame, keyed_error = _keyed_values_by_frame(sphere_binding)
        if keyed_error:
            _log_error(f"Could not read baked keys: {keyed_error}")
            return ""
        _log(f"keyed frames read back from channels: {len(keyed_by_frame)}")

        # Frame wiggle: force real re-evaluations before trusting any sample.
        _log("frame wiggle: end -> start -> refresh, to force fresh evaluation...")
        diag._set_time_and_report(end_frame - 1)
        diag._set_time_and_report(start_frame)
        _safe_call(library, "refresh_current_level_sequence")

        if probe_frames is None:
            probe_frames = _default_probe_frames(start_frame, end_frame)
        probe_set = set(int(f) for f in probe_frames)
        _log(f"probe frames (detailed rows): {sorted(probe_set)}")

        frames = list(range(start_frame, end_frame))
        max_eval_vs_root_loc = 0.0
        max_eval_vs_root_rot = 0.0
        max_eval_vs_keyed_loc = 0.0
        max_eval_vs_keyed_rot = 0.0
        max_keyed_vs_root_loc = 0.0
        still_attached_frames = []
        failures = []

        for frame in frames:
            diag._set_time_and_report(frame)
            sphere_actor, sphere_loc, sphere_rot, _sphere_scale = _sample_sphere_world(sequence, sphere_binding)

            sphere_root = diag._get_root_component(sphere_actor) if sphere_actor else None
            attach_parent = _safe_call(sphere_root, "get_attach_parent")
            attach_socket = _safe_call(sphere_root, "get_attach_socket_name")
            if attach_parent is not None:
                still_attached_frames.append(frame)

            attempts = []
            socket_transform, route, _component = diag._sample_root_world(
                sequence, context, sphere_actor, root_bone_name, attempts
            )
            root_loc, root_rot = diag._transform_loc_rot(socket_transform)

            keyed_loc, keyed_rot = _keyed_loc_rot(keyed_by_frame.get(frame))

            eval_vs_root_loc = _location_error(sphere_loc, root_loc)
            eval_vs_root_rot = _rotation_error_degrees(sphere_rot, root_rot)
            eval_vs_keyed_loc = _location_error(sphere_loc, keyed_loc)
            eval_vs_keyed_rot = _rotation_error_degrees(sphere_rot, keyed_rot)
            keyed_vs_root_loc = _location_error(keyed_loc, root_loc)

            for value, bucket in (
                (eval_vs_root_loc, "evr_loc"), (eval_vs_root_rot, "evr_rot"),
                (eval_vs_keyed_loc, "evk_loc"), (eval_vs_keyed_rot, "evk_rot"),
                (keyed_vs_root_loc, "kvr_loc"),
            ):
                if value is None:
                    continue
                if bucket == "evr_loc":
                    max_eval_vs_root_loc = max(max_eval_vs_root_loc, value)
                elif bucket == "evr_rot":
                    max_eval_vs_root_rot = max(max_eval_vs_root_rot, value)
                elif bucket == "evk_loc":
                    max_eval_vs_keyed_loc = max(max_eval_vs_keyed_loc, value)
                elif bucket == "evk_rot":
                    max_eval_vs_keyed_rot = max(max_eval_vs_keyed_rot, value)
                elif bucket == "kvr_loc":
                    max_keyed_vs_root_loc = max(max_keyed_vs_root_loc, value)

            failed = (
                eval_vs_root_loc is None or eval_vs_root_rot is None
                or eval_vs_root_loc > float(location_tolerance)
                or eval_vs_root_rot > float(rotation_tolerance_degrees)
                or attach_parent is not None
            )
            if failed:
                failures.append((frame, eval_vs_root_loc, eval_vs_root_rot, attach_parent is not None))

            if frame in probe_set or (failed and len(failures) <= int(max_failure_rows_logged)):
                label = "PROBE" if frame in probe_set else "FAIL"
                relative_loc = _safe_get_editor_property(sphere_root, "relative_location")
                relative_rot = _safe_get_editor_property(sphere_root, "relative_rotation")
                _log(f"[{label}] frame={frame}")
                _log(f"[{label}]   attach sections active={attach_states} "
                     f"get_attach_parent()={diag._describe_component(attach_parent)} socket={attach_socket}")
                _log(f"[{label}]   sphere world  loc={diag._fmt_vec(sphere_loc)} rot={diag._fmt_rot(sphere_rot)}")
                _log(f"[{label}]   sphere relative loc={diag._fmt_vec(relative_loc)} rot={diag._fmt_rot(relative_rot)}")
                _log(f"[{label}]   keyed values  loc={diag._fmt_vec(keyed_loc)} rot={diag._fmt_rot(keyed_rot)}")
                _log(f"[{label}]   root world    via {route} loc={diag._fmt_vec(root_loc)} rot={diag._fmt_rot(root_rot)}")
                _log(f"[{label}]   eval-vs-root: loc={_fmt_err(eval_vs_root_loc)} rot={_fmt_err(eval_vs_root_rot)}deg | "
                     f"eval-vs-keyed: loc={_fmt_err(eval_vs_keyed_loc)} rot={_fmt_err(eval_vs_keyed_rot)}deg | "
                     f"keyed-vs-root loc={_fmt_err(keyed_vs_root_loc)}")
                if root_loc is None:
                    for line in attempts:
                        _log(f"[{label}]     root attempt: {line}")

        _log("---------------- settled validation report ----------------")
        _log(f"frames validated: {len(frames)} ({start_frame}..{end_frame - 1})")
        _log(f"still-attached frames: {len(still_attached_frames)} {still_attached_frames[:10]}")
        _log(f"max evaluated-vs-root:  loc={max_eval_vs_root_loc:.6f} rot={max_eval_vs_root_rot:.6f}deg "
             f"(tolerances {location_tolerance} / {rotation_tolerance_degrees})")
        _log(f"max evaluated-vs-keyed: loc={max_eval_vs_keyed_loc:.6f} rot={max_eval_vs_keyed_rot:.6f}deg")
        _log(f"max keyed-vs-root:      loc={max_keyed_vs_root_loc:.6f}")
        if failures:
            _log(f"first failing frame: {failures[0][0]} (total failing frames: {len(failures)})")
        else:
            _log("first failing frame: <none>")

        # Diagnosis hints.
        if still_attached_frames:
            _log_warning(
                "Sphere root component is STILL ATTACHED on some frames - the attach deactivation has not "
                "physically released yet. Scrub/tick more (or reopen the sequence) and re-run validate_settled()."
            )
        elif failures and max_eval_vs_keyed_loc > float(location_tolerance) and max_keyed_vs_root_loc <= float(location_tolerance):
            _log_warning(
                "DIAGNOSIS: keys match root (samples were correct) but the EVALUATED sphere does not match its "
                "own keys -> Sequencer is applying the keyed values in a different space than world "
                "(space/transform-origin problem), not a sampling problem."
            )
        elif failures and max_keyed_vs_root_loc > float(location_tolerance):
            _log_warning(
                "DIAGNOSIS: the keyed values themselves do not match freshly sampled root -> the PASS 1 samples "
                "were wrong or root evaluation differs between runs."
            )

        if failures:
            _log_warning("SETTLED VALIDATION FAILED. The bake is NOT correct.")
            if rollback_on_failure:
                _rollback_internal(sphere_binding, library, start_frame)
            else:
                _log("State left as-is for inspection. Run rollback() to restore the live-attach state.")
            result = ""
        else:
            _log("SETTLED VALIDATION PASSED numerically.")
            _log("Final gate is yours: scrub the timeline by hand and confirm the sphere stays on the root path.")
            result = "true"

        if original_time is not None:
            try:
                library.set_current_time(int(original_time))
            except Exception:
                pass
        _log("================ COMMAND B: validate_settled end ================")
        return result
    except Exception:
        _log_error(traceback.format_exc())
        return ""


# ---------------------------------------------------------------------------
# COMMAND R - rollback to known-good live-attach state
# ---------------------------------------------------------------------------

def _rollback_internal(sphere_binding, library, start_frame):
    cleanup = _remove_transform_tracks(sphere_binding)
    _log(f"Removed transform track(s) on recorder_sphere: {cleanup}")
    reactivated = diag._set_attach_active(sphere_binding, True)
    _log(f"Reactivated {len(reactivated)} attach section(s).")
    _safe_call(library, "refresh_current_level_sequence")
    diag._set_time_and_report(start_frame)
    _log("Rollback done: keys removed FIRST, then attach reactivated (order matters - "
         "world keys under a live attach would double-transform).")


def rollback(
    bp_actor_name="",
    skeletal_mesh_name="",
    global_ctrl_name="global_ctrl",
    sphere_name="recorder_sphere",
    prefer_selected_global_ctrl_sequence=True,
):
    try:
        _reload_dependencies()
        _log("================ COMMAND R: rollback start ================")
        context, sphere_binding, error = _resolve_common(
            bp_actor_name, "", global_ctrl_name, prefer_selected_global_ctrl_sequence, sphere_name
        )
        if error:
            _log_error(error)
            return ""
        library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
        _rollback_internal(sphere_binding, library, int(context["start_frame"]))
        _log("Expected state now: live-attached recorder_sphere, no transform keys, "
             "global_ctrl and Blueprint Actor untouched. Scrub to confirm the sphere follows root again.")
        _log("================ COMMAND R: rollback end ================")
        return "true"
    except Exception:
        _log_error(traceback.format_exc())
        return ""


def run(**kwargs):
    """Deprecated single-call flow. Kept so old buttons don't break; now only bakes+detaches."""
    _log_warning("run() is deprecated: it now only performs Command A (bake_and_detach). "
                 "Run validate_settled() separately after the editor has ticked.")
    kwargs.pop("location_tolerance", None)
    kwargs.pop("rotation_tolerance_degrees", None)
    kwargs.pop("max_failure_rows_logged", None)
    return bake_and_detach(**kwargs)


def reload_and_run(**kwargs):
    return run(**kwargs)
