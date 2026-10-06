import re
import unreal

LOG_PREFIX = "[SetFrameRange]"


def _log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


def _log_warning(message):
    unreal.log_warning(f"{LOG_PREFIX} {message}")


def _log_error(message):
    unreal.log_error(f"{LOG_PREFIX} {message}")


def _sanitize_name(raw_value, label):
    if raw_value is None:
        return "", f"{label} is missing."

    raw_text = str(raw_value)
    text = raw_text.strip()
    if not text:
        return "", f"{label} is empty."

    cleaned = re.sub(r"\s+", "", text)
    cleaned = re.sub(r"[^A-Za-z0-9_\-]", "", cleaned)
    if not cleaned:
        return "", f"{label} became empty after sanitization. raw='{raw_text}'"

    return cleaned, None


def _parse_frame_number(raw_value, label):
    if raw_value is None:
        return None, f"{label} is missing."

    if isinstance(raw_value, bool):
        return None, f"{label} must be an integer, not bool."

    if isinstance(raw_value, int):
        return raw_value, None

    text = str(raw_value).strip()
    if not re.fullmatch(r"[+-]?\d+", text):
        return None, f"{label} must be an integer. raw='{raw_value}'"

    return int(text), None


def _join_game_path(*parts):
    cleaned_parts = []
    for part in parts:
        text = str(part or "").strip().replace("\\", "/")
        while "//" in text:
            text = text.replace("//", "/")
        text = text.strip("/")
        if text:
            cleaned_parts.append(text)

    if not cleaned_parts:
        return ""

    if str(parts[0] or "").strip().startswith("/"):
        return "/" + "/".join(cleaned_parts)

    if cleaned_parts[0] == "Game" or cleaned_parts[0].startswith("Game"):
        return "/" + "/".join(cleaned_parts)

    return "/".join(cleaned_parts)


def _resolve_paths(show_name, sequence_name, shot_name):
    sequence_root = _join_game_path("/Game", f"_{show_name}", "Sequences", sequence_name)
    shot_folder = _join_game_path(sequence_root, shot_name)
    return {
        "sequence_root": sequence_root,
        "master_sequence_path": _join_game_path(sequence_root, shot_name),
        "shot_folder": shot_folder,
        "subsequences_folder": _join_game_path(shot_folder, "SubSequences"),
        "render_passes_folder": _join_game_path(shot_folder, "RenderPasses"),
    }


def _list_level_sequences_in_folder(folder_path):
    if not unreal.EditorAssetLibrary.does_directory_exist(folder_path):
        _log_warning(f"Folder does not exist: {folder_path}")
        return []

    try:
        asset_paths = unreal.EditorAssetLibrary.list_assets(
            folder_path, recursive=False, include_folder=False
        )
    except TypeError:
        asset_paths = unreal.EditorAssetLibrary.list_assets(folder_path, False, False)
    except Exception as exc:
        _log_error(f"Failed to list assets in folder '{folder_path}': {exc}")
        return []

    result = []
    for asset_path in asset_paths:
        asset = unreal.EditorAssetLibrary.load_asset(asset_path)
        if isinstance(asset, unreal.LevelSequence):
            result.append(asset_path)
    return result


def _load_level_sequence(asset_path, label):
    if not unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        _log_error(f"{label} not found at path: {asset_path}")
        return None

    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    if not asset:
        _log_error(f"Failed to load {label}: {asset_path}")
        return None

    if not isinstance(asset, unreal.LevelSequence):
        _log_error(f"{label} is not a LevelSequence: {asset_path}")
        return None

    return asset


def _name(obj):
    try:
        return obj.get_name()
    except Exception:
        return str(obj)


def _asset_key(asset):
    try:
        return asset.get_path_name()
    except Exception:
        return _name(asset)


def _get_playback_range(sequence):
    return int(sequence.get_playback_start()), int(sequence.get_playback_end())


def _to_exclusive_end_frame(inclusive_end_frame):
    return inclusive_end_frame + 1


def _unlock_range(sequence, label):
    try:
        if sequence.is_playback_range_locked():
            sequence.set_playback_range_locked(False)
            _log(f"Unlocked playback range: {label}")
    except Exception as exc:
        _log_warning(f"Playback lock check skipped for {label}: {exc}")


