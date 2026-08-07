"""Refresh Smart Read nodes after Natron has fully restored a project."""

import NatronEngine
import SmartReadExt


if NatronEngine.natron.isBackground():
    SmartReadExt.afterProjectLoaded(app)
else:
    SmartReadExt.scheduleGuiRefresh(app)
