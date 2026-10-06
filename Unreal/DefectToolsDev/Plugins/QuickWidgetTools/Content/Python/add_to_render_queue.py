"""
Compatibility wrapper for add_to_render_queue.

The real render queue implementation lives in add_to_render_queue_impl.py. This
wrapper keeps the existing import path stable while patching a few render-tool
behaviors, including per-shot MP4 / EXR Movie Render Graph Boolean overrides.
"""

import importlib
import os
import re

import unreal

import add_to_render_queue_impl as _impl


importlib.reload(_impl)

_FAST_LEVEL_PATH_PROPERTY = "AssociatedLevelPathString"
MP4_VARIABLE_NAME = "MP4"
EXR_VARIABLE_NAME = "EXR"

_CURRENT_SHOW_FOLDERS = None
_GRAPH_VARIABLE_CACHE = {}
_CURRENT_RENDER_FORMAT_BY_SHOT = {}
_CURRENT_JOB_SHOT_NAMES = {}

try:
    candidates = _impl.ASSOCIATED_LEVEL_PROPERTY_CANDIDATES
except Exception:
    candidates = []
    _impl.ASSOCIATED_LEVEL_PROPERTY_CANDIDATES = candidates

if _FAST_LEVEL_PATH_PROPERTY in candidates:
    candidates.remove(_FAST_LEVEL_PATH_PROPERTY)
candidates.insert(0, _FAST_LEVEL_PATH_PROPERTY)

_ORIGINAL_COERCE_TO_OBJECT_PATH = _impl._coerce_to_object_path
_ORIGINAL_ASSIGN_JOB_NAME = _impl._assign_job_name
_ORIGINAL_EXTRACT_ASSOCIATED_LEVEL_OBJECT_PATH = _impl._extract_associated_level_object_path
_ORIGINAL_FIND_MOVIE_RENDER_GRAPH_ASSET = _impl._find_movie_render_graph_asset
_ORIGINAL_GET_GRAPH_VARIABLES = _impl._get_graph_variables
_ORIGINAL_LOAD_SHOT_DATA_ASSET_FOR_SHOT = _impl._load_shot_data_asset_for_shot
_ORIGINAL_BUILD_RENDER_OUTPUT_DATA = _impl._build_render_output_data
_ORIGINAL_ASSIGN_MOVIE_RENDER_GRAPH_TO_JOB = _impl._assign_movie_render_graph_to_job
_ORIGINAL_APPLY_JOB_OUTPUT_OVERRIDES = _impl._apply_job_output_overrides
_ORIGINAL_APPLY_JOB_HERO_OVERRIDE = _impl._apply_job_hero_override
_ORIGINAL_RUN = _impl.run


def _clean_package_path(path_text):
    text = str(path_text or "").strip().replace("\\", "/")
    while "//" in text:
        text = text.replace("//", "/")
    if len(text) > 1:
        text = text.rstrip("/")
    return text


def _object_path_from_package_path(package_path):
    package_path = _clean_package_path(package_path)
    if not package_path:
        return ""
    asset_name = package_path.rsplit("/", 1)[-1]
    return f"{package_path}.{asset_name}"


def _soft_object_path_to_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    for getter_name in ("to_string", "get_asset_path_name", "get_path_name"):
        getter = getattr(value, getter_name, None)
        if callable(getter):
            try:
                result = getter()
            except Exception:
                continue
            if result:
                return str(result)
    return str(value or "")


def _normalize_map_object_path(path_or_object_path):
    text = _clean_package_path(_soft_object_path_to_text(path_or_object_path))
    if not text:
        return ""
    if text.startswith("SoftObjectPath(") and text.endswith(")"):
        text = _clean_package_path(text[len("SoftObjectPath("):-1].strip().strip("\"'"))
    if not (text.startswith("/Game/") or text.startswith("/QuickWidgetTools/")):
        return text
    leaf = text.rsplit("/", 1)[-1]
    if "." in leaf:
        return text
    return _object_path_from_package_path(text)


