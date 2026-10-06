"""V2-only farm submission, including compatibility with older widget assets."""


def initialize(v1_checkbox, v2_checkbox):
    """Remove obsolete version controls from older widget assets."""
    for checkbox in (v1_checkbox, v2_checkbox):
        if checkbox is not None:
            checkbox.on_check_state_changed.clear()
            checkbox.remove_from_parent()


def use_v2(v1_checkbox, v2_checkbox):
    """Older submission nodes also always route to V2."""
    return True
