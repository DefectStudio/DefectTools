"""Add clickable, width-synchronized headers to the aggregate jobs table."""

from __future__ import annotations

import unreal

import render_farm_viewer


TABLE_PATH = "/QuickWidgetTools/EditorWidgets/RenderFarm/WBP_RenderFarmJobsTable"
VIEWER_PATH = "/QuickWidgetTools/EditorWidgets/WBP_09_Render_Farm_Viewer"
REFERENCE_BUTTON_NAME = "FarmViewerRefreshButton"
SORT_LABEL_FONT_SCALE = 0.70
COLUMNS = tuple(
    (
        field,
        f"{field}Column",
        render_farm_viewer.JOB_SORT_BUTTONS[field],
        f"{field}SortLabel",
        render_farm_viewer.JOB_SORT_HEADINGS[field],
    )
    for field in render_farm_viewer.JOB_FIELDS
)


def _log(message: str) -> None:
    unreal.log_warning(f"[RenderFarmJobSortHeaders] {message}")


def _copy_struct(value):
    return value.copy() if hasattr(value, "copy") else value


def _set_if_supported(widget, property_name: str, value) -> None:
    try:
        widget.set_editor_property(property_name, value)
    except Exception:
        pass


def _copy_if_supported(source, destination, property_name: str) -> None:
    try:
        value = source.get_editor_property(property_name)
    except Exception:
        return
    _set_if_supported(destination, property_name, _copy_struct(value))


def _capture_column(rich_text: unreal.RichTextBlock) -> dict[str, object]:
    slot = rich_text.get_editor_property("slot")
    if not isinstance(slot, unreal.HorizontalBoxSlot):
        raise RuntimeError(f"{rich_text.get_name()} must start in a HorizontalBox")
    default_style = rich_text.get_editor_property("default_text_style_override")
    return {
        "parent": rich_text.get_parent(),
        "slot_size": _copy_struct(slot.get_editor_property("size")),
        "slot_padding": _copy_struct(slot.get_editor_property("padding")),
        "slot_horizontal_alignment": slot.get_editor_property(
            "horizontal_alignment"
        ),
        "slot_vertical_alignment": slot.get_editor_property("vertical_alignment"),
        "font": _copy_struct(default_style.get_editor_property("font")),
        "color": _copy_struct(default_style.get_editor_property("color_and_opacity")),
        "shadow_color": _copy_struct(
            default_style.get_editor_property("shadow_color_and_opacity")
        ),
    }


def _configure_column_slot(column: unreal.VerticalBox, captured: dict[str, object]) -> None:
    slot = column.get_editor_property("slot")
    if not isinstance(slot, unreal.HorizontalBoxSlot):
        raise RuntimeError(f"{column.get_name()} did not receive a HorizontalBoxSlot")
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


def _configure_button(button: unreal.Button) -> None:
    _set_if_supported(button, "is_focusable", False)
    slot = button.get_editor_property("slot")
    if isinstance(slot, unreal.VerticalBoxSlot):
        slot.set_editor_property(
            "horizontal_alignment",
            unreal.HorizontalAlignment.H_ALIGN_FILL,
        )


def _configure_label(
    label: unreal.TextBlock,
    heading: str,
    captured: dict[str, object],
) -> None:
    label.set_editor_property("text", heading)
    label.set_editor_property("font", captured["font"])
    label.set_editor_property("color_and_opacity", captured["color"])
    label.set_editor_property("shadow_color_and_opacity", captured["shadow_color"])
    label.set_editor_property("justification", unreal.TextJustify.CENTER)
    slot = label.get_editor_property("slot")
    _set_if_supported(
        slot,
        "horizontal_alignment",
        unreal.HorizontalAlignment.H_ALIGN_CENTER,
    )
    _set_if_supported(
        slot,
        "vertical_alignment",
        unreal.VerticalAlignment.V_ALIGN_CENTER,
    )


def _configure_body_slot(rich_text: unreal.RichTextBlock) -> None:
    slot = rich_text.get_editor_property("slot")
    if not isinstance(slot, unreal.VerticalBoxSlot):
        raise RuntimeError(f"{rich_text.get_name()} did not receive a VerticalBoxSlot")
    slot.set_editor_property(
        "horizontal_alignment",
        unreal.HorizontalAlignment.H_ALIGN_FILL,
    )


def _copy_button_style(source: unreal.Button, destination: unreal.Button) -> None:
    for property_name in (
        "widget_style",
        "color_and_opacity",
        "background_color",
        "content_padding",
        "click_method",
        "touch_method",
        "press_method",
        "is_focusable",
    ):
        _copy_if_supported(source, destination, property_name)


def _copy_label_style(source: unreal.TextBlock, destination: unreal.TextBlock) -> None:
    for property_name in (
        "color_and_opacity",
        "shadow_offset",
        "shadow_color_and_opacity",
        "strike_brush",
    ):
        _copy_if_supported(source, destination, property_name)

    font = _copy_struct(source.get_editor_property("font"))
    source_size = float(font.get_editor_property("size"))
    font.set_editor_property("size", max(1.0, source_size * SORT_LABEL_FONT_SCALE))
    destination.set_editor_property("font", font)


