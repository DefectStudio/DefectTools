"""
Save the scroll position for the rendering tool.

Blueprint usage:
    import set_rendering_tool_scroll_position
    import importlib
    importlib.reload(set_rendering_tool_scroll_position)

    success = set_rendering_tool_scroll_position.run(scroll_position)

Writes:
    rendering_tool_scroll_position=[scroll_position]
"""

import quick_widget_ui_state_settings


KEY = "rendering_tool_scroll_position"
LOG_PREFIX = "[SetRenderingToolScrollPosition]"


def run(scroll_position):
    return quick_widget_ui_state_settings.set_value(KEY, scroll_position)
