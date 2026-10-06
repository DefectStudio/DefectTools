import importlib

import unreal

import render_warmup_section_utils as _utils


importlib.reload(_utils)

LOG_PREFIX = "[ExtendActorLifetimeWarmup]"


def _log(message):
    _utils.log(LOG_PREFIX, message)


def _log_warning(message):
    _utils.log_warning(LOG_PREFIX, message)


def _is_lifetime_track(track):
    track_class = getattr(unreal, "MovieSceneSpawnTrack", None)
    if track_class:
        try:
            if isinstance(track, track_class):
                return True
        except Exception:
            pass
    return "SpawnTrack" in _utils.get_class_name(track)


def _get_spawnable_bindings(sequence):
    getter = getattr(sequence, "get_spawnables", None)
    if not callable(getter):
        return []
    try:
        return list(getter() or [])
    except Exception:
        return []


def _get_binding_tracks(binding):
    getter = getattr(binding, "get_tracks", None)
    if not callable(getter):
        return []
    try:
        return list(getter() or [])
    except Exception:
        return []


def _should_extend(current_start, current_end, playback_start, target_start):
    if current_start is None or current_end is None:
        return False, "missing_range"
    if current_start <= target_start:
        return False, "already_before_target"
    if current_end <= playback_start:
        return False, "ends_before_shot_start"
    if current_start <= playback_start + _utils.START_TOLERANCE_FRAMES:
        return True, "starts_at_shot_start"
    return False, "starts_after_shot_start"


def _extend_sections_in_sequence(sequence, handle_frames):
    playback_start = _utils.get_playback_start(sequence)
    target_start = playback_start - int(handle_frames)
    changed = False
    checked = 0
    updated = 0

    for binding in _get_spawnable_bindings(sequence):
        binding_name = _utils.name(binding)
        for track in _get_binding_tracks(binding):
            if not _is_lifetime_track(track):
                continue
            try:
                sections = list(track.get_sections() or [])
            except Exception as exc:
                _log_warning(f"Could not read lifetime sections for binding '{binding_name}' in {_utils.asset_key(sequence)}: {exc}")
                continue

            for section in sections:
                checked += 1
                current_start, current_end = _utils.get_section_start_end(section)
                should_extend, reason = _should_extend(current_start, current_end, playback_start, target_start)
                _log(
                    f"Lifetime section: binding='{binding_name}', section='{_utils.name(section)}', "
                    f"range={current_start}->{current_end}, playback_start={playback_start}, "
                    f"target_start={target_start}, should_extend={should_extend}, reason={reason}, "
                    f"sequence={_utils.asset_key(sequence)}"
                )
                if not should_extend:
                    continue
                if _utils.extend_section_start(section, target_start, f"ActorLifetime/{binding_name}", LOG_PREFIX):
                    changed = True
                    updated += 1

    if checked or updated:
        _log(
            f"Sequence actor lifetime sections checked={checked}, updated={updated}, "
            f"playback_start={playback_start}, target_start={target_start}: {_utils.asset_key(sequence)}"
        )

    return changed, checked, updated


def run(shot_name_array, handle_frames=_utils.DEFAULT_HANDLE_FRAMES):
    handle_frames = _utils.coerce_handle_frames(handle_frames)
    shot_names = _utils.coerce_shot_name_list(shot_name_array)

    result = {
        "success": True,
        "shots_checked": len(shot_names),
        "shots_missing": [],
        "sequences_checked": 0,
        "actor_lifetime_sections_checked": 0,
        "actor_lifetime_sections_updated": 0,
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
            changed, checked, updated = _extend_sections_in_sequence(sequence, handle_frames)
            result["actor_lifetime_sections_checked"] += checked
            result["actor_lifetime_sections_updated"] += updated
            if changed:
                if _utils.save_if_changed(sequence, True, LOG_PREFIX):
                    result["sequences_saved"] += 1
                else:
                    result["save_failures"].append(_utils.asset_key(sequence))

    if result["shots_missing"] or result["save_failures"]:
        result["success"] = False

    result["message"] = f"Extended {result['actor_lifetime_sections_updated']} actor lifetime section(s) by {handle_frames} frame(s)."
    return _utils.format_summary(result)
