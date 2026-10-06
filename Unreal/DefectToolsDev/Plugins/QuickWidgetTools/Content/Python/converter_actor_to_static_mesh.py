import re
import unreal

"""
Actor to StaticMeshActor converter.

Converts selected actors, and optionally all of their attached child actors
recursively, into standalone StaticMeshActors while preserving world transform,
component material overrides, and common render/collision settings.

Designed for USD Import Into Level workflows where the visible materials often
live on placed StaticMeshComponent overrides instead of on the StaticMesh asset
slots.
"""

LOG_PREFIX = "[ActorToStaticMeshConverter]"
DEFAULT_TARGET_SUBFOLDER = "SM_Actors"


# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
def _log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


def _warn(message):
    unreal.log_warning(f"{LOG_PREFIX} {message}")


def _error(message):
    unreal.log_error(f"{LOG_PREFIX} {message}")


# -----------------------------------------------------------------------------
# Blueprint input helpers
# -----------------------------------------------------------------------------
def _get_bp_input_string(default=""):
    """
    Unreal's Execute Python Script node injects input pins as globals.
    This remains here for backwards compatibility, but the current Blueprint
    button does not need a folder input pin.
    """
    g = globals()
    for key in (
        "RawFolderPath",
        "raw_folder_path",
        "FolderPath",
        "folder_path",
        "TargetFolder",
        "target_folder",
    ):
        value = g.get(key, None)
        if isinstance(value, str):
            return value
    return default


def _get_bp_input_bool(name, default):
    g = globals()
    value = g.get(name, None)
    if isinstance(value, bool):
        return value
    return default


# -----------------------------------------------------------------------------
# Path / label helpers
# -----------------------------------------------------------------------------
def normalize_folder_path(raw):
    """
    Convert user input like:
      "Environments\\Uplink\\Uplink_Detail"
      "Environments/Uplink/Uplink_Detail/"
      "/Environments/Uplink/Uplink_Detail"
    to Unreal outliner folder path:
      "Environments/Uplink/Uplink_Detail"
    """
    if not raw:
        return ""
    path = str(raw).strip().replace("\\", "/")
    path = path.strip("/")
    return path


def join_folder_path(parent, child):
    parent = normalize_folder_path(parent)
    child = normalize_folder_path(child)

    if parent and child:
        return f"{parent}/{child}"
    if child:
        return child
    return parent


def set_actor_folder(actor, folder_path):
    if not actor or not folder_path:
        return
    try:
        actor.set_folder_path(unreal.Name(folder_path))
    except Exception as exc:
        _warn(f"Could not set folder for {get_actor_label_safe(actor)}: {exc}")


def get_actor_label_safe(actor):
    if not actor:
        return "<None>"
    try:
        return actor.get_actor_label()
    except Exception:
        try:
            return actor.get_name()
        except Exception:
            return str(actor)


def sanitize_actor_label(label):
    label = str(label or "StaticMesh")
    label = label.strip()
    label = re.sub(r"\s+", "_", label)
    label = re.sub(r"[^A-Za-z0-9_\-]+", "_", label)
    label = re.sub(r"_+", "_", label)
    label = label.strip("_")
    return label or "StaticMesh"


def make_actor_label_base(static_mesh, add_sm_prefix=True, avoid_double_sm_prefix=True):
    try:
        mesh_name = static_mesh.get_name()
    except Exception:
        mesh_name = "StaticMesh"

    mesh_name = sanitize_actor_label(mesh_name)

    if not add_sm_prefix:
        return mesh_name

    if avoid_double_sm_prefix and mesh_name.lower().startswith("sm_"):
        return mesh_name

    return f"SM_{mesh_name}"


# -----------------------------------------------------------------------------
# Editor actor helpers
# -----------------------------------------------------------------------------
def get_editor_actor_subsystem():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def get_selected_level_actors():
    actor_subsystem = get_editor_actor_subsystem()

    try:
        return list(actor_subsystem.get_selected_level_actors())
    except Exception:
        pass

    try:
        return list(unreal.EditorLevelLibrary.get_selected_level_actors())
    except Exception:
        return []


