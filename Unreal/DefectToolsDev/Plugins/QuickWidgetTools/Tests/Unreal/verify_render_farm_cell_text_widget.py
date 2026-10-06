"""Static Unreal smoke test for the reusable Render Farm cell-text widget."""

import unreal


ASSET_PATH = "/QuickWidgetTools/EditorWidgets/RenderFarm/WBP_RenderFarmCellText"


def verify() -> None:
    asset = unreal.load_asset(ASSET_PATH)
    if not isinstance(asset, unreal.WidgetBlueprint):
        raise AssertionError(f"Cell-text Widget Blueprint is missing: {ASSET_PATH}")

    text_block = unreal.EditorUtilityLibrary.find_source_widget_by_name(asset, "CellText")
    if not isinstance(text_block, unreal.TextBlock):
        raise AssertionError("CellText must be the widget's TextBlock")
    if text_block.get_parent() is not None:
        raise AssertionError("CellText must remain the root widget")

    font = text_block.get_editor_property("font")
    if font.get_editor_property("size") != 8:
        raise AssertionError("CellText font size must be 8")
    if str(font.get_editor_property("typeface_font_name")) != "Regular":
        raise AssertionError("CellText must use the Regular typeface")

    color = text_block.get_editor_property("color_and_opacity")
    if (
        color.get_editor_property("color_use_rule")
        != unreal.SlateColorStylingMode.USE_COLOR_FOREGROUND
    ):
        raise AssertionError("CellText must inherit Slate's foreground color")

    member_names = unreal.BlueprintEditorLibrary.list_member_variable_names(
        asset,
        False,
    )
    if "Text" not in member_names:
        raise AssertionError("The widget must expose its Text data variable")

    functions = {
        str(function.name): function
        for function in unreal.BlueprintEditorLibrary.list_functions(asset)
    }
    if "SetText" not in functions or not functions["SetText"].is_implemented:
        raise AssertionError("The widget must provide an implemented SetText function")

    events = {
        str(event.name): event
        for event in unreal.BlueprintEditorLibrary.list_events(asset)
    }
    if "PreConstruct" not in events or not events["PreConstruct"].is_implemented:
        raise AssertionError("The widget must update its preview through PreConstruct")


try:
    verify()
except Exception as error:
    unreal.log_error(f"[RenderFarmCellTextTest] FAIL: {error}")
    unreal.SystemLibrary.quit_editor()
    raise
else:
    unreal.log_warning("[RenderFarmCellTextTest] PASS")
    unreal.SystemLibrary.quit_editor()
