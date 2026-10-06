import sys
import unreal

# ------------------------------------------------------------
# Select Static Mesh Actors using the selected Blocking Volume
# ------------------------------------------------------------
# Usage from Unreal Python:
#
#   import select_static_mesh_volume
#   select_static_mesh_volume.run("yes")
#
# select_interior = "yes"
#   Selects only Static Mesh Actors whose actor bounds are fully inside
#   the selected Blocking Volume bounds.
#
# select_interior = "no"
#   Selects Static Mesh Actors whose actor bounds overlap/touch
#   the selected Blocking Volume bounds.
#
# Note:
#   This uses actor bounds / axis-aligned bounding boxes, matching the
#   previous tool behavior. It does not test exact mesh triangles or exact
#   brush shape intersection.


DEFAULT_SELECT_INTERIOR = "yes"


def normalize_select_interior(value):
    """Validate and normalize the select_interior string."""
    if value is None:
        value = DEFAULT_SELECT_INTERIOR

    normalized = str(value).strip().lower()

    if normalized not in ("yes", "no"):
        unreal.log_error(
            'select_interior must be "yes" or "no". Got: {}'.format(value)
        )
        return None

    return normalized


def get_actor_bounds_min_max(actor):
    origin, extent = actor.get_actor_bounds(False)

    min_v = unreal.Vector(
        origin.x - extent.x,
        origin.y - extent.y,
        origin.z - extent.z
    )

    max_v = unreal.Vector(
        origin.x + extent.x,
        origin.y + extent.y,
        origin.z + extent.z
    )

    return min_v, max_v


def bounds_fully_inside(inner_min, inner_max, outer_min, outer_max):
    return (
        inner_min.x >= outer_min.x and inner_max.x <= outer_max.x and
        inner_min.y >= outer_min.y and inner_max.y <= outer_max.y and
        inner_min.z >= outer_min.z and inner_max.z <= outer_max.z
    )


def bounds_overlap(a_min, a_max, b_min, b_max):
    return (
        a_min.x <= b_max.x and a_max.x >= b_min.x and
        a_min.y <= b_max.y and a_max.y >= b_min.y and
        a_min.z <= b_max.z and a_max.z >= b_min.z
    )


def get_selected_blocking_volume(editor_actor_subsystem):
    selected_actors = editor_actor_subsystem.get_selected_level_actors()

    blocking_volumes = [
        actor for actor in selected_actors
        if isinstance(actor, unreal.BlockingVolume)
    ]

    if not blocking_volumes:
        unreal.log_error("Please select one Blocking Volume first.")
        return None

    if len(blocking_volumes) > 1:
        unreal.log_warning(
            "Multiple Blocking Volumes selected. Using first selected volume: {}".format(
                blocking_volumes[0].get_actor_label()
            )
        )

    return blocking_volumes[0]


def run(select_interior=DEFAULT_SELECT_INTERIOR):
    """
    Select Static Mesh Actors using the selected Blocking Volume.

    Args:
        select_interior (str):
            "yes" = select only actors fully inside the volume bounds.
            "no"  = select actors whose bounds overlap/touch the volume bounds.
    """
    select_interior = normalize_select_interior(select_interior)
    if select_interior is None:
        return []

    require_fully_inside = (select_interior == "yes")

    editor_actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

    blocking_volume = get_selected_blocking_volume(editor_actor_subsystem)
    if blocking_volume is None:
        return []

    volume_min, volume_max = get_actor_bounds_min_max(blocking_volume)

    actors_to_select = []
    all_actors = editor_actor_subsystem.get_all_level_actors()

    for actor in all_actors:
        if not isinstance(actor, unreal.StaticMeshActor):
            continue

        mesh_min, mesh_max = get_actor_bounds_min_max(actor)

        if require_fully_inside:
            should_select = bounds_fully_inside(
                mesh_min, mesh_max,
                volume_min, volume_max
            )
        else:
            should_select = bounds_overlap(
                mesh_min, mesh_max,
                volume_min, volume_max
            )

        if should_select:
            actors_to_select.append(actor)

    editor_actor_subsystem.set_selected_level_actors(actors_to_select)

    mode_text = "fully inside" if require_fully_inside else "touching / overlapping"

    unreal.log(
        "Selected {} Static Mesh Actors {} Blocking Volume: {}".format(
            len(actors_to_select),
            mode_text,
            blocking_volume.get_actor_label()
        )
    )

    return actors_to_select


# Allows this file to be run directly as a script from Unreal.
# Optional first argument can be "yes" or "no".
if __name__ == "__main__":
    arg_select_interior = DEFAULT_SELECT_INTERIOR

    if len(sys.argv) > 1:
        arg_select_interior = sys.argv[1]

    run(arg_select_interior)
