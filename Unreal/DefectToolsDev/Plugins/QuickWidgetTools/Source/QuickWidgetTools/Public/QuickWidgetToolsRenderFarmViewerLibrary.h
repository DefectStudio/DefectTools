#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "QuickWidgetToolsRenderFarmViewerLibrary.generated.h"

class UEditorUtilityWidget;
class SDockTab;

/** Access to the level-independent Render Farm Viewer dock tab. */
UCLASS()
class QUICKWIDGETTOOLS_API UQuickWidgetToolsRenderFarmViewerLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintCallable, Category = "Quick Widget Tools|Render Farm")
    static bool OpenViewer();

    UFUNCTION(BlueprintCallable, Category = "Quick Widget Tools|Render Farm")
    static bool CloseViewer();

    UFUNCTION(BlueprintPure, Category = "Quick Widget Tools|Render Farm")
    static UEditorUtilityWidget* GetActiveViewer();

    /** Update an FText data variable on a transient designer widget instance. */
    UFUNCTION(BlueprintCallable, Category = "Quick Widget Tools|Render Farm")
    static bool SetViewerTextProperty(UObject* Widget, FName PropertyName, const FString& Value);

    static void SetActiveViewer(UEditorUtilityWidget* Widget);
    static void SetActiveTab(TSharedPtr<SDockTab> Tab);
    static FName GetTabId();
};
