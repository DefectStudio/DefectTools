# Director's original Unreal–Krita Bridge: feature inventory

Reviewed September 24, 2026. This describes the director's original plugin,
including the newly supplied `F:/ironwidow/Plugins/UnrealKritaBridge` source,
not the replacement native IPC plugin in Defect Kat Dev.

## Evidence and completeness

- **D — documented:** `Unreal-Krita-Bridge-Introduction-and-Setup.pdf` (4 pages),
  `Unreal-Krita-Bridge-Programmer-Handoff-2026-09-23/DEVELOPER-NOTES.md`, and `VALIDATION.md`.
- **K — Krita source verified:** Python files inside the handoff's
  `IronWidow-Krita-Bridge-2026-09-23.zip`.
- **M — manifest only:** `PACKAGE-MANIFEST.json` names and hashes 23 Unreal Python
  files. Their bodies and Unreal content assets are not included in the ZIP.
- **U — Unreal source verified:** the 23 current Python modules in
  `F:/ironwidow/Plugins/UnrealKritaBridge/Content/Python`, now available locally.
  Backup subdirectories are excluded. The plugin descriptor and project widget
  `F:/ironwidow/Content/KritaProjection/Tools/EUW_UnrealKritaBridge.uasset` exist.

The tables below retain their original D/K evidence labels. The source audit
at the end adds implementation evidence and qualifications. This is a static
code review; the director's plugin was not launched or runtime-tested here.
Sixteen modules match the handoff manifest; seven differ: `assigned_camera_send.py`,
`krita_bridge_panel.py`, `krita_capture_lighting.py`, `krita_landscape.py`,
`krita_layer_capture.py`, `krita_live_preview.py`, and `krita_projection.py`.
The handoff's test results therefore do not certify every current file.

## 1. Editor panel and project setup

| Feature | Evidence |
|---|---|
| Window → Unreal / Krita Bridge editor panel | D |
| Initialize bridge storage directories on Unreal startup | D |
| Assign a selected placed CameraActor or CineCameraActor | D |
| Open / Reconnect 1080p Canvas in Krita | D |
| Configure the Krita plugin's project data root | D, K |
| Optional PowerShell configuration helper with path validation, config backup, and WhatIf mode | D |
| Four Krita menu actions: Send Cutout Card, Update Cutout Card, Return Painting to Layer, Live Preview | D, K |

Original Krita UI was scripts-menu dialogs, not a docker. Reconnect opened an
existing KRA; it did not create a missing receiving canvas. One configured local
project root and a hard-coded Krita executable path were portability limitations.

Relevant Unreal modules: `init_unreal.py`, `krita_bridge_panel.py`, `unreal_krita_bridge.py`.

## 2. Shots, RGB and depth capture

| Feature | Evidence |
|---|---|
| New Shot from Assigned Camera | D |
| Save camera position, rotation, horizontal FOV, aspect, near clip, image dimensions and map/shot identity | D, K |
| Send RGB capture to Krita | D |
| Send depth capture to Krita | D |
| Paired RGB/depth captures for linked actor-layer returns | D, K |
| Incoming image refreshed through a Krita File Layer | D |
| Capture lighting/history warm-up: explicit Lumen/history handling and 64 rendered warm-up ticks | D |
| Capture path includes ray tracing when enabled | D |

The simple receiver used 1920×1080 framing. RGB and depth overwrote the same
`viewport.png`; separate incoming layers were not automatically created there.
The linked actor-layer workspace did create separate RGB/depth reference layers.
Typical reported local captures were approximately 3 seconds for RGB and 4.4
seconds for paired capture, not portable performance guarantees.

Relevant modules: `assigned_camera_send.py`, `krita_camera_capture.py`,
`krita_layer_capture.py`, `krita_capture_lighting.py`, `bridge_raster.py`, `depth_png.py`.

## 3. Manual painting projection

