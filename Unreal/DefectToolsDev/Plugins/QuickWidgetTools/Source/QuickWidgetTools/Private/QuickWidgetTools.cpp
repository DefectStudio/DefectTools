#include "QuickWidgetTools.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "Blueprint/WidgetTree.h"
#include "Components/BorderSlot.h"
#include "Components/ButtonSlot.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/OverlaySlot.h"
#include "Components/PanelWidget.h"
#include "Components/ScrollBox.h"
#include "Components/ScrollBoxSlot.h"
#include "Components/SizeBox.h"
#include "Components/SizeBoxSlot.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "EditorUtilitySubsystem.h"
#include "EditorUtilityWidgetBlueprint.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "ToolMenus.h"
#include "ToolMenuEntry.h"
#include "WidgetBlueprint.h"
#include "WidgetBlueprintOperationUtils.h"

#include "Misc/CoreDelegates.h"
#include "Misc/CommandLine.h"
#include "Misc/PackageName.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Modules/ModuleManager.h"
#include "UObject/SavePackage.h"

#define LOCTEXT_NAMESPACE "FQuickWidgetToolsModule"

namespace QuickWidgetToolsMenu
{
struct FParsedWidgetMenuData
{
    FName RawAssetName;
    bool bHasValidPattern = false;
    int32 ToolOrderNumber = MAX_int32;
    FString DisplayLabel;
};

FString BuildFriendlyLabel(const FString& InToolName)
{
    FString SpacedLabel;
    SpacedLabel.Reserve(InToolName.Len() * 2);

    for (int32 Index = 0; Index < InToolName.Len(); ++Index)
    {
        const TCHAR CurrentChar = InToolName[Index];

        if (CurrentChar == TEXT('_'))
        {
            SpacedLabel.AppendChar(TEXT(' '));
            continue;
        }

        if (Index > 0)
        {
            const TCHAR PreviousChar = InToolName[Index - 1];
            const bool bPreviousIsLowerOrDigit = FChar::IsLower(PreviousChar) || FChar::IsDigit(PreviousChar);
            const bool bCurrentIsUpper = FChar::IsUpper(CurrentChar);
            const bool bAcronymBoundary =
                FChar::IsUpper(PreviousChar) &&
                bCurrentIsUpper &&
                (Index + 1 < InToolName.Len()) &&
                FChar::IsLower(InToolName[Index + 1]);

            if (bCurrentIsUpper && (bPreviousIsLowerOrDigit || bAcronymBoundary))
            {
                SpacedLabel.AppendChar(TEXT(' '));
            }
        }

        SpacedLabel.AppendChar(CurrentChar);
    }

    FString NormalizedLabel;
    NormalizedLabel.Reserve(SpacedLabel.Len());

    bool bLastWasSpace = true;
    for (const TCHAR Character : SpacedLabel)
    {
        const bool bIsSpace = FChar::IsWhitespace(Character);
        if (bIsSpace)
        {
            if (!bLastWasSpace)
            {
                NormalizedLabel.AppendChar(TEXT(' '));
            }

            bLastWasSpace = true;
            continue;
        }

        NormalizedLabel.AppendChar(Character);
        bLastWasSpace = false;
    }

    NormalizedLabel.TrimStartAndEndInline();
    return NormalizedLabel;
}

FParsedWidgetMenuData ParseWidgetMenuData(const FAssetData& Asset)
{
    FParsedWidgetMenuData ParsedData;
    ParsedData.RawAssetName = Asset.AssetName;

    const FString RawName = Asset.AssetName.ToString();
    ParsedData.DisplayLabel = RawName;

    FString Prefix;
    FString OrderText;
    FString ToolName;

    if (!RawName.Split(TEXT("_"), &Prefix, &OrderText))
    {
        return ParsedData;
    }

    if (!OrderText.Split(TEXT("_"), &OrderText, &ToolName))
    {
        return ParsedData;
    }

    if (!Prefix.Equals(TEXT("WBP"), ESearchCase::CaseSensitive))
    {
        return ParsedData;
    }

    if (OrderText.IsEmpty() || ToolName.IsEmpty() || !OrderText.IsNumeric())
    {
        return ParsedData;
    }

    ParsedData.bHasValidPattern = true;
    ParsedData.ToolOrderNumber = FCString::Atoi(*OrderText);

    const FString FriendlyLabel = BuildFriendlyLabel(ToolName);
    if (!FriendlyLabel.IsEmpty())
    {
        ParsedData.DisplayLabel = FriendlyLabel;
    }

    return ParsedData;
}
} // namespace QuickWidgetToolsMenu

