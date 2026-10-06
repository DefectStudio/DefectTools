import glob
import json
import os
import unreal

# ------------------------------------------------------------
# Align imported Landscape to selected Static Mesh heightmap source
# ------------------------------------------------------------
# Usage after importing the .r16 as a Landscape:
#
#   1. Select the imported Landscape actor.
#   2. Also select the original Static Mesh Actor(s) used to generate the heightmap.
#   3. Run:
#
#      import align_landscape_to_height_map
#      align_landscape_to_height_map.run()
#
# Optional:
#   align_landscape_to_height_map.run(z_scale_override="10.635283")
#   align_landscape_to_height_map.run(metadata_path="D:/.../static_mesh_heightmap_1009_..._metadata.json")
#   align_landscape_to_height_map.run(resolution_override="1009")
#   align_landscape_to_height_map.run(y_location_offset="162.447266")
#
# What this does:
#   - Finds one selected Landscape/LandscapeStreamingProxy actor.
#   - Finds one or more selected StaticMeshActor source actors.
#   - Computes a square XY capture area from the selected mesh actor bounds, matching
#     the heightmap exporter behavior.
#   - Applies the current clean Landscape orientation convention:
#       Rotation = Pitch 0, Yaw 0, Roll 180
#       X =  square_size / (resolution - 1)
#       Y =  square_size / (resolution - 1)
#       Z =  z_scale_override if supplied, otherwise preserve the Landscape's current Z scale
#   - Uses corner-placement for the final actor location:
#       Location X = square_max_x
#       Location Y = square_max_y + optional y_location_offset
#       Location Z = the bounds-center aligned Z result
#
# Notes:
#   - Older heightmaps required negative X scale. New heightmaps exported after
#     static_mesh_to_height_map commit 5edc1ee mirror the R16 columns during export,
#     so the Landscape can use positive X scale.
#   - Landscape actors can normalize equivalent 180-degree rotations in surprising
#     ways. For this pipeline, the desired displayed rotation is Pitch 0, Yaw 0,
#     Roll 180.
#   - Selecting the source mesh makes alignment safer than relying only on the
#     latest metadata file.
#   - Metadata is still useful for resolution. If no metadata is found, pass
#     resolution_override="1009", "2017", "4033", or "8129".


HEIGHTMAP_METADATA_GLOB = "static_mesh_heightmap_*_metadata.json"
DEFAULT_NEGATIVE_X = False
DEFAULT_LANDSCAPE_YAW = 0.0
DEFAULT_LANDSCAPE_ROLL = 180.0
DEFAULT_Y_LOCATION_OFFSET = 0.0


def log(message):
    unreal.log("[AlignLandscapeToHeightMap] {}".format(message))


def log_warning(message):
    unreal.log_warning("[AlignLandscapeToHeightMap] {}".format(message))


def log_error(message):
    unreal.log_error("[AlignLandscapeToHeightMap] {}".format(message))


def get_editor_actor_subsystem():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def normalize_path(path):
    return os.path.normpath(str(path).replace("\\", "/"))


def find_latest_metadata_path():
    output_dir = os.path.join(unreal.Paths.project_dir(), "_output")
    pattern = os.path.join(output_dir, HEIGHTMAP_METADATA_GLOB)
    matches = glob.glob(pattern)

    if not matches:
        return None

    matches.sort(key=lambda path: os.path.getmtime(path), reverse=True)
    return matches[0]


def load_metadata(metadata_path=None):
    if metadata_path:
        path = normalize_path(metadata_path)
    else:
        path = find_latest_metadata_path()

    if not path:
        return None, None

    if not os.path.isfile(path):
        log_warning("Metadata path does not exist: {}".format(path))
        return None, None

    try:
        with open(path, "r", encoding="utf-8") as json_file:
            metadata = json.load(json_file)
    except Exception as exc:
        log_warning("Could not read metadata JSON: {}".format(exc))
        return None, None

    return metadata, path


def is_landscape_actor(actor):
    class_name = actor.get_class().get_name()
    return class_name in ("Landscape", "LandscapeStreamingProxy") or "Landscape" in class_name