def get_all_level_actors():
    actor_subsystem = get_editor_actor_subsystem()

    try:
        return list(actor_subsystem.get_all_level_actors())
    except Exception:
        pass

    try:
        return list(unreal.EditorLevelLibrary.get_all_level_actors())
    except Exception:
        return []


def _append_unique_actor(actor_list, actor):
    if actor and actor not in actor_list:
        actor_list.append(actor)


def get_actor_direct_children(actor, all_actors=None):
    """
    Return directly attached child actors.

    USD-imported hierarchies are usually represented by actor attachment chains,
    for example:
      burrow_geo_a_v003
        World
          many child actors with StaticMeshComponents
    """
    children = []

    if not actor:
        return children

    # Common Unreal Python exposure.
    try:
        result = actor.get_attached_actors()
        if result:
            for child in result:
                _append_unique_actor(children, child)
    except Exception:
        pass

    # Some engine versions expose optional args for reset/recursive behavior.
    for args in ((False,), (False, False), (True, False)):
        try:
            result = actor.get_attached_actors(*args)
            if result:
                for child in result:
                    _append_unique_actor(children, child)
        except Exception:
            pass

    # Fallback: scan all actors and check parent relationship.
    if all_actors:
        for candidate in all_actors:
            if not candidate or candidate == actor:
                continue

            parent = None

            try:
                parent = candidate.get_attach_parent_actor()
            except Exception:
                parent = None

            if parent == actor:
                _append_unique_actor(children, candidate)
                continue

            try:
                parent = candidate.get_parent_actor()
            except Exception:
                parent = None

            if parent == actor:
                _append_unique_actor(children, candidate)

    return children


def collect_actor_hierarchy(root_actors, include_child_actors=True):
    """
    Collect selected/root actors and, when enabled, all attached child actors
    recursively. The result is ordered parent-first and deduplicated.
    """
    all_actors = get_all_level_actors()
    collected = []
    visited = set()

    def actor_key(actor):
        try:
            return actor.get_path_name()
        except Exception:
            try:
                return actor.get_name()
            except Exception:
                return str(id(actor))

    def walk(actor):
        if not actor:
            return

        key = actor_key(actor)
        if key in visited:
            return

        visited.add(key)
        collected.append(actor)

        if not include_child_actors:
            return

        for child in get_actor_direct_children(actor, all_actors=all_actors):
            walk(child)

    for root_actor in root_actors:
        walk(root_actor)

    return collected


def get_static_mesh_components(actor):
    components = []

    if not actor:
        return components

    for cls in (
        unreal.StaticMeshComponent,
        unreal.InstancedStaticMeshComponent,
        unreal.HierarchicalInstancedStaticMeshComponent,
    ):
        try:
            for component in actor.get_components_by_class(cls):
                if component and component not in components:
                    components.append(component)
        except Exception:
            pass

    return components


def get_component_static_mesh(component):
    if not component:
        return None

    try:
        return component.get_editor_property("static_mesh")
    except Exception:
        pass

    try:
        return component.static_mesh
    except Exception:
        return None


def get_static_mesh_actor_component(actor):
    try:
        return actor.static_mesh_component
    except Exception:
        pass

    try:
        return actor.get_component_by_class(unreal.StaticMeshComponent)
    except Exception:
        return None


# -----------------------------------------------------------------------------
# Material / property copy helpers
# -----------------------------------------------------------------------------
def get_component_material_count(component):
    """
    get_num_materials() usually includes StaticMesh slots and component overrides.
    override_materials catches USD imports where the asset has blank/default slots
    but the placed component has overrides.
    """
    count = 0

    try:
        count = max(count, int(component.get_num_materials()))
    except Exception:
        pass

    try:
        override_materials = component.get_editor_property("override_materials") or []
        count = max(count, len(override_materials))
    except Exception:
        pass

    return count


def copy_component_materials(source_component, target_component):
    """
    Copy the visible material result from the source component to the target.
    get_material(index) returns the component override if present, otherwise it
    falls back to the StaticMesh asset material.
    """
    copied = 0
    material_count = get_component_material_count(source_component)

    for material_index in range(material_count):
        try:
            material = source_component.get_material(material_index)
        except Exception:
            material = None

        if not material:
            continue

        try:
            target_component.set_material(material_index, material)
            copied += 1
        except Exception as exc:
            _warn(
                "Could not copy material slot {} from {} to {}: {}".format(
                    material_index,
                    source_component.get_name(),
                    target_component.get_name(),
                    exc,
                )
            )

    return copied


