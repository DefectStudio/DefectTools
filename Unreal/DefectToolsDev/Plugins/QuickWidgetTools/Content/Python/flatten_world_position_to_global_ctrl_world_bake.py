"""
Flatten Blueprint Actor motion onto global_ctrl using Control Rig world-transform APIs.

Goal: keep the final evaluated world-space animation identical, but move ALL changing
motion onto the Control Rig control (global_ctrl). Afterwards the Blueprint Actor
holds its original frame-1001 transform and global_ctrl carries the combined motion.

Core design decisions:
- The world <-> control-local solve is delegated to Unreal's supported API:
      ControlRigSequencerLibrary.get_control_rig_world_transforms(...)
      ControlRigSequencerLibrary.set_control_rig_world_transforms(...)
  These evaluate the open sequence per frame and convert through the component
  transform, rig space and control parent hierarchy. No hand-rolled Euler math.
- ORDER MATTERS: capture original global_ctrl world transforms FIRST (with the old
  actor animation still live), then flatten the actor, then solve global_ctrl to the
  captured world path. The solve therefore compensates against the new static actor.
- Phases run as SEPARATE editor calls because Sequencer's compiled evaluation graph
  is not rebuilt inside one synchronous Python call (proven earlier in this project
  by a false-positive same-call validation).

PRODUCTION (selection-driven, no hard-coded names anywhere):

Works in any focused ANM/subsequence with any Blueprint character + compatible
Control Rig. Before pressing a widget button, the artist selects in Sequencer:
  1. exactly one Blueprint Actor binding,
  2. exactly one of its child Skeletal Mesh Component bindings,
  3. (optionally) the Control Rig control's channels - the control name is read
     from the selected channels when possible, otherwise from the widget's
     global_ctrl_name string input (default "global_ctrl").

Everything else - focused sequence + playback range, runtime actor (via bound
objects, spawnable/possessable-safe), skeletal component, the Control Rig track
associated with the selected actor hierarchy - is resolved from that.

Sidecars are unique per sequence+actor+control (context hash in the filename,
stored in Saved/QuickWidgetTools/) and record the sequence asset path, binding
GUID, component name, rig class, control name, playback range, and timestamps.
Selection is only needed for diagnose/capture; all later phases re-resolve from
the sidecar for the FOCUSED sequence by GUID.

Phases (each must run as its OWN editor call - never chain destructive phases
in one call; Sequencer's evaluation graph must rebuild between them):

    diagnose()               read-only preflight; resolves everything, probes APIs
    capture_original()       reference capture + rollback snapshots + backup asset
    bake_flattened()         DESTRUCTIVE: flatten actor, bake control world path
    validate_settled()       read-only settled validation (integer + half frames)
    rebase_origin()          DESTRUCTIVE: move frame-1 ctrl offset onto static actor
    validate_rebase_settled() read-only settled validation of the rebase
    rollback() / rollback_rebase_origin()  restore snapshots
    run_next_safe_step()     Option B: advances exactly ONE phase per call based
                             on sidecar + live channel state ("status" previews it)
    save_sequence()          save the sequence asset to disk

Widget button script (identical for every button except the phase name):

    import importlib
    import flatten_world_position_to_global_ctrl_world_bake as flatten_tool
    importlib.invalidate_caches()
    importlib.reload(flatten_tool)
    flatten_tool.run(phase="next", global_ctrl_name="global_ctrl")

Scale: loc/rot only are flattened. Actor scale channels are never cleared or
written; control scale is validated unchanged. Non-unit scales are logged
because they affect conversion.
"""

import hashlib
import importlib
import json
import math
import os
import re
import time as _time
import traceback

import unreal

import flatten_world_position_to_global_ctrl as base
import flatten_world_position_to_global_ctrl_attach_snap_method as attach_base
import flatten_world_position_to_global_ctrl_attach_snap_bake_diagnostic as diag


LOG_PREFIX = "[FlattenGlobalCtrlWorldBake]"
# Legacy single-slot sidecar filenames (pre-production versions). Read once and migrated.
LEGACY_CAPTURE_FILE = "flatten_global_ctrl_capture.json"
LEGACY_REBASE_FILE = "flatten_global_ctrl_rebase_capture.json"

LOCATION_KEYS = ("location_x", "location_y", "location_z")
ROTATION_KEYS = ("rotation_x", "rotation_y", "rotation_z")
SCALE_KEYS = ("scale_x", "scale_y", "scale_z")
FLATTEN_KEYS = LOCATION_KEYS + ROTATION_KEYS


def _log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


# Unmistakable proof that THIS module was imported/reloaded and from which file.
try:
    unreal.log(f"{LOG_PREFIX} MODULE LOADED FROM: {__file__}")
except Exception:
    pass


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
    global base, attach_base, diag
    base = importlib.reload(base)
    attach_base = importlib.reload(attach_base)
    diag = importlib.reload(diag)


# ---------------------------------------------------------------------------
# Capture sidecar
# ---------------------------------------------------------------------------

def _sidecar_dir():
    saved_dir = str(_safe_call(unreal.Paths, "project_saved_dir") or "")
    path = os.path.join(saved_dir, "QuickWidgetTools")
    os.makedirs(path, exist_ok=True)
    return path


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1)
    _log(f"sidecar written: {path}")
    return path


def _context_hash(sequence_path, actor_guid, control_name):
    text = f"{sequence_path}|{actor_guid}|{control_name}".encode("utf-8")
    return hashlib.md5(text).hexdigest()[:12]


def _capture_path_for(data):
    digest = _context_hash(data["sequence_asset_path"], data["actor_binding_guid"], data["control_name"])
    return os.path.join(_sidecar_dir(), f"flatten_ctrl_capture_{digest}.json")


def _rebase_path_for(data):
    digest = _context_hash(data["sequence_asset_path"], data["actor_binding_guid"], data["control_name"])
    return os.path.join(_sidecar_dir(), f"flatten_ctrl_rebase_{digest}.json")


def _write_capture(data):
    return _write_json(_capture_path_for(data), data)


def _write_rebase_capture(data):
    return _write_json(_rebase_path_for(data), data)


def _focused_sequence_path():
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    sequence = _safe_call(library, "get_focused_level_sequence") or _safe_call(library, "get_current_level_sequence")
    return str(_safe_call(sequence, "get_path_name") or "")


