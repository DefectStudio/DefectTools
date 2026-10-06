"""Rebuild the selected spawnable binding in the focused Level Sequence.

Blueprint Execute Python Script body:

    import importlib
    import rebuild_spawnable

    importlib.invalidate_caches()
    importlib.reload(rebuild_spawnable)
    rebuild_spawnable.run()

The focused sequence is the child sequence currently open in Sequencer, not
the root/master sequence. Exactly one spawnable binding must be selected.
"""

import traceback

import unreal


LOG_PREFIX = "[RebuildSpawnable]"


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


def _binding_name(binding):
    return str(
        _safe_call(binding, "get_display_name")
        or _safe_call(binding, "get_name")
        or binding
    )


def _is_valid_binding(binding):
    return bool(binding is not None and _safe_call(binding, "is_valid"))


def _asset_path(asset):
    return str(_safe_call(asset, "get_path_name") or asset)


def _save_focused_sequence(sequence):
    try:
        return bool(
            unreal.EditorAssetLibrary.save_loaded_asset(
                sequence,
                only_if_is_dirty=False,
            )
        )
    except TypeError:
        return bool(unreal.EditorAssetLibrary.save_loaded_asset(sequence))


def run():
    """Round-trip the selected spawnable and save only the focused sequence."""
    try:
        library = unreal.LevelSequenceEditorBlueprintLibrary
        sequence = library.get_focused_level_sequence()
        if sequence is None:
            raise RuntimeError(
                "No focused Level Sequence. Open the affected child sequence "
                "in Sequencer before running this tool."
            )

        selected = [
            binding
            for binding in _as_list(library.get_selected_bindings())
            if _is_valid_binding(binding)
        ]
        if len(selected) != 1:
            raise RuntimeError(
                "Select exactly one spawnable binding row in the focused "
                f"sequence; found {len(selected)} selected bindings."
            )

        selected_binding = selected[0]
        binding_name = _binding_name(selected_binding)

        # Possessables do not expose an object template. This prevents the tool
        # from converting an ordinary level binding into a new spawnable.
        if _safe_call(selected_binding, "get_object_template") is None:
            raise RuntimeError(
                f"Selected binding '{binding_name}' does not appear to be a "
                "spawnable. Select its lightning-bolt binding row."
            )

        subsystem = unreal.get_editor_subsystem(
            unreal.LevelSequenceEditorSubsystem
        )
        if subsystem is None:
            raise RuntimeError("LevelSequenceEditorSubsystem is unavailable.")

        sequence_path = _asset_path(sequence)
        _log(
            f"Rebuilding '{binding_name}' in focused sequence "
            f"'{sequence_path}'."
        )

        with unreal.ScopedEditorTransaction(
            "Rebuild Selected Sequencer Spawnable"
        ):
            possessable = subsystem.convert_to_possessable(selected_binding)
            if not _is_valid_binding(possessable):
                raise RuntimeError(
                    f"Failed to convert '{binding_name}' to a possessable."
                )

            rebuilt_spawnables = [
                binding
                for binding in _as_list(
                    subsystem.convert_to_spawnable(possessable)
                )
                if _is_valid_binding(binding)
            ]
            if not rebuilt_spawnables:
                raise RuntimeError(
                    f"Converted '{binding_name}' to a possessable, but failed "
                    "to convert it back to a spawnable. Use Undo before "
                    "continuing."
                )

        library.empty_selection()
        library.select_bindings(rebuilt_spawnables)
        library.force_update()

        if not _save_focused_sequence(sequence):
            raise RuntimeError(
                f"Rebuilt the binding, but failed to save '{sequence_path}'."
            )

        if len(rebuilt_spawnables) > 1:
            _warning(
                f"The possessable produced {len(rebuilt_spawnables)} "
                "spawnable bindings; all were selected and saved."
            )

        rebuilt_names = ", ".join(
            _binding_name(binding) for binding in rebuilt_spawnables
        )
        _log(
            f"Success. Rebuilt [{rebuilt_names}] and saved only the focused "
            f"sequence '{sequence_path}'."
        )
        return True

    except Exception as exc:
        _error(str(exc))
        unreal.log_error(traceback.format_exc())
        return False


if __name__ == "__main__":
    run()