def copy_basic_component_properties(source_component, target_component):
    """
    Copy simple editor properties that are usually safe for a conversion pass.
    """
    for prop in (
        "mobility",
        "cast_shadow",
        "visible",
        "hidden_in_game",
        "receives_decals",
        "render_custom_depth",
        "custom_depth_stencil_value",
        "custom_depth_stencil_write_mask",
        "can_ever_affect_navigation",
    ):
        try:
            target_component.set_editor_property(
                prop,
                source_component.get_editor_property(prop),
            )
        except Exception:
            pass

    try:
        target_component.set_collision_profile_name(source_component.get_collision_profile_name())
    except Exception:
        pass

    for prop in (
        "collision_enabled",
        "collision_response",
        "generate_overlap_events",
    ):
        try:
            target_component.set_editor_property(
                prop,
                source_component.get_editor_property(prop),
            )
        except Exception:
            pass


def copy_actor_properties(source_actor, target_actor):
    """
    Copy a small set of actor-level metadata.
    """
    try:
        target_actor.set_actor_hidden_in_game(source_actor.is_hidden_ed())
    except Exception:
        pass

    try:
        target_actor.set_actor_enable_collision(source_actor.get_actor_enable_collision())
    except Exception:
        pass

    try:
        tags = list(source_actor.tags)
        target_actor.tags = tags
    except Exception:
        pass


# -----------------------------------------------------------------------------
# Conversion
# -----------------------------------------------------------------------------
def spawn_static_mesh_actor_from_component(
    source_actor,
    source_component,
    actor_subsystem,
):
    static_mesh = get_component_static_mesh(source_component)
    if not static_mesh:
        return None, 0

    try:
        world_transform = source_component.get_world_transform()
    except Exception as exc:
        _warn(
            f"Could not read world transform from {source_component.get_name()} on "
            f"{get_actor_label_safe(source_actor)}: {exc}"
        )
        return None, 0

    location = world_transform.translation
    rotation = world_transform.rotation.rotator()

    new_actor = actor_subsystem.spawn_actor_from_class(
        unreal.StaticMeshActor,
        location,
        rotation,
    )

    if not new_actor:
        _warn(f"Failed to spawn StaticMeshActor for {source_component.get_name()}")
        return None, 0

    new_component = get_static_mesh_actor_component(new_actor)
    if not new_component:
        _warn(f"Spawned actor has no StaticMeshComponent: {get_actor_label_safe(new_actor)}")
        return new_actor, 0

    try:
        new_component.set_static_mesh(static_mesh)
    except Exception:
        try:
            new_component.set_editor_property("static_mesh", static_mesh)
        except Exception as exc:
            _warn(
                f"Could not assign static mesh {static_mesh.get_path_name()} to "
                f"{get_actor_label_safe(new_actor)}: {exc}"
            )

    # Preserve full world transform, including non-uniform scale.
    try:
        new_component.set_world_transform(world_transform, False, True)
    except Exception:
        try:
            new_actor.set_actor_transform(world_transform, False, True)
        except Exception as exc:
            _warn(f"Could not apply world transform to {get_actor_label_safe(new_actor)}: {exc}")

    copy_actor_properties(source_actor, new_actor)
    copy_basic_component_properties(source_component, new_component)
    copied_material_slots = copy_component_materials(source_component, new_component)

    return new_actor, copied_material_slots


def rename_static_mesh_actors_by_mesh(
    static_mesh_actors,
    add_sm_prefix=True,
    avoid_double_sm_prefix=True,
):
    counters = {}
    renamed = 0

    for actor in static_mesh_actors:
        component = get_static_mesh_actor_component(actor)
        static_mesh = get_component_static_mesh(component)
        if not static_mesh:
            continue

        base_label = make_actor_label_base(
            static_mesh,
            add_sm_prefix=add_sm_prefix,
            avoid_double_sm_prefix=avoid_double_sm_prefix,
        )

        counters[base_label] = counters.get(base_label, 0) + 1
        new_label = f"{base_label}_{counters[base_label]:03d}"

        try:
            actor.set_actor_label(new_label, mark_dirty=True)
            renamed += 1
        except Exception as exc:
            _warn(f"Could not rename {get_actor_label_safe(actor)} to {new_label}: {exc}")

    return renamed