namespace QuickWidgetToolsRenderFarmLayout
{
constexpr TCHAR ApplyLayoutParameter[] = TEXT("QuickWidgetToolsApplyRenderFarmLayout");

constexpr TCHAR ViewerAssetPath[] =
    TEXT("/QuickWidgetTools/EditorWidgets/WBP_09_Render_Farm_Viewer.WBP_09_Render_Farm_Viewer");
constexpr TCHAR WorkerRowAssetPath[] =
    TEXT("/QuickWidgetTools/EditorWidgets/RenderFarm/WBP_RenderFarmWorkerRow.WBP_RenderFarmWorkerRow");

FSlateChildSize MakeFillSize(const float Coefficient = 1.0f)
{
    FSlateChildSize Size(ESlateSizeRule::Fill);
    Size.Value = Coefficient;
    return Size;
}

void FillSlot(UPanelSlot* Slot, const bool bFillAlongPanelAxis)
{
    if (UCanvasPanelSlot* CanvasSlot = Cast<UCanvasPanelSlot>(Slot))
    {
        CanvasSlot->SetAnchors(FAnchors(0.0f, 0.0f, 1.0f, 1.0f));
        CanvasSlot->SetOffsets(FMargin(0.0f));
        CanvasSlot->SetAlignment(FVector2D::ZeroVector);
    }
    else if (UHorizontalBoxSlot* HorizontalSlot = Cast<UHorizontalBoxSlot>(Slot))
    {
        HorizontalSlot->SetHorizontalAlignment(HAlign_Fill);
        HorizontalSlot->SetVerticalAlignment(VAlign_Fill);
        if (bFillAlongPanelAxis)
        {
            HorizontalSlot->SetSize(MakeFillSize());
        }
    }
    else if (UVerticalBoxSlot* VerticalSlot = Cast<UVerticalBoxSlot>(Slot))
    {
        VerticalSlot->SetHorizontalAlignment(HAlign_Fill);
        VerticalSlot->SetVerticalAlignment(VAlign_Fill);
        if (bFillAlongPanelAxis)
        {
            VerticalSlot->SetSize(MakeFillSize());
        }
    }
    else if (UScrollBoxSlot* ScrollSlot = Cast<UScrollBoxSlot>(Slot))
    {
        ScrollSlot->SetHorizontalAlignment(HAlign_Fill);
        ScrollSlot->SetVerticalAlignment(VAlign_Fill);
    }
    else if (UBorderSlot* BorderSlot = Cast<UBorderSlot>(Slot))
    {
        BorderSlot->SetHorizontalAlignment(HAlign_Fill);
        BorderSlot->SetVerticalAlignment(VAlign_Fill);
    }
    else if (UButtonSlot* ButtonSlot = Cast<UButtonSlot>(Slot))
    {
        ButtonSlot->SetHorizontalAlignment(HAlign_Fill);
        ButtonSlot->SetVerticalAlignment(VAlign_Fill);
    }
    else if (UOverlaySlot* OverlaySlot = Cast<UOverlaySlot>(Slot))
    {
        OverlaySlot->SetHorizontalAlignment(HAlign_Fill);
        OverlaySlot->SetVerticalAlignment(VAlign_Fill);
    }
    else if (USizeBoxSlot* SizeBoxSlot = Cast<USizeBoxSlot>(Slot))
    {
        SizeBoxSlot->SetHorizontalAlignment(HAlign_Fill);
        SizeBoxSlot->SetVerticalAlignment(VAlign_Fill);
    }
}

void StretchWidgetChain(UWidget* Widget)
{
    for (UWidget* Current = Widget; Current; Current = Current->GetParent())
    {
        if (USizeBox* SizeBox = Cast<USizeBox>(Current))
        {
            SizeBox->ClearWidthOverride();
            SizeBox->ClearMinDesiredWidth();
            SizeBox->ClearMaxDesiredWidth();
        }

        FillSlot(Current->Slot, true);
    }
}

bool MoveChildren(UPanelWidget* Source, UPanelWidget* Destination)
{
    if (!Source || !Destination)
    {
        return false;
    }

    TArray<TObjectPtr<UWidget>> Children;
    for (int32 Index = 0; Index < Source->GetChildrenCount(); ++Index)
    {
        Children.Add(Source->GetChildAt(Index));
    }

    for (UWidget* Child : Children)
    {
        Source->RemoveChild(Child);
        Destination->AddChild(Child);
    }

    return true;
}

UVerticalBox* EnsureDesignerList(
    UWidgetBlueprint* Blueprint,
    const FName PublicName,
    const FName ScrollName)
{
    if (!Blueprint || !Blueprint->WidgetTree)
    {
        return nullptr;
    }

    UWidget* Existing = Blueprint->WidgetTree->FindWidget(PublicName);
    if (UVerticalBox* ExistingList = Cast<UVerticalBox>(Existing))
    {
        FWidgetBlueprintOperationUtils::ToggleWidgetAsVariable(Blueprint, ExistingList, true, false);
        StretchWidgetChain(ExistingList);
        return ExistingList;
    }

    UScrollBox* ScrollBox = Cast<UScrollBox>(Existing);
    if (!ScrollBox)
    {
        UE_LOG(
            LogTemp,
            Error,
            TEXT("QuickWidgetTools: %s must currently be a ScrollBox or VerticalBox (found %s)"),
            *PublicName.ToString(),
            Existing ? *Existing->GetClass()->GetName() : TEXT("nothing")
        );
        return nullptr;
    }

    if (Blueprint->WidgetTree->FindWidget(ScrollName))
    {
        UE_LOG(
            LogTemp,
            Error,
            TEXT("QuickWidgetTools: Cannot rename %s because %s already exists"),
            *PublicName.ToString(),
            *ScrollName.ToString()
        );
        return nullptr;
    }

    if (!FWidgetBlueprintOperationUtils::RenameWidget(Blueprint, ScrollBox, ScrollName.ToString()))
    {
        UE_LOG(LogTemp, Error, TEXT("QuickWidgetTools: Could not rename %s"), *PublicName.ToString());
        return nullptr;
    }

    UVerticalBox* List = Blueprint->WidgetTree->ConstructWidget<UVerticalBox>(
        UVerticalBox::StaticClass(),
        PublicName
    );
    if (!List)
    {
        UE_LOG(LogTemp, Error, TEXT("QuickWidgetTools: Could not create %s"), *PublicName.ToString());
        return nullptr;
    }

    FWidgetBlueprintOperationUtils::ToggleWidgetAsVariable(Blueprint, List, true, false);
    MoveChildren(ScrollBox, List);
    ScrollBox->AddChild(List);
    FillSlot(List->Slot, false);
    StretchWidgetChain(ScrollBox);

    UE_LOG(
        LogTemp,
        Display,
        TEXT("QuickWidgetTools: Added responsive %s inside %s"),
        *PublicName.ToString(),
        *ScrollName.ToString()
    );
    return List;
}

bool RemoveViewerDetails(UWidgetBlueprint* Blueprint)
{
    if (!Blueprint || !Blueprint->WidgetTree)
    {
        return false;
    }

    UWidget* DetailsScroll = Blueprint->WidgetTree->FindWidget(TEXT("FarmViewerDetailsScroll"));
    UWidget* DetailsPanel = Blueprint->WidgetTree->FindWidget(TEXT("FarmViewerDetails"));
    UWidget* WidgetToRemove = DetailsScroll ? DetailsScroll : DetailsPanel;
    if (!WidgetToRemove)
    {
        return true;
    }

    FText ErrorMessage;
    if (!FWidgetBlueprintOperationUtils::RemoveWidget(Blueprint, WidgetToRemove, ErrorMessage))
    {
        UE_LOG(
            LogTemp,
            Error,
            TEXT("QuickWidgetTools: Could not remove the Render Farm details panel: %s"),
            *ErrorMessage.ToString()
        );
        return false;
    }

    UE_LOG(LogTemp, Display, TEXT("QuickWidgetTools: Removed the Render Farm details panel"));
    return true;
}

UHorizontalBox* FindPrimaryHorizontalBox(UWidgetBlueprint* Blueprint)
{
    if (!Blueprint || !Blueprint->WidgetTree)
    {
        return nullptr;
    }

    TArray<UWidget*> Widgets;
    Blueprint->WidgetTree->GetAllWidgets(Widgets);

    UHorizontalBox* BestBox = nullptr;
    int32 BestChildCount = 0;
    for (UWidget* Widget : Widgets)
    {
        UHorizontalBox* Candidate = Cast<UHorizontalBox>(Widget);
        if (Candidate && Candidate->GetChildrenCount() > BestChildCount)
        {
            BestBox = Candidate;
            BestChildCount = Candidate->GetChildrenCount();
        }
    }

    return BestBox;
}

bool ConfigureWorkerColumns(UWidgetBlueprint* Blueprint)
{
    UHorizontalBox* Columns = FindPrimaryHorizontalBox(Blueprint);
    if (!Columns || Columns->GetChildrenCount() < 6)
    {
        UE_LOG(
            LogTemp,
            Error,
            TEXT("QuickWidgetTools: %s needs a HorizontalBox with at least six column children"),
            Blueprint ? *Blueprint->GetName() : TEXT("Worker widget")
        );
        return false;
    }

    constexpr float ColumnWeights[] = {1.5f, 1.2f, 0.9f, 2.0f, 1.1f, 0.9f};
    for (int32 Index = 0; Index < UE_ARRAY_COUNT(ColumnWeights); ++Index)
    {
        UWidget* Column = Columns->GetChildAt(Index);
        UHorizontalBoxSlot* Slot = Column ? Cast<UHorizontalBoxSlot>(Column->Slot) : nullptr;
        if (!Slot)
        {
            UE_LOG(
                LogTemp,
                Error,
                TEXT("QuickWidgetTools: %s column %d does not have a HorizontalBoxSlot"),
                *Blueprint->GetName(),
                Index
            );
            return false;
        }

        Slot->SetHorizontalAlignment(HAlign_Fill);
        Slot->SetVerticalAlignment(VAlign_Fill);
        Slot->SetSize(MakeFillSize(ColumnWeights[Index]));
    }

    TArray<UWidget*> Widgets;
    Blueprint->WidgetTree->GetAllWidgets(Widgets);
    for (UWidget* Widget : Widgets)
    {
        if (USizeBox* SizeBox = Cast<USizeBox>(Widget))
        {
            SizeBox->ClearWidthOverride();
            SizeBox->ClearMinDesiredWidth();
            SizeBox->ClearMaxDesiredWidth();
        }
    }

    StretchWidgetChain(Columns);
    UE_LOG(
        LogTemp,
        Display,
        TEXT("QuickWidgetTools: Configured responsive columns in %s (%s)"),
        *Blueprint->GetName(),
        *Columns->GetName()
    );
    return true;
}

bool SaveWidgetBlueprint(UWidgetBlueprint* Blueprint)
{
    if (!Blueprint)
    {
        return false;
    }

    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
    FKismetEditorUtilities::CompileBlueprint(Blueprint);
    Blueprint->MarkPackageDirty();

    UPackage* Package = Blueprint->GetOutermost();
    const FString Filename = FPackageName::LongPackageNameToFilename(
        Package->GetName(),
        FPackageName::GetAssetPackageExtension()
    );

    FSavePackageArgs SaveArgs;
    SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
    SaveArgs.SaveFlags = SAVE_NoError;
    return UPackage::SavePackage(Package, Blueprint, *Filename, SaveArgs);
}

UWidgetBlueprint* LoadWidgetBlueprint(const TCHAR* ObjectPath)
{
    UWidgetBlueprint* Blueprint = LoadObject<UWidgetBlueprint>(nullptr, ObjectPath);
    if (!Blueprint)
    {
        UE_LOG(LogTemp, Error, TEXT("QuickWidgetTools: Could not load %s"), ObjectPath);
    }
    return Blueprint;
}

bool ApplyViewerLayout()
{
    UWidgetBlueprint* Blueprint = LoadWidgetBlueprint(ViewerAssetPath);
    if (!Blueprint)
    {
        return false;
    }

    UVerticalBox* List = EnsureDesignerList(
        Blueprint,
        TEXT("FarmViewerList"),
        TEXT("FarmViewerListScroll")
    );
    if (!List || !RemoveViewerDetails(Blueprint))
    {
        return false;
    }

    StretchWidgetChain(List);
    return SaveWidgetBlueprint(Blueprint);
}

bool ApplyWorkerLayout(const TCHAR* ObjectPath)
{
    UWidgetBlueprint* Blueprint = LoadWidgetBlueprint(ObjectPath);
    return Blueprint && ConfigureWorkerColumns(Blueprint) && SaveWidgetBlueprint(Blueprint);
}
} // namespace QuickWidgetToolsRenderFarmLayout

