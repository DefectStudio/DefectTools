# Package verification — 23 September 2026

## Checked for this delivery

- ZIP contains the installed six extension/config files plus service descriptor, copied byte-for-byte. Includes the corrected fresh-start Live Preview registration.
- Explicit module-directory entry included, as required by the installed Krita ZIP importer. No extra parent folder obscures the plugin layout.
- Ran **the installed Krita importer's actual `PluginImporter.import_all()`** against this ZIP into a fresh workspace resource directory. It found and imported exactly `ironwidow_krita`; extracted files matched source bytes. Only Krita's translation helper was stubbed, not the import logic.
- Python source compiles without syntax errors.
- Executed the installed menu-registration function with a supplied mock window absent from the global window list; it created the Live Preview action and connected its handler.
- ZIP CRC and extraction-byte checks passed. Manifest records SHA-256 hashes.
- Configuration helper parsed and passed isolated fixture checks: paths with spaces, `-WhatIf` making no change, correct project data root, backup creation, BOM-free JSON, and refusing configuration while Krita is running. Tests used process mocks and workspace files, not the installed plugin configuration.
- No caches, backup copies, artwork, model weights, running-session descriptors or credentials included.

## Existing application evidence

The packaged source is the installed extension used in the preceding local workflow tests. Reports covered brush/undo, group compositing, explicit commit, restart/reconnect, layer/card exports, the startup menu repair, and the restricted Landscape lab. These are local prototype results, not a claim of universal compatibility.

The handoff packaging did not restart or modify either running app. The ZIP was tested through Krita's importer implementation in a fixture; a fresh-machine GUI install and complete round trip are still the recipient's acceptance test, documented in DEVELOPER-NOTES.md.

## Scope

Package snapshot matches the installed Krita files on 23 September 2026. Unreal top-level source hashes in PACKAGE-MANIFEST.json identify the paired implementation. No new runtime features were added during packaging. Recipient project-path configuration is required where the checkout differs from Sam's machine.
