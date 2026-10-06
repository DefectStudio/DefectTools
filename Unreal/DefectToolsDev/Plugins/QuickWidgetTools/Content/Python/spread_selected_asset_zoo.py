import math
import unreal


def _robust_average(values):
    """
    Returns an average with extreme high/low outliers trimmed when the
    selection is large enough. This keeps one enormous asset from making
    every grid cell enormous.
    """
    cleaned = sorted(float(value) for value in values if value > 0.0)

    if not cleaned:
        return 1.0

    if len(cleaned) >= 10:
        trim_count = max(1, int(len(cleaned) * 0.10))
    elif len(cleaned) >= 5:
        trim_count = 1
    else:
        trim_count = 0

    if trim_count > 0 and len(cleaned) > trim_count * 2:
        cleaned = cleaned[trim_count:-trim_count]

    return sum(cleaned) / len(cleaned)


def _actor_contains_static_mesh(actor):
    """
    Accept StaticMeshActors and Blueprint actors containing at least one
    StaticMeshComponent with a mesh assigned.
    """
    try:
        components = actor.get_components_by_class(unreal.StaticMeshComponent)
    except Exception:
        return False

    for component in components:
        try:
            if component.get_editor_property("static_mesh") is not None:
                return True
        except Exception:
            continue

    return False


def _collect_selected_static_mesh_records():
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    selected_actors = actor_subsystem.get_selected_level_actors()

    records = []
    skipped = []

    for actor in selected_actors:
        if not _actor_contains_static_mesh(actor):
            skipped.append(actor.get_actor_label())
            continue

        # False = include components whether or not collision is enabled.
        # False = do not recurse into ChildActorComponents.
        bounds_origin, bounds_extent = actor.get_actor_bounds(False, False)

        size_x = abs(bounds_extent.x) * 2.0
        size_y = abs(bounds_extent.y) * 2.0
        size_z = abs(bounds_extent.z) * 2.0

        if size_x <= 0.001 or size_y <= 0.001 or size_z <= 0.001:
            skipped.append(actor.get_actor_label())
            continue

        actor_location = actor.get_actor_location()

        # Actor pivots are often not centered. Store the actor-location offset
        # from the bounds center so placement is based on the actual bounds.
        pivot_offset = unreal.Vector(
            actor_location.x - bounds_origin.x,
            actor_location.y - bounds_origin.y,
            actor_location.z - bounds_origin.z,
        )

        records.append(
            {
                "index": len(records),
                "actor": actor,
                "label": actor.get_actor_label(),
                "bounds_origin": bounds_origin,
                "bounds_extent": bounds_extent,
                "size": unreal.Vector(size_x, size_y, size_z),
                "pivot_offset": pivot_offset,
            }
        )

    return records, skipped


def _rectangle_is_free(occupied_cells, start_x, start_y, span_x, span_y):
    for cell_y in range(start_y, start_y + span_y):
        for cell_x in range(start_x, start_x + span_x):
            if (cell_x, cell_y) in occupied_cells:
                return False
    return True


def _occupy_rectangle(occupied_cells, start_x, start_y, span_x, span_y):
    for cell_y in range(start_y, start_y + span_y):
        for cell_x in range(start_x, start_x + span_x):
            occupied_cells.add((cell_x, cell_y))


def _pack_records(records, column_count):
    """
    First-fit occupancy-grid packing. Larger assets are supplied first, so
    they claim contiguous space before smaller assets fill the remaining gaps.
    """
    occupied_cells = set()
    placements = {}
    used_rows = 0

    for record in records:
        span_x = record["span_x"]
        span_y = record["span_y"]

        row = 0
        placed = False

        while not placed:
            max_start_column = column_count - span_x

            for column in range(max_start_column + 1):
                if _rectangle_is_free(
                    occupied_cells,
                    column,
                    row,
                    span_x,
                    span_y,
                ):
                    _occupy_rectangle(
                        occupied_cells,
                        column,
                        row,
                        span_x,
                        span_y,
                    )

                    placements[record["index"]] = (
                        column,
                        row,
                        span_x,
                        span_y,
                    )
                    used_rows = max(used_rows, row + span_y)
                    placed = True
                    break

            row += 1

    return placements, used_rows