void FQuickWidgetToolsModule::StartupModule()
{
    if (FParse::Param(
            FCommandLine::Get(),
            QuickWidgetToolsRenderFarmLayout::ApplyLayoutParameter
        ))
    {
        RenderFarmLayoutUpdateHandle = FCoreDelegates::OnFEngineLoopInitComplete.AddRaw(
            this,
            &FQuickWidgetToolsModule::ApplyRequestedRenderFarmLayoutUpdate
        );
    }

    UToolMenus::RegisterStartupCallback(
        FSimpleMulticastDelegate::FDelegate::CreateRaw(this, &FQuickWidgetToolsModule::RegisterMenus)
    );
}

void FQuickWidgetToolsModule::ApplyRequestedRenderFarmLayoutUpdate()
{
    using namespace QuickWidgetToolsRenderFarmLayout;

    if (!FParse::Param(FCommandLine::Get(), ApplyLayoutParameter))
    {
        return;
    }

    UE_LOG(LogTemp, Display, TEXT("QuickWidgetTools: Applying saved Render Farm Viewer layout update"));

    const bool bViewerUpdated = ApplyViewerLayout();
    const bool bWorkerRowUpdated = ApplyWorkerLayout(WorkerRowAssetPath);

    if (bViewerUpdated && bWorkerRowUpdated)
    {
        UE_LOG(LogTemp, Display, TEXT("QuickWidgetTools: Render Farm layout update completed"));
    }
    else
    {
        UE_LOG(
            LogTemp,
            Error,
            TEXT("QuickWidgetTools: Render Farm layout update failed (viewer=%s, row=%s)"),
            bViewerUpdated ? TEXT("ok") : TEXT("failed"),
            bWorkerRowUpdated ? TEXT("ok") : TEXT("failed")
        );
    }
}

