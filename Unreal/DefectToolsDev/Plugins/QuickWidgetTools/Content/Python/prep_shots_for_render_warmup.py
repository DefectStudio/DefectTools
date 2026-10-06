import importlib

import unreal

import render_warmup_section_utils as _utils
import set_frame_range


importlib.reload(_utils)
importlib.reload(set_frame_range)

LOG_PREFIX = "[PrepShotsRenderWarmup]"


def _log(message):
    _utils.log(LOG_PREFIX, message)


def _warn(message):
    _utils.log_warning(LOG_PREFIX, message)


def _to_int(value):
    try:
        return int(value)
    except Exception:
        return 0


def _playback_end(sequence):
    try:
        return int(sequence.get_playback_end())
    except Exception:
        return _utils.get_playback_start(sequence) + 1


def _range_or_master(section, master_start, master_end):
    start_frame, end_frame = _utils.get_section_start_end(section)
    if start_frame is None:
        start_frame = master_start
    if end_frame is None:
        end_frame = master_end
    return start_frame, end_frame


def _set_child_playback(sequence, start_frame, end_frame):
    try:
        current_start = int(sequence.get_playback_start())
        current_end = int(sequence.get_playback_end())
    except Exception:
        return False
    if current_start == start_frame and current_end == end_frame:
        return False
    try:
        if sequence.is_playback_range_locked():
            sequence.set_playback_range_locked(False)
    except Exception:
        pass
    try:
        sequence.set_playback_start(start_frame)
        sequence.set_playback_end(end_frame)
    except Exception as exc:
        _warn(f"Failed to set playback range for {_utils.asset_key(sequence)}: {exc}")
        return False
    _log(f"Playback updated for {_utils.asset_key(sequence)}: {current_start}->{current_end} became {start_frame}->{end_frame}")
    return True


def _extend_track_sections(sequence, track_type_name, label, start_frame, end_frame):
    track_type = getattr(unreal, track_type_name, None)
    if not track_type:
        return False
    try:
        return bool(set_frame_range._extend_track_sections(sequence, track_type, label, start_frame, end_frame))
    except Exception as exc:
        _warn(f"Failed to extend {label} in {_utils.asset_key(sequence)}: {exc}")
        return False


def _is_spawn_track(track):
    track_type = getattr(unreal, "MovieSceneSpawnTrack", None)
    if track_type:
        try:
            if isinstance(track, track_type):
                return True
        except Exception:
            pass
    return "SpawnTrack" in _utils.get_class_name(track)


def _spawn_bindings(sequence):
    getter = getattr(sequence, "get_spawnables", None)
    if not callable(getter):
        return []
    try:
        return list(getter() or [])
    except Exception:
        return []


def _binding_tracks(binding):
    getter = getattr(binding, "get_tracks", None)
    if not callable(getter):
        return []
    try:
        return list(getter() or [])
    except Exception:
        return []


def _extend_spawn_sections(sequence, warmup_start, master_start, master_end):
    changed = False
    checked = 0
    updated = 0
    for binding in _spawn_bindings(sequence):
        binding_name = _utils.name(binding)
        for track in _binding_tracks(binding):
            if not _is_spawn_track(track):
                continue
            try:
                sections = list(track.get_sections() or [])
            except Exception:
                continue
            for section in sections:
                checked += 1
                current_start, current_end = _range_or_master(section, master_start, master_end)
                if current_start <= warmup_start or current_end <= master_start:
                    continue
                if current_start > master_start + _utils.START_TOLERANCE_FRAMES:
                    continue
                try:
                    section.set_range(warmup_start, current_end)
                except Exception as exc:
                    _warn(f"Failed to extend spawn section for {binding_name}: {exc}")
                    continue
                _log(f"Extended Spawn/{binding_name} {current_start}->{current_end} became {warmup_start}->{current_end}")
                changed = True
                updated += 1
    if checked or updated:
        _log(f"Spawn binding sections checked={checked}, updated={updated} in {_utils.asset_key(sequence)}")
    return changed


def _zero_subsection_offsets(section):
    try:
        if set_frame_range._zero_subsection_offsets(section):
            return True
    except Exception:
        pass
    return False