def get_selected_actors(editor_actor_subsystem):
    selected_actors = list(editor_actor_subsystem.get_selected_level_actors())

    landscape_actors = [actor for actor in selected_actors if is_landscape_actor(actor)]
    static_mesh_actors = [actor for actor in selected_actors if isinstance(actor, unreal.StaticMeshActor)]

    if not landscape_actors:
        log_error("Select the imported Landscape actor and the source Static Mesh Actor(s).")
        return None, []

    if not static_mesh_actors:
        log_error("Select the original source Static Mesh Actor(s) along with the imported Landscape actor.")
        return None, []

    if len(landscape_actors) > 1:
        log_warning("Multiple Landscape actors selected. Using first: {}".format(landscape_actors[0].get_actor_label()))

    return landscape_actors[0], static_mesh_actors


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

    return origin, extent, min_v, max_v


def get_combined_bounds(actors):
    combined_min = None
    combined_max = None

    for actor in actors:
        actor_center, actor_extent, actor_min, actor_max = get_actor_bounds_min_max(actor)

        if combined_min is None:
            combined_min = unreal.Vector(actor_min.x, actor_min.y, actor_min.z)
            combined_max = unreal.Vector(actor_max.x, actor_max.y, actor_max.z)
            continue

        combined_min.x = min(combined_min.x, actor_min.x)
        combined_min.y = min(combined_min.y, actor_min.y)
        combined_min.z = min(combined_min.z, actor_min.z)

        combined_max.x = max(combined_max.x, actor_max.x)
        combined_max.y = max(combined_max.y, actor_max.y)
        combined_max.z = max(combined_max.z, actor_max.z)

    return combined_min, combined_max


def make_square_xy_bounds(bounds_min, bounds_max):
    width_x = bounds_max.x - bounds_min.x
    width_y = bounds_max.y - bounds_min.y
    square_size = max(width_x, width_y)

    center_x = (bounds_min.x + bounds_max.x) * 0.5
    center_y = (bounds_min.y + bounds_max.y) * 0.5
    half_size = square_size * 0.5

    square_min = unreal.Vector(center_x - half_size, center_y - half_size, bounds_min.z)
    square_max = unreal.Vector(center_x + half_size, center_y + half_size, bounds_max.z)

    return square_min, square_max, square_size


def get_bounds_center(bounds_min, bounds_max):
    return unreal.Vector(
        (bounds_min.x + bounds_max.x) * 0.5,
        (bounds_min.y + bounds_max.y) * 0.5,
        (bounds_min.z + bounds_max.z) * 0.5
    )


def get_resolution(metadata=None, resolution_override=None):
    if resolution_override is not None and str(resolution_override).strip() != "":
        return int(str(resolution_override).strip())

    if metadata and "resolution" in metadata:
        return int(metadata["resolution"])

    log_error(
        "Could not determine heightmap resolution. Pass resolution_override='1009' "
        "or run from the same project _output folder that contains the metadata JSON."
    )
    return None


def warn_if_metadata_source_mismatch(metadata, static_mesh_actors):
    if not metadata:
        return

    metadata_labels = set(metadata.get("selected_static_mesh_actor_labels", []))
    selected_labels = set(actor.get_actor_label() for actor in static_mesh_actors)

    if not metadata_labels:
        return

    if metadata_labels.isdisjoint(selected_labels):
        log_warning(
            "Selected mesh labels do not match the metadata source labels. "
            "Using selected mesh bounds anyway. Metadata labels={}, selected labels={}".format(
                sorted(metadata_labels),
                sorted(selected_labels)
            )
        )


def get_scale_from_selection(landscape_actor, square_size, resolution, z_scale_override=None, negative_x=DEFAULT_NEGATIVE_X):
    xy_scale = square_size / float(resolution - 1)
    current_scale = landscape_actor.get_actor_scale3d()

    if z_scale_override is not None and str(z_scale_override).strip() != "":
        z_scale = float(str(z_scale_override).strip())
    else:
        # Preserve current Z by default. This is safer because imported Landscape Z scale
        # can be project/import-setting dependent, and the user may have already dialed it in.
        z_scale = current_scale.z

    x_scale = -xy_scale if negative_x else xy_scale
    y_scale = xy_scale

    return unreal.Vector(x_scale, y_scale, z_scale)