def _is_valid_asset_data(asset_data):
    if asset_data is None:
        return False
    is_valid = getattr(asset_data, "is_valid", None)
    if callable(is_valid):
        try:
            return bool(is_valid())
        except Exception:
            pass
    for property_name in ("asset_name", "package_name", "object_path"):
        try:
            value = getattr(asset_data, property_name)
        except Exception:
            continue
        if value and str(value).strip() not in ("None", "null"):
            return True
    return False


def _get_asset_data_class_text(asset_data):
    if not _is_valid_asset_data(asset_data):
        return ""
    class_parts = []
    for property_name in ("asset_class_path", "asset_class", "class_path_name", "class_name"):
        try:
            value = getattr(asset_data, property_name)
        except Exception:
            continue
        if value:
            class_parts.append(str(value))
    return " ".join(class_parts)


def _is_level_sequence_asset_path(asset_path, shot_name):
    try:
        asset_data = unreal.EditorAssetLibrary.find_asset_data(asset_path)
    except Exception:
        asset_data = None
    class_text = _get_asset_data_class_text(asset_data)
    if not class_text:
        _impl._log_warning(
            f"Could not read AssetData class metadata for shot '{shot_name}' at '{asset_path}'. Accepting by path/name."
        )
        return True
    if "LevelSequence" in class_text:
        return True
    _impl._log_warning(
        f"Found candidate shot asset '{asset_path}' for '{shot_name}', but AssetData class was not LevelSequence: {class_text}"
    )
    return False


def _find_level_sequence_asset_path(shot_name):
    sequence_prefix = _impl._derive_sequence_prefix(shot_name)
    if not sequence_prefix:
        return ""

    editor_asset_lib = unreal.EditorAssetLibrary
    show_folders = _CURRENT_SHOW_FOLDERS
    if show_folders is None:
        show_folders = _impl._list_valid_show_folders()

    for show_folder in show_folders:
        package_path = _impl._join_package_path(show_folder, "Sequences", sequence_prefix, shot_name)
        object_path = _impl._asset_object_path_from_package_path(package_path)
        try:
            exists = editor_asset_lib.does_asset_exist(object_path)
        except Exception:
            exists = False
        if not exists:
            continue
        if not _is_level_sequence_asset_path(object_path, shot_name):
            continue
        _impl._log(f"Resolved shot sequence for '{shot_name}': {object_path}")
        return object_path
    return ""


def _is_movie_render_graph_asset(graph_asset):
    if not graph_asset:
        return False
    try:
        class_names = _impl._get_asset_class_names(graph_asset)
    except Exception:
        class_names = set()
    try:
        loaded_class_name = graph_asset.get_class().get_name()
    except Exception:
        loaded_class_name = ""
    if loaded_class_name:
        class_names.add(loaded_class_name)
    return any(class_name in _impl.EXPECTED_GRAPH_CLASS_NAMES for class_name in class_names)


def _find_movie_render_graph_asset(movie_render_graph_name, render_graph_folder_path=None, render_graph_secondary_folder_path=None):
    requested_name = str(movie_render_graph_name or "").strip()
    if not requested_name:
        return _ORIGINAL_FIND_MOVIE_RENDER_GRAPH_ASSET(
            movie_render_graph_name,
            render_graph_folder_path,
            render_graph_secondary_folder_path,
        )

    try:
        search_paths = _impl._get_render_graph_search_paths(render_graph_folder_path, render_graph_secondary_folder_path)
    except Exception:
        search_paths = []

    for search_path in search_paths:
        candidate_package_path = _impl._join_package_path(search_path, requested_name)
        candidate_object_path = _impl._asset_object_path_from_package_path(candidate_package_path)
        if not candidate_object_path:
            continue
        try:
            exists = unreal.EditorAssetLibrary.does_asset_exist(candidate_object_path)
        except Exception:
            exists = False
        if not exists:
            continue
        graph_asset = unreal.load_asset(candidate_object_path)
        if graph_asset and _is_movie_render_graph_asset(graph_asset):
            _impl._log(f"Resolved Movie Render Graph asset by direct path '{requested_name}' -> {candidate_object_path}")
            return graph_asset

    return _ORIGINAL_FIND_MOVIE_RENDER_GRAPH_ASSET(
        movie_render_graph_name,
        render_graph_folder_path,
        render_graph_secondary_folder_path,
    )


