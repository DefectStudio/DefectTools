import re

import unreal


SHOT_NAME_PATTERN = re.compile(r"^([A-Za-z0-9]+)_(\d{3})_(\d{4,})$")
DEFAULT_HANDLE_FRAMES = 50
START_TOLERANCE_FRAMES = 1


def log(prefix, message):
    unreal.log(f"{prefix} {message}")


def log_warning(prefix, message):
    unreal.log_warning(f"{prefix} {message}")


def log_error(prefix, message):
    unreal.log_error(f"{prefix} {message}")


def clean_package_path(path_text):
    text = str(path_text or "").strip().replace("\\", "/")
    while "//" in text:
        text = text.replace("//", "/")
    if len(text) > 1:
        text = text.rstrip("/")
    return text


def join_game_path(*parts):
    cleaned_parts = []
    first_started_with_slash = False

    for index, part in enumerate(parts):
        raw_text = str(part or "").strip().replace("\\", "/")
        if index == 0 and raw_text.startswith("/"):
            first_started_with_slash = True
        while "//" in raw_text:
            raw_text = raw_text.replace("//", "/")
        raw_text = raw_text.strip("/")
        if raw_text:
            cleaned_parts.append(raw_text)

    if not cleaned_parts:
        return ""

    joined = "/".join(cleaned_parts)
    if first_started_with_slash or joined.startswith("Game"):
        return "/" + joined
    return joined


def asset_object_path_from_package_path(package_path):
    package_path = clean_package_path(package_path)
    if not package_path:
        return ""
    asset_name = package_path.rsplit("/", 1)[-1]
    return f"{package_path}.{asset_name}"


def sanitize_shot_name(raw_value):
    if raw_value is None:
        return ""
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", str(raw_value).strip())
    return cleaned.upper()


def derive_sequence_prefix(shot_name):
    match = SHOT_NAME_PATTERN.fullmatch(str(shot_name or ""))
    if not match:
        return ""
    return match.group(1).upper()


def coerce_shot_name_list(shot_name_array):
    if isinstance(shot_name_array, str):
        raw_values = [shot_name_array]
    else:
        try:
            raw_values = list(shot_name_array or [])
        except Exception:
            raw_values = []

    shot_names = []
    seen = set()
    for raw_value in raw_values:
        shot_name = sanitize_shot_name(raw_value)
        if not shot_name:
            continue
        if shot_name in seen:
            continue
        seen.add(shot_name)
        shot_names.append(shot_name)
    return shot_names


def coerce_handle_frames(value):
    try:
        handle_frames = int(value)
    except Exception:
        handle_frames = DEFAULT_HANDLE_FRAMES
    if handle_frames < 0:
        handle_frames = 0
    return handle_frames


def name(obj):
    try:
        return obj.get_name()
    except Exception:
        return str(obj)


def asset_key(asset):
    try:
        return asset.get_path_name()
    except Exception:
        return name(asset)


def get_class_name(obj):
    try:
        return obj.get_class().get_name()
    except Exception:
        return obj.__class__.__name__


def list_valid_show_folders(prefix):
    editor_asset_lib = unreal.EditorAssetLibrary
    try:
        root_entries = editor_asset_lib.list_assets("/Game", recursive=False, include_folder=True)
    except Exception as exc:
        log_error(prefix, f"Failed to list /Game root folders: {exc}")
        return []

    show_folders = []
    for entry in root_entries:
        entry = clean_package_path(entry)
        if not entry.startswith("/Game/_"):
            continue
        if "." in entry:
            continue

        marker_package_path = join_game_path(entry, "_showholder")
        marker_object_path = asset_object_path_from_package_path(marker_package_path)
        try:
            marker_exists = editor_asset_lib.does_asset_exist(marker_package_path) or editor_asset_lib.does_asset_exist(marker_object_path)
        except Exception:
            marker_exists = False

        if marker_exists:
            show_folders.append(entry)

    show_folders.sort()
    log(prefix, f"Valid show folders: {show_folders}")
    return show_folders


def resolve_shot_sequence(shot_name, prefix):
    clean_shot_name = sanitize_shot_name(shot_name)
    sequence_prefix = derive_sequence_prefix(clean_shot_name)
    if not sequence_prefix:
        log_warning(prefix, f"Skipping invalid shot name: {shot_name}")
        return None, ""

    editor_asset_lib = unreal.EditorAssetLibrary
    for show_folder in list_valid_show_folders(prefix):
        package_path = join_game_path(show_folder, "Sequences", sequence_prefix, clean_shot_name)
        object_path = asset_object_path_from_package_path(package_path)
        try:
            exists = editor_asset_lib.does_asset_exist(object_path)
        except Exception:
            exists = False
        if not exists:
            continue

        sequence = unreal.load_asset(object_path)
        if isinstance(sequence, unreal.LevelSequence):
            log(prefix, f"Resolved shot sequence '{clean_shot_name}': {object_path}")
            return sequence, object_path

        log_warning(prefix, f"Found shot asset but it was not a LevelSequence: {object_path}")

    log_warning(prefix, f"Could not resolve shot sequence: {clean_shot_name}")
    return None, ""


def split_object_path_to_package_path(object_path):
    return clean_package_path(str(object_path or "").split(".", 1)[0])


