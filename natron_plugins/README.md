# Portable Pipe Tools Natron PyPlugs

This directory is the source-controlled Natron plug-in search path.

Launch Natron with `tools\natron_with_portable_plugins.bat`. The launcher adds
this directory to `NATRON_PLUGIN_PATH` without copying files into the Natron
installation. Natron scans PyPlugs during startup, so restart Natron after
changing plug-in metadata or adding a new PyPlug.

`SmartRead.py` contains the PyPlug structure and user parameters.
`SmartReadExt.py` contains the Natron callbacks that populate and operate the
version controls. `SmartReadOnLoad.py` performs the final rescan used by Auto
Comp after Natron restores a copied template. `smart_read_core.py` scans beauty
EXR versions relative to a project saved in the required `SHOT/comp/natron`
location.

Each Smart Read has an Element value and selects matching `SHOT_ELEMENT_v###`
directories under `SHOT/lite/unreal/_output`. With **Latest** enabled it uses
the highest populated version. The **File** combo always lists the discovered
versions newest-first; choosing one turns Latest off. Refresh rescans the
current element without reopening the project.