def _get_graph_cache_key(graph_asset):
    if not graph_asset:
        return ""
    try:
        return graph_asset.get_path_name() or str(id(graph_asset))
    except Exception:
        return str(id(graph_asset))


def _get_graph_variables(graph_asset):
    cache_key = _get_graph_cache_key(graph_asset)
    if cache_key and cache_key in _GRAPH_VARIABLE_CACHE:
        return _GRAPH_VARIABLE_CACHE[cache_key]
    variables = _ORIGINAL_GET_GRAPH_VARIABLES(graph_asset)
    if cache_key:
        _GRAPH_VARIABLE_CACHE[cache_key] = variables
        _impl._log(f"Cached {len(variables or [])} Movie Render Graph variable(s).")
    return variables


def _coerce_to_object_path(value):
    return _normalize_map_object_path(_ORIGINAL_COERCE_TO_OBJECT_PATH(value))


def _load_shot_data_asset_for_shot(level_sequence_object_path, shot_name):
    return _ORIGINAL_LOAD_SHOT_DATA_ASSET_FOR_SHOT(level_sequence_object_path, shot_name)


def _extract_associated_level_object_path(shot_data_asset):
    object_path = _ORIGINAL_EXTRACT_ASSOCIATED_LEVEL_OBJECT_PATH(shot_data_asset)
    normalized_object_path = _normalize_map_object_path(object_path)
    if object_path != normalized_object_path:
        _impl._log(f"Normalized AssociatedLevel path for Movie Render Queue map: {object_path} -> {normalized_object_path}")
    return normalized_object_path


def _find_next_render_version_number(output_parent_directory, stem_prefix):
    normalized_parent = os.path.normpath(str(output_parent_directory or "").strip())
    if not normalized_parent:
        return _impl.DEFAULT_VERSION_NUMBER

    version_pattern = re.compile(rf"^{re.escape(str(stem_prefix or ''))}_v(\d{{3}})(?:\.mp4)?$", re.IGNORECASE)
    highest_version = 0
    matched_entries = []

    try:
        entries = os.listdir(normalized_parent)
    except FileNotFoundError:
        _impl._log(
            f"Output parent folder does not exist yet. Starting version at v{_impl.DEFAULT_VERSION_NUMBER:03d}: {normalized_parent}"
        )
        return _impl.DEFAULT_VERSION_NUMBER
    except Exception as exc:
        _impl._log_warning(f"Could not inspect output parent folder '{normalized_parent}' for existing versions: {exc}")
        return _impl.DEFAULT_VERSION_NUMBER

    for entry_name in entries:
        entry_path = os.path.join(normalized_parent, entry_name)
        is_exr_folder = os.path.isdir(entry_path)
        is_mp4_file = os.path.isfile(entry_path) and str(entry_name).lower().endswith(".mp4")

        if not is_exr_folder and not is_mp4_file:
            continue

        match = version_pattern.fullmatch(str(entry_name))
        if not match:
            continue

        try:
            version_number = int(match.group(1))
        except Exception:
            continue

        matched_entries.append(entry_name)
        if version_number > highest_version:
            highest_version = version_number

    next_version_number = highest_version + 1 if highest_version > 0 else _impl.DEFAULT_VERSION_NUMBER
    _impl._log(
        f"Resolved next render version for prefix '{stem_prefix}' under '{normalized_parent}': "
        f"v{next_version_number:03d} from EXR folders and MP4 files: {matched_entries}"
    )
    return next_version_number


def _build_render_output_data(output_root, shot_name, movie_render_graph_name):
    return _ORIGINAL_BUILD_RENDER_OUTPUT_DATA(output_root, shot_name, movie_render_graph_name)


def _assign_job_name(job, shot_name):
    try:
        _CURRENT_JOB_SHOT_NAMES[id(job)] = str(shot_name or "")
    except Exception:
        pass
    return _ORIGINAL_ASSIGN_JOB_NAME(job, shot_name)


