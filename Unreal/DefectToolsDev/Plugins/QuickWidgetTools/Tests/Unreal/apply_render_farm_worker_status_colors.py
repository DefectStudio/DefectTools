"""Apply standalone-manager worker colors to the aggregate Unreal worker table."""

from __future__ import annotations

import json

import unreal

import render_farm_viewer


TABLE_PATH = "/QuickWidgetTools/EditorWidgets/RenderFarm/WBP_RenderFarmWorkersTable"
STYLE_TABLE_PATH = (
    "/QuickWidgetTools/EditorWidgets/RenderFarm/DT_RenderFarmWorkerStatusStyles"
)
SOURCE_WIDGET_NAMES = (
    "TextBlock",
    "TextBlock_1",
    "TextBlock_2",
    "TextBlock_3",
    "TextBlock_4",
    "TextBlock_5",
)
DESTINATION_WIDGET_NAMES = tuple(render_farm_viewer.WORKER_RICH_TEXT_WIDGETS.values())


def _log(message: str) -> None:
    unreal.log_warning(f"[RenderFarmWorkerColors] {message}")


def _linear_color(hex_color: str) -> unreal.LinearColor:
    value = hex_color.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Unsupported color: {hex_color}")
    def srgb_channel(component: int) -> float:
        encoded = component / 255.0
        if encoded <= 0.04045:
            return encoded / 12.92
        return ((encoded + 0.055) / 1.055) ** 2.4

    return unreal.LinearColor(
        srgb_channel(int(value[0:2], 16)),
        srgb_channel(int(value[2:4], 16)),
        srgb_channel(int(value[4:6], 16)),
        1.0,
    )


def _font_json(font: unreal.SlateFontInfo) -> dict[str, object]:
    result: dict[str, object] = {
        "TypefaceFontName": str(font.get_editor_property("typeface_font_name")),
        "Size": float(font.get_editor_property("size")),
        "LetterSpacing": int(font.get_editor_property("letter_spacing")),
        "SkewAmount": float(font.get_editor_property("skew_amount")),
    }
    font_object = font.get_editor_property("font_object")
    if font_object is not None:
        result["FontObject"] = font_object.get_path_name()
    return result


def _style_json(
    font: unreal.SlateFontInfo,
    hex_color: str,
) -> dict[str, object]:
    color = _linear_color(hex_color)
    return {
        "Font": _font_json(font),
        "ColorAndOpacity": {
            "SpecifiedColor": {
                "R": color.r,
                "G": color.g,
                "B": color.b,
                "A": color.a,
            },
            "ColorUseRule": "UseColor_Specified",
        },
    }


def _load_or_create_style_table(
    font: unreal.SlateFontInfo,
) -> unreal.DataTable:
    style_table = unreal.load_asset(STYLE_TABLE_PATH)
    if style_table is None:
        factory = unreal.DataTableFactory()
        factory.set_editor_property("struct", unreal.RichTextStyleRow.static_struct())
        package_path, asset_name = STYLE_TABLE_PATH.rsplit("/", 1)
        style_table = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            asset_name,
            package_path,
            unreal.DataTable,
            factory,
        )
    if not isinstance(style_table, unreal.DataTable):
        raise RuntimeError(f"Style asset is not a DataTable: {STYLE_TABLE_PATH}")

    rows = [
        {
            "Name": style_name,
            "TextStyle": _style_json(font, hex_color),
        }
        for style_name, hex_color in render_farm_viewer.WORKER_STATUS_STYLE_COLORS.items()
    ]
    result = unreal.DataTableFunctionLibrary.fill_data_table_from_json_string(
        style_table,
        json.dumps(rows),
    )
    if result is False:
        raise RuntimeError("Could not populate the worker RichText style table")
    row_names = {
        str(name)
        for name in unreal.DataTableFunctionLibrary.get_data_table_row_names(style_table)
    }
    if row_names != set(render_farm_viewer.WORKER_STATUS_STYLE_COLORS):
        raise RuntimeError(f"Unexpected worker style rows: {sorted(row_names)}")
    return style_table


def _copy_struct(value):
    return value.copy() if hasattr(value, "copy") else value


def _capture_source(text_block: unreal.TextBlock) -> dict[str, object]:
    slot = text_block.get_editor_property("slot")
    return {
        "parent": text_block.get_parent(),
        "font": _copy_struct(text_block.get_editor_property("font")),
        "color": _copy_struct(text_block.get_editor_property("color_and_opacity")),
        "shadow_offset": _copy_struct(text_block.get_editor_property("shadow_offset")),
        "shadow_color": _copy_struct(
            text_block.get_editor_property("shadow_color_and_opacity")
        ),
        "justification": text_block.get_editor_property("justification"),
        "auto_wrap_text": text_block.get_editor_property("auto_wrap_text"),
        "wrap_text_at": text_block.get_editor_property("wrap_text_at"),
        "wrapping_policy": text_block.get_editor_property("wrapping_policy"),
        "visibility": text_block.get_editor_property("visibility"),
        "render_opacity": text_block.get_editor_property("render_opacity"),
        "slot_size": _copy_struct(slot.get_editor_property("size")),
        "slot_padding": _copy_struct(slot.get_editor_property("padding")),
        "slot_horizontal_alignment": slot.get_editor_property("horizontal_alignment"),
        "slot_vertical_alignment": slot.get_editor_property("vertical_alignment"),
    }


