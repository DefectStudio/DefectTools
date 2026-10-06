#include "Modules/ModuleManager.h"
#include "OnlyCloudsEditorInternal.h"
#include "OnlyCloudsEditorQualityUndo.h"
#include "ToolMenus.h"
#include "Styling/AppStyle.h"
#include "Framework/Commands/UIAction.h"

#define LOCTEXT_NAMESPACE "OnlyCloudsEditor"

class FOnlyCloudsEditorModule final : public IModuleInterface
{
public:
    virtual void StartupModule() override
    {
        if (!IsRunningCommandlet())
        {
            OnlyCloudsEditor::StartCloudQualityUndoTracking();
            UToolMenus::RegisterStartupCallback(FSimpleMulticastDelegate::FDelegate::CreateRaw(this, &FOnlyCloudsEditorModule::RegisterMenus));
        }
    }

    virtual void ShutdownModule() override
    {
        OnlyCloudsEditor::StopCloudQualityUndoTracking();
        UToolMenus::UnRegisterStartupCallback(this);
        UToolMenus::UnregisterOwner(OnlyCloudsEditor::OwnerName);
    }

private:
    void RegisterMenus()
    {
        using namespace OnlyCloudsEditor;
        FToolMenuOwnerScoped Owner(OwnerName);
        UToolMenu* Actions = UToolMenus::Get()->RegisterMenu(MenuName);
        FToolMenuSection& Create = Actions->FindOrAddSection(TEXT("Create"));

        auto AddAction = [&Create](FName Name, FText Label, FText Tooltip, FName Icon)
        {
            FToolUIAction Action;
            Action.ExecuteAction = FToolMenuExecuteAction::CreateLambda([Name](const FToolMenuContext&) { RunRegisteredAction(Name); });
            Action.CanExecuteAction = FToolMenuCanExecuteAction::CreateLambda([](const FToolMenuContext&) { return CanUseEditorWorld(); });
            Create.AddMenuEntry(Name, Label, Tooltip, FSlateIcon(FAppStyle::GetAppStyleSetName(), Icon),
                Action);
        };
        AddAction(TEXT("AddBasicLightRigg"), LOCTEXT("BasicRig", "Add Basic Light Rigg"),
            LOCTEXT("BasicRigTip", "Add the saved six-actor lighting rig to the BasicLiteRigg Outliner folder."), TEXT("ClassIcon.DirectionalLight"));
        AddAction(TEXT("AddLayeredWorldClouds"), LOCTEXT("WorldClouds", "Add Layered World Clouds"),
            LOCTEXT("WorldCloudsTip", "Add BP_UDSOnlyClouds at the world origin. Existing visible world-cloud renderers are preserved."), TEXT("ClassIcon.VolumetricCloud"));
        AddAction(TEXT("AddCloudPreset"), LOCTEXT("CloudPreset", "Add Cloud Preset"),
            LOCTEXT("CloudPresetTip", "Add BP_CloudPreset at the world origin with the saved Cumulus cloud and editable guides."), TEXT("ClassIcon.Volume"));

        // The editable WBP_08_FX_Tools buttons own the visible UI. Keep this
        // internal menu for the existing action-dispatch validation API only;
        // do not add a second OnlyClouds menu above the level viewport.
    }
};

IMPLEMENT_MODULE(FOnlyCloudsEditorModule, OnlyCloudsEditor)

#undef LOCTEXT_NAMESPACE