def _set_playback_range(sequence, label, start_frame, inclusive_end_frame):
    exclusive_end_frame = _to_exclusive_end_frame(inclusive_end_frame)
    current_start, current_end = _get_playback_range(sequence)
    if current_start == start_frame and current_end == exclusive_end_frame:
        _log(
            f"Playback already matches: {label} "
            f"{start_frame}->{exclusive_end_frame} (exclusive end)"
        )
        return False

    _unlock_range(sequence, label)
    sequence.set_playback_start(start_frame)
    sequence.set_playback_end(exclusive_end_frame)
    new_start, new_end = _get_playback_range(sequence)
    _log(f"Playback updated: {label} {current_start}->{current_end} became {new_start}->{new_end}")
    return True


def _is_subsequence_section(section):
    try:
        return isinstance(section, unreal.MovieSceneSubSection)
    except Exception:
        return hasattr(section, "get_sequence")


def _get_subsequence_from_section(section):
    try:
        sequence = section.get_sequence()
        if sequence:
            return sequence
    except Exception:
        pass

    try:
        return section.get_editor_property("sub_sequence")
    except Exception:
        return None


def _make_frame_number(value):
    try:
        return unreal.FrameNumber(int(value))
    except Exception:
        return int(value)


def _frame_number_to_int(value):
    try:
        return int(value)
    except Exception:
        return int(value.value)


def _subsection_timing_matches_zero(parameters):
    return (
        _frame_number_to_int(parameters.start_frame_offset) == 0
        and _frame_number_to_int(parameters.first_loop_start_frame_offset) == 0
        and _frame_number_to_int(parameters.end_frame_offset) == 0
        and float(parameters.time_scale) == 1.0
    )


def _zero_subsection_offsets(section):
    if not _is_subsequence_section(section):
        return False

    try:
        params = section.get_editor_property("parameters")
        if _subsection_timing_matches_zero(params):
            return False
        params.start_frame_offset = _make_frame_number(0)
        params.first_loop_start_frame_offset = _make_frame_number(0)
        params.end_frame_offset = _make_frame_number(0)
        params.time_scale = 1.0
        section.set_editor_property("parameters", params)
        return True
    except Exception as exc:
        _log_warning(f"Could not zero subsection parameters on {_name(section)}: {exc}")

    try:
        direct_values = (
            section.get_editor_property("start_frame_offset"),
            section.get_editor_property("first_loop_start_frame_offset"),
            section.get_editor_property("end_frame_offset"),
            section.get_editor_property("time_scale"),
        )
        if (
            _frame_number_to_int(direct_values[0]) == 0
            and _frame_number_to_int(direct_values[1]) == 0
            and _frame_number_to_int(direct_values[2]) == 0
            and float(direct_values[3]) == 1.0
        ):
            return False
        section.set_editor_property("start_frame_offset", _make_frame_number(0))
        section.set_editor_property("first_loop_start_frame_offset", _make_frame_number(0))
        section.set_editor_property("end_frame_offset", _make_frame_number(0))
        section.set_editor_property("time_scale", 1.0)
        return True
    except Exception as exc:
        _log_warning(f"Could not zero direct subsection offsets on {_name(section)}: {exc}")
        return False


def _find_tracks(sequence, track_type):
    try:
        return list(sequence.find_tracks_by_type(track_type))
    except Exception:
        return []


def _subsections(sequence):
    result = []
    seen = set()
    track_types = []

    try:
        track_types.append(unreal.MovieSceneSubTrack)
    except Exception:
        pass

    try:
        track_types.append(unreal.MovieSceneCinematicShotTrack)
    except Exception:
        pass

    for track_type in track_types:
        for track in _find_tracks(sequence, track_type):
            try:
                sections = track.get_sections()
            except Exception:
                continue

            for section in sections:
                if not _is_subsequence_section(section):
                    continue
                key = id(section)
                if key in seen:
                    continue
                seen.add(key)
                result.append(section)

    return result


def _master_subsections(master_sequence):
    """Return direct master subsections for compatibility with companion tools."""
    return _subsections(master_sequence)


def _collect_sequence_graph(root_sequences):
    sequences = []
    seen = set()

    def visit(sequence):
        key = _asset_key(sequence)
        if key in seen:
            return
        seen.add(key)
        sequences.append(sequence)

        for section in _subsections(sequence):
            child = _get_subsequence_from_section(section)
            if child:
                visit(child)

    for root_sequence in root_sequences:
        if root_sequence:
            visit(root_sequence)

    return sequences