def _expose_buttons(blueprint: unreal.WidgetBlueprint) -> None:
    button_type = unreal.BlueprintEditorLibrary.get_object_reference_type(unreal.Button)
    member_names = {
        str(name)
        for name in unreal.BlueprintEditorLibrary.list_member_variable_names(blueprint)
    }
    for _field, _column_name, button_name, _label_name, _heading in COLUMNS:
        changed = (
            unreal.BlueprintEditorLibrary.change_member_variable_type(
                blueprint,
                button_name,
                button_type,
            )
            if button_name in member_names
            else unreal.BlueprintEditorLibrary.add_member_variable(
                blueprint,
                button_name,
                button_type,
            )
        )
        if not changed:
            raise RuntimeError(f"Could not expose sort button {button_name}")


def apply() -> None:
    blueprint = unreal.load_asset(TABLE_PATH)
    if not isinstance(blueprint, unreal.WidgetBlueprint):
        raise RuntimeError(f"Missing jobs table: {TABLE_PATH}")

    viewer = unreal.load_asset(VIEWER_PATH)
    if not isinstance(viewer, unreal.WidgetBlueprint):
        raise RuntimeError(f"Missing viewer widget: {VIEWER_PATH}")
    reference_button = unreal.EditorUtilityLibrary.find_source_widget_by_name(
        viewer,
        REFERENCE_BUTTON_NAME,
    )
    if not isinstance(reference_button, unreal.Button):
        raise RuntimeError(f"Missing reference button {REFERENCE_BUTTON_NAME}")
    reference_label = reference_button.get_child_at(0)
    if not isinstance(reference_label, unreal.TextBlock):
        raise RuntimeError(f"{REFERENCE_BUTTON_NAME} must contain a TextBlock")

    existing_buttons = [
        unreal.EditorUtilityLibrary.find_source_widget_by_name(blueprint, button_name)
        for _field, _column_name, button_name, _label_name, _heading in COLUMNS
    ]
    if all(isinstance(button, unreal.Button) for button in existing_buttons):
        for (_field, _column_name, _button_name, label_name, heading) in COLUMNS:
            label = unreal.EditorUtilityLibrary.find_source_widget_by_name(
                blueprint,
                label_name,
            )
            if not isinstance(label, unreal.TextBlock):
                raise RuntimeError(f"Missing sort label {label_name}")
            label.set_editor_property("text", heading)
            button = unreal.EditorUtilityLibrary.find_source_widget_by_name(
                blueprint,
                _button_name,
            )
            _copy_button_style(reference_button, button)
            _copy_label_style(reference_label, label)
        _log("Existing sort headers updated")
    else:
        if any(button is not None for button in existing_buttons):
            raise RuntimeError("Jobs table contains a partial sort-header conversion")

        rich_texts = [
            unreal.EditorUtilityLibrary.find_source_widget_by_name(
                blueprint,
                render_farm_viewer.JOB_RICH_TEXT_WIDGETS[field],
            )
            for field in render_farm_viewer.JOB_FIELDS
        ]
        if not all(isinstance(widget, unreal.RichTextBlock) for widget in rich_texts):
            raise RuntimeError("Jobs table is missing one or more RichText body columns")
        captured_columns = [_capture_column(widget) for widget in rich_texts]
        root = captured_columns[0]["parent"]
        if not isinstance(root, unreal.HorizontalBox):
            raise RuntimeError("Job body columns must share a HorizontalBox root")
        if any(captured["parent"] != root for captured in captured_columns):
            raise RuntimeError("Job body columns do not share one root")
        root_name = root.get_name()

        for column_info, rich_text, captured in zip(
            COLUMNS,
            rich_texts,
            captured_columns,
        ):
            _field, column_name, button_name, label_name, heading = column_info
            column = unreal.EditorUtilityLibrary.add_source_widget(
                blueprint,
                unreal.VerticalBox,
                column_name,
                root_name,
            )
            if not isinstance(column, unreal.VerticalBox):
                raise RuntimeError(f"Could not create {column_name}")
            _configure_column_slot(column, captured)

            button = unreal.EditorUtilityLibrary.add_source_widget(
                blueprint,
                unreal.Button,
                button_name,
                column_name,
            )
            if not isinstance(button, unreal.Button):
                raise RuntimeError(f"Could not create {button_name}")
            _configure_button(button)
            _copy_button_style(reference_button, button)

            label = unreal.EditorUtilityLibrary.add_source_widget(
                blueprint,
                unreal.TextBlock,
                label_name,
                button_name,
            )
            if not isinstance(label, unreal.TextBlock):
                raise RuntimeError(f"Could not create {label_name}")
            _configure_label(label, heading, captured)
            _copy_label_style(reference_label, label)

            if not root.remove_child(rich_text):
                raise RuntimeError(f"Could not detach {rich_text.get_name()}")
            if column.add_child(rich_text) is None:
                raise RuntimeError(f"Could not reparent {rich_text.get_name()}")
            _configure_body_slot(rich_text)

        _expose_buttons(blueprint)
        _log("Added nine synchronized clickable job headers")

    if not unreal.BlueprintEditorLibrary.compile_blueprint(blueprint):
        raise RuntimeError("Jobs table did not compile after adding sort headers")
    if not unreal.EditorAssetLibrary.save_loaded_asset(blueprint, only_if_is_dirty=False):
        raise RuntimeError(f"Could not save {TABLE_PATH}")
    _log("PASS")


try:
    apply()
except Exception as error:
    unreal.log_error(f"[RenderFarmJobSortHeaders] FAIL: {error}")
    unreal.SystemLibrary.quit_editor()
    raise
else:
    unreal.SystemLibrary.quit_editor()