def make_clean_rotation(yaw=DEFAULT_LANDSCAPE_YAW, roll=DEFAULT_LANDSCAPE_ROLL):
    return unreal.Rotator(0.0, float(yaw), float(roll))


def set_actor_scale(actor, scale):
    actor.set_actor_scale3d(scale)

    try:
        actor.modify()
    except Exception:
        pass


def force_clean_actor_rotation(actor, yaw=DEFAULT_LANDSCAPE_YAW, roll=DEFAULT_LANDSCAPE_ROLL):
    """Try several routes because Landscape actors can normalize equivalent 180-degree rotations."""

    rotation = make_clean_rotation(yaw, roll)

    try:
        actor.set_actor_rotation(rotation, False)
    except Exception as exc:
        log_warning("set_actor_rotation failed: {}".format(exc))

    # This may preserve the displayed Euler better than set_actor_rotation for some actors.
    try:
        actor.set_editor_property("actor_rotation", rotation)
    except Exception:
        pass

    root_component = None
    try:
        root_component = actor.get_root_component()
    except Exception:
        root_component = None

    if root_component:
        try:
            root_component.set_editor_property("relative_rotation", rotation)
        except Exception:
            pass

        try:
            root_component.set_relative_rotation(rotation, False, None, False)
        except Exception:
            try:
                root_component.set_relative_rotation(rotation)
            except Exception:
                pass

    try:
        actor.modify()
    except Exception:
        pass


def move_actor_bounds_center_to(actor, desired_center):
    current_center, current_extent, current_min, current_max = get_actor_bounds_min_max(actor)
    actor_location = actor.get_actor_location()

    delta = unreal.Vector(
        desired_center.x - current_center.x,
        desired_center.y - current_center.y,
        desired_center.z - current_center.z
    )

    new_location = unreal.Vector(
        actor_location.x + delta.x,
        actor_location.y + delta.y,
        actor_location.z + delta.z
    )

    actor.set_actor_location(new_location, False, False)

    try:
        actor.modify()
    except Exception:
        pass

    return delta


def set_actor_location(actor, location):
    actor.set_actor_location(location, False, False)

    try:
        actor.modify()
    except Exception:
        pass


def get_corner_location(square_max, z_location, y_location_offset=DEFAULT_Y_LOCATION_OFFSET):
    return unreal.Vector(
        square_max.x,
        square_max.y + float(y_location_offset),
        z_location
    )


