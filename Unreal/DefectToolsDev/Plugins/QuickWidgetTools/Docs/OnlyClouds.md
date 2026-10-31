# OnlyClouds in FX Tools

The **OnlyClouds** section of `WBP_08_FX_Tools` provides cloud creation actions and a low-lying fog preset. Its buttons are ordinary, editable UMG widgets. The actions remain native C++ Blueprint nodes; no Python installation, MCP connection, or CloudGenerator project is needed to use them.

## Button wiring

Each existing button's **On Clicked** event calls the corresponding function in `OnlyCloudsEditorLibrary`:

| Button | Blueprint node | C++ function |
| --- | --- | --- |
| Add Basic Light Rigg | Add Basic Light Rigg | `AddBasicLightRigg` |
| Add Layered World Clouds | Add Layered World Clouds | `AddLayeredWorldClouds` |
| Add Cloud Preset | Add Cloud Preset | `AddCloudPreset` |
| Add Low Fog Preset | Add Low Fog Preset | `AddLowFogPreset` |

The return value contains **Success**, **Created**, **Message**, and **Actors**. Connect the result to **Report OnlyClouds Action Result** (`ReportActionResult`) to show the original notification and write the result to the Output Log. A widget can also use those fields for its own status display. Reporting does not create actors or start another transaction.

The integrated version does not add the old viewport toolbar dropdown. It retains the internal `OnlyClouds.Tools` menu and `ExecuteRegisteredMenuAction` for existing validation scripts. That dispatcher already reports its result; do not report the same result a second time.

## Behavior

- **Add Basic Light Rigg** copies the saved directional light, skylight, sky atmosphere, height fog, environment dome, and post-process volume into the current level. Their settings, transforms, and references are retained. The actors are grouped in the **BasicLiteRigg** Outliner folder and selected.
- **Add Layered World Clouds** places **BP_UDSOnlyClouds** at the world origin with the saved two-layer configuration. An existing controller is selected instead of duplicated, including a hidden controller. A different visible world-cloud renderer prevents a second one from being added. Edit layers on the actor, including **+ Add Cloud Layer** and **Additional Cloud Layers**.
- **Add Cloud Preset** places **BP_CloudPreset** at the origin using the saved **Cumulus** recipe and its six editable guides. Choose **CP_Cumulonimbus** in the actor's **Preset** field and use **Load Preset** for the saved ten-guide cloud.
- **Add Low Fog Preset** places **BP_LowFogPreset** at the origin using **CP_LowFog_Cemetery**, with the artist-tuned settings from the ground-fog test level: density 8, Cinematic quality, resolution 128, and an oval cylinder approximately 656.25 x 615.23 cm across and 76.90 cm high. The recipe preserves the authored generator scale, guide transform, appearance, and animation controls. Move the generator to place the fog. Its guide supports **Cylinder / Circle**, **Box**, and **Sphere / Ellipsoid**; scale the guide to change the footprint and containment height. Nonuniform XY cylinder scaling creates an oval footprint.

The actions require an editable, unlocked current level and refuse to run during Play or Simulate. They support Undo and Redo, including the placed cloud's guide actors. They do not automatically save the level.

Cloud creation uses the level's existing lighting, HDRI, exposure, fog, and post-process settings. Adding the light rig is a separate action. The world-cloud cinematic quality option changes shared Unreal cloud settings and can affect other clouds and rendering cost. **Restore Previous Cloud Quality** releases those overrides while keeping the actor; undo tracking preserves intervening user changes.

User-created cloud recipes still save to `/Game/OnlyClouds/Presets` by default. **Preset Save Folder** can select another `/Game` folder. Saving creates a unique asset and does not overwrite existing presets.

## Low fog controls

The low-fog actor inherits the cloud's density, color, billow/detail noise, Levels, warp, breakup, animation, guides, and Save/Load Preset controls. Its dedicated material adds moving interior density, an irregular rolling top, and height-dependent wisps. **Ground Offset** moves the ground plane relative to the generator; **Ground Fade** softens contact above that plane; **Fog Height** sets the upper density profile; **Height Falloff** controls how quickly density decreases with height. Increase the guide's containment height as well when raising Fog Height beyond it. These fields, the material, and guide shapes are included in saved recipes.

The ground plane is horizontal and follows the generator's world Z position. It does not automatically follow landscape height or settle dynamically around obstacles. This is an animated procedural volume, not a fluid simulation. Existing lighting is used; adding fog does not install a light rig or change project-wide volumetric-fog settings. Low fog uses shallow per-axis volume bounds, while ordinary clouds retain their existing cubic bounds.

**Animated** drives editor/runtime motion; the viewport must have **Realtime** enabled to advance it. For deterministic Sequencer animation, turn it off and key **Texture Offset Cm** and **Noise Phase** using the existing workflow. Fog density, billow size, detail, wisps, and quality affect appearance and cost; preview from the final camera and validate Movie Render Queue separately.