def _set_if_supported(widget, property_name: str, value) -> None:
    try:
        widget.set_editor_property(property_name, value)
    except Exception:
        pass


def _configure_rich_text(
    rich_text: unreal.RichTextBlock,
    captured: dict[str, object],
    style_table: unreal.DataTable,
) -> None:
    default_style = unreal.TextBlockStyle()
    default_style.set_editor_property("font", captured["font"])
    default_style.set_editor_property("color_and_opacity", captured["color"])
    default_style.set_editor_property(
        "shadow_color_and_opacity",
        captured["shadow_color"],
    )
    rich_text.set_editor_property("default_text_style_override", default_style)
    _set_if_supported(rich_text, "override_default_style", True)
    rich_text.set_editor_property("text_style_set", style_table)
    for property_name in (
        "justification",
        "auto_wrap_text",
        "wrap_text_at",
        "wrapping_policy",
        "visibility",
        "render_opacity",
    ):
        _set_if_supported(rich_text, property_name, captured[property_name])
    rich_text.set_editor_property("text", "<waiting>Worker data</>")

    slot = rich_text.get_editor_property("slot")
    slot.set_editor_property("size", captured["slot_size"])
    slot.set_editor_property("padding", captured["slot_padding"])
    slot.set_editor_property(
        "horizontal_alignment",
        captured["slot_horizontal_alignment"],
    )
    slot.set_editor_property(
        "vertical_alignment",
        captured["slot_vertical_alignment"],
    )


def apply() -> None:
    blueprint = unreal.load_asset(TABLE_PATH)
    if not isinstance(blueprint, unreal.WidgetBlueprint):
        raise RuntimeError(f"Missing workers table: {TABLE_PATH}")

    existing_rich = [
        unreal.EditorUtilityLibrary.find_source_widget_by_name(blueprint, name)
        for name in DESTINATION_WIDGET_NAMES
    ]
    if all(isinstance(widget, unreal.RichTextBlock) for widget in existing_rich):
        first_rich = existing_rich[0]
        default_style = first_rich.get_editor_property("default_text_style_override")
        font = default_style.get_editor_property("font")
        style_table = _load_or_create_style_table(font)
        for rich_text in existing_rich:
            rich_text.set_editor_property("text_style_set", style_table)
        for source_name in SOURCE_WIDGET_NAMES:
            source = unreal.EditorUtilityLibrary.find_source_widget_by_name(
                blueprint,
                source_name,
            )
            if isinstance(source, unreal.TextBlock):
                source.set_editor_property("visibility", unreal.SlateVisibility.COLLAPSED)
        _log("Existing RichText columns updated")
    else:
        sources = [
            unreal.EditorUtilityLibrary.find_source_widget_by_name(blueprint, name)
            for name in SOURCE_WIDGET_NAMES
        ]
        if not all(isinstance(widget, unreal.TextBlock) for widget in sources):
            raise RuntimeError(
                "Expected either six legacy TextBlocks or six worker RichTextBlocks"
            )
        captured_columns = [_capture_source(widget) for widget in sources]
        font = captured_columns[0]["font"]
        style_table = _load_or_create_style_table(font)
        parent = captured_columns[0]["parent"]
        if any(column["parent"] != parent for column in captured_columns):
            raise RuntimeError("Worker columns do not share one HorizontalBox")
        parent_name = parent.get_name()

        for source in sources:
            source.set_editor_property("visibility", unreal.SlateVisibility.COLLAPSED)

        rich_type = unreal.BlueprintEditorLibrary.get_object_reference_type(
            unreal.RichTextBlock
        )
        for name, captured in zip(DESTINATION_WIDGET_NAMES, captured_columns):
            rich_text = unreal.EditorUtilityLibrary.add_source_widget(
                blueprint,
                unreal.RichTextBlock,
                name,
                parent_name,
            )
            if not isinstance(rich_text, unreal.RichTextBlock):
                raise RuntimeError(f"Could not create {name}")
            _configure_rich_text(rich_text, captured, style_table)

        member_names = {
            str(name)
            for name in unreal.BlueprintEditorLibrary.list_member_variable_names(
                blueprint
            )
        }
        for name in DESTINATION_WIDGET_NAMES:
            changed = (
                unreal.BlueprintEditorLibrary.change_member_variable_type(
                    blueprint,
                    name,
                    rich_type,
                )
                if name in member_names
                else unreal.BlueprintEditorLibrary.add_member_variable(
                    blueprint,
                    name,
                    rich_type,
                )
            )
            if not changed:
                raise RuntimeError(f"Could not expose RichText worker column {name}")
        _log("Added six RichText columns; legacy bindings remain collapsed")

    if not unreal.BlueprintEditorLibrary.compile_blueprint(blueprint):
        raise RuntimeError("Workers table did not compile after RichText conversion")
    if not unreal.EditorAssetLibrary.save_loaded_asset(style_table, only_if_is_dirty=False):
        raise RuntimeError(f"Could not save {STYLE_TABLE_PATH}")
    if not unreal.EditorAssetLibrary.save_loaded_asset(blueprint, only_if_is_dirty=False):
        raise RuntimeError(f"Could not save {TABLE_PATH}")

    _log("PASS")


try:
    apply()
except Exception as error:
    unreal.log_error(f"[RenderFarmWorkerColors] FAIL: {error}")
    unreal.SystemLibrary.quit_editor()
    raise
else:
    unreal.SystemLibrary.quit_editor()
