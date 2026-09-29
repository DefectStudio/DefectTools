# Implementation handoff

## Architecture

```text
Unreal assigned camera -> RGB/depth PNG -> Krita linked reference
Krita painting -> explicit PNG/manifest export -> Unreal durable projection/card
Krita bound group -> loopback HTTP PNG -> transient Unreal texture/material
                                      -> explicit commit -> durable asset
```

The live implementation uses a narrow HTTP receiver, **not WebSockets**. PaintBridge's socket-based workflow inspired the investigation, but Unreal's existing Python/Remote Control channels did not supply the needed pixel lifecycle. `RenderingLibrary.import_buffer_as_texture2d` permits transient texture creation without a new native C++ module or per-frame asset import.

## Krita package

| File | Responsibility |
| --- | --- |
| `ironwidow_krita.desktop` | Python Plugin Manager registration; module identity must match folder |
| `__init__.py` | Adds `CardExtension` to Krita |
| `context.py` / `project.json` | Configured data root and destination containment check; loaded at import, restart after reconfiguration |
| `krita_card_export.py` | Registers four menu actions, full-canvas pixel extraction, selection alpha, card manifests |
| `krita_layer_export.py` | Layer-link validation, KRA node annotations, linked workspace creation, versioned group exports |
| `live_preview.py` | Modeless dialog, explicit document/node binding, debounce, PNG encoding, worker-thread HTTP |

Latest menu fix: `createActions(window)` must call `live_preview.install(window)`. Enumerating `Krita.instance().windows()` alone during startup previously omitted Live Preview. The install fallback enumeration remains for manual use. Avoid depending on diagnostic hot injection to validate startup.

## Unreal entry points (supplied through version control)

All are in `Plugins/UnrealKritaBridge/Content/Python`.

- `init_unreal.py`: creates bridge directories, imports panel/capture and live receiver.
- `krita_bridge_panel.py`: editor panel/actions and stop-live transitions; receiver KRA launcher currently hard-coded.
- `assigned_camera_send.py`, `krita_layer_capture.py`: whole-frame and paired captures; inspect shared Lumen helper referenced there.
- `krita_projector.py`, `krita_projection.py`: saved-camera mapping, source checks, material import/apply, original-material ledger.
- `krita_map_scope.py`: map/shot/camera ownership.
- `krita_layers.py`, `krita_layer_return.py`: actor tags, stable layer identity, manifests, returns.
- `krita_cards.py`, `krita_card_math.py`: card validation, placement, updates.
- `krita_live_preview.py`: local receiver, transient preview, lifecycle guards and commit.
- `krita_landscape.py`: experimental component material path and eligibility gate.

`PACKAGE-MANIFEST.json` records top-level Unreal Python hashes for comparison with the version-control revision you receive. It is a source snapshot reference, not a complete project dependency manifest.

## Live contract and lifecycle

Unreal writes `live-preview.json` under the configured data root when a projection is bound. It includes local endpoint, token, session, dimensions and project/map/shot/camera identity. Treat it as an ephemeral credential-bearing descriptor, not a distributable asset.

The sender accepts only `127.0.0.1` and matching local project identity. It uses POST `/frame`, `/status`, `/commit`, with `X-Token`, `X-Session`, `X-Sequence`. Frames are full RGBA8 PNGs. The receiver bounds payloads at 12 MiB and queues one request; Unreal object work runs on the editor/Slate tick, not the HTTP thread. See installed source for the authoritative response schemas.

Krita polls at 350 ms, waits until the mouse is released, and normally waits for two stable hashes. Pixel extraction/PNG encoding remain on the UI thread; network calls run on a worker. This can stall on detailed large frames. Krita native integer pixel order is BGRA on this tested Windows configuration; live QImage encoding and explicit export channel swaps differ deliberately.

Binding is to a document and node UUID, not the currently selected layer afterward. Projected pixels come from `node.projectionPixelData`, not the whole document. Closing/removing/resizing/reprofiling invalidates that input. Files/clones within the bound subtree are rejected to prevent capture feedback. Ordinary raster copies cannot be recognized as references automatically.

Unreal checks current project/map/shot/camera identity, configuration, material ledger, and target material state. All loaded users of the exact bound projection material may receive the preview, not only the clicked actor. Tagged return-layer projections are excluded. Landscape uses its own native component dynamic-material path.

Commit requires an acknowledged current frame, then writes the durable painting and imports its asset. It does not save KRA. Save/map callbacks restore durable materials and invalidate previews. Transport recovery requires explicit rebind; Full Resync resends unchanged pixels within a valid binding. This is not seamless unattended reconnect.

## File return contracts

- `shot.json`: frozen camera/raster framing and map identity.
- `card.json` plus `cutout.png`: full-canvas RGBA, shot/hash, alpha bounds, anchor and stable card ID; `cards/latest.json` points to newest export.
- `layerlink.json`: immutable destination association with shot/context hashes and captured RGB/depth paths.
- `painting-return.json` plus `painting.png`: stable map/layer/link/shot identity, hashes, canvas size, zero crop offset; `latest-return.json` points to newest return.
- KRA `UnrealLayerReturns` annotation maps node UUIDs to destination link paths.

All exports are versioned. Ownership checks intentionally reject another project's paths. The serialized absolute paths are a known migration limitation, not something to bypass by weakening validation.

## Suggested first acceptance test on the programmer's machine

1. Configure a fresh project-local root and verify all four Krita menus after a full restart.
2. In a new map use a placed camera, ordinary cube and new shot. Build receiver canvas, capture RGB/depth, and verify the linked layer changes.
3. Create a raster base + strokes group. Manually export/apply a painting; verify Restore.
4. Start live, bind the parent group, paint then undo. Confirm both base and strokes arrive. Commit, save/reopen, confirm durable result and restoration.
5. Change map / send a capture and confirm preview stops rather than targeting stale objects. Reconnect deliberately.
6. Independently test tagged-layer return and transparent-card placement/update.
7. Keep Landscape tests inside the gated lab folder until broader support has been validated.

## Engineering priorities

1. First-run project selector and automatic linked-canvas creation; avoid hard-coded executable and storage paths.
2. Group binding UI showing source name/thumbnail and base coverage; distinguish incoming reference, outgoing paint and committed result.
3. Explicit durable storage/version-control design with migration tooling; restoration must survive machine changes.
4. Separate RGB/depth reference destinations and deliberate refresh of raster bases.
5. Capture/live coexistence UX, richer error handling, portability and automated lifecycle tests.
6. Background encoding/persistent GPU updates only after profiling; changed tiles require sequencing and full-resync semantics.
7. Landscape streaming, authored terrain materials and Nanite remain separate validation work.

No third-party PaintBridge source is included. This package contains the current internal Krita implementation, not Krita AI Diffusion or AI model weights. Distribution/licensing outside the team has not been assessed.
