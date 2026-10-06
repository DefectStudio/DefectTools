"""Create BP_WorldMover and attach selected Sequencer spawnables to it.

Widget Execute Python Script body:

    import importlib
    import attach_to_worldmover

    importlib.invalidate_caches()
    importlib.reload(attach_to_worldmover)
    attach_to_worldmover.run()

Selection may be on an actor binding row, one of its tracks, or one of its
sections. If the focused sequence does not already contain BP_WorldMover, the
tool creates it as a spawnable from the QuickWidgetTools plugin asset. Attach
sections cover the focused sequence playback range and use KEEP_WORLD so actors
do not jump when the relationship is added.
"""

import traceback

import unreal


LOG_PREFIX = "[AttachToWorldMover]"
DEFAULT_WORLD_MOVER_NAME = "BP_WorldMover"
DEFAULT_WORLD_MOVER_ASSET_PATH = (
    "/QuickWidgetTools/Misc/BP_WorldMover.BP_WorldMover"
)


def _log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


def _warning(message):
    unreal.log_warning(f"{LOG_PREFIX} Warning: {message}")


def _error(message):
    unreal.log_error(f"{LOG_PREFIX} Error: {message}")


def _as_list(value):
    if value is None:
        return []
    try:
        return list(value)
    except Exception:
        return [value]


def _safe_call(obj, method_name, *args):
    method = getattr(obj, method_name, None) if obj is not None else None
    if method is None:
        return None
    try:
        return method(*args)
    except Exception:
        return None


def _safe_set(obj, property_name, value):
    try:
        obj.set_editor_property(property_name, value)
        return True
    except Exception:
        return False


def _binding_name(binding):
    return str(
        _safe_call(binding, "get_display_name")
        or _safe_call(binding, "get_name")
        or binding
    )


def _same_binding(left, right):
    if left is None or right is None:
        return False
    try:
        if left == right:
            return True
    except Exception:
        pass
    left_id = _safe_call(left, "get_id")
    right_id = _safe_call(right, "get_id")
    try:
        return left_id is not None and right_id is not None and left_id == right_id
    except Exception:
        return False


def _object_key(obj):
    path = _safe_call(obj, "get_path_name")
    if path:
        return str(path)
    outer = _safe_call(obj, "get_outer")
    outer_path = _safe_call(outer, "get_path_name") or ""
    return f"{outer_path}|{_safe_call(obj, 'get_name') or obj}"


