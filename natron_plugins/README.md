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
versions in ascending order; choosing one turns Latest off. Refresh rescans the
current element without reopening the project.

`SmartWrite.py` defines the Smart Write PyPlug and its four output checkboxes.
EXR, MP4, and Hero are enabled by default; MOV is disabled. `SmartWriteExt.py`
derives writer paths from the comp saved in `SHOT/comp/natron`, while
`smart_write_core.py` contains the Natron-independent naming rules. EXR beauty,
MP4, and MOV share the next version above any existing `SHOT_beauty_v###`
output. Hero remains unversioned and overwrites its EXR sequence in
`comp/_output/_hero`. When a Smart Write is created, it also creates the enabled
outputs' missing parent directories. Its selected beauty version remains stable
when checkboxes are changed; another newly created Smart Write reserves the next
version.

Each output checkbox has a matching collapsible settings section. Enabled
outputs open their section by default, while disabled outputs start collapsed.
The controls are independent user parameters synchronized to curated parameters
on the concrete internal OIIO or FFmpeg writer, including EXR compression and
bit depth or video codec, quality, bitrate, and FPS. New MP4 writers default to
`libx264`. Smart Write continues to own filenames, writer disable controls,
callbacks, and other pipeline-sensitive parameters. On project load, it
rebuilds restored writers whose format menus are incomplete and repopulates the
exposed choice menus from the active writer implementations.
