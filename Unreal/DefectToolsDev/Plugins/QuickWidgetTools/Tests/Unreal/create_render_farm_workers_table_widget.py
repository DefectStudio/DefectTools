"""Create the aggregate workers table from the visible worker-row asset."""

import unreal


SOURCE_PATH = "/QuickWidgetTools/EditorWidgets/RenderFarm/WBP_RenderFarmWorkerRow"
DESTINATION_PATH = "/QuickWidgetTools/EditorWidgets/RenderFarm/WBP_RenderFarmWorkersTable"


def create() -> unreal.WidgetBlueprint:
    if unreal.EditorAssetLibrary.does_asset_exist(DESTINATION_PATH):
        asset = unreal.load_asset(DESTINATION_PATH)
        if not isinstance(asset, unreal.WidgetBlueprint):
            raise RuntimeError(f"Destination is not a Widget Blueprint: {DESTINATION_PATH}")
        visible_text = unreal.EditorUtilityLibrary.find_source_widget_by_name(
            asset,
            "TextBlock",
        )
        if isinstance(visible_text, unreal.TextBlock):
            unreal.log_warning(
                f"[RenderFarmWorkersTable] Visible asset already exists: {DESTINATION_PATH}"
            )
            return asset
        if not unreal.EditorAssetLibrary.delete_asset(DESTINATION_PATH):
            raise RuntimeError(f"Could not replace blank table asset: {DESTINATION_PATH}")
        unreal.log_warning(
            f"[RenderFarmWorkersTable] Removed blank table asset: {DESTINATION_PATH}"
        )

    if not unreal.EditorAssetLibrary.does_asset_exist(SOURCE_PATH):
        raise RuntimeError(f"Source widget is missing: {SOURCE_PATH}")

    asset = unreal.EditorAssetLibrary.duplicate_asset(SOURCE_PATH, DESTINATION_PATH)
    if not isinstance(asset, unreal.WidgetBlueprint):
        raise RuntimeError(f"Could not duplicate the workers table: {DESTINATION_PATH}")
    if not unreal.BlueprintEditorLibrary.compile_blueprint(asset):
        raise RuntimeError("The duplicated workers table did not compile")
    if not unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
        raise RuntimeError(f"Could not save {DESTINATION_PATH}")

    unreal.log_warning(f"[RenderFarmWorkersTable] Created {DESTINATION_PATH}")
    return asset


try:
    create()
except Exception as error:
    unreal.log_error(f"[RenderFarmWorkersTable] FAIL: {error}")
    unreal.SystemLibrary.quit_editor()
    raise
else:
    unreal.SystemLibrary.quit_editor()
