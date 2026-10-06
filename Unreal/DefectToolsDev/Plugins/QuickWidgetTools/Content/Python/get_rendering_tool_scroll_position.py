"""
Load the scroll position for the rendering tool.

Blueprint usage:
    import get_rendering_tool_scroll_position
    import importlib
    importlib.reload(get_rendering_tool_scroll_position)

    scroll_position = get_rendering_tool_scroll_position.run()

Reads:
    rendering_tool_scroll_position
"""

import quick_widget_ui_state_settings


KEY = "rendering_tool_scroll_position"
LOG_PREFIX = "[GetRenderingToolScrollPosition]"


def run():
    return quick_widget_ui_state_settings.get_value(KEY)
