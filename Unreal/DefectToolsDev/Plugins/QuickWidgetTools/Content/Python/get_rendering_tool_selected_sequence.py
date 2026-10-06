"""
Load the selected sequence for the rendering tool.

Blueprint usage:
    import get_rendering_tool_selected_sequence
    import importlib
    importlib.reload(get_rendering_tool_selected_sequence)

    selected = get_rendering_tool_selected_sequence.run()

Reads:
    rendering_tool_selected_sequence
"""

import quick_widget_ui_state_settings


KEY = "rendering_tool_selected_sequence"
LOG_PREFIX = "[GetRenderingToolSelectedSequence]"


def run():
    return quick_widget_ui_state_settings.get_value(KEY)
