# Portable Pipe Tools Natron PyPlugs

This directory is the source-controlled Natron plug-in search path.

Launch Natron with `tools\natron_with_portable_plugins.bat`. The launcher adds
this directory to `NATRON_PLUGIN_PATH` without copying files into the Natron
installation. Natron scans PyPlugs during startup, so restart Natron after
changing plug-in metadata or adding a new PyPlug.

`SmartRead.py` contains the PyPlug structure and user parameters.
`SmartReadExt.py` contains hand-written Natron callbacks.
`smart_read_core.py` is reserved for Natron-independent pipeline logic.

