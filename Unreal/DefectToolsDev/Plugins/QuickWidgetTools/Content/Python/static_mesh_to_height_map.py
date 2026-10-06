import json
import math
import os
import struct
import time
import unreal

# ------------------------------------------------------------
# Selected Static Mesh Actors to Landscape/Mesh Terrain .r16 Height Map
# ------------------------------------------------------------
# Usage from Unreal Python:
#
#   import static_mesh_to_height_map
#   static_mesh_to_height_map.run("1009")
#
# Supported landscape-friendly resolutions:
#   "1009", "2017", "4033", "8129"
#
# What this does:
#   - Finds selected StaticMeshActor actors in the current open level.
#   - Computes a square XY capture area around their combined actor bounds.
#   - Creates a top-down orthographic CameraActor to frame that square area.
#   - Raycasts downward against the selected StaticMeshComponents directly.
#   - Writes a raw 16-bit little-endian .r16 heightmap to <Project>/_output.
#   - Writes a metadata .json file beside the .r16 with world bounds and scale hints.
#
# Important limitations:
#   - This is a top-surface height map. Overhangs, caves, undersides, and stacked
#     vertical surfaces collapse to the highest surface hit from above.
#   - Component traces require the StaticMeshComponent to have usable mesh/collision
#     data for line_trace_component.
#   - 4033 and 8129 are extremely expensive in editor Python. Test at 1009 first.


VALID_RESOLUTIONS = {
    "1009": 1009,
    "2017": 2017,
    "4033": 4033,
    "8129": 8129,
}

DEFAULT_RESOLUTION = "1009"
CAMERA_LABEL = "HeightMap_TopDown_Ortho_Camera"
OUTPUT_PREFIX = "static_mesh_heightmap"
TRACE_MARGIN_UNITS = 10000.0
MIN_HEIGHT_RANGE = 1.0
XY_HIT_TOLERANCE = 0.5

# Unreal Landscape import was coming in mirrored, forcing negative X scale.
# Keep the Landscape scale clean/positive by mirroring the written R16 columns instead.
FLIP_R16_X_FOR_POSITIVE_LANDSCAPE_SCALE = True


def log(message):
    unreal.log("[StaticMeshToHeightMap] {}".format(message))


def log_warning(message):
    unreal.log_warning("[StaticMeshToHeightMap] {}".format(message))


def log_error(message):
    unreal.log_error("[StaticMeshToHeightMap] {}".format(message))


def normalize_resolution(resolution_string):
    key = str(resolution_string).strip()

    if key not in VALID_RESOLUTIONS:
        log_error(
            'Resolution must be one of: {}. Got: {}'.format(
                ", ".join(sorted(VALID_RESOLUTIONS.keys())),
                resolution_string
            )
        )
        return None, None

    return key, VALID_RESOLUTIONS[key]


def get_editor_actor_subsystem():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def get_editor_world():
    if hasattr(unreal, "UnrealEditorSubsystem"):
        unreal_editor_subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        if unreal_editor_subsystem and hasattr(unreal_editor_subsystem, "get_editor_world"):
            world = unreal_editor_subsystem.get_editor_world()
            if world:
                return world

    if hasattr(unreal, "EditorLevelLibrary") and hasattr(unreal.EditorLevelLibrary, "get_editor_world"):
        return unreal.EditorLevelLibrary.get_editor_world()

    log_error("Could not get editor world.")
    return None


def get_selected_static_mesh_actors(editor_actor_subsystem):
    selected_actors = list(editor_actor_subsystem.get_selected_level_actors())

    static_mesh_actors = [
        actor for actor in selected_actors
        if isinstance(actor, unreal.StaticMeshActor)
    ]

    return selected_actors, static_mesh_actors


def get_static_mesh_components(static_mesh_actors):
    components = []

    for actor in static_mesh_actors:
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        if component:
            components.append(component)
        else:
            log_warning(
                "Could not find StaticMeshComponent on actor: {}".format(
                    actor.get_actor_label()
                )
            )

    return components


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


def get_combined_bounds(actors):
    combined_min = None
    combined_max = None

    for actor in actors:
        actor_min, actor_max = get_actor_bounds_min_max(actor)

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