def _assign_job_sequence_and_map(job, sequence_object_path, map_object_path):
    normalized_map_object_path = _normalize_map_object_path(map_object_path)
    if map_object_path != normalized_map_object_path:
        _impl._log(f"Normalized queue job map SoftObjectPath: {map_object_path} -> {normalized_map_object_path}")

    try:
        job.set_editor_property("sequence", unreal.SoftObjectPath(sequence_object_path))
        _impl._log(f"Assigned queue job sequence SoftObjectPath: {sequence_object_path}")
    except Exception as exc:
        _impl._log_error(f"Failed to assign sequence on queue job: {exc}")
        return False

    try:
        job.set_editor_property("map", unreal.SoftObjectPath(normalized_map_object_path))
        _impl._log(f"Assigned queue job map SoftObjectPath: {normalized_map_object_path}")
    except Exception as exc:
        _impl._log_error(f"Failed to assign map on queue job: {exc}")
        return False

    return True


def _assign_movie_render_graph_to_job(job, graph_asset):
    return _ORIGINAL_ASSIGN_MOVIE_RENDER_GRAPH_TO_JOB(job, graph_asset)


def _get_or_create_job_configuration(job):
    for getter_name in ("get_configuration", "get_config"):
        getter = getattr(job, getter_name, None)
        if not callable(getter):
            continue
        try:
            config = getter()
        except Exception:
            continue
        if config:
            return config
    return None


def _find_or_add_output_setting(config):
    if not config:
        return None

    output_setting_class = getattr(unreal, "MoviePipelineOutputSetting", None)
    if not output_setting_class:
        _impl._log_warning("MoviePipelineOutputSetting class was unavailable; queue Output column may keep its default display path.")
        return None

    for method_name in ("find_or_add_setting_by_class", "find_setting_by_class"):
        method = getattr(config, method_name, None)
        if not callable(method):
            continue
        try:
            output_setting = method(output_setting_class)
        except Exception:
            continue
        if output_setting:
            return output_setting

    return None


def _apply_job_queue_display_output_directory(job, output_directory):
    """Mirror the graph OutputDirectory override into the queue job UI Output column.

    Movie Render Graph uses the Primary Graph Variable override for the actual
    render output path. The Movie Render Queue list view still reads the regular
    MoviePipelineOutputSetting on the queue job for its Output column.
    """
    normalized_output_directory = os.path.normpath(str(output_directory or "").strip())
    if not normalized_output_directory:
        _impl._log_warning("Could not set queue display output directory because output_directory was empty.")
        return False

    config = _get_or_create_job_configuration(job)
    if not config:
        _impl._log_warning("Could not access queue job configuration; queue Output column may keep its default display path.")
        return False

    output_setting = _find_or_add_output_setting(config)
    if not output_setting:
        _impl._log_warning("Could not access MoviePipelineOutputSetting; queue Output column may keep its default display path.")
        return False

    try:
        output_setting.set_editor_property("output_directory", unreal.DirectoryPath(normalized_output_directory))
    except Exception as exc:
        _impl._log_warning(f"Failed to set queue display output directory: {exc}")
        return False

    _impl._log(f"Set queue display Output column directory to: {normalized_output_directory}")
    return True


def _apply_job_output_overrides(job, graph_asset, output_directory, file_name_format, mp4_file_name_format):
    result = _ORIGINAL_APPLY_JOB_OUTPUT_OVERRIDES(
        job,
        graph_asset,
        output_directory,
        file_name_format,
        mp4_file_name_format,
    )

    _apply_job_queue_display_output_directory(job, output_directory)
    return result