| Feature | Evidence |
|---|---|
| Browse Painting to select an exported full-frame PNG | D |
| Apply to Selected supported target objects | D |
| Project painting using saved-camera framing | D |
| Update Painting from the same PNG while retaining projection framing | D |
| Update Projection from Camera as a separate, explicit framing change | D |
| Record original material assignments in a restoration ledger | D |
| Restore original material assignments | D |
| Save/import painting textures and projection materials as durable Unreal assets | D |
| Validate supported source materials and target state | D |

This was fixed-camera material replacement, not UV baking or a universal overlay.
The exact shader math, occlusion behavior, and restoration implementation require
the missing Unreal code/content. The notes identify a painting browser module but
do not establish additional browser features beyond the documented workflows.

Relevant modules: `krita_projector.py`, `krita_projection.py`, `krita_painting_browser.py`.

## 4. Live painting preview and commit

| Feature | Evidence |
|---|---|
| Start Live Preview from an already-projected object in Unreal | D |
| Bind Selected Painting / Reconnect in Krita | D, K |
| Bind by document and layer/group UUID, independent of subsequent selection | D, K |
| Export only the bound node's composited pixels, including child paint layers/masks | D, K |
| Detect changed image content with SHA-256 | K |
| Poll at 350 ms, pause during mouse presses, normally wait for two stable hashes | D, K |
| Encode full-frame PNG and send over local HTTP on a worker thread | D, K |
| Acknowledge frame sequence and report preview status | D, K |
| Status requests during otherwise unchanged sending | K |
| Full Resync forces resend of unchanged pixels in a valid binding | D, K |
| Stop Sending on the Krita side | D, K |
| Stop Live Preview restores the durable painting in Unreal | D |
| Commit Painting saves/imports an acknowledged frame as durable Unreal data | D, K |
| Stop/invalidate preview on save, map/context changes, and conflicting capture actions | D |
| Transient texture/material preview, separate from durable committed state | D |

Commit did not save KRA and required rebinding to continue. Updates were debounced
PNGs after painting paused, not video-rate brush streaming. The notes report that
all loaded objects using the exact bound projection material could receive the
preview, not only the selected actor. Tagged return layers used a separate path.

Relevant Unreal module: `krita_live_preview.py`; Krita source: `live_preview.py`.

## 5. Tagged actor layers and targeted painting returns

| Feature | Evidence |
|---|---|
| Assign actors to named tagged groups/layers | D |
| Stable map/layer/shot/link identities for return destinations | D, K |
| Capture and link a group's return destination | D, K |
| List destinations or browse a layerlink.json explicitly | K |
| Create a New Linked Painting Document for destinations sharing exact framing | D, K |
| Populate editable captured RGB bases in named painting groups | K |
| Populate separate locked RGB/depth reference layers | K |
| Save that generated linked workspace as a KRA | K |
| Associate existing artwork after explicit framing confirmation | K |
| Export one named group/layer with child masks | D, K |
| Record layer UUID → destination association as a KRA annotation | K |
| Version PNG and painting-return manifest; maintain latest-return pointer | D, K |
| Update Layer / Update All in Unreal | D |
| Target stable destination identity rather than current actor selection | D, K |

The documented target path replaces every material slot of the tagged actor group.
Alpha below 50% becomes transparent: this is a masked replacement, not soft-alpha
paint compositing over existing materials.

Relevant Unreal modules: `krita_layers.py`, `krita_layers_ui.py`, `krita_layer_capture.py`,
`krita_layer_return.py`, `krita_layer_return_ui.py`; Krita: `krita_layer_export.py`.

## 6. Transparent 3D cutout cards

| Feature | Evidence |
|---|---|
| Export a transparent active layer from a full-size saved-shot canvas | D, K |
| Optionally apply the current selection as an alpha mask | D, K |
| Choose the exact source shot | D, K |
| Choose a ground-contact anchor in canvas pixels | D, K |
| Preview cutout and compute alpha bounds | K |
| Reject an accidental opaque rectangle; allow intentional rectangular cards explicitly | K |
| Use Latest Krita Export in Unreal | D |
| Import Cutout on Support using a trace from the saved camera | D |
| Use an explicit distance when support cannot be hit | D |
| Stable card ID and versioned cutout PNG/manifest exports | D, K |
| Update existing card texture while preserving placement | D, K |
| Explicit Reposition operation | D |
| Soft transparency on card materials | D |

