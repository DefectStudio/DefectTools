"""Hand-written Natron callbacks for the Smart Read PyPlug.

Keep custom behavior in this module so SmartRead.py can later be regenerated
or replaced without losing the callback implementation.
"""


def createInstanceExt(app, group):
    """Install Smart Read callbacks after the internal graph is constructed."""

    # The initial scaffold has no smart behavior. Parameters and callbacks will
    # be added here as the node's production GUI is defined.
    del app, group