def _choose_compact_layout(records, cell_size_x, cell_size_y):
    """
    Tries several plausible grid widths and chooses a compact, roughly
    square result. This avoids blindly forcing everything into one long row.
    """
    total_cells = sum(record["span_x"] * record["span_y"] for record in records)
    minimum_columns = max(record["span_x"] for record in records)

    # Correct the target column count for non-square cells.
    target_columns = int(
        math.ceil(
            math.sqrt(
                total_cells * (cell_size_y / max(cell_size_x, 0.001))
            )
        )
    )
    target_columns = max(minimum_columns, target_columns)

    candidate_factors = (0.70, 0.80, 0.90, 1.0, 1.10, 1.20, 1.35, 1.50)
    candidate_columns = {minimum_columns, target_columns}

    for factor in candidate_factors:
        candidate_columns.add(
            max(minimum_columns, int(round(target_columns * factor)))
        )

    best_result = None

    for column_count in sorted(candidate_columns):
        placements, used_rows = _pack_records(records, column_count)

        used_columns = max(
            column + span_x
            for column, row, span_x, span_y in placements.values()
        )

        world_width = used_columns * cell_size_x
        world_height = used_rows * cell_size_y
        world_area = world_width * world_height

        occupied_area = max(total_cells, 1)
        allocated_area = max(used_columns * used_rows, 1)
        waste_ratio = (allocated_area - occupied_area) / occupied_area

        aspect_ratio = max(world_width, 0.001) / max(world_height, 0.001)
        aspect_penalty = abs(math.log(aspect_ratio))

        # Physical area matters most. Small penalties discourage extreme
        # strip layouts and excessive unused cells.
        score = world_area * (
            1.0
            + (aspect_penalty * 0.08)
            + (max(waste_ratio, 0.0) * 0.04)
        )

        result = {
            "score": score,
            "placements": placements,
            "used_columns": used_columns,
            "used_rows": used_rows,
        }

        if best_result is None or result["score"] < best_result["score"]:
            best_result = result

    return best_result


