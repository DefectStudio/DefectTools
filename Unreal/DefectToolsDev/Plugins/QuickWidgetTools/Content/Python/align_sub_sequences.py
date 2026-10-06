import importlib

import unreal

import render_warmup_section_utils as _utils
import set_frame_range


importlib.reload(_utils)
importlib.reload(set_frame_range)

LOG_PREFIX = "[AlignSubSequences]"


def _log(message):
    _utils.log(LOG_PREFIX, message)


def _log_warning(message):
    _utils.log_warning(LOG_PREFIX, message)


def _set_sequence_playback_range(sequence, start_frame, end_frame):
    try:
        current_start = int(sequence.get_playback_start())
        current_end = int(sequence.get_playback_end())
    except Exception as exc:
        _log_warning(f"Could not read playback range for {_utils.asset_key(sequence)}: {exc}")
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
        _log_warning(f"Failed to set playback range for {_utils.asset_key(sequence)}: {exc}")
        return False

    _log(f"Playback range aligned for {_utils.asset_key(sequence)}: {current_start}->{current_end} became {start_frame}->{end_frame}")
    return True


def _set_section_range(section, start_frame, end_frame):
    try:
        current_start = int(section.get_start_frame())
        current_end = int(section.get_end_frame())
    except Exception:
        current_start = None
        current_end = None

    if current_start == start_frame and current_end == end_frame:
        return False

    try:
        section.set_range(start_frame, end_frame)
    except Exception as exc:
        _log_warning(f"Failed to set subsection range on {_utils.name(section)}: {exc}")
        return False

    _log(f"Subsection range aligned: {_utils.name(section)} {current_start}->{current_end} became {start_frame}->{end_frame}")
    return True


def _zero_subsection_offsets(section):
    try:
        return bool(set_frame_range._zero_subsection_offsets(section))
    except Exception as exc:
        _log_warning(f"Failed to zero subsection offsets on {_utils.name(section)}: {exc}")
        return False


def _collect_subsequence_sections(master_sequence):
    try:
        return list(set_frame_range._master_subsections(master_sequence) or [])
    except Exception as exc:
        _log_warning(f"Could not collect subsequence sections in {_utils.asset_key(master_sequence)}: {exc}")
        return []


def _align_master_subsections(master_sequence, start_frame, end_frame):
    sections = _collect_subsequence_sections(master_sequence)
    changed = False
    sections_updated = 0
    offsets_zeroed = 0
    updated_assets = []
    seen_assets = set()

    _log(f"Subsections found in {_utils.asset_key(master_sequence)}: {len(sections)}")

    for section in sections:
        if _set_section_range(section, start_frame, end_frame):
            changed = True
            sections_updated += 1

        if _zero_subsection_offsets(section):
            changed = True
            offsets_zeroed += 1

        child_sequence = set_frame_range._get_subsequence_from_section(section)
        if not child_sequence:
            continue

        child_key = _utils.asset_key(child_sequence)
        if child_key in seen_assets:
            continue
        seen_assets.add(child_key)

        if _set_sequence_playback_range(child_sequence, start_frame, end_frame):
            updated_assets.append(child_sequence)

    if changed:
        updated_assets.append(master_sequence)

    return changed, sections_updated, offsets_zeroed, updated_assets


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
        "subsequence_sections_updated": 0,
        "subsequence_offsets_zeroed": 0,
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
        _log(f"Aligning shot {shot_name} to master range {master_start}->{master_end}")

        _changed, sections_updated, offsets_zeroed, assets_to_save = _align_master_subsections(
            master_sequence,
            master_start,
            master_end,
        )

        saved, failures = _save_unique_assets(assets_to_save)
        result["subsequence_sections_updated"] += sections_updated
        result["subsequence_offsets_zeroed"] += offsets_zeroed
        result["assets_saved"] += saved
        result["save_failures"].extend(failures)

    if result["shots_missing"] or result["save_failures"]:
        result["success"] = False

    result["message"] = (
        f"Aligned subsequences for {len(shot_names)} shot(s). "
        f"Sections updated={result['subsequence_sections_updated']}; "
        f"offsets zeroed={result['subsequence_offsets_zeroed']}."
    )
    summary = _utils.format_summary(result)
    _log(summary)
    return summary