void FQuickWidgetToolsModule::ShutdownModule()
{
    if (RenderFarmLayoutUpdateHandle.IsValid())
    {
        FCoreDelegates::OnFEngineLoopInitComplete.Remove(RenderFarmLayoutUpdateHandle);
        RenderFarmLayoutUpdateHandle.Reset();
    }

    if (UToolMenus::IsToolMenuUIEnabled())
    {
        UToolMenus::UnRegisterStartupCallback(this);
        UToolMenus::UnregisterOwner(this);
    }
}

void FQuickWidgetToolsModule::RegisterMenus()
{
    FToolMenuOwnerScoped OwnerScoped(this);

    UToolMenu* MainMenu = UToolMenus::Get()->ExtendMenu("LevelEditor.MainMenu");
    if (!MainMenu)
    {
        UE_LOG(LogTemp, Warning, TEXT("QuickWidgetTools: Failed to extend LevelEditor.MainMenu"));
        return;
    }

    FToolMenuSection& Section = MainMenu->FindOrAddSection("QuickWidgetToolsSection");

    Section.AddSubMenu(
        "QuickWidgetToolsRootMenu",
        LOCTEXT("QuickWidgetToolsMenuLabel", "Quick Widget Tools"),
        LOCTEXT("QuickWidgetToolsMenuTooltip", "Open editor utility widgets from the QuickWidgetTools plugin"),
        FNewToolMenuDelegate::CreateRaw(this, &FQuickWidgetToolsModule::PopulateWidgetsMenu),
        false,
        FSlateIcon()
    );
}

