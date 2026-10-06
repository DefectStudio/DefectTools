"""
Compatibility wrapper for the sequence manifest exporter.

Blueprint / Execute Python usage:
    import unreal
    import export_sequences_manifest
    import importlib

    importlib.reload(export_sequences_manifest)

    manifest_path = export_sequences_manifest.run()

    unreal.log(f"[ShotManager] Exported sequence manifest: {manifest_path}")
"""

import importlib

import export_sequences_manifest_impl


def run():
    importlib.reload(export_sequences_manifest_impl)
    return export_sequences_manifest_impl.run()