A selection clips pixels; it does not automatically remove an object's background.
Cards are separate from projection onto existing scene geometry.

Relevant Unreal modules: `krita_cards.py`, `krita_cards_ui.py`, `krita_card_math.py`;
Krita: `krita_card_export.py`.

## 7. Identity, safety and lifecycle checks

| Feature | Evidence |
|---|---|
| Restrict paths to the configured project data root | D, K |
| Hash and validate source shot/context/link/painting files | D, K |
| Reject mismatched map, shot, layer, project or canvas framing | D, K |
| Preserve full canvas coordinates; no cropped painting-return offsets | K |
| Require compatible RGBA8 colour data and exact sRGB profile for live preview | D, K |
| Invalidate a closed document, removed bound node, resized canvas or changed profile | D, K |
| Reject file/clone layers in outgoing live groups to prevent reference feedback | D, K |
| Localhost-only HTTP binding with session, token and sequence checks | D, K |
| Limit incoming PNGs to 12 MiB and queue one request | D |
| Perform Unreal object changes on the editor/Slate tick | D |
| Require an acknowledged current frame before commit | D, K |

Raster copies cannot be automatically identified as references. Absolute paths in
records/annotations and durable data stored under ignored `Saved` were known
migration/version-control weaknesses. Seamless unattended reconnection was absent.

Relevant additional module: `krita_map_scope.py`.

## 8. Experimental/support limits

- **Landscape:** gated to `/Game/X_Dev/Sam/KritaLandscapeLab`, with a component
  dynamic-material path. Four non-Nanite components were reported tested. General
  Landscape, Nanite Landscape, World Partition/streaming proxies and authored
  weight/hole terrains were not certified. Module: `krita_landscape.py`.
- **Nanite static meshes:** documented support subject to source-material limits.
- **Cameras:** placed standard perspective cameras and centered Cine Cameras;
  not sequence spawnables, lens distortion, off-axis/anamorphic gates or overscan.
- **Materials:** deformation/WPO, source translucency/masks, material attributes
  and displacement excluded; unsupported pixel-depth offset not reliably detected.
- **Painting geometry:** no hidden-geometry reconstruction, all-around finished
  object textures, UV baking, or physically relightable texture-authoring workflow.
- **AI:** Krita AI Diffusion optional and external. Accepted raster results could
  participate in a paint group. No shipped GPT Image provider integration.
- **Portability:** baseline reported Windows/Krita 5.3.3/Unreal 5.8.2; other major
  platforms/versions not verified by the original handoff.

## 9. Source audit of the newly supplied checkout (U)

All paths below are relative to
`F:/ironwidow/Plugins/UnrealKritaBridge/Content/Python`.

