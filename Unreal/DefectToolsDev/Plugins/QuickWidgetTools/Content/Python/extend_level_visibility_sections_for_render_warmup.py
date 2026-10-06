import importlib

import unreal

import render_warmup_section_utils as _utils


importlib.reload(_utils)

LOG_PREFIX = "[ExtendLevelVisibilityWarmup]"


def _log(message):
    _utils.log(LOG_PREFIX, message)


def _log_warning(message):
    _utils.log_warning(LOG_PREFIX, message)


def _get_level_visibility_tracks(sequence):
    level_visibility_track_class = getattr(unreal, "MovieSceneLevelVisibilityTrack", None)
    if level_visibility_track_class:
        tracks = _utils.find_tracks(sequence, level_visibility_track_class)
        if tracks:
            return tracks

    # Fallback for engine/API differences.
    tracks = []
    for getter_name in ("get_master_tracks", "get_tracks"):
        getter = getattr(sequence, getter_name, None)
        if not callable(getter):
            continue
        try:
            all_tracks = list(getter() or [])
        except Exception:
            continue
        for track in all_tracks:
            if "LevelVisibility" in _utils.get_class_name(track):
                tracks.append(track)
    return tracks


def _extend_level_visibility_sections_in_sequence(sequence, handle_frames):
    playback_start = _utils.get_playback_start(sequence)
    target_start = playback_start - int(handle_frames)
    changed = False
    checked_sections = 0
    updated_sections = 0

    for track in _get_level_visibility_tracks(sequence):
        try:
            sections = list(track.get_sections() or [])
        except Exception as exc:
            _log_warning(f"Could not read Level Visibility track sections in {_utils.asset_key(sequence)}: {exc}")
            continue

        for section in sections:
            checked_sections += 1
            current_start, _current_end = _utils.get_section_start_end(section)
            if not _utils.should_extend_section_start(current_start, playback_start, target_start):
                continue

            if _utils.extend_section_start(section, target_start, "LevelVisibility", LOG_PREFIX):
                changed = True
                updated_sections += 1

    if checked_sections or updated_sections:
        _log(
            f"Sequence Level Visibility sections checked={checked_sections}, updated={updated_sections}, "
            f"playback_start={playback_start}, target_start={target_start}: {_utils.asset_key(sequence)}"
        )

    return changed, checked_sections, updated_sections


def run(shot_name_array, handle_frames=_utils.DEFAULT_HANDLE_FRAMES):
    handle_frames = _utils.coerce_handle_frames(handle_frames)
    shot_names = _utils.coerce_shot_name_list(shot_name_array)

    result = {
        "success": True,
        "shots_checked": len(shot_names),
        "shots_missing": [],
        "sequences_checked": 0,
        "level_visibility_sections_checked": 0,
        "level_visibility_sections_updated": 0,
        "sequences_saved": 0,
        "save_failures": [],
        "handle_frames": handle_frames,
        "message": "",
    }

    if not shot_names:
        result["success"] = False
        result["message"] = "No shot names were provided."
        return _utils.format_summary(result)

    for shot_name in shot_names:
        shot_sequence, shot_object_path = _utils.resolve_shot_sequence(shot_name, LOG_PREFIX)
        if not shot_sequence:
            result["shots_missing"].append(shot_name)
            continue

        sequences = _utils.collect_shot_sequences(shot_sequence, shot_object_path, LOG_PREFIX)
        for sequence in sequences:
            result["sequences_checked"] += 1
            changed, checked_sections, updated_sections = _extend_level_visibility_sections_in_sequence(sequence, handle_frames)
            result["level_visibility_sections_checked"] += checked_sections
            result["level_visibility_sections_updated"] += updated_sections

            if changed:
                if _utils.save_if_changed(sequence, True, LOG_PREFIX):
                    result["sequences_saved"] += 1
                else:
                    result["save_failures"].append(_utils.asset_key(sequence))

    if result["shots_missing"] or result["save_failures"]:
        result["success"] = False

    result["message"] = (
        f"Extended {result['level_visibility_sections_updated']} Level Visibility section(s) by {handle_frames} frame(s)."
    )
    return _utils.format_summary(result)
