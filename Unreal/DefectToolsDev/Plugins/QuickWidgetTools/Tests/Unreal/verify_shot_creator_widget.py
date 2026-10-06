"""Unreal integration regression check for WBP_01_ShotCreator.

Run this file through Unreal's PythonScript commandlet. Its non-test filename keeps
ordinary CPython pytest runs from importing the Unreal-only module.
"""

import unreal


_ASSET_PATH = "/QuickWidgetTools/EditorWidgets/WBP_01_ShotCreator"
_GRAPH_PATH = f"{_ASSET_PATH}.WBP_01_ShotCreator:PopulateShotListData"


def _load_graph_object(name):
    obj = unreal.load_object(None, f"{_GRAPH_PATH}.{name}")
    if not obj:
        raise AssertionError(f"Could not load PopulateShotListData graph object: {name}")
    return obj


def _pins_are_connected(first, second):
    return any(
        connected_pin.is_same_native_pin(second)
        for connected_pin in first.list_connected_pins()
    )


def test_shot_list_is_cleared_before_checking_for_shots():
    """An empty sequence must not retain rows from the prior sequence."""
    asset = unreal.load_object(None, f"{_ASSET_PATH}.WBP_01_ShotCreator")
    if not asset:
        raise AssertionError(f"Could not load Shot Creator widget: {_ASSET_PATH}")

    branch = _load_graph_object("K2Node_IfThenElse_1")
    clear_children = _load_graph_object("K2Node_CallFunction_21")
    final_data_assignment = _load_graph_object("K2Node_VariableSet_4")
    pre_branch_assignment = _load_graph_object("K2Node_VariableSet_5")
    populate_loop = _load_graph_object("K2Node_MacroInstance_2")

    assert _pins_are_connected(
        pre_branch_assignment.find_then_pin(), clear_children.find_execute_pin()
    ), "ClearChildren must execute before the has-any-shots branch"
    assert _pins_are_connected(
        clear_children.find_then_pin(), branch.find_execute_pin()
    ), "The has-any-shots branch must execute after ClearChildren"
    assert _pins_are_connected(
        final_data_assignment.find_then_pin(), populate_loop.find_input_pin("Exec")
    ), "The non-empty branch must continue directly into row population"


try:
    test_shot_list_is_cleared_before_checking_for_shots()
except Exception as error:
    unreal.log_error(f"[ShotCreatorWidgetTest] FAIL: {error}")
    raise
else:
    unreal.log_warning("[ShotCreatorWidgetTest] PASS")
