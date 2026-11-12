#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"
#include "UObject/StrongObjectPtr.h"

class UToolMenu;
class UEditorUtilityWidgetBlueprint;
class UEditorUtilityWidget;
class SDockTab;
class FSpawnTabArgs;

class FQuickWidgetToolsModule : public IModuleInterface
{
public:
    virtual void StartupModule() override;
    virtual void ShutdownModule() override;

private:
    FDelegateHandle RenderFarmLayoutUpdateHandle;
    TStrongObjectPtr<UEditorUtilityWidget> RenderFarmViewerWidget;

    void RegisterMenus();
    TSharedRef<SDockTab> SpawnRenderFarmViewerTab(const FSpawnTabArgs& SpawnTabArgs);
    void OnRenderFarmViewerTabClosed(TSharedRef<SDockTab> TabBeingClosed);
    void PopulateWidgetsMenu(UToolMenu* Menu);

    void FindEditorUtilityWidgets(TArray<FAssetData>& OutAssets) const;
    void LaunchEditorUtilityWidget(FSoftObjectPath WidgetPath) const;

    void ApplyRequestedRenderFarmLayoutUpdate();
};