def convert_actors_to_static_mesh_actors(
    raw_folder_path="",
    target_subfolder=DEFAULT_TARGET_SUBFOLDER,
    selected_only=True,
    include_child_actors=True,
    delete_source_actors=True,
    delete_empty_parent_actors=True,
    skip_existing_static_mesh_actors=True,
    rename_by_static_mesh=True,
    add_sm_prefix=True,
    avoid_double_sm_prefix=True,
):
    """
    Convert selected actors, including their child actor hierarchy by default.

    Args:
        raw_folder_path: Optional World Outliner parent folder.
        target_subfolder: Child folder where new actors go. Default: SM_Actors.
        selected_only: When True, start from selected level actors.
        include_child_actors: When True, recursively include attached child actors.
        delete_source_actors: Delete original actors after successful conversion.
        delete_empty_parent_actors: When recursive conversion is enabled, delete
            selected/container parent actors too, even when they had no mesh component,
            as long as the selection produced at least one converted mesh actor.
        skip_existing_static_mesh_actors: Existing StaticMeshActors are skipped by default.
        rename_by_static_mesh: Rename new actor labels from their StaticMesh asset names.
        add_sm_prefix: Prefix new actor labels with SM_ when needed.
        avoid_double_sm_prefix: Avoid SM_SM_ labels when StaticMesh assets already start with SM_.

    Returns:
        dict summary of the conversion.
    """
    actor_subsystem = get_editor_actor_subsystem()

    if selected_only:
        root_actors = get_selected_level_actors()
    else:
        root_actors = get_all_level_actors()

    root_actors = [actor for actor in root_actors if actor]
    source_actors = collect_actor_hierarchy(root_actors, include_child_actors=include_child_actors)

    parent_folder = normalize_folder_path(raw_folder_path)
    target_folder = join_folder_path(parent_folder, target_subfolder)

    summary = {
        "selected_only": bool(selected_only),
        "include_child_actors": bool(include_child_actors),
        "root_actors_considered": len(root_actors),
        "source_actors_considered": len(source_actors),
        "source_child_actors_discovered": max(0, len(source_actors) - len(root_actors)),
        "source_actors_deleted": 0,
        "source_actors_skipped_static_mesh_actor": 0,
        "source_actors_without_static_mesh_components": 0,
        "static_mesh_components_converted": 0,
        "static_mesh_actors_created": 0,
        "static_mesh_actors_renamed": 0,
        "component_material_slots_copied": 0,
        "target_folder": target_folder,
    }

    if not root_actors:
        if selected_only:
            _warn("No selected actors found. Nothing converted.")
        else:
            _warn("No level actors found. Nothing converted.")
        return summary

    if not source_actors:
        _warn("No source actors found after hierarchy collection. Nothing converted.")
        return summary

    _log("Starting actor conversion.")
    _log(f"selected_only: {selected_only}")
    _log(f"include_child_actors: {include_child_actors}")
    _log(f"delete_source_actors: {delete_source_actors}")
    _log(f"delete_empty_parent_actors: {delete_empty_parent_actors}")
    _log(f"target_folder: {target_folder if target_folder else '<Outliner Root>'}")
    _log(f"root actors considered: {len(root_actors)}")
    _log(f"source actors considered including children: {len(source_actors)}")

    with unreal.ScopedEditorTransaction("Convert Actor Hierarchy to StaticMeshActors"):
        new_actors = []
        converted_source_actors = []
        skipped_static_mesh_source_actors = []

        for source_actor in source_actors:
            if skip_existing_static_mesh_actors and isinstance(source_actor, unreal.StaticMeshActor):
                summary["source_actors_skipped_static_mesh_actor"] += 1
                skipped_static_mesh_source_actors.append(source_actor)
                continue

            static_mesh_components = get_static_mesh_components(source_actor)
            if not static_mesh_components:
                summary["source_actors_without_static_mesh_components"] += 1
                continue

            spawned_any_for_source = False

            for source_component in static_mesh_components:
                static_mesh = get_component_static_mesh(source_component)
                if not static_mesh:
                    continue

                new_actor, copied_slots = spawn_static_mesh_actor_from_component(
                    source_actor,
                    source_component,
                    actor_subsystem,
                )

                if not new_actor:
                    continue

                set_actor_folder(new_actor, target_folder)
                new_actors.append(new_actor)
                spawned_any_for_source = True

                summary["static_mesh_components_converted"] += 1
                summary["component_material_slots_copied"] += int(copied_slots)

            if spawned_any_for_source:
                converted_source_actors.append(source_actor)

        if rename_by_static_mesh:
            summary["static_mesh_actors_renamed"] = rename_static_mesh_actors_by_mesh(
                new_actors,
                add_sm_prefix=add_sm_prefix,
                avoid_double_sm_prefix=avoid_double_sm_prefix,
            )

        if delete_source_actors and new_actors:
            source_actors_to_delete = []

            for actor in source_actors:
                if actor in skipped_static_mesh_source_actors:
                    continue

                if actor in converted_source_actors:
                    _append_unique_actor(source_actors_to_delete, actor)
                    continue

                if include_child_actors and delete_empty_parent_actors:
                    # Delete empty USD/container parents from the selected hierarchy too.
                    _append_unique_actor(source_actors_to_delete, actor)

            # Delete children before parents so attachments do not cause double-delete issues.
            for source_actor in reversed(source_actors_to_delete):
                try:
                    actor_subsystem.destroy_actor(source_actor)
                    summary["source_actors_deleted"] += 1
                except Exception as exc:
                    _warn(f"Could not delete source actor {get_actor_label_safe(source_actor)}: {exc}")

        summary["static_mesh_actors_created"] = len(new_actors)

    _log("Conversion complete.")
    _log(f"Created StaticMeshActors: {summary['static_mesh_actors_created']}")
    _log(f"Converted StaticMeshComponents: {summary['static_mesh_components_converted']}")
    _log(f"Renamed StaticMeshActors: {summary['static_mesh_actors_renamed']}")
    _log(f"Copied material slot assignments: {summary['component_material_slots_copied']}")
    _log(f"Deleted source actors: {summary['source_actors_deleted']}")
    _log(f"Skipped existing StaticMeshActors: {summary['source_actors_skipped_static_mesh_actor']}")
    _log(f"Source actors without StaticMeshComponents: {summary['source_actors_without_static_mesh_components']}")

    if target_folder:
        _log(f"Placed new actors under folder: {target_folder}")
    else:
        _log("No folder path provided; new actors left at the outliner root.")

    return summary