def _get_or_create_override_container(job, graph_asset, context_label):
    get_overrides = getattr(job, "get_or_create_variable_overrides", None)
    if not callable(get_overrides):
        _impl._log_warning(f"Queue job does not expose get_or_create_variable_overrides(); leaving {context_label} defaults unchanged.")
        return None
    try:
        override_container = get_overrides(graph_asset)
    except Exception as exc:
        _impl._log_warning(f"Failed to get graph variable override container for {context_label}: {exc}")
        return None
    if not override_container:
        _impl._log_warning(f"Graph variable override container was empty for {context_label}; leaving graph defaults unchanged.")
        return None
    updater = getattr(override_container, "update_graph_variable_overrides", None)
    if callable(updater):
        try:
            updater()
        except Exception as exc:
            _impl._log_warning(f"update_graph_variable_overrides() failed for {context_label}: {exc}")
    return override_container


def _set_graph_bool_override(override_container, graph_asset, variable_name, enabled):
    graph_variable = _impl._find_graph_variable_by_name(graph_asset, variable_name)
    if not graph_variable:
        _impl._log_warning(f"Graph does not expose '{variable_name}'. Job will use graph default {variable_name} behavior.")
        return "unsupported"

    _impl._set_variable_enable_state(override_container, graph_variable, True)

    try:
        success = override_container.set_value_bool(graph_variable, bool(enabled))
    except Exception as exc:
        _impl._log_error(f"Failed to set {variable_name} override: {exc}")
        return "failed"

    if not success:
        _impl._log_error(f"set_value_bool() reported failure for {variable_name}.")
        return "failed"

    _impl._log(f"Set {variable_name} override to: {bool(enabled)}")
    return "configured"


def _apply_job_render_format_overrides(job, graph_asset):
    shot_name = _CURRENT_JOB_SHOT_NAMES.get(id(job), "")
    if not shot_name:
        _impl._log_warning("Could not resolve shot name for MP4/EXR graph overrides; leaving graph defaults unchanged.")
        return "unsupported"

    render_format_flags = _CURRENT_RENDER_FORMAT_BY_SHOT.get(shot_name)
    if render_format_flags is None:
        _impl._log_warning(f"No MP4/EXR flags were registered for shot '{shot_name}'; leaving graph defaults unchanged.")
        return "unsupported"

    override_container = _get_or_create_override_container(job, graph_asset, "MP4/EXR")
    if not override_container:
        return "unsupported"

    mp4_result = _set_graph_bool_override(override_container, graph_asset, MP4_VARIABLE_NAME, render_format_flags.get("mp4", False))
    exr_result = _set_graph_bool_override(override_container, graph_asset, EXR_VARIABLE_NAME, render_format_flags.get("exr", False))

    if "failed" in (mp4_result, exr_result):
        return "failed"
    if mp4_result == "configured" and exr_result == "configured":
        return "configured"
    if "configured" in (mp4_result, exr_result):
        return "partial"
    return "unsupported"


def _apply_job_hero_override(job, graph_asset, hero_enabled):
    format_override_result = _apply_job_render_format_overrides(job, graph_asset)
    if format_override_result == "failed":
        return "failed"

    hero_result = _ORIGINAL_APPLY_JOB_HERO_OVERRIDE(job, graph_asset, hero_enabled)
    shot_name = _CURRENT_JOB_SHOT_NAMES.get(id(job), "")
    _impl._log(
        f"MP4/EXR override result for shot '{shot_name}': {format_override_result}; hero_override_result={hero_result}"
    )
    return hero_result


def _build_render_format_lookup(shot_name_array, is_active_array, mp4_array, exr_array):
    try:
        shot_names = list(shot_name_array or [])
    except Exception:
        shot_names = []
    try:
        active_flags = list(is_active_array or [])
    except Exception:
        active_flags = []
    try:
        mp4_flags = list(mp4_array or [])
    except Exception:
        mp4_flags = []
    try:
        exr_flags = list(exr_array or [])
    except Exception:
        exr_flags = []

    if len(active_flags) < len(shot_names):
        active_flags.extend([0] * (len(shot_names) - len(active_flags)))
    if len(mp4_flags) < len(shot_names):
        mp4_flags.extend([0] * (len(shot_names) - len(mp4_flags)))
    if len(exr_flags) < len(shot_names):
        exr_flags.extend([0] * (len(shot_names) - len(exr_flags)))

    render_format_by_shot = {}
    seen_active_shots = set()

    for index, raw_shot_name in enumerate(shot_names):
        shot_name = _impl._sanitize_shot_name(raw_shot_name)
        is_active = _impl._coerce_to_bool_flag(active_flags[index] if index < len(active_flags) else 0)
        if not shot_name or not is_active:
            continue
        if shot_name in seen_active_shots:
            continue
        seen_active_shots.add(shot_name)
        render_format_by_shot[shot_name] = {
            "mp4": _impl._coerce_to_bool_flag(mp4_flags[index] if index < len(mp4_flags) else 0),
            "exr": _impl._coerce_to_bool_flag(exr_flags[index] if index < len(exr_flags) else 0),
        }

    return render_format_by_shot


