"""
Load the selected sequence for WBP_02_Shot_Manager.

Blueprint usage:
    import get_shot_manager_selected_sequence
    import importlib
    importlib.reload(get_shot_manager_selected_sequence)

    selected = get_shot_manager_selected_sequence.run()

Reads:
    shot_manager_selected_sequence
"""

import quick_widget_ui_state_settings


KEY = "shot_manager_selected_sequence"
LOG_PREFIX = "[GetShotManagerSelectedSequence]"


def run():
    return quick_widget_ui_state_settings.get_value(KEY)