def _normalize_name(value):
    text = str(value or "").lower().strip()
    for character in " \\/:;,.[]{}()<>|?*\"'`~!@#$%^&+=-":
        text = text.replace(character, "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


def _get_focused_sequence():
    library = unreal.LevelSequenceEditorBlueprintLibrary
    return (
        _safe_call(library, "get_focused_level_sequence")
        or _safe_call(library, "get_current_level_sequence")
    )


def _get_spawnables(sequence):
    spawnables = _safe_call(sequence, "get_spawnables")
    if spawnables is not None:
        return _as_list(spawnables)
    return _as_list(
        _safe_call(unreal.MovieSceneSequenceExtensions, "get_spawnables", sequence)
    )


def _get_tracks(binding):
    return _as_list(_safe_call(binding, "get_tracks"))


def _get_sections(track):
    return _as_list(_safe_call(track, "get_sections"))


def _collect_selected_spawnables(spawnables):
    """Capture selection before creating BP_WorldMover.

    Creating a binding can change Sequencer selection, so callers must invoke
    this before adding the missing World Mover spawnable.
    """
    library = unreal.LevelSequenceEditorBlueprintLibrary
    selected = []

    def add_unique(binding):
        if not any(_same_binding(binding, existing) for existing in selected):
            selected.append(binding)

    for selected_binding in _as_list(_safe_call(library, "get_selected_bindings")):
        for spawnable in spawnables:
            if _same_binding(selected_binding, spawnable):
                add_unique(spawnable)
                break

    selected_tracks = {
        _object_key(track)
        for track in _as_list(_safe_call(library, "get_selected_tracks"))
    }
    selected_sections = {
        _object_key(section)
        for section in _as_list(_safe_call(library, "get_selected_sections"))
    }

    if selected_tracks or selected_sections:
        for binding in spawnables:
            for track in _get_tracks(binding):
                track_selected = _object_key(track) in selected_tracks
                section_selected = any(
                    _object_key(section) in selected_sections
                    for section in _get_sections(track)
                )
                if track_selected or section_selected:
                    add_unique(binding)
                    break

    return selected


def _find_world_mover(spawnables, world_mover_name):
    """Return the existing mover, None when missing, or fail on duplicates."""
    target = _normalize_name(world_mover_name)
    exact = []
    prefixed = []

    for binding in spawnables:
        normalized = _normalize_name(_binding_name(binding))
        if normalized == target:
            exact.append(binding)
        elif normalized.startswith((target + "_", target + "_c")):
            prefixed.append(binding)

    matches = exact or prefixed
    if len(matches) == 1:
        return matches[0]
    if not matches:
        return None
    raise RuntimeError(
        f"Multiple spawnables matched {world_mover_name!r}: "
        f"{[_binding_name(item) for item in matches]}"
    )


def _load_world_mover_class(asset_path):
    """Load the Blueprint generated class from the plugin content mount."""
    editor_asset_library = getattr(unreal, "EditorAssetLibrary", None)
    blueprint_class = _safe_call(
        editor_asset_library,
        "load_blueprint_class",
        asset_path,
    )
    if blueprint_class is not None:
        return blueprint_class

    blueprint_asset = _safe_call(unreal, "load_asset", asset_path)
    if blueprint_asset is None:
        raise RuntimeError(
            f"Could not load BP_WorldMover asset at {asset_path!r}. "
            "Confirm the QuickWidgetTools plugin content is mounted."
        )

    blueprint_class = _safe_call(blueprint_asset, "generated_class")
    if blueprint_class is None:
        try:
            blueprint_class = blueprint_asset.get_editor_property("generated_class")
        except Exception:
            blueprint_class = None

    if blueprint_class is None:
        generated_class_path = asset_path + "_C"
        blueprint_class = _safe_call(unreal, "load_class", None, generated_class_path)

    if blueprint_class is None:
        raise RuntimeError(
            f"Loaded {asset_path!r}, but could not resolve its generated Blueprint class"
        )

    return blueprint_class


def _set_binding_display_name(binding, display_name):
    for method_name in ("set_display_name", "set_name"):
        method = getattr(binding, method_name, None)
        if method is None:
            continue
        try:
            method(display_name)
            return True
        except Exception:
            pass

    return _safe_set(binding, "display_name", display_name) or _safe_set(
        binding,
        "name",
        display_name,
    )


def _create_world_mover_spawnable(
    sequence,
    world_mover_name,
    world_mover_asset_path,
):
    blueprint_class = _load_world_mover_class(world_mover_asset_path)

    world_mover = _safe_call(sequence, "add_spawnable_from_class", blueprint_class)
    if world_mover is None:
        world_mover = _safe_call(
            unreal.MovieSceneSequenceExtensions,
            "add_spawnable_from_class",
            sequence,
            blueprint_class,
        )

    if world_mover is None:
        raise RuntimeError(
            f"Could not add {world_mover_name!r} as a spawnable from "
            f"{world_mover_asset_path!r}"
        )

    if not _set_binding_display_name(world_mover, world_mover_name):
        _warning(
            f"Created the World Mover spawnable, but could not force its display "
            f"name to {world_mover_name!r}. Current name: {_binding_name(world_mover)!r}"
        )

    _log(
        f"Created World Mover spawnable: {_binding_name(world_mover)} "
        f"from {world_mover_asset_path}"
    )
    return world_mover


def _is_attach_track(track):
    try:
        return isinstance(track, unreal.MovieScene3DAttachTrack)
    except Exception:
        class_name = _safe_call(_safe_call(track, "get_class"), "get_name")
        return str(class_name or "") == "MovieScene3DAttachTrack"


def _resolve_constraint_parent(sequence, section):
    constraint_id = _safe_call(section, "get_constraint_binding_id")
    if constraint_id is None:
        try:
            constraint_id = section.get_editor_property("constraint_binding_id")
        except Exception:
            return None

    resolved = _safe_call(sequence, "resolve_binding_id", constraint_id)
    if resolved is not None:
        return resolved
    return _safe_call(
        unreal.MovieSceneSequenceExtensions,
        "resolve_binding_id",
        sequence,
        constraint_id,
    )


def _existing_attach_status(sequence, child, world_mover):
    for track in _get_tracks(child):
        if not _is_attach_track(track):
            continue
        for section in _get_sections(track):
            parent = _resolve_constraint_parent(sequence, section)
            if parent is not None and _same_binding(parent, world_mover):
                return "world_mover"
        return "other"
    return "none"


def _get_binding_id(sequence, binding):
    binding_id = _safe_call(sequence, "get_binding_id", binding)
    if binding_id is not None:
        return binding_id

    # Reflected signatures differed across recent UE releases, so retain both.
    for args in ((sequence, binding), (binding,)):
        binding_id = _safe_call(
            unreal.MovieSceneSequenceExtensions,
            "get_binding_id",
            *args,
        )
        if binding_id is not None:
            return binding_id
    return None


def _remove_track(binding, track):
    if _safe_call(binding, "remove_track", track) is not None:
        return
    extensions = getattr(unreal, "MovieSceneBindingExtensions", None)
    _safe_call(extensions, "remove_track", binding, track)


def _set_keep_world(section):
    keep_world = unreal.AttachmentRule.KEEP_WORLD
    required = (
        "attachment_location_rule",
        "attachment_rotation_rule",
        "attachment_scale_rule",
    )
    missing = [name for name in required if not _safe_set(section, name, keep_world)]
    if missing:
        raise RuntimeError(f"Could not set KEEP_WORLD on {missing}")

    # These are not exposed consistently by every Unreal Python build.
    for optional_name in (
        "detachment_location_rule",
        "detachment_rotation_rule",
        "detachment_scale_rule",
    ):
        _safe_set(section, optional_name, keep_world)


def _create_attach(sequence, child, world_mover, start_frame, end_frame):
    track = child.add_track(unreal.MovieScene3DAttachTrack)
    if track is None:
        raise RuntimeError("Could not create MovieScene3DAttachTrack")

    try:
        section = track.add_section()
        if section is None:
            raise RuntimeError("Could not create MovieScene3DAttachSection")

        section.set_range(int(start_frame), int(end_frame))

        world_mover_id = _get_binding_id(sequence, world_mover)
        if world_mover_id is None:
            raise RuntimeError("Could not create BP_WorldMover binding ID")

        section.set_constraint_binding_id(world_mover_id)
        _safe_set(section, "attach_component_name", unreal.Name(""))
        _safe_set(section, "attach_socket_name", unreal.Name(""))
        _set_keep_world(section)
    except Exception:
        _remove_track(child, track)
        raise


def run(
    world_mover_name=DEFAULT_WORLD_MOVER_NAME,
    world_mover_asset_path=DEFAULT_WORLD_MOVER_ASSET_PATH,
):
    """Create/reuse BP_WorldMover and attach selected spawnables to it."""
    _log("----- run() called -----")

    try:
        sequence = _get_focused_sequence()
        if sequence is None:
            raise RuntimeError("No Level Sequence is open/focused in Sequencer")

        if _safe_call(
            unreal.LevelSequenceEditorBlueprintLibrary,
            "is_level_sequence_locked",
        ):
            raise RuntimeError("The focused Level Sequence is locked for editing")

        # Capture this before creating a binding; Sequencer may change selection.
        spawnables = _get_spawnables(sequence)
        selected = _collect_selected_spawnables(spawnables)
        existing_world_mover = _find_world_mover(spawnables, world_mover_name)
        targets = [
            item
            for item in selected
            if not _same_binding(item, existing_world_mover)
        ]

        if existing_world_mover is not None and len(targets) != len(selected):
            _warning("BP_WorldMover was selected and was excluded from its own children")
        if not targets:
            raise RuntimeError(
                "No child spawnables are selected. Select actor binding rows, tracks, "
                "or sections and run again"
            )

        start_frame = int(sequence.get_playback_start())
        end_frame = int(sequence.get_playback_end())

        _log(f"Focused sequence: {sequence.get_name()}")
        _log(f"Attach range: {start_frame} to {end_frame} end-exclusive")
        _log(f"Targets captured before mover creation: {[_binding_name(item) for item in targets]}")

        attached = []
        already_attached = []
        blocked = []
        failed = []
        created_world_mover = False

        with unreal.ScopedEditorTransaction(
            "Create BP_WorldMover and Attach Selected Spawnables"
        ):
            _safe_call(sequence, "modify")

            world_mover = existing_world_mover
            if world_mover is None:
                world_mover = _create_world_mover_spawnable(
                    sequence,
                    world_mover_name,
                    world_mover_asset_path,
                )
                created_world_mover = True
            else:
                _log(f"Using existing World Mover: {_binding_name(world_mover)}")

            for child in targets:
                name = _binding_name(child)
                status = _existing_attach_status(sequence, child, world_mover)

                if status == "world_mover":
                    already_attached.append(name)
                    continue
                if status == "other":
                    blocked.append(name)
                    _warning(
                        f"Skipped {name!r}: it already has an Attach track. "
                        "Existing parent relationships are never overwritten."
                    )
                    continue

                try:
                    _create_attach(
                        sequence,
                        child,
                        world_mover,
                        start_frame,
                        end_frame,
                    )
                    attached.append(name)
                    _log(f"Attached: {name} -> {_binding_name(world_mover)}")
                except Exception as exc:
                    failed.append(name)
                    _error(f"Failed to attach {name!r}: {exc}")

        _safe_call(
            unreal.LevelSequenceEditorBlueprintLibrary,
            "refresh_current_level_sequence",
        )

        _log(f"World Mover created this run: {created_world_mover}")
        _log(f"Newly attached: {len(attached)} {attached}")
        _log(f"Already attached: {len(already_attached)} {already_attached}")
        if blocked:
            _warning(f"Blocked by existing Attach tracks: {blocked}")
        if failed:
            _error(f"Failed: {failed}")

        success = not blocked and not failed
        _log(f"Final return value: {success}")
        return success

    except Exception as exc:
        _error(str(exc))
        _error(traceback.format_exc())
        _log("Final return value: False")
        return False