def run(
    metadata_path=None,
    z_scale_override=None,
    resolution_override=None,
    negative_x=DEFAULT_NEGATIVE_X,
    yaw=DEFAULT_LANDSCAPE_YAW,
    roll=DEFAULT_LANDSCAPE_ROLL,
    y_location_offset=DEFAULT_Y_LOCATION_OFFSET,
    use_corner_location=True
):
    """
    Align the selected imported Landscape to the selected source Static Mesh Actor(s).

    Args:
        metadata_path (str|None): Optional explicit metadata JSON path. Used for resolution only.
        z_scale_override (str|float|None): Optional Z scale override. If omitted,
            the selected Landscape's current Z scale is preserved.
        resolution_override (str|int|None): Optional explicit heightmap resolution.
        negative_x (bool): Use False for new flipped heightmaps. Use True only for older pre-flip heightmaps.
        yaw (str|float): Landscape yaw. Default 0.0.
        roll (str|float): Landscape roll. Default 180.0.
        y_location_offset (str|float): Optional extra world-space Y offset for corner placement.
        use_corner_location (bool): If true, final X/Y use the Landscape corner convention instead of bounds center.

    Returns:
        dict or None: Applied settings.
    """

    editor_actor_subsystem = get_editor_actor_subsystem()
    if not editor_actor_subsystem:
        log_error("Editor actor subsystem was not available.")
        return None

    landscape_actor, static_mesh_actors = get_selected_actors(editor_actor_subsystem)
    if not landscape_actor or not static_mesh_actors:
        return None

    metadata, resolved_metadata_path = load_metadata(metadata_path)
    resolution = get_resolution(metadata, resolution_override)
    if resolution is None:
        return None

    warn_if_metadata_source_mismatch(metadata, static_mesh_actors)

    mesh_bounds_min, mesh_bounds_max = get_combined_bounds(static_mesh_actors)
    square_min, square_max, square_size = make_square_xy_bounds(mesh_bounds_min, mesh_bounds_max)
    desired_center = get_bounds_center(mesh_bounds_min, mesh_bounds_max)

    scale = get_scale_from_selection(
        landscape_actor,
        square_size,
        resolution,
        z_scale_override,
        negative_x
    )

    log("Landscape actor: {}".format(landscape_actor.get_actor_label()))
    log("Source mesh actors: {}".format([actor.get_actor_label() for actor in static_mesh_actors]))
    log("Metadata: {}".format(resolved_metadata_path if resolved_metadata_path else "None"))
    log("Resolution: {}".format(resolution))
    log("Selected mesh square size: {:.6f}".format(square_size))
    log("Desired source bounds center: {}".format(desired_center))
    log("Applying rotation: Pitch=0.0, Yaw={:.6f}, Roll={:.6f}".format(float(yaw), float(roll)))
    log("Applying scale: X={:.6f}, Y={:.6f}, Z={:.6f}".format(scale.x, scale.y, scale.z))
    log("Use corner location: {}".format(bool(use_corner_location)))

    with unreal.ScopedEditorTransaction("Align Landscape To Selected Mesh Height Map Source"):
        force_clean_actor_rotation(landscape_actor, yaw, roll)
        set_actor_scale(landscape_actor, scale)

        # First align Z safely from bounds. This preserves the known-good Z placement.
        first_delta = move_actor_bounds_center_to(landscape_actor, desired_center)
        second_delta = move_actor_bounds_center_to(landscape_actor, desired_center)

        bounds_center_location = landscape_actor.get_actor_location()

        if use_corner_location:
            corner_location = get_corner_location(square_max, bounds_center_location.z, y_location_offset)
            set_actor_location(landscape_actor, corner_location)
        else:
            corner_location = None

        # Final clean rotation pass after location/scale changes.
        force_clean_actor_rotation(landscape_actor, yaw, roll)

    final_center, final_extent, final_min, final_max = get_actor_bounds_min_max(landscape_actor)
    final_location = landscape_actor.get_actor_location()
    final_rotation = landscape_actor.get_actor_rotation()
    final_scale = landscape_actor.get_actor_scale3d()

    result = {
        "landscape_actor_label": landscape_actor.get_actor_label(),
        "source_static_mesh_actor_labels": [actor.get_actor_label() for actor in static_mesh_actors],
        "metadata_path": normalize_path(resolved_metadata_path) if resolved_metadata_path else None,
        "resolution": resolution,
        "selected_mesh_square_size": square_size,
        "applied_rotation_pitch": final_rotation.pitch,
        "applied_rotation_yaw": final_rotation.yaw,
        "applied_rotation_roll": final_rotation.roll,
        "applied_scale_x": final_scale.x,
        "applied_scale_y": final_scale.y,
        "applied_scale_z": final_scale.z,
        "applied_location_x": final_location.x,
        "applied_location_y": final_location.y,
        "applied_location_z": final_location.z,
        "desired_center_x": desired_center.x,
        "desired_center_y": desired_center.y,
        "desired_center_z": desired_center.z,
        "final_center_x": final_center.x,
        "final_center_y": final_center.y,
        "final_center_z": final_center.z,
        "square_max_x": square_max.x,
        "square_max_y": square_max.y,
        "corner_location": str(corner_location) if corner_location else None,
        "bounds_center_location_before_corner": str(bounds_center_location),
        "y_location_offset": float(y_location_offset),
        "first_delta": str(first_delta),
        "second_delta": str(second_delta),
        "negative_x": bool(negative_x),
        "z_scale_source": "override" if z_scale_override is not None and str(z_scale_override).strip() != "" else "preserved_landscape_current_z",
        "use_corner_location": bool(use_corner_location),
    }

    log("Final actor location: {}".format(final_location))
    log("Final actor rotation: {}".format(final_rotation))
    log("Final actor scale: {}".format(final_scale))
    log("Final bounds center: {}".format(final_center))
    log("First move delta: {}".format(first_delta))
    log("Second move delta: {}".format(second_delta))
    if corner_location:
        log("Corner location applied: {}".format(corner_location))
    log("Done.")

    return result


if __name__ == "__main__":
    run()