def _extend_subsections(sequence, warmup_start, master_start, master_end):
    changed = False
    checked = 0
    updated = 0
    zeroed = 0
    for section in set_frame_range._master_subsections(sequence):
        checked += 1
        current_start, current_end = _range_or_master(section, master_start, master_end)
        if _zero_subsection_offsets(section):
            changed = True
            zeroed += 1
        if current_end <= master_start:
            continue
        if current_start > master_start + _utils.START_TOLERANCE_FRAMES:
            continue
        if current_start == warmup_start and current_end == master_end:
            continue
        try:
            section.set_range(warmup_start, master_end)
        except Exception as exc:
            _warn(f"Failed to extend SubSequence section {_utils.name(section)}: {exc}")
            continue
        child = set_frame_range._get_subsequence_from_section(section)
        child_name = _utils.name(child) if child else "None"
        _log(f"Extended SubSequence/{child_name} {current_start}->{current_end} became {warmup_start}->{master_end}; offsets zeroed")
        changed = True
        updated += 1
    if checked or updated or zeroed:
        _log(f"SubSequence sections checked={checked}, updated={updated}, offsets_zeroed={zeroed} in {_utils.asset_key(sequence)}")
    return changed


def _prep_one_sequence(sequence, warmup_start, master_start, master_end, set_playback):
    changed = False
    if set_playback and _set_child_playback(sequence, warmup_start, master_end):
        changed = True
    if _extend_subsections(sequence, warmup_start, master_start, master_end):
        changed = True
    if _extend_spawn_sections(sequence, warmup_start, master_start, master_end):
        changed = True
    for track_type_name, label in (("MovieSceneCameraCutTrack", "CameraCut"), ("MovieSceneLevelVisibilityTrack", "LevelVisibility")):
        if _extend_track_sections(sequence, track_type_name, label, warmup_start, master_end):
            changed = True
    if changed:
        _log(f"Prepared warmup sections in {_utils.asset_key(sequence)}: {warmup_start}->{master_end}")
    return changed


def _prep_sequences(shot_names, handle_frames):
    result = {
        "success": True,
        "shots_checked": len(shot_names),
        "shots_missing": [],
        "sequences_checked": 0,
        "sequences_saved": 0,
        "save_failures": [],
        "handle_frames": handle_frames,
        "message": "",
    }
    for shot_name in shot_names:
        shot_sequence, shot_path = _utils.resolve_shot_sequence(shot_name, LOG_PREFIX)
        if not shot_sequence:
            result["shots_missing"].append(shot_name)
            continue
        master_start = _utils.get_playback_start(shot_sequence)
        master_end = _playback_end(shot_sequence)
        warmup_start = master_start - int(handle_frames)
        master_key = _utils.asset_key(shot_sequence)
        for sequence in _utils.collect_shot_sequences(shot_sequence, shot_path, LOG_PREFIX):
            result["sequences_checked"] += 1
            set_playback = _utils.asset_key(sequence) != master_key
            if not _prep_one_sequence(sequence, warmup_start, master_start, master_end, set_playback):
                continue
            if _utils.save_if_changed(sequence, True, LOG_PREFIX):
                result["sequences_saved"] += 1
            else:
                result["save_failures"].append(_utils.asset_key(sequence))
    if result["shots_missing"] or result["save_failures"]:
        result["success"] = False
    result["message"] = f"Prepared {result['sequences_saved']} sequence(s) for render warmup."
    return result


def run(shot_name_array, handle=_utils.DEFAULT_HANDLE_FRAMES, handle_frames=None):
    if handle_frames is not None:
        handle = handle_frames
    handle_frames = _utils.coerce_handle_frames(handle)
    shot_names = _utils.coerce_shot_name_list(shot_name_array)
    if not shot_names:
        return "success=0;message=No shot names were provided."
    _log(f"Preparing {len(shot_names)} shot(s) for render warmup. handle={handle_frames}; shots={shot_names}")
    prep_result = _prep_sequences(shot_names, handle_frames)
    result = {
        "success": bool(prep_result.get("success")),
        "shots_checked": len(shot_names),
        "handle": handle_frames,
        "handle_frames": handle_frames,
        "sequences_checked": _to_int(prep_result.get("sequences_checked", 0)),
        "sequences_saved": _to_int(prep_result.get("sequences_saved", 0)),
        "save_failures": prep_result.get("save_failures", []),
        "shots_missing": prep_result.get("shots_missing", []),
        "message": prep_result.get("message", ""),
    }
    summary = _utils.format_summary(result)
    _log(summary)
    return summary
