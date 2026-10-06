"""
Save the selected sequence for WBP_02_Shot_Manager.

Blueprint usage:
    import set_shot_manager_selected_sequence
    import importlib
    importlib.reload(set_shot_manager_selected_sequence)

    success = set_shot_manager_selected_sequence.run(selected)

Writes:
    shot_manager_selected_sequence=[selected]
"""

import quick_widget_ui_state_settings


KEY = "shot_manager_selected_sequence"
LOG_PREFIX = "[SetShotManagerSelectedSequence]"


def run(selected):
    return quick_widget_ui_state_settings.set_value(KEY, selected)
