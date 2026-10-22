# Manual Render Hero Chooser

Double-click `tools\ManualRenderHeroChooser.bat`. It uses the same Python and
Tkinter installation as the other DefectTools apps and works without Unreal open.

1. Browse to your shared **defect** folder, for example `K:\Defect Dropbox\defect`.
2. Choose a show, then a sequence.
3. Choose a render version beside a shot and click **Hero**.

The folder, show, and sequence are remembered locally in
`LocalSaveFiles\manual_render_hero_chooser.json`. Use **Refresh** after new renders
arrive. Every shot is listed, including shots without renders; those rows have
Hero disabled. Version choices include only populated EXR version folders,
ordered by numeric version with the newest first.

The source is `SHOW\sequences\SEQUENCE\SHOT\lite\unreal\_output\SHOT_ELEMENT_v###`.
The destination is its sibling `_hero`. Hero replaces all existing contents of
that shot's `_hero` with the selected EXRs. It keeps source renders and uses the
same naming rule as `mrg_callbacks_hero.py`, for example:

```text
SPE_000_0050_beauty_v046.1001.exr -> SPE_000_0050.1001.exr
```

Hero clears the existing `_hero` contents, then copies each selected EXR directly
into `_hero` using its unversioned filename. It creates no backup or preparation
copy. Dropbox online-only frames may need time to download during the copy.
A failed copy stops and reports how many frames finished; `_hero` contains the
files copied so far. Keep the window open until the copy finishes.

This standalone tool mirrors the callback's EXR copy and filename behavior; it
does not invoke Unreal's render callback or change the automatic post-render tool.