def spread_selected_static_meshes(
    buffer_space,
    layout_center=None,
    ground_z=0.0,
    align_bottoms_to_ground=True,
):
    """
    Spread selected Static Mesh actors into a compact, non-overlapping grid.

    Args:
        buffer_space:
            Desired minimum empty space, in Unreal units, between neighboring
            actor bounds.

        layout_center:
            XY center of the finished asset zoo. Defaults to world origin.

        ground_z:
            World Z plane used when align_bottoms_to_ground is True.

        align_bottoms_to_ground:
            When True, every actor's world-space bounding-box bottom is placed
            on ground_z. When False, each actor keeps its existing bounds-center Z.

    Returns:
        A list of dictionaries describing the actors that were moved.
    """
    if buffer_space < 0.0:
        raise ValueError("buffer_space must be zero or greater.")

    if layout_center is None:
        layout_center = unreal.Vector(0.0, 0.0, 0.0)

    records, skipped = _collect_selected_static_mesh_records()

    if not records:
        unreal.log_warning(
            "[AssetZooGrid] No selected actors containing valid static meshes."
        )
        return []

    # The average padded footprint becomes one grid cell. Large objects then
    # reserve multiple cells; small objects usually reserve one.
    padded_widths = [
        record["size"].x + buffer_space
        for record in records
    ]
    padded_depths = [
        record["size"].y + buffer_space
        for record in records
    ]

    cell_size_x = max(_robust_average(padded_widths), 1.0)
    cell_size_y = max(_robust_average(padded_depths), 1.0)

    for record in records:
        padded_size_x = record["size"].x + buffer_space
        padded_size_y = record["size"].y + buffer_space

        record["span_x"] = max(
            1,
            int(math.ceil(padded_size_x / cell_size_x)),
        )
        record["span_y"] = max(
            1,
            int(math.ceil(padded_size_y / cell_size_y)),
        )

    # Place large and awkward footprints first.
    packing_order = sorted(
        records,
        key=lambda record: (
            record["span_x"] * record["span_y"],
            max(record["span_x"], record["span_y"]),
            record["size"].x * record["size"].y,
        ),
        reverse=True,
    )

    layout = _choose_compact_layout(
        packing_order,
        cell_size_x,
        cell_size_y,
    )

    placements = layout["placements"]
    layout_width = layout["used_columns"] * cell_size_x
    layout_depth = layout["used_rows"] * cell_size_y

    # Center the complete zoo around layout_center instead of growing only
    # into positive X and Y.
    layout_min_x = layout_center.x - (layout_width * 0.5)
    layout_min_y = layout_center.y - (layout_depth * 0.5)

    moved_report = []

    with unreal.ScopedEditorTransaction("Spread Selected Asset Zoo"):
        for record in records:
            actor = record["actor"]
            column, row, span_x, span_y = placements[record["index"]]

            reserved_width = span_x * cell_size_x
            reserved_depth = span_y * cell_size_y

            desired_bounds_center_x = (
                layout_min_x
                + (column * cell_size_x)
                + (reserved_width * 0.5)
            )
            desired_bounds_center_y = (
                layout_min_y
                + (row * cell_size_y)
                + (reserved_depth * 0.5)
            )

            if align_bottoms_to_ground:
                desired_bounds_center_z = (
                    ground_z + record["bounds_extent"].z
                )
            else:
                desired_bounds_center_z = record["bounds_origin"].z

            target_actor_location = unreal.Vector(
                desired_bounds_center_x + record["pivot_offset"].x,
                desired_bounds_center_y + record["pivot_offset"].y,
                desired_bounds_center_z + record["pivot_offset"].z,
            )

            actor.modify()
            actor.set_actor_location(
                target_actor_location,
                False,  # Do not sweep; this is an editor layout operation.
                True,   # Teleport physics state.
            )

            moved_report.append(
                {
                    "actor": actor,
                    "label": record["label"],
                    "bounds_size": record["size"],
                    "grid_span": (span_x, span_y),
                    "new_location": target_actor_location,
                }
            )

    unreal.log(
        "[AssetZooGrid] Moved {} static-mesh actors. "
        "Buffer: {:.2f}. Cell size: X={:.2f}, Y={:.2f}. "
        "Grid used: {} x {} cells.".format(
            len(records),
            buffer_space,
            cell_size_x,
            cell_size_y,
            layout["used_columns"],
            layout["used_rows"],
        )
    )

    for item in moved_report:
        size = item["bounds_size"]
        span_x, span_y = item["grid_span"]
        unreal.log(
            "[AssetZooGrid] {} | Bounds: "
            "X={:.2f}, Y={:.2f}, Z={:.2f} | Cells: {} x {}".format(
                item["label"],
                size.x,
                size.y,
                size.z,
                span_x,
                span_y,
            )
        )

    if skipped:
        unreal.log_warning(
            "[AssetZooGrid] Skipped {} selected actor(s) without a valid "
            "static mesh or usable bounds: {}".format(
                len(skipped),
                ", ".join(skipped),
            )
        )

    return moved_report


def run(
    buffer_space,
    layout_center=None,
    ground_z=0.0,
    align_bottoms_to_ground=True,
):
    """Entry point intended for Unreal Execute Python Script nodes."""
    return spread_selected_static_meshes(
        buffer_space=buffer_space,
        layout_center=layout_center,
        ground_z=ground_z,
        align_bottoms_to_ground=align_bottoms_to_ground,
    )