void FQuickWidgetToolsModule::PopulateWidgetsMenu(UToolMenu* Menu)
{
    if (!Menu)
    {
        return;
    }

    FToolMenuSection& Section = Menu->AddSection(
        "QuickWidgetToolsWidgetsSection",
        LOCTEXT("QuickWidgetToolsWidgetsHeading", "Editor Widgets")
    );

    TArray<FAssetData> WidgetAssets;
    FindEditorUtilityWidgets(WidgetAssets);

    if (WidgetAssets.Num() == 0)
    {
        FToolMenuEntry Entry = FToolMenuEntry::InitMenuEntry(
            NAME_None,
            LOCTEXT("NoWidgetsFound", "No Editor Utility Widgets Found"),
            LOCTEXT("NoWidgetsFoundTooltip", "No Editor Utility Widget Blueprints were found in /QuickWidgetTools/EditorWidgets"),
            FSlateIcon(),
            FToolUIActionChoice(),
            EUserInterfaceActionType::Button
        );

        Section.AddEntry(Entry);
        return;
    }

    struct FWidgetMenuEntryData
    {
        FAssetData Asset;
        QuickWidgetToolsMenu::FParsedWidgetMenuData ParsedData;
    };

    TArray<FWidgetMenuEntryData> MenuEntries;
    MenuEntries.Reserve(WidgetAssets.Num());

    for (const FAssetData& Asset : WidgetAssets)
    {
        FWidgetMenuEntryData& EntryData = MenuEntries.AddDefaulted_GetRef();
        EntryData.Asset = Asset;
        EntryData.ParsedData = QuickWidgetToolsMenu::ParseWidgetMenuData(Asset);
    }

    MenuEntries.Sort([](const FWidgetMenuEntryData& A, const FWidgetMenuEntryData& B)
        {
            if (A.ParsedData.bHasValidPattern != B.ParsedData.bHasValidPattern)
            {
                return A.ParsedData.bHasValidPattern;
            }

            if (A.ParsedData.bHasValidPattern && A.ParsedData.ToolOrderNumber != B.ParsedData.ToolOrderNumber)
            {
                return A.ParsedData.ToolOrderNumber < B.ParsedData.ToolOrderNumber;
            }

            return A.Asset.AssetName.LexicalLess(B.Asset.AssetName);
        });

    for (const FWidgetMenuEntryData& MenuEntry : MenuEntries)
    {
        const FAssetData& Asset = MenuEntry.Asset;
        const FText Label = FText::FromString(MenuEntry.ParsedData.DisplayLabel);
        const FText Tooltip = FText::FromString(Asset.GetSoftObjectPath().ToString());
        const FSoftObjectPath WidgetPath = Asset.GetSoftObjectPath();

        FToolMenuEntry Entry = FToolMenuEntry::InitMenuEntry(
            NAME_None,
            Label,
            Tooltip,
            FSlateIcon(),
            FToolUIActionChoice(
                FExecuteAction::CreateRaw(this, &FQuickWidgetToolsModule::LaunchEditorUtilityWidget, WidgetPath)
            ),
            EUserInterfaceActionType::Button
        );

        Section.AddEntry(Entry);
    }
}

