#include "QuickWidgetToolsRenderFarmViewerLibrary.h"

#include "Editor.h"
#include "EditorUtilitySubsystem.h"
#include "EditorUtilityWidget.h"
#include "EditorUtilityWidgetBlueprint.h"
#include "Framework/Docking/TabManager.h"
#include "Widgets/Docking/SDockTab.h"
#include "UObject/UnrealType.h"

namespace
{
TWeakObjectPtr<UEditorUtilityWidget> ActiveRenderFarmViewer;
TWeakPtr<SDockTab> ActiveRenderFarmViewerTab;
}

FName UQuickWidgetToolsRenderFarmViewerLibrary::GetTabId()
{
    static const FName TabId(TEXT("QuickWidgetTools.RenderFarmViewer"));
    return TabId;
}

bool UQuickWidgetToolsRenderFarmViewerLibrary::OpenViewer()
{
    // An older editor layout may still have the level-bound utility tab open.
    // Close it when switching to the native tab so it cannot retain a level.
    if (GEditor)
    {
        UEditorUtilitySubsystem* Subsystem = GEditor->GetEditorSubsystem<UEditorUtilitySubsystem>();
        UEditorUtilityWidgetBlueprint* Blueprint = LoadObject<UEditorUtilityWidgetBlueprint>(
            nullptr,
            TEXT("/QuickWidgetTools/EditorWidgets/WBP_09_Render_Farm_Viewer.WBP_09_Render_Farm_Viewer")
        );
        if (Subsystem && Blueprint)
        {
            Subsystem->CloseTabByID(Subsystem->GetTabIDFromBlueprint(Blueprint));
        }
    }
    if (TSharedPtr<SDockTab> Tab = ActiveRenderFarmViewerTab.Pin())
    {
        Tab->ActivateInParent(ETabActivationCause::SetDirectly);
        return true;
    }
    return FGlobalTabmanager::Get()->TryInvokeTab(GetTabId()).IsValid();
}

bool UQuickWidgetToolsRenderFarmViewerLibrary::CloseViewer()
{
    if (TSharedPtr<SDockTab> Tab = ActiveRenderFarmViewerTab.Pin())
    {
        return Tab->RequestCloseTab();
    }
    if (TSharedPtr<SDockTab> Tab = FGlobalTabmanager::Get()->FindExistingLiveTab(GetTabId()))
    {
        return Tab->RequestCloseTab();
    }
    return false;
}

UEditorUtilityWidget* UQuickWidgetToolsRenderFarmViewerLibrary::GetActiveViewer()
{
    return ActiveRenderFarmViewer.Get();
}

bool UQuickWidgetToolsRenderFarmViewerLibrary::SetViewerTextProperty(
    UObject* Widget, FName PropertyName, const FString& Value
)
{
    if (!IsValid(Widget))
    {
        return false;
    }
    FTextProperty* Property = FindFProperty<FTextProperty>(Widget->GetClass(), PropertyName);
    if (!Property)
    {
        return false;
    }
    Property->SetPropertyValue_InContainer(Widget, FText::FromString(Value));
    return true;
}

void UQuickWidgetToolsRenderFarmViewerLibrary::SetActiveViewer(UEditorUtilityWidget* Widget)
{
    ActiveRenderFarmViewer = Widget;
}

void UQuickWidgetToolsRenderFarmViewerLibrary::SetActiveTab(TSharedPtr<SDockTab> Tab)
{
    ActiveRenderFarmViewerTab = Tab;
}
