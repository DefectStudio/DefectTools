# OnlyClouds in FX Tools

The **OnlyClouds** section of `WBP_08_FX_Tools` provides the three creation actions from the original CloudGenerator plugin. Its buttons are ordinary, editable UMG widgets. The actions remain native C++ Blueprint nodes; no Python installation, MCP connection, or CloudGenerator project is needed to use them.

## Button wiring

Each existing button's **On Clicked** event calls the corresponding function in `OnlyCloudsEditorLibrary`:

| Button | Blueprint node | C++ function |
| --- | --- | --- |
| Add Basic Light Rigg | Add Basic Light Rigg | `AddBasicLightRigg` |
| Add Layered World Clouds | Add Layered World Clouds | `AddLayeredWorldClouds` |
| Add Cloud Preset | Add Cloud Preset | `AddCloudPreset` |

The return value contains **Success**, **Created**, **Message**, and **Actors**. Connect the result to **Report OnlyClouds Action Result** (`ReportActionResult`) to show the original notification and write the result to the Output Log. A widget can also use those fields for its own status display. Reporting does not create actors or start another transaction.

The integrated version does not add the old viewport toolbar dropdown. It retains the internal `OnlyClouds.Tools` menu and `ExecuteRegisteredMenuAction` for existing validation scripts. That dispatcher already reports its result; do not report the same result a second time.

## Behavior

- **Add Basic Light Rigg** copies the saved directional light, skylight, sky atmosphere, height fog, environment dome, and post-process volume into the current level. Their settings, transforms, and references are retained. The actors are grouped in the **BasicLiteRigg** Outliner folder and selected.
- **Add Layered World Clouds** places **BP_UDSOnlyClouds** at the world origin with the saved two-layer configuration. An existing controller is selected instead of duplicated, including a hidden controller. A different visible world-cloud renderer prevents a second one from being added. Edit layers on the actor, including **+ Add Cloud Layer** and **Additional Cloud Layers**.
- **Add Cloud Preset** places **BP_CloudPreset** at the origin using the saved **Cumulus** recipe and its six editable guides. Choose **CP_Cumulonimbus** in the actor's **Preset** field and use **Load Preset** for the saved ten-guide cloud.

The actions require an editable, unlocked current level and refuse to run during Play or Simulate. They support Undo and Redo, including the placed cloud's guide actors. They do not automatically save the level.

Cloud creation uses the level's existing lighting, HDRI, exposure, fog, and post-process settings. Adding the light rig is a separate action. The world-cloud cinematic quality option changes shared Unreal cloud settings and can affect other clouds and rendering cost. **Restore Previous Cloud Quality** releases those overrides while keeping the actor; undo tracking preserves intervening user changes.

User-created cloud recipes still save to `/Game/OnlyClouds/Presets` by default. **Preset Save Folder** can select another `/Game` folder. Saving creates a unique asset and does not overwrite existing presets.

## Distribution

The shared QuickWidgetTools repository must carry the complete change: the widget, all 32 OnlyClouds content assets, both native source modules, descriptor entries, matching Win64 editor DLLs, and their module manifest. Updating only `WBP_08_FX_Tools.uasset` is insufficient.

The integrated assets live under `/QuickWidgetTools/OnlyClouds`. The native module names **CloudGeneratorTools** and **OnlyCloudsEditor** are intentionally retained so their C++ class identities remain stable. The content and native code travel with the QuickWidgetTools submodule; they do not depend on the developer's local CloudGenerator checkout.

The distributed editor binaries target **Unreal Engine 5.8.3 on Windows 64-bit** and must match the receiving engine build. Other engine builds or platforms need compatible binaries built and tested with the appropriate engine and toolchain. Ordinary artists on the matching Windows engine build do not need to compile this plugin. Cooked game deployment requires its own packaging validation; editor use does not establish that validation.

Do not enable a separate **OnlyClouds** or legacy **CloudGeneratorTools** plugin alongside this integrated version: they contain native modules with the same names. Projects using the standalone plugin should preserve their existing maps and assets and plan the content-path migration before replacing it.

Publish the QuickWidgetTools commit first, then update each consuming project's submodule reference to that commit. Changes to a development project's level, camera, or unrelated plugins are not required to distribute these tools.

## Integration validation

The migrated version was built with UE 5.8.3, Win64 BuildId `55116800`, for editor Development and runtime Development/Shipping. A copied plugin in an isolated receiving project passed 83 integration checks, including actual widget clicks, complete-action Undo/Redo, hidden world-cloud reuse, all three preset recipes, edited guide/density persistence, and level save/reload. Cirrus preserves ten editable guides, five of which are intentionally disabled.

A separate GPU smoke test compiled all six migrated materials, read back valid world-cloud layer data, and visually confirmed both the placed cloud and the world-cloud on/off difference. This establishes editor functionality; it is not a Movie Render Queue or cooked-project certification. The integration test is `Tests/Unreal/verify_onlyclouds_integration.py` and intentionally refuses to modify a production project.

## Source and content provenance

The native implementation and 32 bundled cloud, preset, and lighting assets were ported from the company's **OnlyClouds** plugin in **CloudGenerator**. The world-cloud materials derive from the Ultra Dynamic Sky content used in that source project. This integration preserves those asset origins; it does not require the UDS toolbar or a UDS actor in the destination level.

The port preserves the original action logic, preset initialization, controller ownership, actor transactions, and cloud-quality undo tracking. Input asset paths now resolve inside QuickWidgetTools, while user-generated presets remain project content.