| Implemented feature | Source evidence and behavior |
|---|---|
| Python/content editor plugin | Descriptor declares Python, Editor Scripting Utilities, Slate Scripting and Geometry Scripting dependencies; no native C++ module. Panel uses a project Editor Utility Widget. |
| Panel capture and depth controls | `krita_bridge_panel.py:41`: RGB, depth, explicit depth-range fitting, fixed range in metres, receiver reconnect. Reconnect requires an existing KRA and uses a hard-coded Krita executable path. |
| Assigned-camera captures | `assigned_camera_send.py:36`, `krita_layer_capture.py:29`: transient SceneCapture2D actors, 1920x1080 render targets; RGB uses final-color LDR, depth uses scene depth. Layer capture produces both RGB and depth, with a show-only actor list. |
| Lighting/history handling | `krita_capture_lighting.py:6`: Lumen GI/reflections, persistent history, ray tracing when enabled, camera post-process weight handling. Default warm-up is 64 frames; capture API accepts 1–256. |
| Frozen camera projection | `krita_projection.py:137`: world position projected through saved origin/basis/lens into image UVs. Replaces receiving materials with an opaque, two-sided, **unlit** material whose image RGB feeds emissive. It does not multiply the source surface material. Outside the projection frustum it outputs dark gray. |
| Projection restoration and toggles | `krita_projection.py:355`: restore selected or all recorded loaded targets, preserving exact original override arrays (including empty/default slots). `:383` re-enables saved projections. Editor transactions wrap actor/material assignment changes. |
| Navigate and reactivate shots | `krita_projection.py:400` returns viewport position, rotation and FOV to the saved shot; requires leaving pilot mode. `krita_map_scope.py:115` activates a shot from selected projected objects, rejecting mixed-shot selections. Camera assignment can also be cleared (`:101`). |
| Explicit camera update | `krita_projector.py:121` updates frozen projection parameters from the assigned camera. This changes the shared shot material rather than continuously following camera movement. |
| Actor-layer management | `krita_layers.py:35–68`: create, add/remove selected mesh actors, rename with stable layer ID, and delete. Membership changes route through return restoration checks. Lights/cameras are excluded as layer members. |
| Masked painting return | `krita_layer_return.py:84`: separate unlit material with alpha-mask threshold 0.5. Transparent pixels remove receiver coverage; they do not reveal the original material on that same surface. |
| Update all linked layers | `krita_layer_return.py:136`: prevalidates all plans before modifying actors; writes an update report. Apply-time failures can still yield partial results, which the report records. |
| Safe layer removal/restoration | `krita_layer_return.py:153`: validates original materials and requires affected projected members to be loaded before unassigning/deleting. Restores original override arrays. |
| Soft-alpha cutout cards | `krita_cards.py:87`: translucent, two-sided, unlit RGB/alpha material. `:137` updates texture while retaining transform/mesh/pivot; `:147` explicitly rebuilds placement from saved shot and resets scale. |
| Live incoming painting | `krita_live_preview.py:65,145`: authenticated local receiver binds existing durable projection, decodes PNG to a transient texture, updates dynamic material instances on editor tick. A shared projection material determines affected loaded targets. This is Krita-to-Unreal painting preview, not continuous Unreal viewport video. |
| Explicit durable commit | `krita_live_preview.py:169`: backs up existing painting PNG, stops transient preview, replaces the destination PNG, imports/updates durable projection assets. Does not save KRA. Stop/save/map changes restore or retain durable state. |
| Binding protection | `krita_live_preview.py:30`: detects changed project/map/shot/camera identity, destination, ledger or material assignments. Stop avoids overwriting a manually changed material binding. |
| Restricted Landscape support | `krita_landscape.py:20`: only the lab map path; rejects Nanite Landscape, missing loaded components and per-LOD overrides. `:52` checks topology and outside edits; `:84` refuses an existing dynamic-material controller and creates component MIDs for preview. |
| Camera/source restrictions | `krita_projector.py:57` validates native perspective CameraActor/CineCameraActor, centered lens, squeeze 1, no overscan or post-process blendables. `krita_projection.py:251` accepts ordinary StaticMeshActors plus gated Landscape; rejects source masks/translucency, material attributes, WPO and tessellation. |

### Implications for our replacement

- The director's ordinary projection replaces object materials; it does not
  spawn a dedicated projector actor. The saved shot, material parameters and
  restoration ledger hold the projection state. Cutout import is a separate
  actor-creation workflow.
- Unlit replacement avoids source-material lighting/multiplication, but emissive
  still participates in Unreal's subsequent image processing. It is not proof
  of pixel-identical Krita display colors. Our after-tone-mapping overwrite
  approach has a different receiver/depth scope and should not be treated as
  feature-equivalent to per-object material replacement.
- Depth capture is present, but the ordinary projection shader does not sample
  a captured depth map to reject occluded geometry. Receiver selection and
  projection coverage need their own design in our replacement.
- Reusable product features are saved-shot identity, receiver selection,
  layer/group return, explicit commit, exact restoration, and independent cards.
  These can be implemented over IPC without retaining the original HTTP path.

Remaining validation: inspect the widget/material assets inside Unreal and run
the director's workflows against this checkout. Presence of assets and readable
source is not runtime verification, nor proof of portability to another project.