void FQuickWidgetToolsModule::FindEditorUtilityWidgets(TArray<FAssetData>& OutAssets) const
{
    OutAssets.Reset();

    static const FName SearchPath(TEXT("/QuickWidgetTools/EditorWidgets"));

    FAssetRegistryModule& AssetRegistryModule =
        FModuleManager::LoadModuleChecked<FAssetRegistryModule>("AssetRegistry");

    IAssetRegistry& AssetRegistry = AssetRegistryModule.Get();

    const FTopLevelAssetPath WidgetBlueprintClassPath(
        TEXT("/Script/Blutility"),
        TEXT("EditorUtilityWidgetBlueprint")
    );

    FARFilter Filter;
    Filter.PackagePaths.Add(SearchPath);
    Filter.ClassPaths.Add(WidgetBlueprintClassPath);
    Filter.bRecursivePaths = true;
    Filter.bRecursiveClasses = true;

    AssetRegistry.GetAssets(Filter, OutAssets);

    UE_LOG(LogTemp, Log, TEXT("QuickWidgetTools: Found %d Editor Utility Widget(s) under %s"),
        OutAssets.Num(),
        *SearchPath.ToString()
    );
}

void FQuickWidgetToolsModule::LaunchEditorUtilityWidget(FSoftObjectPath WidgetPath) const
{
    if (!WidgetPath.IsValid())
    {
        UE_LOG(LogTemp, Warning, TEXT("QuickWidgetTools: Invalid widget path"));
        return;
    }

    UObject* LoadedObject = WidgetPath.TryLoad();
    if (!LoadedObject)
    {
        UE_LOG(LogTemp, Error, TEXT("QuickWidgetTools: Failed to load widget asset: %s"), *WidgetPath.ToString());
        return;
    }

    UEditorUtilityWidgetBlueprint* WidgetBlueprint = Cast<UEditorUtilityWidgetBlueprint>(LoadedObject);
    if (!WidgetBlueprint)
    {
        UE_LOG(LogTemp, Error, TEXT("QuickWidgetTools: Asset is not a UEditorUtilityWidgetBlueprint: %s"), *WidgetPath.ToString());
        return;
    }

    UEditorUtilitySubsystem* EditorUtilitySubsystem = GEditor
        ? GEditor->GetEditorSubsystem<UEditorUtilitySubsystem>()
        : nullptr;

    if (!EditorUtilitySubsystem)
    {
        UE_LOG(LogTemp, Error, TEXT("QuickWidgetTools: Could not get UEditorUtilitySubsystem"));
        return;
    }

    EditorUtilitySubsystem->SpawnAndRegisterTab(WidgetBlueprint);

    UE_LOG(LogTemp, Log, TEXT("QuickWidgetTools: Launched widget %s"), *WidgetPath.ToString());
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FQuickWidgetToolsModule, QuickWidgetTools)