### Resolution and edge fade

On the generator actor, **Cloud Quality > Volume Resolution** sets the number of voxels per axis, from 32 to 512 (default 128). All three component axes follow this value. The generator compensates its component scale, material coordinates, and extinction, preserving the physical footprint, world-space noise sizes, and density. Try 256 for finer sampling. Rendering cost rises with resolution, and Unreal's ray-marching step budget can limit the visible improvement at high settings. **Quality** remains a separate sampling/lighting choice. Resolution is saved in recipes and remains adjustable while the cloud is locked.

**Cloud Appearance > Edge Fall Off** contains three controls:

- **Edge Fall Off** enables the boundary fade.
- **Edge Fall Off Distance** sets how many centimeters inward the transition reaches. The interior beyond that distance keeps its full density envelope; the boundary reaches zero. The distance is limited to the shape's usable inner radius so its center can reach full density. Zero gives a hard edge.
- **Edge Fall Off Contrast** shapes that transition: 1 is linear, values above 1 concentrate density toward the core, and values below 1 retain more density near the outer edge.

Low-fog cylinders and boxes fade around their horizontal perimeter; existing ground and height controls retain the vertical profile. Spheres/ellipsoids, and ordinary clouds, use the full 3D boundary. Overlapping additive guides share one union fade; subtractive guides retain their existing cuts. The cemetery fog preset enables a 200 cm transition with contrast 1; existing ordinary cloud presets keep the fade disabled. All three controls are saved in recipes and protected by the appearance lock.

## Distribution

The shared QuickWidgetTools repository must carry the complete change: the widget, all OnlyClouds content assets (including the low-fog Blueprint, cemetery recipe, and material), both native source modules, descriptor entries, matching Win64 editor DLLs, and their module manifest. Updating only `WBP_08_FX_Tools.uasset` is insufficient.

The integrated assets live under `/QuickWidgetTools/OnlyClouds`. The native module names **CloudGeneratorTools** and **OnlyCloudsEditor** are intentionally retained so their C++ class identities remain stable. The content and native code travel with the QuickWidgetTools submodule; they do not depend on the developer's local CloudGenerator checkout.

The distributed editor binaries target **Unreal Engine 5.8.4 on Windows 64-bit** and must match the receiving engine build. Other engine builds or platforms need compatible binaries built and tested with the appropriate engine and toolchain. Ordinary artists on the matching Windows engine build do not need to compile this plugin. Cooked game deployment requires its own packaging validation; editor use does not establish that validation.

Do not enable a separate **OnlyClouds** or legacy **CloudGeneratorTools** plugin alongside this integrated version: they contain native modules with the same names. Projects using the standalone plugin should preserve their existing maps and assets and plan the content-path migration before replacing it.

Publish the QuickWidgetTools commit first, then update each consuming project's submodule reference to that commit. Changes to a development project's level, camera, or unrelated plugins are not required to distribute these tools.

## Integration validation

The low-fog and detail-control extensions were built with UE 5.8.4, Win64 BuildId `55116800`, for editor Development and runtime Development/Shipping. Five native regression/integration tests passed, including fog/resolution/falloff recipe serialization, fixed physical bounds and optical-density scaling across resolutions, existing preset placement/scale persistence, and the actual FX Tools Low Fog button with complete single-action Undo/Redo. Rendered checks in a separate test editor verified all three guide shapes and changing noise phase/offset. Movie Render Queue output was not tested.

The migrated version was built with UE 5.8.3, Win64 BuildId `55116800`, for editor Development and runtime Development/Shipping. A copied plugin in an isolated receiving project passed 83 integration checks, including actual widget clicks, complete-action Undo/Redo, hidden world-cloud reuse, all three preset recipes, edited guide/density persistence, and level save/reload. Cirrus preserves ten editable guides, five of which are intentionally disabled.

A separate GPU smoke test compiled all six migrated materials, read back valid world-cloud layer data, and visually confirmed both the placed cloud and the world-cloud on/off difference. This establishes editor functionality; it is not a Movie Render Queue or cooked-project certification. The integration test is `Tests/Unreal/verify_onlyclouds_integration.py` and intentionally refuses to modify a production project.

## Source and content provenance

The native implementation and 32 bundled cloud, preset, and lighting assets were ported from the company's **OnlyClouds** plugin in **CloudGenerator**. The world-cloud materials derive from the Ultra Dynamic Sky content used in that source project. This integration preserves those asset origins; it does not require the UDS toolbar or a UDS actor in the destination level.

The port preserves the original action logic, preset initialization, controller ownership, actor transactions, and cloud-quality undo tracking. Input asset paths now resolve inside QuickWidgetTools, while user-generated presets remain project content.
