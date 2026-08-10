"""Refresh Smart Read and Smart Write nodes after project restoration."""

import NatronEngine
import SmartReadExt
import SmartWriteExt


if NatronEngine.natron.isBackground():
    SmartReadExt.afterProjectLoaded(app)
    SmartWriteExt.afterProjectLoaded(app)
else:
    SmartReadExt.scheduleGuiRefresh(app)
    SmartWriteExt.scheduleGuiRefresh(app)
