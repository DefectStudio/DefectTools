"""
Save the selected sequence for the rendering tool.

Blueprint usage:
    import set_rendering_tool_selected_sequence
    import importlib
    importlib.reload(set_rendering_tool_selected_sequence)

    success = set_rendering_tool_selected_sequence.run(selected)

Writes:
    rendering_tool_selected_sequence=[selected]
"""

import quick_widget_ui_state_settings


KEY = "rendering_tool_selected_sequence"
LOG_PREFIX = "[SetRenderingToolSelectedSequence]"


def run(selected):
    return quick_widget_ui_state_settings.set_value(KEY, selected)