def _load_json_file(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def _read_capture():
    """Find the capture sidecar for the FOCUSED sequence. Sidecars are unique per
    sequence+actor+control (context hash in the filename); legacy single-slot files
    are migrated on first read."""
    sequence_path = _focused_sequence_path()
    if not sequence_path:
        return None, "no sequence focused/open in Sequencer."
    directory = _sidecar_dir()
    candidates = []
    for name in sorted(os.listdir(directory)):
        is_new = name.startswith("flatten_ctrl_capture_") and name.endswith(".json")
        if not is_new and name != LEGACY_CAPTURE_FILE:
            continue
        path = os.path.join(directory, name)
        data = _load_json_file(path)
        if data is not None and data.get("sequence_asset_path") == sequence_path:
            candidates.append((path, data))
    if not candidates:
        return None, (
            f"no capture sidecar found for focused sequence {sequence_path}. "
            "Run Diagnose + Capture first (with the Blueprint Actor and Skeletal Mesh bindings selected)."
        )
    if len(candidates) > 1:
        selected_guids = {_binding_guid_text(binding) for binding in attach_base._get_selected_bindings()}
        matching = [(p, d) for p, d in candidates if d.get("actor_binding_guid") in selected_guids]
        if len(matching) == 1:
            candidates = matching
        else:
            candidates.sort(key=lambda item: str(item[1].get("captured_at", "")))
            _log_warning(f"{len(candidates)} capture sidecars match this sequence; using newest: {candidates[-1][0]}")
            candidates = [candidates[-1]]
    path, data = candidates[0]
    if os.path.basename(path) == LEGACY_CAPTURE_FILE:
        new_path = _write_capture(data)
        try:
            os.remove(path)
        except Exception:
            pass
        _log(f"migrated legacy capture sidecar to {new_path}")
    else:
        _log(f"using capture sidecar: {path}")
    return data, ""


def _read_rebase_capture():
    capture, error = _read_capture()
    if capture is None:
        return None, error
    path = _rebase_path_for(capture)
    if os.path.isfile(path):
        data = _load_json_file(path)
        if data is not None:
            return data, ""
    legacy = os.path.join(_sidecar_dir(), LEGACY_REBASE_FILE)
    if os.path.isfile(legacy):
        data = _load_json_file(legacy)
        if data is not None and data.get("sequence_asset_path") == capture.get("sequence_asset_path"):
            # A legacy sidecar is NOT proof a rebase is applied to the live sequence.
            # Keep reference data, clear all success state - it must be re-proven.
            for stale_key in ("rebased", "rebased_at", "rebase_validated_at", "rebase_id", "for_baked_at"):
                data.pop(stale_key, None)
            data["rebased"] = False
            data["migration_note"] = "legacy migration: applied/validated flags cleared; must be re-proven against live sequence"
            new_path = _write_rebase_capture(data)
            try:
                os.remove(legacy)
            except Exception:
                pass
            _log_warning(f"migrated legacy rebase sidecar to {new_path} with applied/validated state CLEARED.")
            return data, ""
    return None, f"rebase sidecar not found: {path}. Run rebase_origin() first."


# ---------------------------------------------------------------------------
# Math / transform helpers
# ---------------------------------------------------------------------------

def _rotation_error_degrees(rot_a, rot_b):
    """Quaternion angular distance in degrees; wrap-safe component fallback."""
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
    worst = 0.0
    for attr in ("roll", "pitch", "yaw"):
        delta = float(getattr(rot_a, attr)) - float(getattr(rot_b, attr))
        worst = max(worst, abs((delta + 180.0) % 360.0 - 180.0))
    return worst


def _location_error(loc_a, loc_b):
    if loc_a is None or loc_b is None:
        return None
    diff = unreal.Vector(loc_a.x - loc_b.x, loc_a.y - loc_b.y, loc_a.z - loc_b.z)
    return float(diff.length())


def _transform_quat(transform):
    """The transform's rotation as a Quat, read directly (no rotator round-trip)."""
    quat = _safe_get_editor_property(transform, "rotation")
    if quat is not None and _safe_get_editor_property(quat, "w") is not None:
        return quat
    _location, rotation, _scale = diag._transform_parts(transform)
    return _safe_call(rotation, "quaternion")


def _make_quat(x, y, z, w):
    # UE 5.8 probe-verified: the Quat(x=,y=,z=,w=) keyword constructor truncates
    # components to float32 (~0.01-0.03deg angular error); set_editor_property
    # keeps full double precision. Property route first, constructor as fallback.
    quat = unreal.Quat()
    try:
        for name, value in (("x", x), ("y", y), ("z", z), ("w", w)):
            quat.set_editor_property(name, float(value))
        return quat
    except Exception:
        pass
    try:
        return unreal.Quat(x=float(x), y=float(y), z=float(z), w=float(w))
    except Exception:
        return quat


def _quat_error_degrees(quat_a, quat_b):
    if quat_a is None or quat_b is None:
        return None
    radians = _safe_call(quat_a, "angular_distance", quat_b)
    if radians is None:
        return None
    try:
        return abs(math.degrees(float(radians)))
    except Exception:
        return None


def _transform_record(transform):
    """Serialize a Transform to JSON-safe loc/quat/scale lists.

    Rotation is stored as a QUATERNION read straight off the transform, because
    rotator decomposition proved suspect (roll==yaw pattern in diagnose probes).
    The rotator is kept alongside for human-readable logging only.
    """
    location, rotation, scale = diag._transform_parts(transform)
    quat = _transform_quat(transform)
    if location is None or quat is None:
        return None
    return {
        "loc": [float(location.x), float(location.y), float(location.z)],
        "quat": [float(quat.x), float(quat.y), float(quat.z), float(quat.w)],
        "rot": [float(rotation.roll), float(rotation.pitch), float(rotation.yaw)] if rotation is not None else [0.0, 0.0, 0.0],
        "scale": [float(scale.x), float(scale.y), float(scale.z)] if scale is not None else [1.0, 1.0, 1.0],
    }


def _record_loc(record):
    return unreal.Vector(*record["loc"]) if record else None


def _record_quat(record):
    if not record:
        return None
    quat_values = record.get("quat")
    if quat_values:
        return _make_quat(*quat_values)
    rotator = unreal.Rotator(roll=record["rot"][0], pitch=record["rot"][1], yaw=record["rot"][2])
    return _safe_call(rotator, "quaternion")


def _record_to_transform(record):
    location = _record_loc(record)
    quat = _record_quat(record)
    scale = unreal.Vector(*record.get("scale", [1.0, 1.0, 1.0]))
    for kwargs in (
        {"translation": location, "rotation": quat, "scale3d": scale},
        {"location": location, "rotation": quat, "scale": scale},
    ):
        try:
            return unreal.Transform(**kwargs)
        except Exception:
            pass
    transform = unreal.Transform()
    for name, value in (("translation", location), ("rotation", quat), ("scale3d", scale)):
        try:
            transform.set_editor_property(name, value)
        except Exception:
            pass
    return transform


def _record_roundtrip_error(record, source_transform):
    """Rebuild the record's transform and compare against the live source transform."""
    rebuilt = _record_to_transform(record)
    rebuilt_loc, _rot, _scale = diag._transform_parts(rebuilt)
    source_loc, _rot2, _scale2 = diag._transform_parts(source_transform)
    loc_error = _location_error(rebuilt_loc, source_loc)
    rot_error = _quat_error_degrees(_transform_quat(rebuilt), _transform_quat(source_transform))
    return loc_error, rot_error


def _fmt_record(record):
    if not record:
        return "<none>"
    return (
        f"loc=({record['loc'][0]:.4f}, {record['loc'][1]:.4f}, {record['loc'][2]:.4f}) "
        f"rot=(roll={record['rot'][0]:.4f}, pitch={record['rot'][1]:.4f}, yaw={record['rot'][2]:.4f})"
    )


# ---------------------------------------------------------------------------
# Sequence / binding / control rig resolution
# ---------------------------------------------------------------------------

def _sequence_frame_range(sequence):
    start_frame, end_frame = attach_base._get_sequence_frame_range(sequence)
    return int(start_frame), int(end_frame)


def _require_sequence_open(sequence):
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    focused = _safe_call(library, "get_focused_level_sequence")
    current = _safe_call(library, "get_current_level_sequence")
    target = str(_safe_call(sequence, "get_path_name"))
    names = {str(_safe_call(focused, "get_path_name")), str(_safe_call(current, "get_path_name"))}
    if target not in names:
        return False, (
            f"target sequence {target} is not the open/focused Sequencer sequence "
            f"(focused={_safe_call(focused, 'get_name')} current={_safe_call(current, 'get_name')}). "
            "Open the shot and focus the ANM subsequence, then re-run."
        )
    return True, ""


def _binding_guid_text(binding):
    """Canonical GUID string. str(guid) is just a repr with a memory address
    (probe-verified: '<Struct Guid (0x...) {}>'), so convert properly."""
    guid = _safe_call(binding, "get_id")
    if guid is None:
        return ""
    text = _safe_call(getattr(unreal, "GuidLibrary", None), "conv_guid_to_string", guid)
    if text:
        return str(text).upper()
    text = _safe_call(guid, "to_string")
    if text:
        return str(text).upper()
    return str(guid)


def _find_binding_by_guid(sequence, guid_text):
    target = str(guid_text).upper()
    for binding in attach_base._iter_all_bindings(sequence):
        if _binding_guid_text(binding) == target:
            return binding
    return None


def _crl():
    return getattr(unreal, "ControlRigSequencerLibrary", None)


def _time_unit(member_name):
    for enum_name in ("MovieSceneTimeUnit", "SequenceTimeUnit"):
        enum_type = getattr(unreal, enum_name, None)
        value = getattr(enum_type, member_name, None) if enum_type else None
        if value is not None:
            return value
    return None


def _control_rig_proxies(sequence, attempts):
    library = _crl()
    if library is None:
        attempts.append("unreal.ControlRigSequencerLibrary is MISSING")
        return []
    proxies = _as_list(_safe_call(library, "get_control_rigs", sequence))
    attempts.append(f"get_control_rigs -> {len(proxies)} proxies")
    return proxies


def _control_names(control_rig, attempts):
    hierarchy = _safe_call(control_rig, "get_hierarchy")
    keys = _as_list(_safe_call(hierarchy, "get_controls"))
    if keys:
        attempts.append(f"hierarchy.get_controls -> {len(keys)}")
    else:
        all_keys = _as_list(_safe_call(hierarchy, "get_all_keys", True))
        control_type = getattr(getattr(unreal, "RigElementType", None), "CONTROL", None)
        keys = [k for k in all_keys if control_type is None or _safe_get_editor_property(k, "type") == control_type]
        attempts.append(f"hierarchy.get_all_keys fallback -> {len(keys)} (of {len(all_keys)})")
    names = []
    for key in keys:
        name = _safe_get_editor_property(key, "name") or _safe_call(key, "get_name")
        if name:
            names.append(str(name))
    return names


def _find_control_rig(sequence, control_name, preferred_track_paths=None, rig_class_hint=""):
    """Find the Control Rig that owns `control_name`. No hard-coded rig names:
    primary filter is control containment; ties are broken by whether the rig's
    parameter track lives under the selected actor binding hierarchy, then by an
    optional class hint (only used when re-resolving from a capture sidecar).
    Returns (control_rig, track, attempts, error)."""
    attempts = []
    matches = []
    for proxy in _control_rig_proxies(sequence, attempts):
        control_rig = _safe_get_editor_property(proxy, "control_rig")
        track = _safe_get_editor_property(proxy, "track")
        rig_class = _class_name(control_rig)
        names = _control_names(control_rig, attempts)
        has_control = control_name in names
        track_path = str(_safe_call(track, "get_path_name") or "")
        under_selection = bool(preferred_track_paths and track_path in preferred_track_paths)
        attempts.append(
            f"rig={rig_class} controls={len(names)} has_{control_name}={has_control} "
            f"track_under_selected_actor={under_selection}"
        )
        if has_control:
            matches.append((under_selection, control_rig, track, rig_class))
    if not matches:
        return None, None, attempts, f"No Control Rig in this sequence has a control named {control_name!r}."
    pool = [m for m in matches if m[0]] or matches
    hint = str(rig_class_hint or "").lower()
    if hint:
        hinted = [m for m in pool if hint in m[3].lower()]
        pool = hinted or pool
    if len(pool) > 1:
        attempts.append(f"{len(pool)} candidate rigs remain; using first: {[m[3] for m in pool]}")
    _under, control_rig, track, _rig_class = pool[0]
    return control_rig, track, attempts, ""


def _control_channels_from_section(section, control_name):
    """Transform channels for any control name. Strict prefix match first
    (control.Location.X style) so e.g. 'global_ctrl' cannot swallow channels of
    'global_ctrl_offset'; loose contains-match only as fallback."""
    strict = {key: [] for key in base.TRANSFORM_KEYS}
    loose = {key: [] for key in base.TRANSFORM_KEYS}
    target = base._normalize_name(control_name)
    for channel in base._get_section_channels(section):
        channel_name = base._get_channel_name(channel)
        transform_key = base._classify_transform_channel(channel_name)
        if not transform_key:
            continue
        normalized = base._normalize_name(channel_name)
        group = transform_key.rsplit("_", 1)[0]
        if normalized.startswith(f"{target}_{group}"):
            strict[transform_key].append(channel)
        elif target in normalized:
            loose[transform_key].append(channel)
    if any(strict[key] for key in base.TRANSFORM_KEYS):
        return strict
    return loose


def _control_bundle(track, control_name):
    sections = _as_list(_safe_call(track, "get_sections"))
    if not sections:
        return None, "Control Rig track has no sections."
    if len(sections) > 1:
        _log_warning(f"Control Rig track has {len(sections)} sections; using the first.")
    bundle = _control_channels_from_section(sections[0], control_name)
    missing = [key for key in FLATTEN_KEYS if not bundle.get(key)]
    if missing:
        return None, f"Control Rig section is missing {control_name} channels: {missing}"
    return bundle, ""


def _bundle_key_counts(bundle):
    counts = {}
    for key in base.TRANSFORM_KEYS:
        channel = base._first_channel(bundle, key)
        counts[key] = base._count_channel_keys(channel) if channel is not None else None
    return counts


def _snapshot_bundle_for_json(bundle, keys):
    snapshot = {}
    for key in keys:
        channel = base._first_channel(bundle, key)
        if channel is None:
            snapshot[key] = None
            continue
        key_values, default_value = base._snapshot_channel(channel)
        snapshot[key] = {
            "default": float(default_value) if default_value is not None else None,
            "keys": [[int(frame), float(value)] for frame, value in key_values],
        }
    return snapshot


# ---------------------------------------------------------------------------
# Control Rig world transform API wrappers (introspective, multi-signature)
# ---------------------------------------------------------------------------

def _log_api_availability():
    library = _crl()
    for fn_name in (
        "get_control_rig_world_transform", "get_control_rig_world_transforms",
        "set_control_rig_world_transform", "set_control_rig_world_transforms",
    ):
        fn = getattr(library, fn_name, None) if library else None
        if fn is None:
            _log_warning(f"API MISSING: ControlRigSequencerLibrary.{fn_name}")
        else:
            doc = (getattr(fn, "__doc__", "") or "").strip().splitlines()
            _log(f"API OK: {fn_name} :: {doc[0] if doc else '<no doc>'}")


def _frame_numbers(values):
    return [unreal.FrameNumber(int(v)) for v in values]


def _get_world_transforms(sequence, control_rig, control_name, frame_values, time_unit_member):
    """Returns (list[Transform] or None, attempts)."""
    library = _crl()
    attempts = []
    name = unreal.Name(control_name)
    frames = _frame_numbers(frame_values)
    unit = _time_unit(time_unit_member)
    plural = getattr(library, "get_control_rig_world_transforms", None) if library else None
    if plural is not None:
        variants = []
        if unit is not None:
            variants.append((sequence, control_rig, name, frames, unit))
        variants.append((sequence, control_rig, name, frames))
        for args in variants:
            try:
                result = _as_list(plural(*args))
                attempts.append(f"get_..._transforms({len(args)} args, {time_unit_member}) -> {len(result)} transforms")
                if len(result) == len(frames):
                    return result, attempts
            except Exception as exc:
                attempts.append(f"get_..._transforms({len(args)} args) -> EXCEPTION {exc}")
    singular = getattr(library, "get_control_rig_world_transform", None) if library else None
    if singular is not None:
        output = []
        for frame in frames:
            transform = None
            for args in ((sequence, control_rig, name, frame, unit), (sequence, control_rig, name, frame)):
                if unit is None and len(args) == 5:
                    continue
                try:
                    transform = singular(*args)
                    break
                except Exception as exc:
                    attempts.append(f"get_..._transform(frame={frame}) -> EXCEPTION {exc}")
            if transform is None:
                return None, attempts
            output.append(transform)
        attempts.append(f"singular fallback -> {len(output)} transforms")
        return output, attempts
    attempts.append("no get_control_rig_world_transform(s) API available")
    return None, attempts


def _set_world_transforms(sequence, control_rig, control_name, frame_values, transforms, time_unit_member):
    library = _crl()
    attempts = []
    name = unreal.Name(control_name)
    frames = _frame_numbers(frame_values)
    unit = _time_unit(time_unit_member)
    plural = getattr(library, "set_control_rig_world_transforms", None) if library else None
    if plural is not None:
        variants = []
        if unit is not None:
            variants.append((sequence, control_rig, name, frames, transforms, unit))
        variants.append((sequence, control_rig, name, frames, transforms))
        for args in variants:
            try:
                plural(*args)
                attempts.append(f"set_..._transforms({len(args)} args, {time_unit_member}) -> OK")
                return True, attempts
            except Exception as exc:
                attempts.append(f"set_..._transforms({len(args)} args) -> EXCEPTION {exc}")
    singular = getattr(library, "set_control_rig_world_transform", None) if library else None
    if singular is not None:
        wrote = 0
        for frame, transform in zip(frames, transforms):
            done = False
            for args in (
                (sequence, control_rig, name, frame, transform, unit, True),
                (sequence, control_rig, name, frame, transform, unit),
                (sequence, control_rig, name, frame, transform, True),
                (sequence, control_rig, name, frame, transform),
            ):
                if unit is None and len(args) >= 6 and args[5] is unit:
                    continue
                try:
                    singular(*args)
                    done = True
                    break
                except Exception as exc:
                    attempts.append(f"set_..._transform(frame={frame}) -> EXCEPTION {exc}")
            if not done:
                attempts.append(f"singular set failed at frame {frame} after {wrote} writes")
                return False, attempts
            wrote += 1
        attempts.append(f"singular fallback wrote {wrote} frames")
        return True, attempts
    attempts.append("no set_control_rig_world_transform(s) API available")
    return False, attempts


def _ticks_per_frame(sequence):
    tick = _safe_call(sequence, "get_tick_resolution")
    display = _safe_call(sequence, "get_display_rate")
    try:
        value = (float(tick.numerator) * float(display.denominator)) / (float(tick.denominator) * float(display.numerator))
        if abs(value - round(value)) < 1e-6:
            return int(round(value))
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Actor sampling / editing
# ---------------------------------------------------------------------------

def _actor_world_record_at_current_time(sequence, actor_binding):
    objects, _attempts = attach_base._resolve_bound_objects(sequence, actor_binding)
    for obj in objects:
        transform = _safe_call(obj, "get_actor_transform")
        record = _transform_record(transform)
        if record is not None:
            return record
    return None


def _flatten_actor_channels(actor_bundle, start_frame, base_values):
    for key in FLATTEN_KEYS:
        channel = base._first_channel(actor_bundle, key)
        if channel is None:
            return f"actor channel missing for {key}"
        if not base._remove_all_keys(channel):
            return f"could not remove all actor keys for {key}"
        base._set_channel_default(channel, base_values[key])
        if not base._add_channel_key(channel, start_frame, base_values[key]):
            return f"could not key actor base value for {key}"
    return ""


def _clear_control_channels(control_bundle):
    for key in FLATTEN_KEYS:
        channel = base._first_channel(control_bundle, key)
        if channel is None:
            return f"control channel missing for {key}"
        if not base._remove_all_keys(channel):
            return f"could not remove all control keys for {key}"
    return ""


def _restore_bundle_from_snapshot(bundle, snapshot, keys):
    problems = []
    for key in keys:
        channel = base._first_channel(bundle, key)
        data = snapshot.get(key)
        if channel is None or data is None:
            problems.append(f"{key}: channel or snapshot missing")
            continue
        if not base._remove_all_keys(channel):
            problems.append(f"{key}: could not clear current keys")
            continue
        if data.get("default") is not None:
            base._set_channel_default(channel, data["default"])
        for frame, value in data.get("keys", []):
            if not base._add_channel_key(channel, int(frame), float(value)):
                problems.append(f"{key}: could not restore key at {frame}")
                break
    return problems


def _refresh_and_wiggle(start_frame, end_frame):
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    _safe_call(library, "refresh_current_level_sequence")
    diag._set_time_and_report(end_frame - 1)
    diag._set_time_and_report(start_frame)
    _safe_call(library, "refresh_current_level_sequence")


def _scale_report(actor_bundle, control_bundle, skeletal_component):
    lines = []
    for label, bundle in (("actor", actor_bundle), ("control", control_bundle)):
        snapshots = base._snapshot_bundle(bundle)
        for key in SCALE_KEYS:
            key_values, default_value, _channel = snapshots.get(key, ([], 1.0, None))
            values = [v for _f, v in key_values] or [default_value if default_value is not None else 1.0]
            non_unit = [v for v in values if abs(float(v) - 1.0) > 1e-4]
            if non_unit:
                _log_warning(f"NON-UNIT SCALE on {label} {key}: sample={non_unit[:3]} (affects conversion)")
                lines.append(f"{label}.{key} non-unit")
    relative_scale = _safe_get_editor_property(skeletal_component, "relative_scale3d")
    if relative_scale is not None:
        lines.append(f"skeletal component relative_scale3d={diag._fmt_vec(relative_scale)}")
        if any(abs(float(getattr(relative_scale, axis)) - 1.0) > 1e-4 for axis in ("x", "y", "z")):
            _log_warning("NON-UNIT skeletal component relative scale (affects conversion)")
    return lines


def _control_name_from_selected_channels():
    """Extract a single control name from the selected Sequencer channels
    (e.g. 'my_ctrl.Location.X' -> 'my_ctrl'). Returns '' if none or ambiguous."""
    controls = set()
    for name in base._get_selected_channel_names():
        text = str(name)
        lowered = text.lower()
        for token in (".location", ".rotation", ".scale"):
            index = lowered.find(token)
            if index > 0:
                controls.add(text[:index])
                break
        else:
            if "." in text:
                controls.add(text.split(".", 1)[0])
    controls = {control.strip() for control in controls if control.strip()}
    if len(controls) == 1:
        return next(iter(controls))
    return ""


def _resolve_selection_generic(global_ctrl_name="global_ctrl", sequence_asset_path=""):
    """Resolve EVERYTHING from the focused Sequencer + current selection. No
    hard-coded actor/component/rig/sequence names anywhere.

    Requires selected in Sequencer: exactly one Blueprint Actor binding plus
    exactly one of its child (Skeletal Mesh Component) bindings. The control
    name comes from the selected Control Rig channels when readable, otherwise
    from global_ctrl_name (widget input, default 'global_ctrl')."""
    # Sequence: focused, unless explicitly overridden.
    if sequence_asset_path:
        sequence = base._load_sequence_from_asset_path(sequence_asset_path)
        if sequence is None:
            return None, f"could not load sequence asset {sequence_asset_path}"
        ok, open_error = _require_sequence_open(sequence)
        if not ok:
            return None, open_error
    else:
        library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
        sequence = _safe_call(library, "get_focused_level_sequence") or _safe_call(library, "get_current_level_sequence")
        if sequence is None:
            return None, "no Level Sequence is focused/open in Sequencer."
    start_frame, end_frame = _sequence_frame_range(sequence)

    # Actor + component: exactly one selected parent/child binding pair.
    # NOTE: guid comparison must go through _binding_guid_text - str()/repr() of a
    # Guid struct embeds the Python wrapper's memory address and never matches.
    selected = [binding for binding in attach_base._get_selected_bindings() if binding is not None]
    selected_names = [attach_base._binding_name(binding) for binding in selected]

    def _descendant_guids(parent_binding):
        guids = set()
        child_stack = list(_as_list(_safe_call(parent_binding, "get_child_possessables")))
        child_stack += _as_list(_safe_call(parent_binding, "get_child_spawnables"))
        while child_stack:
            child = child_stack.pop()
            guid = _binding_guid_text(child)
            if not guid or guid in guids:
                continue
            guids.add(guid)
            child_stack.extend(_as_list(_safe_call(child, "get_child_possessables")))
            child_stack.extend(_as_list(_safe_call(child, "get_child_spawnables")))
        return guids

    pairs = []
    for parent in selected:
        descendants = _descendant_guids(parent)
        for child in selected:
            if parent is not child and _binding_guid_text(child) in descendants:
                pairs.append((parent, child))
    if len(pairs) != 1:
        return None, (
            "Selection must contain exactly one Blueprint Actor binding and exactly one of its child "
            f"Skeletal Mesh bindings. Found {len(pairs)} parent/child pair(s) in selected bindings: {selected_names}"
        )
    actor_binding, component_binding = pairs[0]
    component_name = attach_base._binding_name(component_binding)

    # Runtime actor via the binding's bound objects (spawnable- and possessable-safe).
    bound_objects, resolve_attempts = attach_base._resolve_bound_objects(sequence, actor_binding)
    runtime_actor = next((obj for obj in bound_objects if _safe_call(obj, "get_actor_location") is not None), None)
    if runtime_actor is None:
        return None, (
            f"could not resolve the runtime actor for binding {attach_base._binding_name(actor_binding)!r}. "
            f"Attempts: {resolve_attempts}"
        )
    skeletal_class = getattr(unreal, "SkeletalMeshComponent", None)
    components = _as_list(_safe_call(runtime_actor, "get_components_by_class", skeletal_class))
    matched = [c for c in components if attach_base._name_matches(_safe_call(c, "get_name"), component_name)]
    if len(matched) != 1:
        return None, (
            f"could not uniquely match skeletal component {component_name!r} on actor "
            f"{attach_base._object_name(runtime_actor)!r}. Available: {[_safe_call(c, 'get_name') for c in components]}"
        )
    skeletal_component = matched[0]

    # Control name: selected channels first, widget input as fallback.
    detected = _control_name_from_selected_channels()
    control_name = detected or str(global_ctrl_name or "global_ctrl")
    control_name_source = "selected channels" if detected else f"parameter default ({control_name!r})"

    # Control Rig: contains the control; prefer track under the selected actor hierarchy.
    track_paths = set()
    stack = [actor_binding]
    seen = set()
    while stack:
        binding = stack.pop()
        key = str(_safe_call(binding, "get_id"))
        if key in seen:
            continue
        seen.add(key)
        for track in _as_list(_safe_call(binding, "get_tracks")):
            path = _safe_call(track, "get_path_name")
            if path:
                track_paths.add(str(path))
        stack.extend(_as_list(_safe_call(binding, "get_child_possessables")))
        stack.extend(_as_list(_safe_call(binding, "get_child_spawnables")))
    control_rig, control_track, rig_attempts, rig_error = _find_control_rig(
        sequence, control_name, preferred_track_paths=track_paths
    )
    if rig_error:
        for line in rig_attempts:
            _log(f"  rig: {line}")
        return None, rig_error

    control_bundle, bundle_error = _control_bundle(control_track, control_name)
    if bundle_error:
        return None, bundle_error
    actor_bundle = base._find_actor_transform_channels_for_binding(actor_binding)
    missing = [key for key in FLATTEN_KEYS if not actor_bundle.get(key)]
    if missing:
        return None, f"actor binding {attach_base._binding_name(actor_binding)!r} is missing transform channels: {missing}"

    return {
        "sequence": sequence,
        "sequence_asset_path": str(_safe_call(sequence, "get_path_name")),
        "start_frame": int(start_frame),
        "end_frame": int(end_frame),
        "actor_binding": actor_binding,
        "actor_binding_guid": _binding_guid_text(actor_binding),
        "component_binding": component_binding,
        "component_name": component_name,
        "runtime_actor": runtime_actor,
        "skeletal_component": skeletal_component,
        "control_name": control_name,
        "control_name_source": control_name_source,
        "control_rig": control_rig,
        "control_track": control_track,
        "rig_class": _class_name(control_rig),
        "control_bundle": control_bundle,
        "actor_bundle": actor_bundle,
    }, ""


# ---------------------------------------------------------------------------
# Shared resolution for the JSON-driven phases
# ---------------------------------------------------------------------------

def _resolve_from_capture(capture):
    sequence = base._load_sequence_from_asset_path(capture["sequence_asset_path"])
    if sequence is None:
        return None, f"could not load sequence asset {capture['sequence_asset_path']}"
    ok, error = _require_sequence_open(sequence)
    if not ok:
        return None, error
    actor_binding = _find_binding_by_guid(sequence, capture["actor_binding_guid"])
    if actor_binding is None:
        return None, (
            f"actor binding guid {capture['actor_binding_guid']} not found in sequence "
            "(binding deleted or different sequence version?)"
        )
    control_rig, track, rig_attempts, rig_error = _find_control_rig(
        sequence, capture["control_name"],
        rig_class_hint=capture.get("rig_class") or capture.get("control_rig_name_hint", ""),
    )
    if rig_error:
        for line in rig_attempts:
            _log(f"  rig attempt: {line}")
        return None, rig_error
    control_bundle, bundle_error = _control_bundle(track, capture["control_name"])
    if bundle_error:
        return None, bundle_error
    actor_bundle = base._find_actor_transform_channels_for_binding(actor_binding)
    missing = [key for key in FLATTEN_KEYS if not actor_bundle.get(key)]
    if missing:
        return None, f"actor binding is missing transform channels: {missing}"
    return {
        "sequence": sequence,
        "actor_binding": actor_binding,
        "actor_bundle": actor_bundle,
        "control_rig": control_rig,
        "control_track": track,
        "control_bundle": control_bundle,
        "start_frame": int(capture["start_frame"]),
        "end_frame": int(capture["end_frame"]),
    }, ""


# ---------------------------------------------------------------------------
# PHASE 1: diagnose (read-only)
# ---------------------------------------------------------------------------

def diagnose(
    global_ctrl_name="global_ctrl",
    probe_frames=None,
    sequence_asset_path="",
    **_ignored,
):
    try:
        _reload_dependencies()
        _log("================ PHASE diagnose start (read-only) ================")
        context, error = _resolve_selection_generic(global_ctrl_name, sequence_asset_path)
        if error:
            _log_error(error)
            return ""
        sequence = context["sequence"]
        start_frame, end_frame = context["start_frame"], context["end_frame"]
        control_name = context["control_name"]
        _log(f"sequence: {context['sequence_asset_path']} range=[{start_frame},{end_frame})")
        _log(f"actor binding: {attach_base._binding_name(context['actor_binding'])!r} "
             f"guid={context['actor_binding_guid']} "
             f"kind={diag._binding_kind(sequence, context['actor_binding'])}")
        _log(f"skeletal component: {diag._describe_component(context['skeletal_component'])} "
             f"(binding {context['component_name']!r})")
        _log(f"control: {control_name!r} (source: {context['control_name_source']})")
        _log(f"control rig: {context['rig_class']} track={_class_name(context['control_track'])}")

        _log_api_availability()
        _log(f"actor channel key counts:   {_bundle_key_counts(context['actor_bundle'])}")
        _log(f"control channel key counts: {_bundle_key_counts(context['control_bundle'])}")
        _scale_report(context["actor_bundle"], context["control_bundle"], context["skeletal_component"])

        ticks = _ticks_per_frame(sequence)
        _log(f"ticks per display frame: {ticks} (half-frame sampling {'available' if ticks else 'UNAVAILABLE'})")

        if probe_frames is None:
            mid = start_frame + (end_frame - start_frame) // 2
            probe_frames = sorted({start_frame, start_frame + 1, min(start_frame + 9, end_frame - 1), mid, end_frame - 1})
        transforms, attempts = _get_world_transforms(sequence, context["control_rig"], control_name, probe_frames, "DISPLAY_RATE")
        for line in attempts:
            _log(f"  world-get: {line}")
        if transforms is None:
            _log_error("get_control_rig_world_transforms probe FAILED - paste the attempt lines above back for analysis.")
            return ""
        for frame, transform in zip(probe_frames, transforms):
            _log(f"  probe frame={frame} {control_name} world {_fmt_record(_transform_record(transform))}")

        diag._set_time_and_report(start_frame)
        actor_record = _actor_world_record_at_current_time(sequence, context["actor_binding"])
        _log(f"actor world at frame {start_frame}: {_fmt_record(actor_record)}")

        _log("DIAGNOSE RESULT: all resolutions and API probes succeeded. Next: capture.")
        _log("================ PHASE diagnose end ================")
        return "true"
    except Exception:
        _log_error(traceback.format_exc())
        return ""


# ---------------------------------------------------------------------------
# PHASE 2: capture (read-only wrt animation; writes JSON + backup asset)
# ---------------------------------------------------------------------------

def capture_original(
    global_ctrl_name="global_ctrl",
    sample_half_frames=True,
    make_backup=True,
    sequence_asset_path="",
    **_ignored,
):
    try:
        _reload_dependencies()
        _log("================ PHASE capture_original start ================")
        context, error = _resolve_selection_generic(global_ctrl_name, sequence_asset_path)
        if error:
            _log_error(error)
            return ""
        sequence = context["sequence"]
        start_frame, end_frame = context["start_frame"], context["end_frame"]
        control_name = context["control_name"]
        control_rig = context["control_rig"]
        control_bundle = context["control_bundle"]
        actor_binding = context["actor_binding"]
        actor_bundle = context["actor_bundle"]
        _log(f"context: sequence={context['sequence_asset_path']} "
             f"actor={attach_base._binding_name(actor_binding)!r} component={context['component_name']!r} "
             f"rig={context['rig_class']} control={control_name!r} ({context['control_name_source']})")

        frames = list(range(start_frame, end_frame))

        # Original control world path at integer frames (old animation still live).
        originals, attempts = _get_world_transforms(sequence, control_rig, control_name, frames, "DISPLAY_RATE")
        if originals is None:
            for line in attempts:
                _log(f"  world-get: {line}")
            _log_error("could not capture original global_ctrl world transforms. NOTHING was modified.")
            return ""
        original_records = []
        worst_roundtrip_loc, worst_roundtrip_rot = 0.0, 0.0
        for frame, transform in zip(frames, originals):
            record = _transform_record(transform)
            if record is None:
                _log_error(f"unreadable world transform at frame {frame}. NOTHING was modified.")
                return ""
            record["frame"] = frame
            # Round-trip guard: rebuilding the record must reproduce the live transform
            # exactly, otherwise a serialization artifact would poison bake AND cancel
            # out in validation (silent false positive). Abort on any mismatch.
            loc_error, rot_error = _record_roundtrip_error(record, transform)
            if loc_error is None or rot_error is None or loc_error > 1e-3 or rot_error > 1e-3:
                _log_error(
                    f"record round-trip mismatch at frame {frame}: loc_err={loc_error} rot_err={rot_error}deg. "
                    "Transform serialization is not faithful on this build - NOTHING was modified. "
                    "Paste this output back for analysis."
                )
                return ""
            worst_roundtrip_loc = max(worst_roundtrip_loc, loc_error)
            worst_roundtrip_rot = max(worst_roundtrip_rot, rot_error)
            original_records.append(record)
        _log(f"captured {len(original_records)} integer-frame world transforms "
             f"(round-trip max err loc={worst_roundtrip_loc:.6f} rot={worst_roundtrip_rot:.6f}deg)")
        _log(f"  first: frame={frames[0]} {_fmt_record(original_records[0])}")
        _log(f"  last:  frame={frames[-1]} {_fmt_record(original_records[-1])}")

        # Half-frame reference samples (tick-resolution time unit).
        half_records = []
        ticks = _ticks_per_frame(sequence)
        if sample_half_frames and ticks:
            tick_values = [frame * ticks + ticks // 2 for frame in frames[:-1]]
            halves, half_attempts = _get_world_transforms(
                sequence, control_rig, control_name, tick_values, "TICK_RESOLUTION"
            )
            if halves is None:
                for line in half_attempts:
                    _log(f"  half-get: {line}")
                _log_warning("half-frame capture unavailable; subframe validation will be skipped.")
            else:
                for frame, transform in zip(frames[:-1], halves):
                    record = _transform_record(transform)
                    if record is None:
                        _log_error(f"unreadable half-frame transform at {frame}.5. NOTHING was modified.")
                        return ""
                    record["frame"] = frame + 0.5
                    record["tick"] = frame * ticks + ticks // 2
                    loc_error, rot_error = _record_roundtrip_error(record, transform)
                    if loc_error is None or rot_error is None or loc_error > 1e-3 or rot_error > 1e-3:
                        _log_error(
                            f"half-frame record round-trip mismatch at {frame}.5: "
                            f"loc_err={loc_error} rot_err={rot_error}deg. NOTHING was modified."
                        )
                        return ""
                    half_records.append(record)
                _log(f"captured {len(half_records)} half-frame world transforms (round-trip checked)")
        elif sample_half_frames:
            _log_warning("ticks-per-frame not integral/readable; half-frame sampling skipped.")

        # Actor reference: evaluated world at start frame + channel-space values at start frame.
        diag._set_time_and_report(start_frame)
        actor_world_start = _actor_world_record_at_current_time(sequence, actor_binding)
        if actor_world_start is None:
            _log_error(f"could not read actor world transform at frame {start_frame}. NOTHING was modified.")
            return ""
        actor_snapshots = base._snapshot_bundle(actor_bundle)
        actor_channel_values_start = base._evaluate_transform_values(actor_snapshots, start_frame)
        _log(f"actor world at {start_frame}: {_fmt_record(actor_world_start)}")
        _log(f"actor channel values at {start_frame}: {base._format_values(actor_channel_values_start)}")

        backup_path = ""
        if make_backup:
            package = str(_safe_call(sequence, "get_path_name")).split(".")[0]
            destination = _unique_backup_destination(package, "PreFlattenBackup")
            duplicated = _safe_call(getattr(unreal, "EditorAssetLibrary", None), "duplicate_asset", package, destination)
            if duplicated is not None:
                backup_path = destination
                _log(f"backup asset created: {destination}")
            else:
                _log_error(
                    f"could not duplicate backup asset to {destination}. Aborting capture per safety policy "
                    "(pass make_backup=False to knowingly proceed with JSON-only rollback). NOTHING was modified."
                )
                return ""

        # Backup manifest: carry forward backups from earlier captures of the SAME
        # sequence+actor context so cleanup can positively identify all of them.
        backup_manifest = []
        previous_capture, _previous_message = _read_capture()
        if previous_capture and previous_capture.get("actor_binding_guid") == context["actor_binding_guid"]:
            backup_manifest = [str(p) for p in _as_list(previous_capture.get("backup_manifest")) if p]
            old_backup = previous_capture.get("backup_asset_path")
            if old_backup and old_backup not in backup_manifest:
                backup_manifest.append(old_backup)
        if backup_path and backup_path not in backup_manifest:
            backup_manifest.append(backup_path)

        capture = {
            "captured_at": _time.strftime("%Y-%m-%d %H:%M:%S"),
            "sequence_asset_path": context["sequence_asset_path"],
            "start_frame": start_frame,
            "end_frame": end_frame,
            "control_name": control_name,
            "control_name_source": context["control_name_source"],
            "rig_class": context["rig_class"],
            "component_name": context["component_name"],
            "actor_binding_guid": context["actor_binding_guid"],
            "actor_binding_name": attach_base._binding_name(actor_binding),
            "actor_world_start": actor_world_start,
            "actor_channel_values_start": {k: float(v) for k, v in actor_channel_values_start.items()},
            "original_ctrl_world": original_records,
            "original_ctrl_world_half": half_records,
            "actor_channels_snapshot": _snapshot_bundle_for_json(actor_bundle, base.TRANSFORM_KEYS),
            "control_channels_snapshot": _snapshot_bundle_for_json(control_bundle, base.TRANSFORM_KEYS),
            "key_counts_before": {
                "actor": _bundle_key_counts(actor_bundle),
                "control": _bundle_key_counts(control_bundle),
            },
            "backup_asset_path": backup_path,
            "backup_manifest": backup_manifest,
            "baked": False,
        }
        _write_capture(capture)
        _log("CAPTURE RESULT: reference data + rollback snapshots stored. NO animation was modified.")
        _log("Next: bake_flattened() (destructive).")
        _log("================ PHASE capture_original end ================")
        return "true"
    except Exception:
        _log_error(traceback.format_exc())
        return ""


# ---------------------------------------------------------------------------
# PHASE 3: bake (destructive; validation happens in a SEPARATE call)
# ---------------------------------------------------------------------------

def bake_flattened(**_ignored):
    try:
        _reload_dependencies()
        _log("================ PHASE bake_flattened start (DESTRUCTIVE) ================")
        capture, error = _read_capture()
        if capture is None:
            _log_error(error)
            return ""
        resolved, error = _resolve_from_capture(capture)
        if error:
            _log_error(f"{error} NOTHING was modified.")
            return ""
        sequence = resolved["sequence"]
        start_frame = resolved["start_frame"]
        end_frame = resolved["end_frame"]
        frames = [record["frame"] for record in capture["original_ctrl_world"]]
        transforms = [_record_to_transform(record) for record in capture["original_ctrl_world"]]

        current_actor_counts = _bundle_key_counts(resolved["actor_bundle"])
        if current_actor_counts != capture["key_counts_before"]["actor"]:
            _log_warning(
                f"actor key counts changed since capture: now={current_actor_counts} "
                f"captured={capture['key_counts_before']['actor']}. Captured reference may be stale."
            )

        transaction_class = getattr(unreal, "ScopedEditorTransaction", None)

        def _mutate():
            flatten_error = _flatten_actor_channels(
                resolved["actor_bundle"], start_frame, capture["actor_channel_values_start"]
            )
            if flatten_error:
                return f"actor flatten failed: {flatten_error}"
            clear_error = _clear_control_channels(resolved["control_bundle"])
            if clear_error:
                return f"control clear failed: {clear_error}"
            return ""

        if transaction_class is not None:
            with transaction_class("Flatten actor + clear global_ctrl loc/rot"):
                mutate_error = _mutate()
        else:
            mutate_error = _mutate()
        if mutate_error:
            _log_error(f"{mutate_error}. Run rollback() to restore from the capture snapshot.")
            return ""
        _log(f"actor flattened to its frame-{start_frame} channel values (1 key per loc/rot channel); "
             "global_ctrl loc/rot keys cleared. Scale channels untouched.")

        _refresh_and_wiggle(start_frame, end_frame)

        ok, attempts = _set_world_transforms(
            sequence, resolved["control_rig"], capture["control_name"], frames, transforms, "DISPLAY_RATE"
        )
        for line in attempts:
            _log(f"  world-set: {line}")
        if not ok:
            _log_error("set_control_rig_world_transforms FAILED. Run rollback() to restore original animation.")
            return ""

        _safe_call(getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None), "refresh_current_level_sequence")
        _log(f"key counts after bake: actor={_bundle_key_counts(resolved['actor_bundle'])} "
             f"control={_bundle_key_counts(resolved['control_bundle'])}")

        if not _enforce_and_report_key_times(resolved, capture, start_frame, end_frame):
            _log_error("bake produced out-of-spec key times that could not be repaired. Run rollback().")
            return ""

        capture["baked"] = True
        capture["baked_at"] = _time.strftime("%Y-%m-%d %H:%M:%S")
        capture.pop("bake_validated_at", None)
        _write_capture(capture)

        _log("BAKE DONE. NOT validated yet - the numbers in this call prove nothing (stale-graph lesson).")
        _log(f"NOW: let the editor tick, scrub frames {start_frame}..{end_frame - 1} by hand,")
        _log("then run validate_settled() as a SEPARATE command. Run rollback() if it looks wrong.")
        _log("================ PHASE bake_flattened end ================")
        return "true"
    except Exception:
        _log_error(traceback.format_exc())
        return ""


# ---------------------------------------------------------------------------
# PHASE 4: settled validation (read-only, separate editor call)
# ---------------------------------------------------------------------------

def validate_settled(
    location_tolerance=0.1,
    rotation_tolerance_degrees=0.1,
    max_failure_rows_logged=15,
    **_ignored,
):
    try:
        _reload_dependencies()
        _log("================ PHASE validate_settled start (read-only) ================")
        capture, error = _read_capture()
        if capture is None:
            _log_error(error)
            return ""
        if not capture.get("baked"):
            _log_error("capture sidecar says no bake has run yet.")
            return ""
        _log(f"captured at {capture.get('captured_at')} baked at {capture.get('baked_at')} "
             f"- this validation runs in a separate editor call (fresh evaluation graph).")
        resolved, error = _resolve_from_capture(capture)
        if error:
            _log_error(error)
            return ""
        sequence = resolved["sequence"]
        start_frame = resolved["start_frame"]
        end_frame = resolved["end_frame"]
        _refresh_and_wiggle(start_frame, end_frame)

        def _compare(records, time_unit_member, value_key, label):
            values = [record[value_key] for record in records]
            fresh, attempts = _get_world_transforms(
                sequence, resolved["control_rig"], capture["control_name"], values, time_unit_member
            )
            if fresh is None:
                for line in attempts:
                    _log(f"  {label}-get: {line}")
                return None
            results = []
            for record, transform in zip(records, fresh):
                loc, _rot = diag._transform_loc_rot(transform)
                loc_error = _location_error(loc, _record_loc(record))
                # Quaternion-vs-quaternion, straight off the transforms - no rotator round-trip.
                rot_error = _quat_error_degrees(_transform_quat(transform), _record_quat(record))
                results.append((record["frame"], loc_error, rot_error, record, _transform_record(transform)))
            return results

        int_results = _compare(capture["original_ctrl_world"], "DISPLAY_RATE", "frame", "int")
        if int_results is None:
            _log_error("could not evaluate baked global_ctrl world transforms.")
            return ""
        half_records = capture.get("original_ctrl_world_half") or []
        half_results = _compare(half_records, "TICK_RESOLUTION", "tick", "half") if half_records else []

        def _summarize(results, label, tolerate_loc, tolerate_rot):
            max_loc, max_loc_frame, max_rot, max_rot_frame = 0.0, None, 0.0, None
            failures = []
            for frame, loc_error, rot_error, original, fresh in results:
                if loc_error is None or rot_error is None:
                    failures.append((frame, loc_error, rot_error, original, fresh))
                    continue
                if loc_error > max_loc:
                    max_loc, max_loc_frame = loc_error, frame
                if rot_error > max_rot:
                    max_rot, max_rot_frame = rot_error, frame
                if loc_error > tolerate_loc or rot_error > tolerate_rot:
                    failures.append((frame, loc_error, rot_error, original, fresh))
            _log(f"[{label}] samples={len(results)} max_loc_error={max_loc:.6f} at frame {max_loc_frame} | "
                 f"max_rot_error={max_rot:.6f}deg at frame {max_rot_frame}")
            if failures:
                _log(f"[{label}] first failing frame: {failures[0][0]} (total {len(failures)})")
                for frame, loc_error, rot_error, original, fresh in failures[:int(max_failure_rows_logged)]:
                    _log(f"[{label}]   FAIL frame={frame} loc_err={loc_error} rot_err={rot_error}")
                    _log(f"[{label}]     original: {_fmt_record(original)}")
                    _log(f"[{label}]     baked:    {_fmt_record(fresh)}")
            return failures

        int_failures = _summarize(int_results, "INTEGER", float(location_tolerance), float(rotation_tolerance_degrees))
        half_failures = _summarize(half_results, "HALF", float(location_tolerance), float(rotation_tolerance_degrees)) if half_results else []
        if not half_records:
            _log_warning("no half-frame reference captured; subframe (motion blur) fidelity NOT validated.")

        # Actor stability: evaluated world per integer frame vs captured frame-start world.
        actor_reference = capture["actor_world_start"]
        actor_max_dev, actor_dev_frame = 0.0, None
        for frame in range(start_frame, end_frame):
            diag._set_time_and_report(frame)
            record = _actor_world_record_at_current_time(sequence, resolved["actor_binding"])
            deviation = _location_error(_record_loc(record), _record_loc(actor_reference)) if record else None
            if deviation is not None and deviation > actor_max_dev:
                actor_max_dev, actor_dev_frame = deviation, frame
        actor_counts = _bundle_key_counts(resolved["actor_bundle"])
        control_counts = _bundle_key_counts(resolved["control_bundle"])
        actor_static = all((actor_counts.get(key) or 0) <= 1 for key in FLATTEN_KEYS)
        expected_ctrl_keys = end_frame - start_frame
        ctrl_carries_motion = all((control_counts.get(key) or 0) >= expected_ctrl_keys for key in LOCATION_KEYS)

        _log("---------------- settled validation report ----------------")
        _log(f"frames sampled: {len(int_results)} integer + {len(half_results)} half")
        _log(f"actor world max deviation from frame-{start_frame}: {actor_max_dev:.6f} at frame {actor_dev_frame} "
             f"(expected ~0)")
        _log(f"actor loc/rot key counts (expect <=1 each): { {k: actor_counts.get(k) for k in FLATTEN_KEYS} } "
             f"static={actor_static}")
        _log(f"control loc/rot key counts (expect >={expected_ctrl_keys}): "
             f"{ {k: control_counts.get(k) for k in FLATTEN_KEYS} } carries_motion={ctrl_carries_motion}")
        _log(f"key counts before (from capture): {capture['key_counts_before']}")

        integer_pass = not int_failures and actor_max_dev <= float(location_tolerance) and actor_static and ctrl_carries_motion
        if integer_pass and half_records and half_failures:
            _log_warning(
                "INTEGER frames PASS but HALF frames FAIL: per-frame keys do not reproduce the original "
                "subframe interpolation. Motion Render Queue motion blur may differ. Options: denser sampling, "
                "matching interpolation modes, or accept integer-frame fidelity."
            )
        if integer_pass:
            capture["bake_validated_at"] = _time.strftime("%Y-%m-%d %H:%M:%S")
            _write_capture(capture)
            _log("SETTLED VALIDATION (numeric): PASS on integer frames.")
            _log(f"FINAL GATE IS MANUAL: scrub {start_frame}, {start_frame + 1}, mid-range, {end_frame - 1} and in-betweens.")
            _log("Do not declare success unless viewport scrubbing agrees. Run rollback() otherwise.")
            result = "true"
        else:
            capture.pop("bake_validated_at", None)
            _write_capture(capture)
            _log_warning("SETTLED VALIDATION: FAIL. Run rollback() to restore original animation, "
                         "then paste this report back for analysis.")
            result = ""
        _log("================ PHASE validate_settled end ================")
        return result
    except Exception:
        _log_error(traceback.format_exc())
        return ""


# ---------------------------------------------------------------------------
# PHASE 5: rollback (destructive restore from snapshot)
# ---------------------------------------------------------------------------

def rollback(**_ignored):
    try:
        _reload_dependencies()
        _log("================ PHASE rollback start ================")
        capture, error = _read_capture()
        if capture is None:
            _log_error(error)
            return ""
        resolved, error = _resolve_from_capture(capture)
        if error:
            _log_error(error)
            return ""

        transaction_class = getattr(unreal, "ScopedEditorTransaction", None)

        def _mutate():
            problems = []
            problems += _restore_bundle_from_snapshot(
                resolved["actor_bundle"], capture["actor_channels_snapshot"], FLATTEN_KEYS
            )
            problems += _restore_bundle_from_snapshot(
                resolved["control_bundle"], capture["control_channels_snapshot"], FLATTEN_KEYS
            )
            return problems

        if transaction_class is not None:
            with transaction_class("Rollback flatten global_ctrl bake"):
                problems = _mutate()
        else:
            problems = _mutate()

        _refresh_and_wiggle(resolved["start_frame"], resolved["end_frame"])
        _log(f"key counts after rollback: actor={_bundle_key_counts(resolved['actor_bundle'])} "
             f"control={_bundle_key_counts(resolved['control_bundle'])}")
        if problems:
            for problem in problems:
                _log_error(f"rollback problem: {problem}")
            if capture.get("backup_asset_path"):
                _log_error(f"full-fidelity fallback: restore from backup asset {capture['backup_asset_path']}")
            return ""
        _log_warning("rollback restored key frames+values but NOT tangent/interpolation modes. "
                     f"Full-fidelity fallback if needed: {capture.get('backup_asset_path') or '<no backup asset>'}")
        capture["baked"] = False
        capture.pop("bake_validated_at", None)
        _write_capture(capture)
        _log("ROLLBACK DONE. Scrub to confirm the original motion is back, then save or discard as appropriate.")
        _log("================ PHASE rollback end ================")
        return "true"
    except Exception:
        _log_error(traceback.format_exc())
        return ""


# ---------------------------------------------------------------------------
# Rebase-origin: transform algebra helpers (UE child-first convention:
# ComposeTransforms(A, B) applies A first, then B; child_world = local * parent)
# ---------------------------------------------------------------------------

def _t_inverse(transform):
    result = _safe_call(transform, "inverse")
    if result is not None:
        return result
    return _safe_call(getattr(unreal, "MathLibrary", None), "invert_transform", transform)


def _t_compose(first, then):
    """Apply `first`, then `then` (UE ComposeTransforms order)."""
    return _safe_call(getattr(unreal, "MathLibrary", None), "compose_transforms", first, then)


def _t_chain(*transforms):
    result = transforms[0]
    for transform in transforms[1:]:
        result = _t_compose(result, transform)
        if result is None:
            return None
    return result


def _transform_from_channel_values(values):
    """Build a Transform from channel-space values (loc xyz, rotation eulers as
    Rotation.X=roll / .Y=pitch / .Z=yaw, scale xyz) via the double-precision
    property route."""
    rotator = unreal.Rotator(roll=float(values["rotation_x"]), pitch=float(values["rotation_y"]), yaw=float(values["rotation_z"]))
    quat = rotator.quaternion()
    transform = unreal.Transform()
    transform.set_editor_property("translation", unreal.Vector(float(values["location_x"]), float(values["location_y"]), float(values["location_z"])))
    transform.set_editor_property("rotation", quat)
    transform.set_editor_property("scale3d", unreal.Vector(float(values.get("scale_x", 1.0)), float(values.get("scale_y", 1.0)), float(values.get("scale_z", 1.0))))
    return transform


def _channel_values_from_transform(transform):
    location, rotation, scale = diag._transform_parts(transform)
    return {
        "location_x": float(location.x), "location_y": float(location.y), "location_z": float(location.z),
        "rotation_x": float(rotation.roll), "rotation_y": float(rotation.pitch), "rotation_z": float(rotation.yaw),
        "scale_x": float(scale.x) if scale else 1.0, "scale_y": float(scale.y) if scale else 1.0, "scale_z": float(scale.z) if scale else 1.0,
    }


def _bundle_values_at(bundle, frame):
    snapshots = base._snapshot_bundle(bundle)
    return base._evaluate_transform_values(snapshots, frame)


def _capture_world_records(sequence, control_rig, control_name, frames, ticks, sample_half_frames=True):
    """Fresh int (+half) world records with round-trip guards. Returns (ints, halves, error)."""
    originals, attempts = _get_world_transforms(sequence, control_rig, control_name, frames, "DISPLAY_RATE")
    if originals is None:
        for line in attempts:
            _log(f"  world-get: {line}")
        return None, None, "could not evaluate control world transforms"
    records = []
    for frame, transform in zip(frames, originals):
        record = _transform_record(transform)
        if record is None:
            return None, None, f"unreadable world transform at frame {frame}"
        loc_error, rot_error = _record_roundtrip_error(record, transform)
        if loc_error is None or rot_error is None or loc_error > 1e-3 or rot_error > 1e-3:
            return None, None, f"record round-trip mismatch at frame {frame}: loc={loc_error} rot={rot_error}deg"
        record["frame"] = frame
        records.append(record)
    half_records = []
    if sample_half_frames and ticks:
        tick_values = [frame * ticks + ticks // 2 for frame in frames[:-1]]
        halves, half_attempts = _get_world_transforms(sequence, control_rig, control_name, tick_values, "TICK_RESOLUTION")
        if halves is None:
            for line in half_attempts:
                _log(f"  half-get: {line}")
            _log_warning("half-frame capture unavailable; subframe validation will be skipped.")
        else:
            for frame, transform in zip(frames[:-1], halves):
                record = _transform_record(transform)
                if record is None:
                    return None, None, f"unreadable half-frame transform at {frame}.5"
                loc_error, rot_error = _record_roundtrip_error(record, transform)
                if loc_error is None or rot_error is None or loc_error > 1e-3 or rot_error > 1e-3:
                    return None, None, f"half-frame round-trip mismatch at {frame}.5: loc={loc_error} rot={rot_error}deg"
                record["frame"] = frame + 0.5
                record["tick"] = frame * ticks + ticks // 2
                half_records.append(record)
    return records, half_records, ""


def _solve_rebased_actor(actor_current, ctrl_local_1001, ctrl_world_1001):
    """A' = A * W^-1 * L * W (child-first convention). Verified empirically after
    application; the correction loop in rebase_origin() covers any residual."""
    inverse_world = _t_inverse(ctrl_world_1001)
    if inverse_world is None:
        return None
    return _t_chain(actor_current, inverse_world, ctrl_local_1001, ctrl_world_1001)


def _snap_frame_keys_to_zero(bundle, frame, threshold=0.01):
    snapped = []
    for key_name in FLATTEN_KEYS:
        channel = base._first_channel(bundle, key_name)
        for key in base._get_channel_keys(channel):
            if base._get_key_time(key) != int(frame):
                continue
            value = base._get_key_value(key)
            try:
                value = float(value)
            except Exception:
                continue
            if value != 0.0 and abs(value) <= threshold:
                if _safe_call(key, "set_value", 0.0) is not None or True:
                    snapped.append(f"{key_name}={value:.6f}->0")
    return snapped


def _verify_baked_state(capture, resolved):
    expected = int(capture["end_frame"]) - int(capture["start_frame"])
    actor_counts = _bundle_key_counts(resolved["actor_bundle"])
    control_counts = _bundle_key_counts(resolved["control_bundle"])
    problems = []
    if any((actor_counts.get(k) or 0) > 1 for k in FLATTEN_KEYS):
        problems.append(f"actor loc/rot channels are not static: {actor_counts}")
    if any((control_counts.get(k) or 0) < expected for k in FLATTEN_KEYS):
        problems.append(f"control loc/rot channels do not carry the dense bake (expected >={expected}): {control_counts}")
    return actor_counts, control_counts, problems


# ---------------------------------------------------------------------------
# REBASE PHASE A: diagnose (read-only)
# ---------------------------------------------------------------------------

def diagnose_rebase_origin(**_ignored):
    try:
        _reload_dependencies()
        _log("================ PHASE diagnose_rebase_origin start (read-only) ================")
        capture, error = _read_capture()
        if capture is None:
            _log_error(error)
            return ""
        if not capture.get("baked"):
            _log_error("original capture sidecar says no bake has run; nothing to rebase.")
            return ""
        resolved, error = _resolve_from_capture(capture)
        if error:
            _log_error(error)
            return ""
        sequence = resolved["sequence"]
        start_frame, end_frame = resolved["start_frame"], resolved["end_frame"]

        actor_counts, control_counts, problems = _verify_baked_state(capture, resolved)
        _log(f"actor key counts:   {actor_counts}")
        _log(f"control key counts: {control_counts}")
        for problem in problems:
            _log_error(f"baked-state check: {problem}")
        if problems:
            return ""

        _refresh_and_wiggle(start_frame, end_frame)
        world_transforms, attempts = _get_world_transforms(
            sequence, resolved["control_rig"], capture["control_name"], [start_frame, end_frame - 1], "DISPLAY_RATE"
        )
        if world_transforms is None:
            for line in attempts:
                _log(f"  world-get: {line}")
            _log_error("could not evaluate baked ctrl world transforms.")
            return ""
        ctrl_world_1001 = world_transforms[0]
        _log(f"ctrl world at {start_frame} (rebase target): {_fmt_record(_transform_record(ctrl_world_1001))}")
        _log(f"ctrl world at {end_frame - 1}: {_fmt_record(_transform_record(world_transforms[1]))}")

        actor_values = _bundle_values_at(resolved["actor_bundle"], start_frame)
        actor_current = _transform_from_channel_values(actor_values)
        _log(f"actor CURRENT channel transform: {_fmt_record(_transform_record(actor_current))}")
        diag._set_time_and_report(start_frame)
        actor_world = _actor_world_record_at_current_time(sequence, resolved["actor_binding"])
        _log(f"actor CURRENT evaluated world:   {_fmt_record(actor_world)}")

        ctrl_values = _bundle_values_at(resolved["control_bundle"], start_frame)
        ctrl_local_1001 = _transform_from_channel_values(ctrl_values)
        _log(f"ctrl LOCAL at {start_frame} (channel values): {_fmt_record(_transform_record(ctrl_local_1001))}")
        scale_values = (ctrl_values.get("scale_x"), ctrl_values.get("scale_y"), ctrl_values.get("scale_z"))
        _log(f"ctrl scale at {start_frame} (preserved by rebase): {scale_values}")

        proposed = _solve_rebased_actor(actor_current, ctrl_local_1001, ctrl_world_1001)
        if proposed is None:
            _log_error("transform composition failed while solving the proposed actor transform.")
            return ""
        proposed_record = _transform_record(proposed)
        _log(f"PROPOSED new static actor transform: {_fmt_record(proposed_record)}")
        target_record = _transform_record(ctrl_world_1001)
        naive_distance = _location_error(_record_loc(proposed_record), _record_loc(target_record))
        naive_rot = _quat_error_degrees(_record_quat(proposed_record), _record_quat(target_record))
        _log(
            f"proposed-actor vs ctrl-world-target delta: loc={naive_distance:.6f} rot={naive_rot:.6f}deg "
            "(zero means rig/component offsets are trivial and the actor lands exactly on the ctrl world transform; "
            "nonzero means offsets exist and were solved through the hierarchy)"
        )
        _log("Note: rebase_origin() additionally verifies this solve EMPIRICALLY in-editor "
             "(evaluates zeroed ctrl world vs target, applies measured correction, aborts+rolls back if it cannot converge).")
        _log("DIAGNOSE RESULT: rebase is well-posed. Next (destructive, needs approval): rebase_origin().")
        _log("================ PHASE diagnose_rebase_origin end ================")
        return "true"
    except Exception:
        _log_error(traceback.format_exc())
        return ""


# ---------------------------------------------------------------------------
# REBASE PHASE B: rebase (DESTRUCTIVE; validation is a separate call)
# ---------------------------------------------------------------------------

def rebase_origin(make_backup=True, sample_half_frames=True, **_ignored):
    try:
        _reload_dependencies()
        _log("================ PHASE rebase_origin start (DESTRUCTIVE) ================")
        capture, error = _read_capture()
        if capture is None:
            _log_error(error)
            return ""
        resolved, error = _resolve_from_capture(capture)
        if error:
            _log_error(f"{error} NOTHING was modified.")
            return ""
        sequence = resolved["sequence"]
        start_frame, end_frame = resolved["start_frame"], resolved["end_frame"]
        frames = list(range(start_frame, end_frame))
        library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)

        actor_counts, control_counts, problems = _verify_baked_state(capture, resolved)
        if problems:
            for problem in problems:
                _log_error(f"baked-state check: {problem}")
            _log_error("NOTHING was modified.")
            return ""

        # 1-3. Read-only capture of the successful bake + rollback snapshots.
        _refresh_and_wiggle(start_frame, end_frame)
        ticks = _ticks_per_frame(sequence)
        records, half_records, error = _capture_world_records(
            sequence, resolved["control_rig"], capture["control_name"], frames, ticks, sample_half_frames
        )
        if error:
            _log_error(f"{error}. NOTHING was modified.")
            return ""
        _log(f"captured successful-bake world path: {len(records)} integer + {len(half_records)} half samples")

        actor_before_values = _bundle_values_at(resolved["actor_bundle"], start_frame)
        actor_before = _transform_from_channel_values(actor_before_values)
        ctrl_before_values = _bundle_values_at(resolved["control_bundle"], start_frame)
        ctrl_local_before = _transform_from_channel_values(ctrl_before_values)
        ctrl_world_target = _record_to_transform(records[0])
        _log(f"actor BEFORE: {_fmt_record(_transform_record(actor_before))}")
        _log(f"ctrl local at {start_frame} BEFORE: {_fmt_record(_transform_record(ctrl_local_before))}")

        backup_path = ""
        if make_backup:
            package = str(_safe_call(sequence, "get_path_name")).split(".")[0]
            destination = _unique_backup_destination(package, "PreRebaseBackup")
            duplicated = _safe_call(getattr(unreal, "EditorAssetLibrary", None), "duplicate_asset", package, destination)
            if duplicated is None:
                _log_error(f"could not duplicate backup asset to {destination}. Aborting; NOTHING was modified.")
                return ""
            backup_path = destination
            _log(f"backup asset created: {destination}")

        rebase_manifest = []
        previous_rebase, _previous_message = _read_rebase_capture()
        if previous_rebase:
            rebase_manifest = [str(p) for p in _as_list(previous_rebase.get("backup_manifest")) if p]
            old_backup = previous_rebase.get("backup_asset_path")
            if old_backup and old_backup not in rebase_manifest:
                rebase_manifest.append(old_backup)
        if backup_path and backup_path not in rebase_manifest:
            rebase_manifest.append(backup_path)

        rebase = {
            "captured_at": _time.strftime("%Y-%m-%d %H:%M:%S"),
            "for_baked_at": capture.get("baked_at", ""),
            "sequence_asset_path": capture["sequence_asset_path"],
            "start_frame": start_frame,
            "end_frame": end_frame,
            "control_name": capture["control_name"],
            "rig_class": capture.get("rig_class", "") or capture.get("control_rig_name_hint", ""),
            "actor_binding_guid": capture["actor_binding_guid"],
            "baked_ctrl_world": records,
            "baked_ctrl_world_half": half_records,
            "actor_before_values": {k: float(v) for k, v in actor_before_values.items()},
            "ctrl_local_before_values": {k: float(v) for k, v in ctrl_before_values.items()},
            "actor_channels_snapshot": _snapshot_bundle_for_json(resolved["actor_bundle"], base.TRANSFORM_KEYS),
            "control_channels_snapshot": _snapshot_bundle_for_json(resolved["control_bundle"], base.TRANSFORM_KEYS),
            "key_counts_before": {"actor": actor_counts, "control": control_counts},
            "backup_asset_path": backup_path,
            "backup_manifest": rebase_manifest,
            "rebased": False,
        }
        _write_rebase_capture(rebase)

        def _restore_pre_rebase():
            problems_r = _restore_bundle_from_snapshot(resolved["actor_bundle"], rebase["actor_channels_snapshot"], FLATTEN_KEYS)
            problems_r += _restore_bundle_from_snapshot(resolved["control_bundle"], rebase["control_channels_snapshot"], FLATTEN_KEYS)
            _refresh_and_wiggle(start_frame, end_frame)
            for problem in problems_r:
                _log_error(f"auto-rollback problem: {problem}")
            _log_warning("auto-rollback to pre-rebase (successful bake) state executed.")

        # 4-5. Solve actor, apply, zero the control.
        actor_solved = _solve_rebased_actor(actor_before, ctrl_local_before, ctrl_world_target)
        if actor_solved is None:
            _log_error("transform composition failed. NOTHING was modified.")
            return ""
        transaction_class = getattr(unreal, "ScopedEditorTransaction", None)

        def _apply_actor(transform):
            values = _channel_values_from_transform(transform)
            values["scale_x"], values["scale_y"], values["scale_z"] = (
                actor_before_values.get("scale_x", 1.0), actor_before_values.get("scale_y", 1.0), actor_before_values.get("scale_z", 1.0)
            )
            return _flatten_actor_channels(resolved["actor_bundle"], start_frame, values)

        def _mutate():
            apply_error = _apply_actor(actor_solved)
            if apply_error:
                return f"actor apply failed: {apply_error}"
            clear_error = _clear_control_channels(resolved["control_bundle"])
            if clear_error:
                return f"control clear failed: {clear_error}"
            for key_name in FLATTEN_KEYS:
                base._set_channel_default(base._first_channel(resolved["control_bundle"], key_name), 0.0)
            return ""

        if transaction_class is not None:
            with transaction_class("Rebase global_ctrl origin"):
                mutate_error = _mutate()
        else:
            mutate_error = _mutate()
        if mutate_error:
            _log_error(mutate_error)
            _restore_pre_rebase()
            return ""

        # 6a. Empirical verification + correction of the actor solve.
        converged = False
        for iteration in range(3):
            _refresh_and_wiggle(start_frame, end_frame)
            evaluated, attempts = _get_world_transforms(
                sequence, resolved["control_rig"], capture["control_name"], [start_frame], "DISPLAY_RATE"
            )
            if evaluated is None:
                for line in attempts:
                    _log(f"  world-get: {line}")
                break
            loc_error = _location_error(diag._transform_loc_rot(evaluated[0])[0], _record_loc(records[0]))
            rot_error = _quat_error_degrees(_transform_quat(evaluated[0]), _record_quat(records[0]))
            _log(f"empirical check iter {iteration}: zeroed-ctrl world vs target loc={loc_error:.6f} rot={rot_error:.6f}deg")
            if loc_error is not None and rot_error is not None and loc_error <= 1e-3 and rot_error <= 1e-3:
                converged = True
                break
            correction = _t_compose(_t_inverse(evaluated[0]), ctrl_world_target)
            actor_solved = _t_compose(actor_solved, correction)
            if actor_solved is None:
                break
            _log(f"applying measured correction; new actor candidate: {_fmt_record(_transform_record(actor_solved))}")
            apply_error = _apply_actor(actor_solved)
            if apply_error:
                _log_error(apply_error)
                break
        if not converged:
            _log_error("actor solve did not converge through the rig hierarchy. Auto-rolling back (safety check failure).")
            _restore_pre_rebase()
            return ""
        solved_record = _transform_record(actor_solved)
        _log(f"SOLVED static actor transform (empirically verified): {_fmt_record(solved_record)}")
        rebase["actor_after_values"] = _channel_values_from_transform(actor_solved)
        rebase["actor_after_record"] = solved_record

        # 6b. Re-solve and key the control across all frames to the captured bake path.
        ok, attempts = _set_world_transforms(
            sequence, resolved["control_rig"], capture["control_name"], frames,
            [_record_to_transform(record) for record in records], "DISPLAY_RATE"
        )
        for line in attempts:
            _log(f"  world-set: {line}")
        if not ok:
            _log_error("set_control_rig_world_transforms FAILED. Auto-rolling back (safety check failure).")
            _restore_pre_rebase()
            return ""

        snapped = _snap_frame_keys_to_zero(resolved["control_bundle"], start_frame, threshold=0.01)
        if snapped:
            _log(f"snapped near-zero frame-{start_frame} ctrl keys to exact 0: {snapped}")
        _safe_call(library, "refresh_current_level_sequence")
        _log(f"key counts after rebase: actor={_bundle_key_counts(resolved['actor_bundle'])} "
             f"control={_bundle_key_counts(resolved['control_bundle'])}")

        # Prove what was actually written: fresh reads from the live channels.
        actor_written = _bundle_values_at(resolved["actor_bundle"], start_frame)
        ctrl_written = _bundle_values_at(resolved["control_bundle"], start_frame)
        _log(f"actor channel values BEFORE:              {base._format_values(actor_before_values)}")
        _log(f"actor channel values WRITTEN (fresh read): {base._format_values(actor_written)}")
        _log(f"ctrl local at {start_frame} BEFORE:              {base._format_values(ctrl_before_values)}")
        _log(f"ctrl local at {start_frame} WRITTEN (fresh read): {base._format_values(ctrl_written)}")
        written_delta = max(
            abs(float(actor_written[k]) - float(rebase["actor_after_values"][k]))
            for k in LOCATION_KEYS + ROTATION_KEYS
        )
        if written_delta > 0.1:
            _log_error(
                f"actor channels read back differ from intended solve by {written_delta:.6f} - "
                "mutation did not stick. Auto-rolling back (safety check failure)."
            )
            _restore_pre_rebase()
            return ""

        if not _enforce_and_report_key_times(resolved, capture, start_frame, end_frame):
            _log_error("rebase produced out-of-spec key times that could not be repaired. Auto-rolling back.")
            _restore_pre_rebase()
            return ""

        rebase["rebased"] = True
        rebase["rebased_at"] = _time.strftime("%Y-%m-%d %H:%M:%S")
        rebase["rebase_id"] = f"rebase_{_time.strftime('%Y%m%d_%H%M%S')}_for_{str(capture.get('baked_at', '')).replace(':', '').replace(' ', '_')}"
        _write_rebase_capture(rebase)
        _log(f"rebase operation id: {rebase['rebase_id']} (tied to bake {capture.get('baked_at')!r})")

        _log("REBASE APPLIED. NOT validated yet. Let the editor tick / scrub by hand, then run "
             "validate_rebase_settled() as a SEPARATE call. rollback_rebase_origin() restores the successful bake.")
        _log("================ PHASE rebase_origin end ================")
        return "true"
    except Exception:
        _log_error(traceback.format_exc())
        return ""


# ---------------------------------------------------------------------------
# REBASE PHASE C: settled validation (read-only, separate editor call)
# ---------------------------------------------------------------------------

def validate_rebase_settled(
    location_tolerance=0.1,
    rotation_tolerance_degrees=0.1,
    max_failure_rows_logged=15,
    **_ignored,
):
    try:
        _reload_dependencies()
        _log("================ PHASE validate_rebase_settled start (read-only) ================")
        rebase, error = _read_rebase_capture()
        if rebase is None:
            _log_error(error)
            return ""
        if not rebase.get("rebased"):
            _log_error("rebase sidecar says rebase has not been applied.")
            return ""
        capture, _capture_error = _read_capture()
        if capture is not None and rebase.get("for_baked_at") != capture.get("baked_at"):
            _log_error(
                f"rebase sidecar is tied to bake revision {rebase.get('for_baked_at')!r} but the current bake "
                f"is {capture.get('baked_at')!r} - stale sidecar, nothing valid to validate. Run status/next."
            )
            return ""
        resolved, error = _resolve_from_capture(rebase)
        if error:
            _log_error(error)
            return ""
        sequence = resolved["sequence"]
        start_frame, end_frame = resolved["start_frame"], resolved["end_frame"]
        _log(f"rebase applied at {rebase.get('rebased_at')} (id={rebase.get('rebase_id')}); "
             "validating in a separate editor call now.")
        live_ok, live_details = _rebase_live_check(rebase, resolved)
        _log(f"live-state pre-check: matches_rebased_state={live_ok} details={live_details}")
        _refresh_and_wiggle(start_frame, end_frame)

        loc_tol = float(location_tolerance)
        rot_tol = float(rotation_tolerance_degrees)

        def _compare(records, unit, value_key, label):
            values = [record[value_key] for record in records]
            fresh, attempts = _get_world_transforms(sequence, resolved["control_rig"], rebase["control_name"], values, unit)
            if fresh is None:
                for line in attempts:
                    _log(f"  {label}-get: {line}")
                return None
            max_loc, max_loc_frame, max_rot, max_rot_frame = 0.0, None, 0.0, None
            failures = []
            for record, transform in zip(records, fresh):
                loc_error = _location_error(diag._transform_loc_rot(transform)[0], _record_loc(record))
                rot_error = _quat_error_degrees(_transform_quat(transform), _record_quat(record))
                if loc_error is None or rot_error is None:
                    failures.append((record["frame"], loc_error, rot_error, record, _transform_record(transform)))
                    continue
                if loc_error > max_loc:
                    max_loc, max_loc_frame = loc_error, record["frame"]
                if rot_error > max_rot:
                    max_rot, max_rot_frame = rot_error, record["frame"]
                if loc_error > loc_tol or rot_error > rot_tol:
                    failures.append((record["frame"], loc_error, rot_error, record, _transform_record(transform)))
            _log(f"[{label}] samples={len(records)} max_loc_error={max_loc:.6f} at {max_loc_frame} | "
                 f"max_rot_error={max_rot:.6f}deg at {max_rot_frame}")
            if failures:
                _log(f"[{label}] first failing frame: {failures[0][0]} (total {len(failures)})")
                for frame, loc_error, rot_error, original, fresh_rec in failures[:int(max_failure_rows_logged)]:
                    _log(f"[{label}]   FAIL frame={frame} loc={loc_error} rot={rot_error}")
                    _log(f"[{label}]     pre-rebase bake: {_fmt_record(original)}")
                    _log(f"[{label}]     post-rebase:     {_fmt_record(fresh_rec)}")
            return failures

        int_failures = _compare(rebase["baked_ctrl_world"], "DISPLAY_RATE", "frame", "INTEGER")
        if int_failures is None:
            _log_error("could not evaluate rebased ctrl world transforms.")
            return ""
        half_records = rebase.get("baked_ctrl_world_half") or []
        half_failures = _compare(half_records, "TICK_RESOLUTION", "tick", "HALF") if half_records else []
        if not half_records:
            _log_warning("no half-frame reference; subframe fidelity NOT validated.")

        # Actor static + at solved transform.
        actor_after_target = rebase.get("actor_after_record")
        actor_max_dev, actor_dev_frame = 0.0, None
        for frame in range(start_frame, end_frame):
            diag._set_time_and_report(frame)
            record = _actor_world_record_at_current_time(sequence, resolved["actor_binding"])
            deviation = _location_error(_record_loc(record), _record_loc(actor_after_target)) if record and actor_after_target else None
            if deviation is not None and deviation > actor_max_dev:
                actor_max_dev, actor_dev_frame = deviation, frame
        actor_counts = _bundle_key_counts(resolved["actor_bundle"])
        control_counts = _bundle_key_counts(resolved["control_bundle"])
        actor_static = all((actor_counts.get(k) or 0) <= 1 for k in FLATTEN_KEYS)

        # ctrl local at start frame ~ identity; scale unchanged.
        ctrl_values_now = _bundle_values_at(resolved["control_bundle"], start_frame)
        local_loc = unreal.Vector(ctrl_values_now["location_x"], ctrl_values_now["location_y"], ctrl_values_now["location_z"])
        local_loc_error = float(local_loc.length())
        local_rot_error = _quat_error_degrees(
            unreal.Rotator(roll=ctrl_values_now["rotation_x"], pitch=ctrl_values_now["rotation_y"], yaw=ctrl_values_now["rotation_z"]).quaternion(),
            _make_quat(0.0, 0.0, 0.0, 1.0),
        )
        scale_before = tuple(rebase["ctrl_local_before_values"].get(k, 1.0) for k in SCALE_KEYS)
        scale_now = tuple(ctrl_values_now.get(k, 1.0) for k in SCALE_KEYS)
        scale_unchanged = all(abs(a - b) < 1e-4 for a, b in zip(scale_before, scale_now))

        actor_live_values = _bundle_values_at(resolved["actor_bundle"], start_frame)
        _log("---------------- rebase settled validation report ----------------")
        _log(f"actor BEFORE (stored):             {base._format_values(rebase['actor_before_values'])}")
        _log(f"intended actor transform (stored): {base._format_values(rebase['actor_after_values'])}")
        _log(f"actor LIVE channels (fresh read):  {base._format_values(actor_live_values)}")
        _log(f"ctrl local at {start_frame} BEFORE (stored): {base._format_values(rebase['ctrl_local_before_values'])}")
        _log(f"ctrl local at {start_frame} LIVE (fresh):    {base._format_values(ctrl_values_now)}")
        _log(f"ctrl local identity check: loc_mag={local_loc_error:.6f} rot={local_rot_error:.6f}deg (want ~0)")
        _log(f"ctrl scale before={scale_before} now={scale_now} unchanged={scale_unchanged}")
        _log(f"actor max deviation from INTENDED (stored) transform across range, freshly evaluated: "
             f"{actor_max_dev:.6f} at frame {actor_dev_frame}")
        _log(f"actor static={actor_static} key counts: {actor_counts}")
        _log(f"control key counts: {control_counts}")
        _log(f"key counts before rebase: {rebase['key_counts_before']}")

        passed = (
            not int_failures and actor_static and actor_max_dev <= loc_tol
            and local_loc_error <= loc_tol and (local_rot_error or 0.0) <= rot_tol and scale_unchanged
        )
        if passed and half_records and half_failures:
            _log_warning("INTEGER frames PASS but HALF frames FAIL - subframe interpolation differs from the pre-rebase bake.")
        if passed:
            rebase["rebase_validated_at"] = _time.strftime("%Y-%m-%d %H:%M:%S")
            _write_rebase_capture(rebase)
            _log("REBASE SETTLED VALIDATION (numeric): PASS.")
            _log(f"FINAL GATE IS MANUAL: scrub {start_frame}, {start_frame + 1}, mid-range, {end_frame - 1} and in-betweens; confirm identical motion.")
            result = "true"
        else:
            rebase.pop("rebase_validated_at", None)
            _write_rebase_capture(rebase)
            _log_warning("REBASE SETTLED VALIDATION: FAIL. Run rollback_rebase_origin() to restore the successful bake.")
            result = ""
        _log("================ PHASE validate_rebase_settled end ================")
        return result
    except Exception:
        _log_error(traceback.format_exc())
        return ""


# ---------------------------------------------------------------------------
# REBASE PHASE D: rollback (restores the successful pre-rebase bake)
# ---------------------------------------------------------------------------

def rollback_rebase_origin(**_ignored):
    try:
        _reload_dependencies()
        _log("================ PHASE rollback_rebase_origin start ================")
        rebase, error = _read_rebase_capture()
        if rebase is None:
            _log_error(error)
            return ""
        resolved, error = _resolve_from_capture(rebase)
        if error:
            _log_error(error)
            return ""
        transaction_class = getattr(unreal, "ScopedEditorTransaction", None)

        def _mutate():
            problems = _restore_bundle_from_snapshot(resolved["actor_bundle"], rebase["actor_channels_snapshot"], FLATTEN_KEYS)
            problems += _restore_bundle_from_snapshot(resolved["control_bundle"], rebase["control_channels_snapshot"], FLATTEN_KEYS)
            return problems

        if transaction_class is not None:
            with transaction_class("Rollback global_ctrl origin rebase"):
                problems = _mutate()
        else:
            problems = _mutate()
        _refresh_and_wiggle(resolved["start_frame"], resolved["end_frame"])
        _log(f"key counts after rollback: actor={_bundle_key_counts(resolved['actor_bundle'])} "
             f"control={_bundle_key_counts(resolved['control_bundle'])}")
        if problems:
            for problem in problems:
                _log_error(f"rollback problem: {problem}")
            _log_error(f"full-fidelity fallback: backup asset {rebase.get('backup_asset_path') or '<none>'}")
            return ""
        rebase["rebased"] = False
        rebase.pop("rebase_validated_at", None)
        _write_rebase_capture(rebase)
        _log("ROLLBACK DONE: pre-rebase (successful bake) key state restored. "
             f"Backup asset if needed: {rebase.get('backup_asset_path') or '<none>'}")
        _log("================ PHASE rollback_rebase_origin end ================")
        return "true"
    except Exception:
        _log_error(traceback.format_exc())
        return ""


# ---------------------------------------------------------------------------
# Key-time validation: every key this tool generates must sit on an EXACT
# integer display frame inside the playback range. Half-frame sampling stays
# validation-only and is never written as keys. Placement uses integer frame
# numbers with MovieSceneTimeUnit.DISPLAY_RATE (sub_frame 0.0) and the engine's
# exact display-rate -> tick-resolution conversion; verification reads the
# ACTUAL stored key times back in both time units with pure integer arithmetic.
# ---------------------------------------------------------------------------

def _generated_channels(resolved):
    """The exact channels this tool writes: actor loc/rot, control loc/rot/scale
    (set_control_rig_world_transforms keys scale too). Actor scale is untouched
    by the tool and therefore not inspected."""
    channels = []
    for label, bundle, keys in (
        ("actor", resolved["actor_bundle"], FLATTEN_KEYS),
        ("control", resolved["control_bundle"], FLATTEN_KEYS + SCALE_KEYS),
    ):
        for key_name in keys:
            channel = base._first_channel(bundle, key_name)
            if channel is not None:
                channels.append((f"{label}.{key_name}", channel))
    return channels


def _frame_time_parts(key, unit):
    """Actual stored key time in the given unit -> (integer frame_number, sub_frame)."""
    time_value = _safe_call(key, "get_time", unit)
    if time_value is None:
        return None, None
    frame_number = getattr(time_value, "frame_number", None)
    frame = getattr(frame_number, "value", None)
    if frame is None:
        try:
            frame = int(time_value)
        except Exception:
            return None, None
    sub_frame = float(getattr(time_value, "sub_frame", 0.0) or 0.0)
    return int(frame), sub_frame


def _inspect_generated_key_times(resolved, start_frame, end_frame, repair=False):
    """Inspect every generated key's ACTUAL stored time. A key passes iff its
    tick-resolution time is an exact integer multiple of ticks-per-frame, its
    sub_frame is 0.0 in both units, and its display frame is inside
    [start_frame, end_frame). repair=True deletes offending keys (generated
    channels only - never touches unrelated tracks)."""
    stats = {
        "ticks_per_frame": _ticks_per_frame(resolved["sequence"]),
        "total": 0, "integer": 0, "subframe": 0, "out_of_range": 0,
        "min_frame": None, "max_frame": None,
        "offenders": [], "removed": [], "error": "",
    }
    ticks = stats["ticks_per_frame"]
    if not ticks:
        stats["error"] = "ticks-per-frame is not an exact integer; cannot verify key times."
        return stats
    unit_tick = _time_unit("TICK_RESOLUTION")
    unit_display = _time_unit("DISPLAY_RATE")
    for name, channel in _generated_channels(resolved):
        bad_keys = []
        for key in base._get_channel_keys(channel):
            stats["total"] += 1
            tick_value, tick_sub = _frame_time_parts(key, unit_tick)
            display_frame, display_sub = _frame_time_parts(key, unit_display)
            if tick_value is None:
                stats["offenders"].append((name, "tick=<unreadable>", "display=<unreadable>"))
                bad_keys.append(key)
                continue
            frame_float = tick_value / float(ticks)
            if stats["min_frame"] is None or frame_float < stats["min_frame"]:
                stats["min_frame"] = frame_float
            if stats["max_frame"] is None or frame_float > stats["max_frame"]:
                stats["max_frame"] = frame_float
            on_frame = (tick_value % ticks == 0) and tick_sub == 0.0 and (display_sub or 0.0) == 0.0
            in_range = on_frame and (start_frame <= tick_value // ticks <= end_frame - 1)
            if on_frame and in_range:
                stats["integer"] += 1
                continue
            if not on_frame:
                stats["subframe"] += 1
            else:
                stats["out_of_range"] += 1
            stats["offenders"].append(
                (name, f"tick={tick_value}+{tick_sub}", f"display={display_frame}+{display_sub}")
            )
            bad_keys.append(key)
        if repair and bad_keys:
            for key in bad_keys:
                removed = False
                for fn_name in ("remove_key", "delete_key"):
                    fn = getattr(channel, fn_name, None)
                    if fn is None:
                        continue
                    try:
                        fn(key)
                        removed = True
                        break
                    except Exception:
                        pass
                stats["removed"].append((name, removed))
    return stats


def _log_key_time_report(stats, start_frame, end_frame):
    _log(f"ticks per display frame: {stats.get('ticks_per_frame')}")
    _log(f"total generated keys inspected: {stats['total']}")
    _log(f"min generated key time (display frames): {stats['min_frame']}")
    _log(f"max generated key time (display frames): {stats['max_frame']}")
    _log(f"exact integer-frame in-range keys: {stats['integer']}")
    _log(f"subframe keys: {stats['subframe']} | out-of-playback-range keys: {stats['out_of_range']}")
    for name, tick_text, display_text in stats["offenders"][:40]:
        _log_error(f"  OFFENDER channel={name} {tick_text} {display_text}")
    if len(stats["offenders"]) > 40:
        _log_error(f"  ... and {len(stats['offenders']) - 40} more offender(s)")
    if stats.get("removed"):
        _log_warning(f"repaired (removed) {len(stats['removed'])} out-of-spec generated key(s)")
    if stats.get("error"):
        _log_error(stats["error"])
    passed = (
        not stats.get("error") and stats["total"] > 0
        and stats["subframe"] == 0 and stats["out_of_range"] == 0 and not stats["offenders"]
    )
    if passed:
        _log(f"KEY TIME VALIDATION: PASS - all generated keys are on integer display frames "
             f"{start_frame}-{end_frame - 1}; subframe keys=0")
    else:
        _log_error(f"KEY TIME VALIDATION: FAIL - subframe={stats['subframe']} "
                   f"out_of_range={stats['out_of_range']} offenders={len(stats['offenders'])} "
                   f"total={stats['total']}")
    return passed


def _enforce_and_report_key_times(resolved, capture, start_frame, end_frame):
    """Post-write enforcement for bake/rebase: repair (delete off-spec generated
    keys), then re-inspect and prove from the actual stored key times."""
    stats = _inspect_generated_key_times(resolved, start_frame, end_frame, repair=True)
    if stats.get("removed"):
        _log_warning("out-of-spec generated keys were removed; re-inspecting stored key times...")
        stats = _inspect_generated_key_times(resolved, start_frame, end_frame, repair=False)
    passed = _log_key_time_report(stats, start_frame, end_frame)
    if passed:
        capture["key_times_validated_at"] = _time.strftime("%Y-%m-%d %H:%M:%S")
    else:
        capture.pop("key_times_validated_at", None)
    _write_capture(capture)
    return passed


def validate_key_times(**_ignored):
    """Read-only wrt animation: inspects the actual stored key times of every
    generated channel and records the result in the capture sidecar."""
    try:
        _reload_dependencies()
        _log("================ PHASE validate_key_times start (read-only) ================")
        capture, error = _read_capture()
        if capture is None:
            _log_error(error)
            return ""
        if not capture.get("baked"):
            _log_error("no bake recorded for this sequence; nothing generated to validate.")
            return ""
        resolved, error = _resolve_from_capture(capture)
        if error:
            _log_error(error)
            return ""
        shape, actor_counts, control_counts = _state_shape(capture, resolved)
        if shape != "baked":
            _log_error(
                f"live sequence state is {shape!r}, not the baked/rebased result "
                f"(actor={actor_counts} control={control_counts}). The generated keys are not present - "
                "there is nothing of this tool's to validate. Run status/next to repair first."
            )
            capture.pop("key_times_validated_at", None)
            _write_capture(capture)
            return ""
        start_frame, end_frame = resolved["start_frame"], resolved["end_frame"]
        stats = _inspect_generated_key_times(resolved, start_frame, end_frame, repair=False)
        passed = _log_key_time_report(stats, start_frame, end_frame)
        if passed:
            capture["key_times_validated_at"] = _time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            capture.pop("key_times_validated_at", None)
        _write_capture(capture)
        _log("================ PHASE validate_key_times end ================")
        return "true" if passed else ""
    except Exception:
        _log_error(traceback.format_exc())
        return ""


# ---------------------------------------------------------------------------
# Visible-subframe-keys diagnostic (read-only): reconcile what Sequencer SHOWS
# with what is actually STORED. Enumerates every key on every channel whose
# name loosely contains the control name, across ALL Control Rig tracks and ALL
# sections (not just what the strict validator matched), in tick + display time,
# and computes the local -> root subsequence time mapping.
# ---------------------------------------------------------------------------

def _key_full_detail(key, ticks_local):
    tick_value, tick_sub = _frame_time_parts(key, _time_unit("TICK_RESOLUTION"))
    display_frame, display_sub = _frame_time_parts(key, _time_unit("DISPLAY_RATE"))
    value = _safe_call(key, "get_value")
    try:
        value = float(value)
    except Exception:
        value = str(value)
    decimal = (tick_value / float(ticks_local)) if (tick_value is not None and ticks_local) else None
    integer_local = bool(
        tick_value is not None and ticks_local
        and tick_value % ticks_local == 0 and (tick_sub or 0.0) == 0.0 and (display_sub or 0.0) == 0.0
    )
    return {
        "tick": tick_value, "tick_sub": tick_sub,
        "display_frame": display_frame, "display_sub": display_sub,
        "decimal_display_frame": decimal, "value": value, "integer_local": integer_local,
    }


def _rate_text(rate):
    numerator = _safe_get_editor_property(rate, "numerator")
    denominator = _safe_get_editor_property(rate, "denominator")
    return f"{numerator}/{denominator}"


def _find_subsequence_sections(owner_sequence, target_path, trail=""):
    """Recursively find SubSequence/Shot sections whose inner sequence is target_path.
    Returns list of (owner_sequence, trail, track, section, inner_sequence)."""
    results = []
    for track in _as_list(_safe_call(owner_sequence, "get_tracks")):
        track_class = _class_name(track)
        if "Sub" not in track_class and "Shot" not in track_class:
            continue
        for section in _as_list(_safe_call(track, "get_sections")):
            inner = _safe_call(section, "get_sequence")
            if inner is None:
                continue
            inner_path = str(_safe_call(inner, "get_path_name"))
            label = f"{trail}/{_safe_call(owner_sequence, 'get_name')}"
            if inner_path == target_path:
                results.append((owner_sequence, label, track, section, inner))
            else:
                results.extend(_find_subsequence_sections(inner, target_path, label))
    return results


def diagnose_visible_subframe_keys(**_ignored):
    """READ-ONLY. Explains why Sequencer may show subframe keys while
    validate_key_times reports zero. Writes a full JSON dump next to the sidecars."""
    try:
        _reload_dependencies()
        _log("================ PHASE diagnose_visible_subframe_keys start (read-only) ================")
        capture, error = _read_capture()
        if capture is None:
            # The user may be viewing through the ROOT sequence (itself a clue for
            # case B). Fall back to the sidecars on disk if unambiguous.
            _log_warning(error)
            found = []
            for name in sorted(os.listdir(_sidecar_dir())):
                if name.startswith("flatten_ctrl_capture_") and name.endswith(".json"):
                    data = _load_json_file(os.path.join(_sidecar_dir(), name))
                    if data is not None:
                        found.append(data)
            if len(found) == 1:
                capture = found[0]
                _log_warning(f"falling back to the only capture sidecar on disk: "
                             f"{capture.get('sequence_asset_path')}")
            else:
                _log_error(f"cannot pick a capture sidecar automatically ({len(found)} found). "
                           "Focus the ANM subsequence and re-run.")
                return ""
        control_name = capture.get("control_name", "global_ctrl")
        target_norm = base._normalize_name(control_name)
        sequence = base._load_sequence_from_asset_path(capture["sequence_asset_path"])
        if sequence is None:
            _log_error(f"could not load {capture['sequence_asset_path']}")
            return ""
        start_frame, end_frame = int(capture["start_frame"]), int(capture["end_frame"])
        ticks_local = _ticks_per_frame(sequence)

        # The strict validator's inclusion criteria, for included/excluded marking.
        resolved, resolve_error = _resolve_from_capture(capture)
        validator_track_path = ""
        validator_channel_names = set()
        if not resolve_error:
            validator_track_path = str(_safe_call(resolved["control_track"], "get_path_name") or "")
            for key_name in FLATTEN_KEYS + SCALE_KEYS:
                channel = base._first_channel(resolved["control_bundle"], key_name)
                if channel is not None:
                    validator_channel_names.add(str(base._get_channel_name(channel)))
        else:
            _log_warning(f"could not resolve validator context: {resolve_error}")

        library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
        root_sequence = _safe_call(library, "get_current_level_sequence")
        focused_sequence = _safe_call(library, "get_focused_level_sequence")
        _log(f"focused sequence: {_safe_call(focused_sequence, 'get_name')} "
             f"display_rate={_rate_text(_safe_call(focused_sequence, 'get_display_rate'))} "
             f"tick_resolution={_rate_text(_safe_call(focused_sequence, 'get_tick_resolution'))}")
        _log(f"root sequence:    {_safe_call(root_sequence, 'get_name')} "
             f"display_rate={_rate_text(_safe_call(root_sequence, 'get_display_rate'))} "
             f"tick_resolution={_rate_text(_safe_call(root_sequence, 'get_tick_resolution'))}")
        _log(f"target (ANM) sequence ticks per display frame: {ticks_local}")

        # ---- Part 1: every key on every loosely-matching channel, all rigs/tracks/sections ----
        dump = {"control_name": control_name, "sequence": capture["sequence_asset_path"], "tracks": []}
        total_keys = 0
        non_integer_keys = []
        excluded_channels = []
        rig_attempts = []
        for proxy in _control_rig_proxies(sequence, rig_attempts):
            control_rig = _safe_get_editor_property(proxy, "control_rig")
            track = _safe_get_editor_property(proxy, "track")
            rig_class = _class_name(control_rig)
            track_path = str(_safe_call(track, "get_path_name") or "")
            track_name = str(_safe_call(track, "get_display_name") or _safe_call(track, "get_name") or track_path)
            sections = _as_list(_safe_call(track, "get_sections"))
            track_entry = {"rig": rig_class, "track": track_name, "track_path": track_path,
                           "is_validator_track": track_path == validator_track_path, "sections": []}
            _log(f"rig={rig_class} track={track_name!r} sections={len(sections)} "
                 f"validator_track={track_path == validator_track_path}")
            for section_index, section in enumerate(sections):
                section_start = _safe_call(section, "get_start_frame")
                section_end = _safe_call(section, "get_end_frame")
                active = _safe_call(section, "is_active")
                # Collect channels through EVERY getter, dedupe by channel name.
                channels_by_name = {}
                getter_counts = {}
                for getter, args in (
                    ("get_all_channels", ()),
                    ("get_channels_by_type", (getattr(unreal, "MovieSceneScriptingFloatChannel", None),)),
                    ("get_channels_by_type", (getattr(unreal, "MovieSceneScriptingDoubleChannel", None),)),
                ):
                    if args and args[0] is None:
                        continue
                    found = _as_list(_safe_call(section, getter, *args))
                    label = getter if not args else f"{getter}({_safe_call(args[0], 'get_name') or args[0].__name__})"
                    getter_counts[label] = len(found)
                    for channel in found:
                        name = str(base._get_channel_name(channel))
                        channels_by_name.setdefault(name, channel)
                section_entry = {
                    "index": section_index, "range": f"[{section_start},{section_end})", "active": active,
                    "channel_getter_counts": getter_counts, "channels": [],
                }
                _log(f"  section[{section_index}] range=[{section_start},{section_end}) active={active} "
                     f"channel counts per getter={getter_counts}")
                for name, channel in sorted(channels_by_name.items()):
                    if target_norm not in base._normalize_name(name):
                        continue
                    included = (
                        track_path == validator_track_path and section_index == 0
                        and name in validator_channel_names
                    )
                    if included:
                        exclusion_reason = ""
                    elif track_path != validator_track_path:
                        exclusion_reason = "different track than validator's resolved rig track"
                    elif section_index != 0:
                        exclusion_reason = "validator only inspects section[0]"
                    else:
                        exclusion_reason = "channel name not matched by strict validator matcher"
                    keys = base._get_channel_keys(channel)
                    details = [_key_full_detail(key, ticks_local) for key in keys]
                    total_keys += len(details)
                    integer_count = sum(1 for d in details if d["integer_local"])
                    channel_entry = {
                        "channel": name, "class": _class_name(channel),
                        "included_by_validator": included, "exclusion_reason": exclusion_reason,
                        "key_count": len(details), "integer_local_count": integer_count,
                        "keys": details,
                    }
                    section_entry["channels"].append(channel_entry)
                    if not included and details:
                        excluded_channels.append((rig_class, track_name, section_index, name,
                                                  len(details), exclusion_reason))
                    for detail in details:
                        if not detail["integer_local"]:
                            non_integer_keys.append((rig_class, track_name, section_index, name, detail))
                    summary_first = details[0] if details else None
                    summary_last = details[-1] if details else None
                    _log(f"    channel {name!r} class={channel_entry['class']} keys={len(details)} "
                         f"integer_local={integer_count} included_by_validator={included}"
                         + (f" EXCLUDED: {exclusion_reason}" if not included else ""))
                    if summary_first:
                        _log(f"      first key: tick={summary_first['tick']}+{summary_first['tick_sub']} "
                             f"display={summary_first['display_frame']}+{summary_first['display_sub']} "
                             f"decimal={summary_first['decimal_display_frame']} value={summary_first['value']}")
                        _log(f"      last key:  tick={summary_last['tick']}+{summary_last['tick_sub']} "
                             f"display={summary_last['display_frame']}+{summary_last['display_sub']} "
                             f"decimal={summary_last['decimal_display_frame']} value={summary_last['value']}")
                track_entry["sections"].append(section_entry)
            dump["tracks"].append(track_entry)

        _log(f"TOTAL keys on loosely-matched {control_name!r} channels (all rigs/tracks/sections): {total_keys}")
        _log(f"keys NOT on an exact integer LOCAL display frame: {len(non_integer_keys)}")
        for rig_class, track_name, section_index, name, detail in non_integer_keys[:60]:
            _log_error(f"  NON-INTEGER key: rig={rig_class} track={track_name!r} section={section_index} "
                       f"channel={name!r} tick={detail['tick']}+{detail['tick_sub']} "
                       f"display={detail['display_frame']}+{detail['display_sub']} "
                       f"decimal={detail['decimal_display_frame']} value={detail['value']}")
        if excluded_channels:
            _log_warning(f"channels with keys the validator EXCLUDED: {len(excluded_channels)}")
            for row in excluded_channels[:30]:
                _log_warning(f"  excluded: rig={row[0]} track={row[1]!r} section={row[2]} channel={row[3]!r} "
                             f"keys={row[4]} reason: {row[5]}")
        else:
            _log("no excluded channels carry keys - validator coverage matches the stored data.")

        # ---- Part 2: local -> root time mapping through the subsequence hierarchy ----
        _log("---- subsequence time-transform analysis ----")
        target_path = str(_safe_call(sequence, "get_path_name"))
        mappings = _find_subsequence_sections(root_sequence, target_path) if root_sequence else []
        if not mappings:
            _log_warning("no SubSequence/Shot section referencing the ANM sequence was found from the root.")
        ticks_root = _ticks_per_frame(root_sequence) if root_sequence else None
        root_tick_res = _safe_call(root_sequence, "get_tick_resolution")
        local_tick_res = _safe_call(sequence, "get_tick_resolution")
        for owner, trail, track, section, _inner in mappings:
            sec_start = _safe_call(section, "get_start_frame")
            sec_end = _safe_call(section, "get_end_frame")
            params = _safe_get_editor_property(section, "parameters")
            offset = _safe_get_editor_property(params, "start_frame_offset")
            offset_ticks = getattr(offset, "value", offset)
            time_scale = _safe_get_editor_property(params, "time_scale")
            _log(f"sub section in {trail}: owner={_safe_call(owner, 'get_name')} track={_class_name(track)} "
                 f"range=[{sec_start},{sec_end}) start_frame_offset={offset_ticks} ticks "
                 f"time_scale={time_scale}")
            try:
                offset_ticks = int(offset_ticks or 0)
                scale = float(time_scale if time_scale not in (None, 0) else 1.0)
                owner_ticks_per_frame = _ticks_per_frame(owner)
                owner_res = _safe_get_editor_property(_safe_call(owner, "get_tick_resolution"), "numerator")
                local_res = _safe_get_editor_property(local_tick_res, "numerator")
                res_ratio = float(owner_res) / float(local_res) if owner_res and local_res else 1.0
                # inner_tick = (outer_tick - section_start_tick) * scale * res_ratio_inv + offset
                # => outer_tick = section_start_tick + (inner_tick - offset) / scale * res_ratio
                section_start_tick = int(sec_start) * int(owner_ticks_per_frame)
                fractional = []
                for frame in range(start_frame, end_frame):
                    inner_tick = frame * int(ticks_local)
                    outer_tick = section_start_tick + (inner_tick - offset_ticks) / scale * res_ratio
                    on_frame = abs(outer_tick % owner_ticks_per_frame) < 1e-6
                    if not on_frame:
                        fractional.append((frame, outer_tick, outer_tick / owner_ticks_per_frame))
                _log(f"  local frames {start_frame}..{end_frame - 1} -> owner-frame mapping: "
                     f"{len(fractional)} of {end_frame - start_frame} map to FRACTIONAL owner frames")
                _log(f"  example mapping: local {start_frame} -> owner tick "
                     f"{section_start_tick + (start_frame * int(ticks_local) - offset_ticks) / scale * res_ratio} "
                     f"(owner ticks/frame={owner_ticks_per_frame})")
                for frame, outer_tick, outer_frame in fractional[:10]:
                    _log_error(f"  FRACTIONAL: local frame {frame} -> owner tick {outer_tick} "
                               f"= owner display frame {outer_frame}")
            except Exception as exc:
                _log_warning(f"  could not compute mapping: {exc}")

        dump_path = os.path.join(_sidecar_dir(), "subframe_key_diagnostic.json")
        _write_json(dump_path, dump)
        _log(f"full per-key dump written to: {dump_path}")

        # ---- Verdict ----
        if non_integer_keys:
            _log_error("VERDICT A: real subframe/non-integer keys exist in LOCAL time (listed above). "
                       "The strict validator missed them for the per-channel reasons listed.")
        elif any(True for _o, _t, _tr, _s, _i in mappings) and total_keys > 0:
            _log("VERDICT: all stored keys are on exact integer LOCAL display frames. "
                 "If keys still appear between frames in the Sequencer UI, check the local->root "
                 "mapping report above (case B) or UI artifacts (case C: tangent handles / selected "
                 "curve points / the root-level SUB-SECTION bar markers rather than channel keys).")
        _log("================ PHASE diagnose_visible_subframe_keys end ================")
        return "true"
    except Exception:
        _log_error(traceback.format_exc())
        return ""


# ---------------------------------------------------------------------------
# Option B: one-button state machine ("Run Next Safe Step")
# ---------------------------------------------------------------------------

def _state_shape(capture, resolved):
    """Classify the live channel state: 'baseline', 'baked', or 'other'."""
    expected = int(capture["end_frame"]) - int(capture["start_frame"])
    actor_counts = _bundle_key_counts(resolved["actor_bundle"])
    control_counts = _bundle_key_counts(resolved["control_bundle"])
    baseline = capture.get("key_counts_before", {})
    flatten_actor = {k: actor_counts.get(k) for k in FLATTEN_KEYS}
    flatten_ctrl = {k: control_counts.get(k) for k in FLATTEN_KEYS}
    baseline_actor = {k: (baseline.get("actor") or {}).get(k) for k in FLATTEN_KEYS}
    baseline_ctrl = {k: (baseline.get("control") or {}).get(k) for k in FLATTEN_KEYS}
    if flatten_actor == baseline_actor and flatten_ctrl == baseline_ctrl:
        return "baseline", actor_counts, control_counts
    actor_static = all((actor_counts.get(k) or 0) <= 1 for k in FLATTEN_KEYS)
    ctrl_dense = all((control_counts.get(k) or 0) >= expected for k in FLATTEN_KEYS)
    if actor_static and ctrl_dense:
        return "baked", actor_counts, control_counts
    return "other", actor_counts, control_counts


def _rebase_live_check(rebase, resolved, tolerance=0.1):
    """Does the LIVE sequence actually look rebased per this sidecar? Requires the
    actor's channel transform to match the stored intended transform AND the
    control's local loc/rot at the first frame to be ~identity. Never trust the
    sidecar flag alone."""
    details = []
    intended = rebase.get("actor_after_values")
    if not intended:
        return False, ["no intended actor values stored in rebase sidecar"]
    start_frame = int(rebase["start_frame"])
    actor_values = _bundle_values_at(resolved["actor_bundle"], start_frame)
    actor_delta = max(abs(float(actor_values[k]) - float(intended[k])) for k in LOCATION_KEYS + ROTATION_KEYS)
    details.append(f"actor channel max delta vs intended: {actor_delta:.6f}")
    ctrl_values = _bundle_values_at(resolved["control_bundle"], start_frame)
    ctrl_loc_mag = (
        float(ctrl_values["location_x"]) ** 2
        + float(ctrl_values["location_y"]) ** 2
        + float(ctrl_values["location_z"]) ** 2
    ) ** 0.5
    ctrl_rot_max = max(abs(float(ctrl_values[k])) for k in ROTATION_KEYS)
    details.append(f"ctrl local at {start_frame}: loc_mag={ctrl_loc_mag:.6f} rot_max={ctrl_rot_max:.6f}")
    matches = actor_delta <= tolerance and ctrl_loc_mag <= tolerance and ctrl_rot_max <= tolerance
    return matches, details


def _clear_stale_rebase_flags():
    rebase, _error = _read_rebase_capture()
    if rebase is None:
        return
    rebase["rebased"] = False
    for stale_key in ("rebased_at", "rebase_validated_at", "rebase_id", "for_baked_at"):
        rebase.pop(stale_key, None)
    _write_rebase_capture(rebase)
    _log("cleared stale rebase-applied flags in sidecar (reference data kept).")


def _next_step_decision(global_ctrl_name="global_ctrl"):
    """Returns (step, reason). step is one of: capture, bake, validate,
    rebase_origin, validate_rebase, done, blocked."""
    sequence_path = _focused_sequence_path()
    if not sequence_path:
        return "blocked", "no Level Sequence is focused/open in Sequencer."
    capture, error = _read_capture()
    if capture is None:
        return "capture", (
            f"no capture sidecar for {sequence_path} - Diagnose + Capture is next "
            "(requires actor + skeletal bindings selected)."
        )
    resolved, error = _resolve_from_capture(capture)
    if error:
        return "blocked", error
    shape, actor_counts, control_counts = _state_shape(capture, resolved)
    if not capture.get("baked"):
        if shape == "baseline":
            return "bake", "capture exists and live state matches the captured baseline."
        return "blocked", (
            f"sidecar says not baked but live state is {shape!r} "
            f"(actor={actor_counts} control={control_counts}). Investigate / rollback / recapture."
        )
    # Sidecar says baked - but never trust flags over the live sequence. A reverted
    # asset must fall back to re-bake regardless of any validated flags.
    if shape == "baseline":
        return "bake", "sidecar says baked but live state is the baseline (asset reverted?) - re-bake."
    if shape != "baked":
        return "blocked", (
            f"unexpected live state {shape!r} after bake "
            f"(actor={actor_counts} control={control_counts}). Investigate."
        )
    if not capture.get("bake_validated_at"):
        return "validate", "bake applied but not yet validated in a settled call."
    rebase, _rebase_error = _read_rebase_capture()
    stale_note = ""
    if rebase is not None and rebase.get("rebased"):
        # Never trust the sidecar flag alone: require revision tie + live proof.
        stale_reasons = []
        if rebase.get("for_baked_at") != capture.get("baked_at"):
            stale_reasons.append(
                f"rebase sidecar is tied to bake revision {rebase.get('for_baked_at')!r} "
                f"but the current bake is {capture.get('baked_at')!r}"
            )
        live_ok, live_details = _rebase_live_check(rebase, resolved)
        if not live_ok:
            stale_reasons.append("live sequence does not match the rebased state (" + "; ".join(live_details) + ")")
        if stale_reasons:
            stale_note = (
                "STALE REBASE SIDECAR DETECTED: live sequence is still in pre-rebase baked state. "
                + " | ".join(stale_reasons)
            )
            rebase = None
    if rebase is None or not rebase.get("rebased"):
        if shape == "baked":
            reason = "bake validated; origin rebase is next."
            if stale_note:
                reason = f"{stale_note} -> clearing rebase-applied status; {reason}"
            return "rebase_origin", reason
        blocked_reason = f"expected baked state before rebase, found {shape!r}."
        if stale_note:
            blocked_reason = f"{stale_note} | {blocked_reason}"
        return "blocked", blocked_reason
    if not rebase.get("rebase_validated_at"):
        return "validate_rebase", "rebase applied (live-state verified) but not yet validated in a settled call."
    return "done", "all phases complete and validated - save the sequence asset."


def status(global_ctrl_name="global_ctrl", **_ignored):
    """Read-only: report what the next safe step would be, without running it."""
    try:
        _reload_dependencies()
        _log("================ status (read-only) ================")
        step, reason = _next_step_decision(global_ctrl_name)
        _log(f"NEXT SAFE STEP: {step}")
        _log(f"REASON: {reason}")
        _log("====================================================")
        return step
    except Exception:
        _log_error(traceback.format_exc())
        return ""


def run_next_safe_step(global_ctrl_name="global_ctrl", **_ignored):
    """Option B single-button flow: advances exactly one phase per call, chosen
    from the sidecar + live channel state. Never runs two destructive phases in
    one call; validation always happens on a later click (separate editor call)."""
    try:
        _reload_dependencies()
        _log("================ run_next_safe_step ================")
        step, reason = _next_step_decision(global_ctrl_name)
        _log(f"decided step: {step} ({reason})")
        if step == "blocked":
            _log_error(reason)
            return ""
        if step == "done":
            _log("Nothing left to do. Save the sequence asset (phase='save') and scrub to confirm.")
            return "true"
        if step == "capture":
            if diagnose(global_ctrl_name=global_ctrl_name) != "true":
                return ""
            return capture_original(global_ctrl_name=global_ctrl_name)
        if step == "bake":
            return bake_flattened()
        if step == "validate":
            return validate_settled()
        if step == "rebase_origin":
            if "STALE REBASE SIDECAR DETECTED" in reason:
                _log_warning("STALE REBASE SIDECAR DETECTED: live sequence is still in pre-rebase baked state. "
                             "Clearing rebase-applied status.")
                _clear_stale_rebase_flags()
            return rebase_origin()
        if step == "validate_rebase":
            return validate_rebase_settled()
        _log_error(f"unknown step {step!r}")
        return ""
    except Exception:
        _log_error(traceback.format_exc())
        return ""


def save_sequence(**_ignored):
    """Save the sidecar's sequence asset (falls back to the focused sequence)."""
    try:
        _reload_dependencies()
        _log("================ PHASE save start ================")
        capture, _error = _read_capture()
        sequence_path = (capture or {}).get("sequence_asset_path") or _focused_sequence_path()
        if not sequence_path:
            _log_error("no sequence to save.")
            return ""
        package_path = sequence_path.split(".")[0]
        saved = _safe_call(getattr(unreal, "EditorAssetLibrary", None), "save_asset", package_path, False)
        _log(f"save_asset({package_path}) -> {saved}")
        if not saved:
            _log_error(
                "SAVE FAILED. Most common cause here: another (possibly windowless/zombie) UnrealEditor "
                "process holding the file - check the log for 'Error Code 32' sharing violations."
            )
            return ""
        if capture is not None:
            capture["saved_at"] = _time.strftime("%Y-%m-%d %H:%M:%S")
            _write_capture(capture)
        _log("SAVE DONE. The current state is now on disk.")
        _log("================ PHASE save end ================")
        return "true"
    except Exception:
        _log_error(traceback.format_exc())
        return ""


# ---------------------------------------------------------------------------
# Cleanup of tool-generated backup Level Sequence assets (extremely conservative)
# ---------------------------------------------------------------------------

def _package_of(path):
    return str(path).split(".")[0]


def _unique_backup_destination(package, kind):
    """Collision-proof backup asset path: timestamp plus _NNN suffix if an asset
    with that name already exists (second-resolution timestamps can collide)."""
    base_name = f"{package}_{kind}_{_time.strftime('%Y%m%d_%H%M%S')}"
    eal = getattr(unreal, "EditorAssetLibrary", None)
    destination = base_name
    suffix = 0
    while _safe_call(eal, "does_asset_exist", destination):
        suffix += 1
        destination = f"{base_name}_{suffix:03d}"
    return destination


def _package_is_dirty(package_path):
    utils = getattr(unreal, "EditorLoadingAndSavingUtils", None)
    for package in _as_list(_safe_call(utils, "get_dirty_content_packages")):
        if str(_safe_call(package, "get_name")) == package_path:
            return True
    return False


def _gather_backup_candidates(capture, rebase):
    """Identify backup assets created by THIS tool for THIS exact sequence.
    Positive identification requires: recorded in a sidecar manifest, OR an exact
    <SequenceName>_Pre(Flatten|Rebase)Backup_<YYYYMMDD_HHMMSS> name for this
    sequence - AND the asset must load as a LevelSequence. The focused/original
    sequence itself is never a candidate. Returns (candidates, rejected)."""
    package = _package_of(capture["sequence_asset_path"])
    folder, sequence_name = package.rsplit("/", 1)
    recorded = set()
    for sidecar in (capture, rebase or {}):
        for path in _as_list(sidecar.get("backup_manifest")) + [sidecar.get("backup_asset_path")]:
            if path:
                recorded.add(_package_of(path))
    pattern = re.compile(re.escape(sequence_name) + r"_Pre(?:Flatten|Rebase)Backup_\d{8}_\d{6}(?:_\d{3})?$")
    eal = getattr(unreal, "EditorAssetLibrary", None)
    assets = _as_list(_safe_call(eal, "list_assets", folder, False, False))
    candidates, rejected = [], []
    for asset_path in assets:
        pkg = _package_of(asset_path)
        name = pkg.rsplit("/", 1)[1]
        if pkg == package:
            continue  # the production sequence itself - never a candidate
        in_manifest = pkg in recorded
        matches_pattern = bool(pattern.fullmatch(name))
        if not in_manifest and not matches_pattern:
            if "Backup" in name or sequence_name in name:
                rejected.append((pkg, "not in any sidecar manifest and does not match this tool's exact "
                                      "backup naming for this sequence"))
            continue
        asset = _safe_call(eal, "load_asset", pkg)
        if asset is None or not isinstance(asset, getattr(unreal, "LevelSequence", ())):
            rejected.append((pkg, f"matched by name/manifest but is not a loadable LevelSequence "
                                  f"(class={_class_name(asset)})"))
            continue
        reasons = []
        if in_manifest:
            reasons.append("recorded in sidecar backup manifest")
        if matches_pattern:
            reasons.append("exact tool backup naming for this sequence")
        candidates.append((pkg, "; ".join(reasons)))
    return candidates, rejected


def _cleanup_gates(capture, rebase):
    gates = []
    gates.append(("bake validated", bool(capture.get("baked") and capture.get("bake_validated_at")),
                  f"baked={capture.get('baked')} bake_validated_at={capture.get('bake_validated_at')}"))
    if rebase is not None and rebase.get("rebased"):
        gates.append(("rebase validated", bool(rebase.get("rebase_validated_at")),
                      f"rebase_validated_at={rebase.get('rebase_validated_at')}"))
    else:
        gates.append(("rebase validated", True, "rebase not applied (not required)"))
    gates.append(("key times validated", bool(capture.get("key_times_validated_at")),
                  f"key_times_validated_at={capture.get('key_times_validated_at')}"))
    package = _package_of(capture["sequence_asset_path"])
    dirty = _package_is_dirty(package)
    gates.append(("sequence saved", bool(capture.get("saved_at")) and not dirty,
                  f"saved_at={capture.get('saved_at')} package_dirty={dirty}"))
    return gates


def cleanup_preview(**_ignored):
    """Read-only: list backup-cleanup candidates with reasons, rejected lookalikes
    with reasons, and the current state of every cleanup gate. Deletes nothing."""
    try:
        _reload_dependencies()
        _log("================ PHASE cleanup_preview start (read-only) ================")
        capture, error = _read_capture()
        if capture is None:
            _log_error(error)
            return ""
        rebase, _rebase_error = _read_rebase_capture()
        candidates, rejected = _gather_backup_candidates(capture, rebase)
        gates = _cleanup_gates(capture, rebase)
        _log(f"target sequence: {capture['sequence_asset_path']}")
        _log(f"cleanup gates (all must pass before phase='cleanup' will delete):")
        for gate_name, ok, detail in gates:
            _log(f"  [{'PASS' if ok else 'FAIL'}] {gate_name}: {detail}")
        _log(f"candidates for deletion: {len(candidates)}")
        for pkg, reason in candidates:
            _log(f"  CANDIDATE {pkg}")
            _log(f"    reason: {reason}")
        _log(f"rejected lookalikes: {len(rejected)}")
        for pkg, reason in rejected:
            _log(f"  REJECTED {pkg}")
            _log(f"    reason: {reason}")
        _log("Nothing was modified. Run phase='cleanup' to delete the candidates above (after all gates pass).")
        _log("================ PHASE cleanup_preview end ================")
        return "true"
    except Exception:
        _log_error(traceback.format_exc())
        return ""


def cleanup(delete_sidecars=False, **_ignored):
    """Delete tool-generated backup LevelSequence assets for the focused sequence.
    Refuses unless every gate passes (bake validated, rebase validated when used,
    key times validated, sequence saved). Sidecar JSONs are kept unless
    delete_sidecars=True."""
    try:
        _reload_dependencies()
        _log("================ PHASE cleanup start ================")
        capture, error = _read_capture()
        if capture is None:
            _log_error(error)
            return ""
        rebase, _rebase_error = _read_rebase_capture()
        gates = _cleanup_gates(capture, rebase)
        failed_gates = [g for g in gates if not g[1]]
        for gate_name, ok, detail in gates:
            _log(f"  gate [{'PASS' if ok else 'FAIL'}] {gate_name}: {detail}")
        if failed_gates:
            _log_error(f"CLEANUP REFUSED: {len(failed_gates)} gate(s) failed: "
                       f"{[g[0] for g in failed_gates]}. Nothing was deleted.")
            return ""
        candidates, rejected = _gather_backup_candidates(capture, rebase)
        for pkg, reason in rejected:
            _log(f"  skipping (rejected): {pkg} - {reason}")
        if not candidates:
            _log("no tool-generated backup assets found for this sequence; nothing to delete.")
            _log("================ PHASE cleanup end ================")
            return "true"
        _log(f"deleting {len(candidates)} backup asset(s):")
        for pkg, reason in candidates:
            _log(f"  WILL DELETE {pkg} ({reason})")
        eal = getattr(unreal, "EditorAssetLibrary", None)
        failures = []
        for pkg, _reason in candidates:
            deleted = _safe_call(eal, "delete_asset", pkg)
            still_exists = bool(_safe_call(eal, "does_asset_exist", pkg))
            if deleted and not still_exists:
                _log(f"  DELETED {pkg} (verified gone)")
            else:
                failures.append(pkg)
                _log_error(f"  FAILED to delete {pkg} (delete_asset={deleted} still_exists={still_exists})")
        if failures:
            _log_error(f"CLEANUP INCOMPLETE: {len(failures)} backup(s) remain: {failures}")
            return ""
        if delete_sidecars:
            for path in (_capture_path_for(capture), _rebase_path_for(capture)):
                if os.path.isfile(path):
                    try:
                        os.remove(path)
                        _log(f"deleted sidecar {path}")
                    except Exception as exc:
                        _log_error(f"could not delete sidecar {path}: {exc}")
        else:
            _log("sidecar JSONs kept (delete_sidecars=False).")
        _log("CLEANUP COMPLETE: all identified tool-generated backups deleted and verified gone. "
             "Animation was not modified.")
        _log("================ PHASE cleanup end ================")
        return "true"
    except Exception:
        _log_error(traceback.format_exc())
        return ""


# ---------------------------------------------------------------------------
# PHASE 0: verify (plumbing check - proves the widget actually executes Python)
# ---------------------------------------------------------------------------

def verify(**kwargs):
    """Read-only plumbing check. Writes no files, touches no animation, does not
    resolve context. If this does not log, the widget is not executing this module."""
    try:
        _log("================ PHASE verify start ================")
        _log(f"MODULE FILE: {__file__}")
        _log(f"run() exists: {callable(run)} | available phases: {sorted(_PHASES)}")
        _log(f"received kwargs: {kwargs}")
        library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
        focused = _safe_call(library, "get_focused_level_sequence")
        current = _safe_call(library, "get_current_level_sequence")
        _log(f"focused sequence: {_safe_call(focused, 'get_name') or '<none>'}")
        _log(f"open (root) sequence: {_safe_call(current, 'get_name') or '<none>'}")
        selected_bindings = [attach_base._binding_name(b) for b in attach_base._get_selected_bindings()]
        _log(f"selected Sequencer bindings: {selected_bindings}")
        _log(f"selected level actors: {[attach_base._object_name(a) for a in attach_base._get_selected_level_actors()]}")
        _log("VERIFY RESULT: Python execution path is working. No files written, no animation touched.")
        _log("================ PHASE verify end ================")
        return "true"
    except Exception:
        _log_error(traceback.format_exc())
        return ""


# ---------------------------------------------------------------------------
# Widget-friendly dispatcher
# ---------------------------------------------------------------------------

_PHASES = {
    "verify": verify,
    "diagnose": diagnose,
    "capture": capture_original,
    "capture_original": capture_original,
    "bake": bake_flattened,
    "bake_flattened": bake_flattened,
    "validate": validate_settled,
    "validate_settled": validate_settled,
    "rollback": rollback,
    "diagnose_rebase": diagnose_rebase_origin,
    "diagnose_rebase_origin": diagnose_rebase_origin,
    "rebase": rebase_origin,
    "rebase_origin": rebase_origin,
    "validate_rebase": validate_rebase_settled,
    "validate_rebase_settled": validate_rebase_settled,
    "rollback_rebase": rollback_rebase_origin,
    "rollback_rebase_origin": rollback_rebase_origin,
    "status": status,
    "next": run_next_safe_step,
    "next_step": run_next_safe_step,
    "run_next_safe_step": run_next_safe_step,
    "save": save_sequence,
    "save_sequence": save_sequence,
    "validate_key_times": validate_key_times,
    "cleanup_preview": cleanup_preview,
    "cleanup": cleanup,
    "diagnose_visible_subframe_keys": diagnose_visible_subframe_keys,
}


def run(phase="diagnose", **kwargs):
    _log(f"run() called with phase={phase!r} kwargs_keys={sorted(kwargs)}")
    fn = _PHASES.get(str(phase).strip().lower())
    if fn is None:
        _log_error(f"unknown phase {phase!r}. Valid: {sorted(_PHASES)}")
        return ""
    return fn(**kwargs)


def reload_and_run(**kwargs):
    return run(**kwargs)