def _load_extra_children(subsequence_paths, render_pass_paths, known_children):
    known = {_asset_key(child) for child in known_children}
    extras = []
    for path in list(subsequence_paths) + list(render_pass_paths):
        if path in known:
            continue
        sequence = _load_level_sequence(path, "Folder child sequence")
        if not sequence:
            continue
        key = _asset_key(sequence)
        if key in known:
            continue
        known.add(key)
        extras.append(sequence)
    return extras


def _set_section_range(section, label, start_frame, end_frame):
    try:
        current_start = int(section.get_start_frame())
        current_end = int(section.get_end_frame())
    except Exception:
        current_start = None
        current_end = None

    if current_start == start_frame and current_end == end_frame:
        return False

    section.set_range(start_frame, end_frame)
    _log(f"Section range updated: {label} {_name(section)} {current_start}->{current_end} became {start_frame}->{end_frame}")
    return True


def _sync_subsections(sequence, start_frame, end_frame):
    checked = 0
    updated = 0
    zeroed = 0
    for section in _subsections(sequence):
        checked += 1
        try:
            if _set_section_range(section, "SubSection", start_frame, end_frame):
                updated += 1
            if _zero_subsection_offsets(section):
                zeroed += 1
        except Exception as exc:
            _log_warning(
                f"Failed to update subsection {_name(section)} in {_name(sequence)}: {exc}"
            )
    _log(
        f"Subsections checked in {_name(sequence)}: checked={checked}, "
        f"ranges_updated={updated}, offsets_zeroed={zeroed}"
    )
    return updated + zeroed > 0


def _extend_track_sections(sequence, track_type, label, start_frame, end_frame):
    changed = False
    tracks = _find_tracks(sequence, track_type)
    for track in tracks:
        try:
            sections = track.get_sections()
        except Exception:
            continue
        for section in sections:
            try:
                if _set_section_range(section, label, start_frame, end_frame):
                    changed = True
            except Exception as exc:
                _log_warning(f"Failed to update {label} section {_name(section)} in {_name(sequence)}: {exc}")
    _log(f"{label} tracks checked in {_name(sequence)}: {len(tracks)}")
    return changed


def _extend_safe_child_sections(sequence, start_frame, end_frame):
    changed = False

    try:
        if _extend_track_sections(sequence, unreal.MovieSceneLevelVisibilityTrack, "LevelVisibility", start_frame, end_frame):
            changed = True
    except Exception as exc:
        _log_warning(f"LevelVisibility update skipped for {_name(sequence)}: {exc}")

    try:
        if _extend_track_sections(sequence, unreal.MovieSceneCameraCutTrack, "CameraCut", start_frame, end_frame):
            changed = True
    except Exception as exc:
        _log_warning(f"CameraCut update skipped for {_name(sequence)}: {exc}")

    return changed


def _save_if_changed(asset, changed, label):
    if not changed:
        _log(f"No save needed: {label}")
        return True
    if not unreal.EditorAssetLibrary.save_loaded_asset(asset):
        _log_error(f"Failed to save: {label}")
        return False
    _log(f"Saved: {label}")
    return True


def _extract_asset_name(asset_path):
    leaf = str(asset_path).rstrip("/").rsplit("/", 1)[-1]
    return leaf.split(".", 1)[0]


def _build_expected_data_asset_path(shot_folder_path, shot_name):
    data_asset_name = f"{shot_name}_Data"
    package_path = _join_game_path(shot_folder_path, data_asset_name)
    return f"{package_path}.{data_asset_name}"