def create_top_down_ortho_camera(editor_actor_subsystem, square_min, square_max, square_size):
    center_x = (square_min.x + square_max.x) * 0.5
    center_y = (square_min.y + square_max.y) * 0.5
    height_range = max(square_max.z - square_min.z, MIN_HEIGHT_RANGE)
    camera_z = square_max.z + max(square_size, height_range, 1000.0)

    camera_location = unreal.Vector(center_x, center_y, camera_z)
    # In this project, -90,-90,0 points the ortho camera straight down.
    camera_rotation = unreal.Rotator(-90.0, -90.0, 0.0)

    camera_actor = editor_actor_subsystem.spawn_actor_from_class(
        unreal.CameraActor,
        camera_location,
        camera_rotation
    )

    if not camera_actor:
        log_warning("Could not create top-down orthographic camera.")
        return None

    camera_actor.set_actor_label(CAMERA_LABEL, mark_dirty=True)

    camera_component = camera_actor.get_component_by_class(unreal.CameraComponent)
    if camera_component:
        try:
            camera_component.set_editor_property("projection_mode", unreal.CameraProjectionMode.ORTHOGRAPHIC)
            camera_component.set_editor_property("ortho_width", float(square_size))
            camera_component.set_editor_property("aspect_ratio", 1.0)
        except Exception as exc:
            log_warning("Camera was created, but ortho settings failed: {}".format(exc))

    return camera_actor


def get_hit_property(hit_result, property_name, default=None):
    if hit_result is None:
        return default

    try:
        return hit_result.get_editor_property(property_name)
    except Exception:
        return getattr(hit_result, property_name, default)


def get_hit_location(hit_result):
    for property_name in ("location", "impact_point"):
        location = get_hit_property(hit_result, property_name, None)
        if location is not None:
            return location

    return None


def is_vector_like(value):
    return (
        value is not None and
        hasattr(value, "x") and
        hasattr(value, "y") and
        hasattr(value, "z")
    )


def is_vector_on_vertical_trace(value, start, end):
    if not is_vector_like(value):
        return False

    min_z = min(start.z, end.z)
    max_z = max(start.z, end.z)

    return (
        abs(value.x - start.x) <= XY_HIT_TOLERANCE and
        abs(value.y - start.y) <= XY_HIT_TOLERANCE and
        value.z >= min_z and
        value.z <= max_z
    )


def extract_component_trace_location(hit_data, start, end):
    """
    Normalize StaticMeshComponent.line_trace_component return variants.

    UE 5.8 can return:
        (hit_location, hit_normal, bone_name, hit_result)

    Other builds may return:
        HitResult
        (did_hit, HitResult)
        (HitResult, did_hit)
    """

    if isinstance(hit_data, tuple):
        # Observed UE 5.8 component trace form:
        # (Vector hit_location, Vector hit_normal, Name bone_name, HitResult hit)
        if len(hit_data) >= 4 and is_vector_on_vertical_trace(hit_data[0], start, end):
            return hit_data[0]

        # Common world trace form: (did_hit, hit_result)
        if len(hit_data) >= 2 and isinstance(hit_data[0], bool):
            if not hit_data[0]:
                return None
            return get_hit_location(hit_data[1])

        # Common component trace form in some builds: (hit_result, did_hit)
        if len(hit_data) >= 2 and isinstance(hit_data[1], bool):
            if not hit_data[1]:
                return None
            return get_hit_location(hit_data[0])

        # Fallback: find any vector that lies on the vertical ray.
        for candidate in hit_data:
            if is_vector_on_vertical_trace(candidate, start, end):
                return candidate

        # Fallback: find a HitResult-style object with a valid location.
        for candidate in hit_data:
            location = get_hit_location(candidate)
            if is_vector_on_vertical_trace(location, start, end):
                return location

        return None

    location = get_hit_location(hit_data)
    if is_vector_on_vertical_trace(location, start, end):
        return location

    return None


def line_trace_component_height(component, start, end, trace_complex=True):
    if not hasattr(component, "line_trace_component"):
        return None

    try:
        hit_data = component.line_trace_component(
            start,
            end,
            trace_complex,
            False,
            False
        )
    except Exception as exc:
        log_warning("Component trace failed: {}".format(exc))
        return None

    hit_location = extract_component_trace_location(hit_data, start, end)
    if hit_location is None:
        return None

    return hit_location.z


def line_trace_height_components(components, start, end):
    """Return the highest component hit from a top-down trace."""

    highest_z = None

    for component in components:
        hit_z = line_trace_component_height(component, start, end, True)

        if hit_z is None:
            hit_z = line_trace_component_height(component, start, end, False)

        if hit_z is None:
            continue

        if highest_z is None or hit_z > highest_z:
            highest_z = hit_z

    return highest_z


