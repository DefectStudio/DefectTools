import math
import unreal

# ------------------------------------------------------------
# Spawn Blocking Volume in front of the active level viewport camera
# ------------------------------------------------------------
# Usage from Unreal Python:
#
#   import spawn_blocking_volume
#   spawn_blocking_volume.run()
#
# Optional:
#   spawn_blocking_volume.run(500.0)
#
# Notes:
#   - The volume is spawned 500 Unreal units in front of the active viewport
#     camera by default.
#   - The spawned volume is selected after creation.
#   - The script uses camera direction for placement, but keeps the volume
#     rotation at zero so its bounds stay easy to reason about for selection.


DEFAULT_DISTANCE = 500.0
DEFAULT_LABEL = "BPV_StaticMeshSelection"


def get_active_viewport_camera_info():
    """Return the active level viewport camera location and rotation."""

    # Preferred newer editor subsystem path.
    if hasattr(unreal, "UnrealEditorSubsystem"):
        unreal_editor_subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)

        if unreal_editor_subsystem and hasattr(unreal_editor_subsystem, "get_level_viewport_camera_info"):
            return unreal_editor_subsystem.get_level_viewport_camera_info()

    # Fallback for older Unreal Python setups.
    if hasattr(unreal, "EditorLevelLibrary") and hasattr(unreal.EditorLevelLibrary, "get_level_viewport_camera_info"):
        return unreal.EditorLevelLibrary.get_level_viewport_camera_info()

    unreal.log_error("Could not get active level viewport camera info.")
    return None, None


def rotator_to_forward_vector(rotator):
    """Convert an Unreal Rotator to a forward vector using pitch/yaw."""

    pitch = math.radians(rotator.pitch)
    yaw = math.radians(rotator.yaw)

    return unreal.Vector(
        math.cos(pitch) * math.cos(yaw),
        math.cos(pitch) * math.sin(yaw),
        math.sin(pitch)
    )


def make_location_in_front_of_camera(camera_location, camera_rotation, distance):
    forward = rotator_to_forward_vector(camera_rotation)

    return unreal.Vector(
        camera_location.x + forward.x * distance,
        camera_location.y + forward.y * distance,
        camera_location.z + forward.z * distance
    )


def spawn_actor(actor_class, location, rotation):
    """Spawn an actor using the editor actor subsystem, with legacy fallback."""

    editor_actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

    if editor_actor_subsystem and hasattr(editor_actor_subsystem, "spawn_actor_from_class"):
        return editor_actor_subsystem.spawn_actor_from_class(actor_class, location, rotation)

    if hasattr(unreal, "EditorLevelLibrary") and hasattr(unreal.EditorLevelLibrary, "spawn_actor_from_class"):
        return unreal.EditorLevelLibrary.spawn_actor_from_class(actor_class, location, rotation)

    unreal.log_error("Could not find an editor spawn_actor_from_class function.")
    return None


def select_actor(actor):
    editor_actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

    if editor_actor_subsystem and hasattr(editor_actor_subsystem, "set_selected_level_actors"):
        editor_actor_subsystem.set_selected_level_actors([actor])
        return

    if hasattr(unreal, "EditorLevelLibrary") and hasattr(unreal.EditorLevelLibrary, "set_selected_level_actors"):
        unreal.EditorLevelLibrary.set_selected_level_actors([actor])


def run(distance=DEFAULT_DISTANCE):
    """
    Spawn a Blocking Volume in front of the active level viewport camera.

    Args:
        distance (float): Distance in Unreal units in front of the camera.

    Returns:
        unreal.BlockingVolume or None
    """

    try:
        distance = float(distance)
    except Exception:
        unreal.log_error("distance must be a number. Got: {}".format(distance))
        return None

    camera_location, camera_rotation = get_active_viewport_camera_info()
    if camera_location is None or camera_rotation is None:
        return None

    spawn_location = make_location_in_front_of_camera(
        camera_location,
        camera_rotation,
        distance
    )

    spawn_rotation = unreal.Rotator(0.0, 0.0, 0.0)

    with unreal.ScopedEditorTransaction("Spawn Blocking Volume"):
        blocking_volume = spawn_actor(
            unreal.BlockingVolume,
            spawn_location,
            spawn_rotation
        )

        if blocking_volume is None:
            unreal.log_error("Failed to spawn Blocking Volume.")
            return None

        blocking_volume.set_actor_label(DEFAULT_LABEL, mark_dirty=True)
        select_actor(blocking_volume)

    unreal.log(
        "Spawned Blocking Volume '{}' at {} units in front of the active viewport camera.".format(
            blocking_volume.get_actor_label(),
            distance
        )
    )

    return blocking_volume


if __name__ == "__main__":
    run()