def convert_selected_actors_to_static_mesh_actors(
    raw_folder_path="",
    target_subfolder=DEFAULT_TARGET_SUBFOLDER,
    include_child_actors=True,
    delete_source_actors=True,
    delete_empty_parent_actors=True,
):
    return convert_actors_to_static_mesh_actors(
        raw_folder_path=raw_folder_path,
        target_subfolder=target_subfolder,
        selected_only=True,
        include_child_actors=include_child_actors,
        delete_source_actors=delete_source_actors,
        delete_empty_parent_actors=delete_empty_parent_actors,
        skip_existing_static_mesh_actors=True,
        rename_by_static_mesh=True,
        add_sm_prefix=True,
        avoid_double_sm_prefix=True,
    )


def run_from_bp_globals():
    return convert_actors_to_static_mesh_actors(
        raw_folder_path=_get_bp_input_string(""),
        target_subfolder=DEFAULT_TARGET_SUBFOLDER,
        selected_only=_get_bp_input_bool("selected_only", True),
        include_child_actors=_get_bp_input_bool("include_child_actors", True),
        delete_source_actors=_get_bp_input_bool("delete_source_actors", True),
        delete_empty_parent_actors=_get_bp_input_bool("delete_empty_parent_actors", True),
        skip_existing_static_mesh_actors=_get_bp_input_bool("skip_existing_static_mesh_actors", True),
        rename_by_static_mesh=True,
        add_sm_prefix=True,
        avoid_double_sm_prefix=True,
    )
