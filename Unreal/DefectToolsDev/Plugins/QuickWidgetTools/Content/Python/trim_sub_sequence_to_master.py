import importlib

import unreal

import render_warmup_section_utils as _utils
import set_frame_range


importlib.reload(_utils)
importlib.reload(set_frame_range)

LOG_PREFIX = "[TrimSubSequenceToMaster]"


def _log(message):
    _utils.log(LOG_PREFIX, message)


def _log_warning(message):
    _utils.log_warning(LOG_PREFIX, message)


def _collect_subsequence_assets(master_sequence):
    sections = []
    try:
        sections = list(set_frame_range._master_subsections(master_sequence) or [])
    except Exception as exc:
        _log_warning(f"Could not collect subsequence sections in {_utils.asset_key(master_sequence)}: {exc}")
        return []

    assets = []
    seen = set()
    for section in sections:
        child_sequence = set_frame_range._get_subsequence_from_section(section)
        if not child_sequence:
            continue
        key = _utils.asset_key(child_sequence)
        if key in seen:
            continue
        seen.add(key)
        assets.append(child_sequence)
    return assets


def _clamp_camera_cut_sections(sequence, start_frame, end_frame):
    try:
        tracks = list(sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack) or [])
    except Exception as exc:
        _log_warning(f"Could not query CameraCut tracks in {_utils.asset_key(sequence)}: {exc}")
        return False, 0, 0

    changed = False
    sections_checked = 0
    sections_updated = 0

    for track in tracks:
        try:
            sections = list(track.get_sections() or [])
        except Exception:
            continue

        _log(f"CameraCut track '{_utils.name(track)}' sections={len(sections)} in {_utils.asset_key(sequence)}")

        for section in sections:
            sections_checked += 1
            try:
                current_start = int(section.get_start_frame())
                current_end = int(section.get_end_frame())
            except Exception:
                current_start = None
                current_end = None

            if current_start == start_frame and current_end == end_frame:
                continue

            try:
                section.set_range(start_frame, end_frame)
            except Exception as exc:
                _log_warning(f"Failed to clamp CameraCut section {_utils.name(section)} in {_utils.asset_key(sequence)}: {exc}")
                continue

            _log(f"Clamped CameraCut section {_utils.name(section)} {current_start}->{current_end} became {start_frame}->{end_frame}")
            changed = True
            sections_updated += 1

    if tracks:
        _log(f"CameraCut tracks checked in {_utils.name(sequence)}: {len(tracks)}; sections updated={sections_updated}")

    return changed, len(tracks), sections_updated


def _save_unique_assets(assets):
    saved = 0
    failures = []
    seen = set()
    for asset in assets:
        key = _utils.asset_key(asset)
        if key in seen:
            continue
        seen.add(key)
        try:
            if unreal.EditorAssetLibrary.save_loaded_asset(asset):
                saved += 1
                _log(f"Saved asset: {key}")
            else:
                failures.append(key)
                _log_warning(f"Failed to save asset: {key}")
        except Exception as exc:
            failures.append(key)
            _log_warning(f"Failed to save asset {key}: {exc}")
    return saved, failures


def run(shot_name_array):
    shot_names = _utils.coerce_shot_name_list(shot_name_array)
    result = {
        "success": True,
        "shots_checked": len(shot_names),
        "shots_missing": [],
        "subsequence_assets_checked": 0,
        "camera_cut_tracks_checked": 0,
        "camera_cut_sections_updated": 0,
        "assets_saved": 0,
        "save_failures": [],
        "message": "",
    }

    if not shot_names:
        result["success"] = False
        result["message"] = "No shot names were provided."
        return _utils.format_summary(result)

    for shot_name in shot_names:
        master_sequence, _shot_path = _utils.resolve_shot_sequence(shot_name, LOG_PREFIX)
        if not master_sequence:
            result["shots_missing"].append(shot_name)
            continue

        master_start = int(master_sequence.get_playback_start())
        master_end = int(master_sequence.get_playback_end())
        _log(f"Trimming CameraCut sections for shot {shot_name} to master range {master_start}->{master_end}")

        assets_to_save = []
        subsequences = _collect_subsequence_assets(master_sequence)
        result["subsequence_assets_checked"] += len(subsequences)
        _log(f"Referenced subsequence assets found: {len(subsequences)}")

        for subsequence in subsequences:
            changed, tracks_checked, sections_updated = _clamp_camera_cut_sections(
                subsequence,
                master_start,
                master_end,
            )
            result["camera_cut_tracks_checked"] += tracks_checked
            result["camera_cut_sections_updated"] += sections_updated
            if changed:
                assets_to_save.append(subsequence)

        saved, failures = _save_unique_assets(assets_to_save)
        result["assets_saved"] += saved
        result["save_failures"].extend(failures)

    if result["shots_missing"] or result["save_failures"]:
        result["success"] = False

    result["message"] = (
        f"Trimmed CameraCut sections for {len(shot_names)} shot(s). "
        f"CameraCut sections updated={result['camera_cut_sections_updated']}."
    )
    summary = _utils.format_summary(result)
    _log(summary)
    return summary