def _find_fallback_data_asset_in_shot_folder(shot_folder_path, shot_name):
    if not unreal.EditorAssetLibrary.does_directory_exist(shot_folder_path):
        _log_error(f"Shot data asset folder does not exist: {shot_folder_path}")
        return None, ""

    try:
        asset_paths = unreal.EditorAssetLibrary.list_assets(
            shot_folder_path, recursive=False, include_folder=False
        )
    except Exception as exc:
        _log_error(f"Failed to list shot data asset folder '{shot_folder_path}': {exc}")
        return None, ""

    preferred_name = f"{shot_name}_Data"
    fallback_candidate_path = ""
    for asset_path in asset_paths:
        asset_name = _extract_asset_name(asset_path)
        if asset_name == preferred_name:
            fallback_candidate_path = asset_path
            break
        if asset_name.endswith("_Data") and not fallback_candidate_path:
            fallback_candidate_path = asset_path

    if not fallback_candidate_path:
        _log_error(f"No *_Data asset candidate found in shot folder: {shot_folder_path}")
        return None, ""

    loaded = unreal.load_asset(fallback_candidate_path)
    if not loaded:
        _log_error(f"Fallback shot data asset failed to load: {fallback_candidate_path}")
        return None, ""

    _log(f"Loaded fallback shot data asset: {fallback_candidate_path}")
    return loaded, fallback_candidate_path


def _load_shot_data_asset(shot_folder_path, shot_name):
    expected_path = _build_expected_data_asset_path(shot_folder_path, shot_name)
    if unreal.EditorAssetLibrary.does_asset_exist(expected_path):
        loaded = unreal.load_asset(expected_path)
        if loaded:
            _log(f"Loaded expected shot data asset: {expected_path}")
            return loaded, expected_path
        _log_error(f"Expected shot data asset exists but failed to load: {expected_path}")
    return _find_fallback_data_asset_in_shot_folder(shot_folder_path, shot_name)


def _set_int_property(asset, property_name, value, asset_path):
    try:
        asset.get_editor_property(property_name)
    except Exception as exc:
        _log_error(f"Shot data asset does not expose {property_name}: {asset_path} | {exc}")
        return False

    try:
        asset.set_editor_property(property_name, int(value))
        _log(f"Set {property_name}={value} on shot data asset: {asset_path}")
        return True
    except Exception as exc:
        _log_error(f"Failed to set {property_name}={value} on shot data asset: {asset_path} | {exc}")
        return False


def _get_int_property(asset, property_name, asset_path):
    try:
        raw_value = asset.get_editor_property(property_name)
    except Exception as exc:
        _log_error(f"Shot data asset does not expose {property_name}: {asset_path} | {exc}")
        return None

    if isinstance(raw_value, bool):
        _log_error(
            f"Shot data asset property {property_name} must be an integer, not bool: "
            f"{asset_path}"
        )
        return None

    try:
        return int(raw_value)
    except Exception as exc:
        _log_error(
            f"Shot data asset property {property_name} is not an integer: "
            f"{asset_path} | value={raw_value!r} | {exc}"
        )
        return None


def _get_shot_data_asset_frame_range(asset, asset_path):
    start_frame = _get_int_property(asset, "StartFrame", asset_path)
    if start_frame is None:
        return None

    end_frame = _get_int_property(asset, "EndFrame", asset_path)
    if end_frame is None:
        return None

    return start_frame, end_frame


def _update_shot_data_asset_frame_range(
    shot_folder_path,
    shot_name,
    start_frame,
    end_frame,
    asset=None,
    asset_path=None,
):
    if asset is None:
        asset, asset_path = _load_shot_data_asset(shot_folder_path, shot_name)
    if not asset:
        return False

    stored_frame_range = _get_shot_data_asset_frame_range(asset, asset_path)
    if stored_frame_range is None:
        return False

    stored_start, stored_end = stored_frame_range
    changed = False

    if stored_start != start_frame:
        if not _set_int_property(asset, "StartFrame", start_frame, asset_path):
            return False
        changed = True

    if stored_end != end_frame:
        if not _set_int_property(asset, "EndFrame", end_frame, asset_path):
            return False
        changed = True

    if not changed:
        _log(
            f"No shot data asset save needed: {asset_path} "
            f"already matches {start_frame}->{end_frame}"
        )
        return True

    if not unreal.EditorAssetLibrary.save_loaded_asset(asset):
        _log_error(f"Failed to save shot data asset: {asset_path}")
        return False

    _log(f"Shot data asset updated: {asset_path} StartFrame={start_frame} EndFrame={end_frame}")
    return True


def _refresh_sequencer():
    try:
        unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()
    except Exception as exc:
        _log_warning(f"Sequencer refresh skipped: {exc}")


