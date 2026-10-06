"""Create the reusable Render Farm cell-text Widget Blueprint without C++."""

import unreal


ASSET_PATH = "/QuickWidgetTools/EditorWidgets/RenderFarm/WBP_RenderFarmCellText"
TEXT_WIDGET_NAME = "CellText"
TEXT_VARIABLE_NAME = "Text"
SETTER_NAME = "SetText"


def _connect(output_pin, input_pin, description: str) -> None:
    if not output_pin.try_create_connection(input_pin):
        raise RuntimeError(f"Could not connect {description}")


def _configure_text_block(text_block: unreal.TextBlock) -> None:
    font = text_block.get_editor_property("font")
    font.set_editor_property("font_object", unreal.load_asset("/Engine/EngineFonts/Roboto"))
    font.set_editor_property("typeface_font_name", "Regular")
    font.set_editor_property("size", 8)
    text_block.set_editor_property("font", font)

    foreground = unreal.SlateColor(
        specified_color=unreal.LinearColor.WHITE,
        color_use_rule=unreal.SlateColorStylingMode.USE_COLOR_FOREGROUND,
    )
    text_block.set_editor_property("color_and_opacity", foreground)
    text_block.set_editor_property("text", "Text")


def _add_preconstruct_sync(blueprint: unreal.WidgetBlueprint) -> None:
    event = unreal.BlueprintEditorLibrary.add_event_override(
        blueprint,
        "PreConstruct",
        unreal.IntPoint(0, 0),
    )
    if event is None:
        raise RuntimeError("Could not add the PreConstruct event")

    graph = unreal.BlueprintEditorLibrary.find_event_graph(blueprint)
    editor = unreal.BlueprintGraphEditor.get_graph_editor(graph)
    cell_node = editor.add_get_member_variable_node(TEXT_WIDGET_NAME)
    text_node = editor.add_get_member_variable_node(TEXT_VARIABLE_NAME)
    set_text_node = editor.add_call_function_node("/Script/UMG.TextBlock.SetText")

    _connect(event.find_then_pin(), set_text_node.find_execute_pin(), "PreConstruct execution")
    _connect(
        cell_node.find_output_pin(TEXT_WIDGET_NAME),
        set_text_node.find_self_pin(),
        "CellText target",
    )
    _connect(
        text_node.find_output_pin(TEXT_VARIABLE_NAME),
        set_text_node.find_input_pin("InText"),
        "Text value",
    )

    cell_node.set_node_pos(unreal.IntPoint(190, 120))
    text_node.set_node_pos(unreal.IntPoint(190, 220))
    set_text_node.set_node_pos(unreal.IntPoint(440, 0))


def _add_public_setter(
    blueprint: unreal.WidgetBlueprint,
    text_type: unreal.EdGraphPinType,
) -> None:
    editor = unreal.BlueprintGraphEditor.create_and_edit_function_graph(
        blueprint,
        SETTER_NAME,
    )
    if editor is None:
        raise RuntimeError(f"Could not create {SETTER_NAME}")

    editor.set_function_is_public()
    input_text = editor.add_graph_input_parameter("InText", text_type)
    entry_exec = editor.find_graph_entry_pin()
    set_variable = editor.add_set_member_variable_node(TEXT_VARIABLE_NAME)
    cell_node = editor.add_get_member_variable_node(TEXT_WIDGET_NAME)
    set_text_node = editor.add_call_function_node("/Script/UMG.TextBlock.SetText")

    _connect(entry_exec, set_variable.find_execute_pin(), "SetText entry execution")
    _connect(
        input_text,
        set_variable.find_input_pin(TEXT_VARIABLE_NAME),
        "stored Text value",
    )
    _connect(
        set_variable.find_then_pin(),
        set_text_node.find_execute_pin(),
        "TextBlock update execution",
    )
    _connect(
        cell_node.find_output_pin(TEXT_WIDGET_NAME),
        set_text_node.find_self_pin(),
        "SetText CellText target",
    )
    _connect(
        input_text,
        set_text_node.find_input_pin("InText"),
        "SetText display value",
    )

    set_variable.set_node_pos(unreal.IntPoint(250, 0))
    cell_node.set_node_pos(unreal.IntPoint(480, 160))
    set_text_node.set_node_pos(unreal.IntPoint(700, 0))


def create() -> unreal.WidgetBlueprint:
    if unreal.EditorAssetLibrary.does_asset_exist(ASSET_PATH):
        existing = unreal.load_asset(ASSET_PATH)
        unreal.log_warning(f"[RenderFarmCellText] Asset already exists: {ASSET_PATH}")
        return existing

    blueprint = unreal.BlueprintEditorLibrary.create_blueprint_asset_with_parent(
        ASSET_PATH,
        unreal.UserWidget,
    )
    if not isinstance(blueprint, unreal.WidgetBlueprint):
        raise RuntimeError(f"Could not create Widget Blueprint: {ASSET_PATH}")

    text_block = unreal.EditorUtilityLibrary.add_source_widget(
        blueprint,
        unreal.TextBlock,
        TEXT_WIDGET_NAME,
        "None",
    )
    if not isinstance(text_block, unreal.TextBlock):
        raise RuntimeError("Could not create the CellText root TextBlock")
    _configure_text_block(text_block)

    cell_type = unreal.BlueprintEditorLibrary.get_object_reference_type(unreal.TextBlock)
    if not unreal.BlueprintEditorLibrary.add_member_variable(
        blueprint,
        TEXT_WIDGET_NAME,
        cell_type,
    ):
        raise RuntimeError("Could not expose the CellText widget variable")

    text_type = unreal.BlueprintEditorLibrary.get_basic_type_by_name("text")
    if not unreal.BlueprintEditorLibrary.add_member_variable(
        blueprint,
        TEXT_VARIABLE_NAME,
        text_type,
    ):
        raise RuntimeError("Could not add the Text variable")
    unreal.BlueprintEditorLibrary.set_blueprint_variable_instance_editable(
        blueprint,
        TEXT_VARIABLE_NAME,
        True,
    )
    unreal.BlueprintEditorLibrary.set_blueprint_variable_expose_on_spawn(
        blueprint,
        TEXT_VARIABLE_NAME,
        True,
    )
    unreal.BlueprintEditorLibrary.set_blueprint_variable_category(
        blueprint,
        TEXT_VARIABLE_NAME,
        "Data",
    )

    if not unreal.BlueprintEditorLibrary.compile_blueprint(blueprint):
        raise RuntimeError("The initial Widget Blueprint compile failed")

    _add_preconstruct_sync(blueprint)
    _add_public_setter(blueprint, text_type)

    if not unreal.BlueprintEditorLibrary.compile_blueprint(blueprint):
        raise RuntimeError("The completed Widget Blueprint compile failed")
    if not unreal.EditorAssetLibrary.save_loaded_asset(blueprint, only_if_is_dirty=False):
        raise RuntimeError(f"Could not save {ASSET_PATH}")

    unreal.log_warning(f"[RenderFarmCellText] Created {ASSET_PATH}")
    return blueprint


try:
    create()
except Exception as error:
    unreal.log_error(f"[RenderFarmCellText] FAIL: {error}")
    unreal.SystemLibrary.quit_editor()
    raise
else:
    unreal.SystemLibrary.quit_editor()
