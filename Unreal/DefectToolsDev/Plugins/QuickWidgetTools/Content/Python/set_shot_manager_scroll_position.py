"""
Save the scroll position for WBP_02_Shot_Manager.

Blueprint usage:
    import set_shot_manager_scroll_position
    import importlib
    importlib.reload(set_shot_manager_scroll_position)

    success = set_shot_manager_scroll_position.run(scroll_position)

Writes:
    shot_manager_scroll_position=[scroll_position]
"""

import quick_widget_ui_state_settings


KEY = "shot_manager_scroll_position"
LOG_PREFIX = "[SetShotManagerScrollPosition]"


def run(scroll_position):
    return quick_widget_ui_state_settings.set_value(KEY, scroll_position)
