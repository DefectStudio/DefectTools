"""
Load the scroll position for WBP_02_Shot_Manager.

Blueprint usage:
    import get_shot_manager_scroll_position
    import importlib
    importlib.reload(get_shot_manager_scroll_position)

    scroll_position = get_shot_manager_scroll_position.run()

Reads:
    shot_manager_scroll_position
"""

import quick_widget_ui_state_settings


KEY = "shot_manager_scroll_position"
LOG_PREFIX = "[GetShotManagerScrollPosition]"


def run():
    return quick_widget_ui_state_settings.get_value(KEY)