def list_level_sequences_in_folder(folder_path, prefix, recursive=True):
    folder_path = clean_package_path(folder_path)
    if not folder_path:
        return []
    if not unreal.EditorAssetLibrary.does_directory_exist(folder_path):
        return []

    try:
        asset_paths = unreal.EditorAssetLibrary.list_assets(folder_path, recursive=recursive, include_folder=False)
    except TypeError:
        asset_paths = unreal.EditorAssetLibrary.list_assets(folder_path, recursive, False)
    except Exception as exc:
        log_warning(prefix, f"Failed to list LevelSequence assets in '{folder_path}': {exc}")
        return []

    sequences = []
    for asset_path in asset_paths:
        try:
            asset = unreal.load_asset(asset_path)
        except Exception:
            asset = None
        if isinstance(asset, unreal.LevelSequence):
            sequences.append(asset)
    return sequences


def is_subsequence_section(section):
    try:
        return isinstance(section, unreal.MovieSceneSubSection)
    except Exception:
        return hasattr(section, "get_sequence")


def get_subsequence_from_section(section):
    try:
        sequence = section.get_sequence()
        if sequence:
            return sequence
    except Exception:
        pass

    for property_name in ("sub_sequence", "sequence"):
        try:
            sequence = section.get_editor_property(property_name)
            if sequence:
                return sequence
        except Exception:
            continue

    return None


def find_tracks(sequence, track_type):
    try:
        return list(sequence.find_tracks_by_type(track_type))
    except Exception:
        return []


def get_subsequence_sections(sequence):
    sections = []
    seen = set()
    track_types = []

    for type_name in ("MovieSceneSubTrack", "MovieSceneCinematicShotTrack"):
        track_type = getattr(unreal, type_name, None)
        if track_type:
            track_types.append(track_type)

    for track_type in track_types:
        for track in find_tracks(sequence, track_type):
            try:
                track_sections = track.get_sections()
            except Exception:
                continue
            for section in track_sections:
                if not is_subsequence_section(section):
                    continue
                key = id(section)
                if key in seen:
                    continue
                seen.add(key)
                sections.append(section)

    return sections


def collect_referenced_sequences_recursive(root_sequence, prefix, max_depth=10):
    result = []
    seen = set()

    def visit(sequence, depth):
        if not sequence or depth > max_depth:
            return
        key = asset_key(sequence)
        if key in seen:
            return
        seen.add(key)
        result.append(sequence)

        for section in get_subsequence_sections(sequence):
            child = get_subsequence_from_section(section)
            if child:
                visit(child, depth + 1)

    visit(root_sequence, 0)
    log(prefix, f"Referenced LevelSequences collected: {len(result)}")
    return result


def collect_shot_sequences(shot_sequence, shot_object_path, prefix):
    sequences = collect_referenced_sequences_recursive(shot_sequence, prefix)
    seen = {asset_key(sequence) for sequence in sequences}

    shot_package_path = split_object_path_to_package_path(shot_object_path)
    extra_folders = [
        join_game_path(shot_package_path, "SubSequences"),
        join_game_path(shot_package_path, "RenderPasses"),
    ]

    for folder_path in extra_folders:
        for sequence in list_level_sequences_in_folder(folder_path, prefix, recursive=True):
            key = asset_key(sequence)
            if key in seen:
                continue
            seen.add(key)
            sequences.append(sequence)
            log(prefix, f"Included extra LevelSequence from folder '{folder_path}': {key}")

    return sequences


def get_playback_start(sequence):
    try:
        return int(sequence.get_playback_start())
    except Exception:
        return 0


def get_section_start_end(section):
    try:
        start_frame = int(section.get_start_frame())
        end_frame = int(section.get_end_frame())
        return start_frame, end_frame
    except Exception:
        return None, None


def should_extend_section_start(current_start, playback_start, target_start):
    if current_start is None:
        return False
    if current_start <= target_start:
        return False
    return current_start <= playback_start + START_TOLERANCE_FRAMES


def extend_section_start(section, target_start, label, prefix):
    current_start, current_end = get_section_start_end(section)
    if current_start is None or current_end is None:
        log_warning(prefix, f"Could not read {label} section range: {name(section)}")
        return False

    if current_start == target_start:
        return False

    try:
        section.set_range(target_start, current_end)
    except Exception as exc:
        log_warning(prefix, f"Failed to extend {label} section '{name(section)}': {exc}")
        return False

    log(prefix, f"Extended {label} section '{name(section)}' {current_start}->{current_end} became {target_start}->{current_end}")
    return True


def save_if_changed(sequence, changed, prefix):
    if not changed:
        return True
    try:
        if unreal.EditorAssetLibrary.save_loaded_asset(sequence):
            log(prefix, f"Saved LevelSequence: {asset_key(sequence)}")
            return True
    except Exception as exc:
        log_error(prefix, f"Failed to save LevelSequence '{asset_key(sequence)}': {exc}")
        return False

    log_error(prefix, f"Failed to save LevelSequence: {asset_key(sequence)}")
    return False


def format_summary(result):
    def join_values(values):
        return ",".join(str(value) for value in values) if values else ""

    parts = []
    for key in sorted(result.keys()):
        value = result.get(key)
        if isinstance(value, bool):
            value = 1 if value else 0
        elif isinstance(value, list):
            value = join_values(value)
        parts.append(f"{key}={value}")
    return ";".join(parts)