def run(
    shot_name_array,
    is_active_array,
    is_hero_array,
    movie_render_graph,
    render_graph_folder_path=None,
    render_graph_secondary_folder_path=None,
    mp4_array=None,
    exr_array=None,
):
    global _CURRENT_SHOW_FOLDERS
    global _GRAPH_VARIABLE_CACHE
    global _CURRENT_RENDER_FORMAT_BY_SHOT
    global _CURRENT_JOB_SHOT_NAMES

    previous_show_folders = _CURRENT_SHOW_FOLDERS
    previous_graph_variable_cache = _GRAPH_VARIABLE_CACHE
    previous_render_format_by_shot = _CURRENT_RENDER_FORMAT_BY_SHOT
    previous_job_shot_names = _CURRENT_JOB_SHOT_NAMES

    try:
        _CURRENT_SHOW_FOLDERS = _impl._list_valid_show_folders()
        _GRAPH_VARIABLE_CACHE = {}
        _CURRENT_JOB_SHOT_NAMES = {}
        _CURRENT_RENDER_FORMAT_BY_SHOT = _build_render_format_lookup(
            shot_name_array,
            is_active_array,
            mp4_array,
            exr_array,
        )
        _impl._log(f"Cached valid show folders for render queue submission: {_CURRENT_SHOW_FOLDERS}")
        _impl._log(f"Cached MP4/EXR render format flags by shot: {_CURRENT_RENDER_FORMAT_BY_SHOT}")
        return _ORIGINAL_RUN(
            shot_name_array,
            is_active_array,
            is_hero_array,
            movie_render_graph,
            render_graph_folder_path,
            render_graph_secondary_folder_path,
        )
    finally:
        _CURRENT_SHOW_FOLDERS = previous_show_folders
        _GRAPH_VARIABLE_CACHE = previous_graph_variable_cache
        _CURRENT_RENDER_FORMAT_BY_SHOT = previous_render_format_by_shot
        _CURRENT_JOB_SHOT_NAMES = previous_job_shot_names


_WRAPPER_RUN = run

_impl._coerce_to_object_path = _coerce_to_object_path
_impl._load_shot_data_asset_for_shot = _load_shot_data_asset_for_shot
_impl._extract_associated_level_object_path = _extract_associated_level_object_path
_impl._find_next_render_version_number = _find_next_render_version_number
_impl._build_render_output_data = _build_render_output_data
_impl._assign_job_name = _assign_job_name
_impl._assign_job_sequence_and_map = _assign_job_sequence_and_map
_impl._assign_movie_render_graph_to_job = _assign_movie_render_graph_to_job
_impl._apply_job_output_overrides = _apply_job_output_overrides
_impl._apply_job_hero_override = _apply_job_hero_override
_impl._find_level_sequence_asset_path = _find_level_sequence_asset_path
_impl._find_movie_render_graph_asset = _find_movie_render_graph_asset
_impl._get_graph_variables = _get_graph_variables
_impl.run = _WRAPPER_RUN

for _name in dir(_impl):
    if _name.startswith("__"):
        continue
    globals()[_name] = getattr(_impl, _name)

ASSOCIATED_LEVEL_PROPERTY_CANDIDATES = _impl.ASSOCIATED_LEVEL_PROPERTY_CANDIDATES
run = _WRAPPER_RUN