def run(show_name, sequence_name, shot_name, start_frame, end_frame):
    """Set shot frame range without moving artist content in child sequences."""
    clean_show_name, err = _sanitize_name(show_name, "show_name")
    if err:
        _log_error(err)
        return False
    clean_sequence_name, err = _sanitize_name(sequence_name, "sequence_name")
    if err:
        _log_error(err)
        return False
    clean_shot_name, err = _sanitize_name(shot_name, "shot_name")
    if err:
        _log_error(err)
        return False
    if clean_show_name.startswith("_"):
        clean_show_name = clean_show_name[1:]

    clean_start, err = _parse_frame_number(start_frame, "start_frame")
    if err:
        _log_error(err)
        return False
    clean_end, err = _parse_frame_number(end_frame, "end_frame")
    if err:
        _log_error(err)
        return False
    if clean_end < clean_start:
        _log_error(f"end_frame is less than start_frame: {clean_start}->{clean_end}")
        return False

    exclusive_end = _to_exclusive_end_frame(clean_end)

    paths = _resolve_paths(clean_show_name, clean_sequence_name, clean_shot_name)
    shot_data_asset, shot_data_asset_path = _load_shot_data_asset(
        paths["shot_folder"], clean_shot_name
    )
    if not shot_data_asset:
        return False

    stored_frame_range = _get_shot_data_asset_frame_range(
        shot_data_asset, shot_data_asset_path
    )
    if stored_frame_range is None:
        return False

    if stored_frame_range == (clean_start, clean_end):
        _log(
            f"Shot data asset already matches {clean_start}->{clean_end}; "
            "checking sequence assets for drift"
        )

    master = _load_level_sequence(paths["master_sequence_path"], "Master sequence")
    if not master:
        return False

    old_master_start, old_master_end = _get_playback_range(master)
    _log(f"Master old range: {old_master_start}->{old_master_end}")
    _log(f"Requested range: {clean_start}->{clean_end}")

    subsequence_paths = _list_level_sequences_in_folder(paths["subsequences_folder"])
    render_pass_paths = _list_level_sequences_in_folder(paths["render_passes_folder"])

    master_graph = _collect_sequence_graph([master])
    referenced_children = master_graph[1:]
    folder_children = _load_extra_children(
        subsequence_paths, render_pass_paths, referenced_children
    )
    all_sequences = _collect_sequence_graph([master] + folder_children)
    master_key = _asset_key(master)
    children = [
        sequence for sequence in all_sequences if _asset_key(sequence) != master_key
    ]

    _log(f"Referenced child assets: {len(referenced_children)}")
    _log(f"Folder-only root assets: {len(folder_children)}")
    _log(f"Total recursive child assets: {len(children)}")

    failed = []
    changed_count = 0
    skipped_count = 0

    for child in children:
        label = _asset_key(child)
        changed = False
        try:
            if _set_playback_range(child, label, clean_start, clean_end):
                changed = True
            if _extend_safe_child_sections(child, clean_start, exclusive_end):
                changed = True
            if _sync_subsections(child, clean_start, exclusive_end):
                changed = True
        except Exception as exc:
            _log_error(f"Failed updating child {label}: {exc}")
            failed.append(label)
            continue

        if not _save_if_changed(child, changed, label):
            failed.append(label)
            continue
        if changed:
            changed_count += 1
        else:
            skipped_count += 1

    if failed:
        _log_error(f"Failed child updates: {failed}")
        return False

    master_changed = False
    try:
        if _set_playback_range(master, paths["master_sequence_path"], clean_start, clean_end):
            master_changed = True
        if _sync_subsections(master, clean_start, exclusive_end):
            master_changed = True
    except Exception as exc:
        _log_error(f"Failed updating master: {exc}")
        return False

    if not _save_if_changed(master, master_changed, paths["master_sequence_path"]):
        return False
    if master_changed:
        changed_count += 1
    else:
        skipped_count += 1

    if not _update_shot_data_asset_frame_range(
        paths["shot_folder"],
        clean_shot_name,
        clean_start,
        clean_end,
        asset=shot_data_asset,
        asset_path=shot_data_asset_path,
    ):
        return False

    _refresh_sequencer()
    _log(
        f"Success. changed={changed_count}, skipped={skipped_count}, "
        f"old_master={old_master_start}->{old_master_end}, new={clean_start}->{clean_end}"
    )
    return True