def z_to_uint16(z_value, min_z, max_z):
    height_range = max(max_z - min_z, MIN_HEIGHT_RANGE)
    normalized = (z_value - min_z) / height_range
    normalized = max(0.0, min(1.0, normalized))
    return int(round(normalized * 65535.0))


def get_output_paths(resolution_key):
    project_dir = unreal.Paths.project_dir()
    output_dir = os.path.join(project_dir, "_output")

    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    base_name = "{}_{}_{}".format(OUTPUT_PREFIX, resolution_key, timestamp)

    r16_path = os.path.join(output_dir, base_name + ".r16")

    # Do not use the exact same base name as the .r16 for metadata.
    # Unreal may interpret same-base .json files as RAW import sidecars.
    json_path = os.path.join(output_dir, base_name + "_metadata.json")

    return r16_path, json_path


def write_metadata(json_path, metadata):
    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(metadata, json_file, indent=4, sort_keys=True)


def restore_selection(editor_actor_subsystem, selected_actors):
    try:
        editor_actor_subsystem.set_selected_level_actors(selected_actors)
    except Exception as exc:
        log_warning("Could not restore original selection: {}".format(exc))


def run(resolution_string=DEFAULT_RESOLUTION):
    """
    Convert selected StaticMeshActor actors into a top-down .r16 height map.

    Args:
        resolution_string (str): "1009", "2017", "4033", or "8129".

    Returns:
        dict or None: Output paths and metadata.
    """

    resolution_key, resolution = normalize_resolution(resolution_string)
    if resolution is None:
        return None

    if resolution >= 4033:
        log_warning(
            "Resolution {} requires {} component traces minimum. This can be very slow in editor Python.".format(
                resolution,
                resolution * resolution
            )
        )

    editor_actor_subsystem = get_editor_actor_subsystem()
    world = get_editor_world()

    if not editor_actor_subsystem or not world:
        log_error("Editor actor subsystem or editor world was not available.")
        return None

    selected_actors, static_mesh_actors = get_selected_static_mesh_actors(editor_actor_subsystem)

    if not static_mesh_actors:
        log_error("Please select one or more Static Mesh Actors in the current level.")
        return None

    static_mesh_components = get_static_mesh_components(static_mesh_actors)

    if not static_mesh_components:
        log_error("No StaticMeshComponents were found on the selected Static Mesh Actors.")
        return None

    bounds_min, bounds_max = get_combined_bounds(static_mesh_actors)
    square_min, square_max, square_size = make_square_xy_bounds(bounds_min, bounds_max)

    min_z = bounds_min.z
    max_z = bounds_max.z

    if abs(max_z - min_z) < MIN_HEIGHT_RANGE:
        max_z = min_z + MIN_HEIGHT_RANGE

    xy_world_units_per_pixel = square_size / float(resolution - 1)

    r16_path, json_path = get_output_paths(resolution_key)

    log("Selected Static Mesh Actors: {}".format(len(static_mesh_actors)))
    log("Selected Static Mesh Components: {}".format(len(static_mesh_components)))
    log("Resolution: {} x {}".format(resolution, resolution))
    log("Square XY size: {:.3f} Unreal units".format(square_size))
    log("XY units per pixel/vertex: {:.6f}".format(xy_world_units_per_pixel))
    log("Height range Z: {:.3f} to {:.3f}".format(min_z, max_z))
    log("Trace method: StaticMeshComponent.line_trace_component")
    log("R16 X flip for positive Landscape X scale: {}".format(FLIP_R16_X_FOR_POSITIVE_LANDSCAPE_SCALE))
    log("Output R16: {}".format(r16_path))

    trace_start_z = max_z + TRACE_MARGIN_UNITS
    trace_end_z = min_z - TRACE_MARGIN_UNITS

    hit_count = 0
    miss_count = 0
    cancelled = False

    with unreal.ScopedEditorTransaction("Static Mesh To Height Map"):
        camera_actor = create_top_down_ortho_camera(
            editor_actor_subsystem,
            square_min,
            square_max,
            square_size
        )

        with open(r16_path, "wb") as r16_file:
            slow_task = unreal.ScopedSlowTask(
                resolution,
                "Writing static mesh height map {} x {}".format(resolution, resolution)
            )
            slow_task.make_dialog(True)

            with slow_task:
                for row_index in range(resolution):
                    if slow_task.should_cancel():
                        cancelled = True
                        break

                    # Row 0 writes max Y first. This usually matches top-down image orientation.
                    y_alpha = float(row_index) / float(resolution - 1)
                    y = square_max.y - (y_alpha * square_size)

                    row_buffer = bytearray(resolution * 2)

                    for column_index in range(resolution):
                        x_alpha = float(column_index) / float(resolution - 1)
                        x = square_min.x + (x_alpha * square_size)

                        start = unreal.Vector(x, y, trace_start_z)
                        end = unreal.Vector(x, y, trace_end_z)

                        hit_z = line_trace_height_components(static_mesh_components, start, end)

                        if hit_z is None:
                            height_value = 0
                            miss_count += 1
                        else:
                            height_value = z_to_uint16(hit_z, min_z, max_z)
                            hit_count += 1

                        write_column_index = resolution - 1 - column_index if FLIP_R16_X_FOR_POSITIVE_LANDSCAPE_SCALE else column_index
                        struct.pack_into("<H", row_buffer, write_column_index * 2, height_value)

                    r16_file.write(row_buffer)
                    slow_task.enter_progress_frame(1)

    restore_selection(editor_actor_subsystem, selected_actors)

    metadata = {
        "resolution": resolution,
        "resolution_string": resolution_key,
        "r16_path": r16_path.replace("\\", "/"),
        "json_path": json_path.replace("\\", "/"),
        "selected_static_mesh_actor_count": len(static_mesh_actors),
        "selected_static_mesh_component_count": len(static_mesh_components),
        "selected_static_mesh_actor_labels": [actor.get_actor_label() for actor in static_mesh_actors],
        "square_min_x": square_min.x,
        "square_min_y": square_min.y,
        "square_max_x": square_max.x,
        "square_max_y": square_max.y,
        "square_size_unreal_units": square_size,
        "min_z": min_z,
        "max_z": max_z,
        "height_range_unreal_units": max_z - min_z,
        "xy_world_units_per_pixel_or_vertex": xy_world_units_per_pixel,
        "trace_start_z": trace_start_z,
        "trace_end_z": trace_end_z,
        "trace_method": "StaticMeshComponent.line_trace_component",
        "trace_return_handling": "supports HitResult, (did_hit, HitResult), (HitResult, did_hit), and (hit_location, hit_normal, bone_name, HitResult)",
        "camera_rotation": "Rotator(-90.0, -90.0, 0.0)",
        "r16_x_flipped_for_positive_landscape_scale": FLIP_R16_X_FOR_POSITIVE_LANDSCAPE_SCALE,
        "recommended_landscape_rotation": "Rotator(0.0, -180.0, 0.0)",
        "recommended_landscape_scale_x_sign": "positive",
        "hit_count": hit_count,
        "miss_count": miss_count,
        "cancelled": cancelled,
        "created_camera_label": camera_actor.get_actor_label() if camera_actor else None,
        "notes": [
            "Raw .r16 is little-endian unsigned 16-bit height data.",
            "Pixel value 0 maps to min_z; pixel value 65535 maps to max_z.",
            "For Landscape import, use the .r16 file and set XY scale based on square_size_unreal_units / (resolution - 1).",
            "This is a top-surface projection. Overhangs and stacked surfaces are collapsed from above.",
            "This exporter uses StaticMeshComponent.line_trace_component because some large/Nanite meshes do not respond to world traces.",
            "The generated camera is only a visual guide; component traces generate the R16 data.",
            "R16 columns are mirrored at write time so the imported Landscape can use positive X scale.",
            "The metadata JSON deliberately uses _metadata.json so Unreal does not treat it as a RAW sidecar."
        ]
    }

    write_metadata(json_path, metadata)

    if hit_count == 0:
        log_error(
            "No component traces hit the selected meshes. The R16 will import flat. "
            "Check whether component.line_trace_component returns hit_location as tuple[0]."
        )

    if cancelled:
        log_warning("Height map generation was cancelled. Partial R16 was written: {}".format(r16_path))
    else:
        log("Finished height map generation.")

    log("Hit pixels: {} | Miss pixels: {}".format(hit_count, miss_count))
    log("Metadata JSON: {}".format(json_path))

    return metadata


if __name__ == "__main__":
    run(DEFAULT_RESOLUTION)
