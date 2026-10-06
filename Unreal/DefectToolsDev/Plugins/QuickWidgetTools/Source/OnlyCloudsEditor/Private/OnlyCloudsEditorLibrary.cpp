#include "OnlyCloudsEditorLibrary.h"
#include "OnlyCloudsEditorInternal.h"
#include "OnlyCloudsEditorQualityUndo.h"

#include "CloudGeneratorActor.h"
#include "Editor.h"
#include "Misc/App.h"
#include "EngineUtils.h"
#include "LevelUtils.h"
#include "ScopedTransaction.h"
#include "Subsystems/EditorActorSubsystem.h"
#include "Engine/World.h"
#include "Engine/Level.h"
#include "Engine/DirectionalLight.h"
#include "Engine/SkyLight.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/PostProcessVolume.h"
#include "Components/VolumetricCloudComponent.h"
#include "UObject/StrongObjectPtr.h"
#include "ToolMenus.h"
#include "Framework/Commands/UIAction.h"
#include "Framework/Application/SlateApplication.h"
#include "Framework/Notifications/NotificationManager.h"
#include "Widgets/Notifications/SNotificationList.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

#define LOCTEXT_NAMESPACE "OnlyCloudsEditor"
DEFINE_LOG_CATEGORY_STATIC(LogOnlyCloudsEditor, Log, All);

namespace OnlyCloudsEditor
{
    static constexpr const TCHAR* RigWorldPath = TEXT("/QuickWidgetTools/OnlyClouds/Templates/LVL_BasicLiteRigg.LVL_BasicLiteRigg");
    static constexpr const TCHAR* WorldCloudClassPath = TEXT("/QuickWidgetTools/OnlyClouds/WorldClouds/BP_UDSOnlyClouds.BP_UDSOnlyClouds_C");
    static constexpr const TCHAR* PresetCloudClassPath = TEXT("/QuickWidgetTools/OnlyClouds/PlacedClouds/BP_CloudPreset.BP_CloudPreset_C");
    static constexpr const TCHAR* CumulusPath = TEXT("/QuickWidgetTools/OnlyClouds/PlacedClouds/Presets/CP_Cumulus.CP_Cumulus");

    // Stored only during synchronous dispatch of an actual registered menu delegate.
    static FOnlyCloudsEditorActionResult LastActionResult;
    static TArray<TWeakObjectPtr<AActor>> LastActionActors;

    static FOnlyCloudsEditorActionResult Fail(FString Message)
    {
        FOnlyCloudsEditorActionResult Result;
        Result.Message = MoveTemp(Message);
        return Result;
    }

    static FToolMenuEntry* FindMenuEntry(UToolMenu* Menu, FName Name)
    {
        if (Menu)
            for (FToolMenuSection& Section : Menu->Sections)
                if (FToolMenuEntry* Entry = Section.FindEntry(Name)) return Entry;
        return nullptr;
    }

    static bool GetDestination(UWorld*& World, ULevel*& Level, UEditorActorSubsystem*& Actors, FString& Error)
    {
        World = nullptr; Level = nullptr; Actors = nullptr;
        if (!GEditor || GEditor->PlayWorld || GEditor->bIsSimulatingInEditor)
        {
            Error = TEXT("Stop Play or Simulate before adding cloud tools to the editor level.");
            return false;
        }
        World = GEditor->GetEditorWorldContext().World();
        if (!IsValid(World) || World->WorldType != EWorldType::Editor)
        {
            Error = TEXT("Open an editable level before using OnlyClouds.");
            return false;
        }
        Level = World->GetCurrentLevel();
        if (!IsValid(Level) || FLevelUtils::IsLevelLocked(Level))
        {
            Error = TEXT("The current level is unavailable or locked.");
            return false;
        }
        Actors = GEditor->GetEditorSubsystem<UEditorActorSubsystem>();
        if (!Actors)
        {
            Error = TEXT("The editor actor subsystem is unavailable.");
            return false;
        }
        return true;
    }

    bool CanUseEditorWorld()
    {
        UWorld* World; ULevel* Level; UEditorActorSubsystem* Actors; FString Error;
        return GetDestination(World, Level, Actors, Error);
    }

    static void Select(UEditorActorSubsystem* Subsystem, const TArray<AActor*>& Actors)
    {
        Subsystem->SetSelectedLevelActors(Actors);
        GEditor->RedrawLevelEditingViewports();
    }

    static bool IsRigActor(const AActor* Actor)
    {
        return Actor && (Actor->IsA<ADirectionalLight>() || Actor->IsA<ASkyLight>()
            || Actor->IsA<ASkyAtmosphere>() || Actor->IsA<AExponentialHeightFog>()
            || Actor->IsA<AStaticMeshActor>() || Actor->IsA<APostProcessVolume>());
    }

    static AActor* FindVisibleWorldCloud(UWorld* World)
    {
        for (TActorIterator<AActor> It(World); It; ++It)
        {
            AActor* Actor = *It;
            if (!IsValid(Actor) || Actor->IsActorBeingDestroyed() || Actor->IsHiddenEd()) continue;
            TInlineComponentArray<UVolumetricCloudComponent*> Components;
            Actor->GetComponents(Components);
            for (UVolumetricCloudComponent* Component : Components)
            {
                if (IsValid(Component) && Component->GetVisibleFlag()) return Actor;
            }
        }
        return nullptr;
    }

    static void ReportResult(const FOnlyCloudsEditorActionResult& Result)
    {
        if (Result.bSuccess) { UE_LOG(LogOnlyCloudsEditor, Display, TEXT("%s"), *Result.Message); }
        else { UE_LOG(LogOnlyCloudsEditor, Warning, TEXT("%s"), *Result.Message); }
        if (!FApp::IsUnattended() && FSlateApplication::IsInitialized())
        {
            FNotificationInfo Info(FText::FromString(Result.Message));
            Info.ExpireDuration = Result.bSuccess ? 4.0f : 7.0f;
            Info.bFireAndForget = true;
            FSlateNotificationManager::Get().AddNotification(Info);
        }
    }

    void RunRegisteredAction(FName Name)
    {
        if (Name == TEXT("AddBasicLightRigg")) LastActionResult = UOnlyCloudsEditorLibrary::AddBasicLightRigg();
        else if (Name == TEXT("AddLayeredWorldClouds")) LastActionResult = UOnlyCloudsEditorLibrary::AddLayeredWorldClouds();
        else if (Name == TEXT("AddCloudPreset")) LastActionResult = UOnlyCloudsEditorLibrary::AddCloudPreset();
        else LastActionResult = Fail(TEXT("Unknown OnlyClouds toolbar action."));
        UOnlyCloudsEditorLibrary::ReportActionResult(LastActionResult);
        // A normal action invocation has no result reader. Do not retain world objects
        // in a module-global result after the action or across a later map change.
        LastActionActors.Reset();
        for (AActor* Actor : LastActionResult.Actors) LastActionActors.Add(Actor);
        LastActionResult.Actors.Reset();
    }

    FOnlyCloudsEditorActionResult TakeLastActionResult()
    {
        FOnlyCloudsEditorActionResult Result = MoveTemp(LastActionResult);
        for (const TWeakObjectPtr<AActor>& Actor : LastActionActors) if (Actor.IsValid()) Result.Actors.Add(Actor.Get());
        LastActionActors.Reset();
        LastActionResult = FOnlyCloudsEditorActionResult();
        return Result;
    }

    void ResetLastActionResult()
    {
        LastActionResult = Fail(TEXT("The menu delegate did not produce an action result."));
        LastActionActors.Reset();
    }
}

FOnlyCloudsEditorActionResult UOnlyCloudsEditorLibrary::AddBasicLightRigg()
{
    using namespace OnlyCloudsEditor;
    UWorld* World; ULevel* Level; UEditorActorSubsystem* Actors; FString Error;
    if (!GetDestination(World, Level, Actors, Error)) return Fail(Error);

    // Load only the saved template asset. Never replace the active editor world or add a world context.
    TStrongObjectPtr<UWorld> TemplateWorld(LoadObject<UWorld>(nullptr, RigWorldPath));
    if (!TemplateWorld.IsValid() || !TemplateWorld->PersistentLevel || TemplateWorld.Get() == World)
        return Fail(TEXT("The saved BasicLiteRigg template map is missing or invalid."));

    TArray<AActor*> Templates;
    for (AActor* Actor : TemplateWorld->PersistentLevel->Actors)
        if (IsValid(Actor) && IsRigActor(Actor)) Templates.Add(Actor);

    const UClass* ExpectedClasses[] = { ADirectionalLight::StaticClass(), ASkyLight::StaticClass(),
        ASkyAtmosphere::StaticClass(), AExponentialHeightFog::StaticClass(), AStaticMeshActor::StaticClass(), APostProcessVolume::StaticClass() };
    if (Templates.Num() != 6)
        return Fail(FString::Printf(TEXT("BasicLiteRigg must contain exactly six rig actors; found %d."), Templates.Num()));
    for (const UClass* Class : ExpectedClasses)
        if (Templates.FilterByPredicate([Class](AActor* Actor) { return Actor->IsA(Class); }).Num() != 1)
            return Fail(TEXT("BasicLiteRigg needs one directional light, skylight, atmosphere, height fog, environment dome, and post-process volume."));

    const TArray<AActor*> PreviousSelection = Actors->GetSelectedLevelActors();
    FScopedTransaction Transaction(LOCTEXT("AddBasicLightRigTransaction", "OnlyClouds: Add Basic Light Rigg"));
    World->Modify(); Level->Modify();
    UEditorActorSubsystem::FActorDuplicateParameters DuplicateParameters;
    DuplicateParameters.LevelOverride = Level;
    DuplicateParameters.bTransact = false;
    // One batch is crucial: Unreal's native duplicate path remaps intra-rig actor and component references.
    TArray<AActor*> Copies = Actors->DuplicateActors(Templates, World, FVector::ZeroVector, DuplicateParameters);
    if (Copies.Num() != Templates.Num() || Copies.Contains(nullptr))
    {
        for (AActor* Copy : Copies) if (IsValid(Copy)) World->EditorDestroyActor(Copy, true);
        Transaction.Cancel();
        Select(Actors, PreviousSelection);
        return Fail(TEXT("Unreal could not copy the complete lighting rig. The incomplete copies were removed."));
    }

    FOnlyCloudsEditorActionResult Result;
    Result.bSuccess = true; Result.bCreated = true;
    for (AActor* Copy : Copies)
    {
        Copy->SetFlags(RF_Transactional);
        Copy->Modify();
        Copy->SetFolderPath(TEXT("BasicLiteRigg"));
        Copy->MarkPackageDirty();
        Result.Actors.Add(Copy);
    }
    Level->MarkPackageDirty();
    Select(Actors, Copies);
    Result.Message = TEXT("Added the six saved lighting actors to BasicLiteRigg. Undo removes the complete rig.");
    return Result;
}

FOnlyCloudsEditorActionResult UOnlyCloudsEditorLibrary::AddLayeredWorldClouds()
{
    using namespace OnlyCloudsEditor;
    UWorld* World; ULevel* Level; UEditorActorSubsystem* Actors; FString Error;
    if (!GetDestination(World, Level, Actors, Error)) return Fail(Error);
    UClass* Class = LoadClass<AActor>(nullptr, WorldCloudClassPath);
    if (!Class) return Fail(TEXT("The plugin BP_UDSOnlyClouds asset could not be loaded."));

    // A hidden or temporarily unready controller can still own its private MPC.
    // Reuse it before considering visible renderers of any other actor class.
    for (TActorIterator<AActor> It(World, Class); It; ++It)
    {
        AActor* Existing = *It;
        if (!IsValid(Existing) || Existing->IsActorBeingDestroyed()) continue;
        FOnlyCloudsEditorActionResult Result;
        Result.bSuccess = true;
        Result.Actors.Add(Existing);
        Result.Message = Existing->IsHiddenEd()
            ? TEXT("Selected the existing hidden BP_UDSOnlyClouds. Unhide that actor to see its clouds; no duplicate was added.")
            : TEXT("Selected the existing BP_UDSOnlyClouds. Add cloud layers on that actor.");
        Select(Actors, {Existing});
        return Result;
    }

    if (AActor* Existing = FindVisibleWorldCloud(World))
    {
        FOnlyCloudsEditorActionResult Result;
        Result.bSuccess = Existing->IsA(Class);
        Result.Actors.Add(Existing);
        Result.Message = Result.bSuccess
            ? TEXT("Selected the existing BP_UDSOnlyClouds. Add cloud layers on that actor.")
            : FString::Printf(TEXT("%s already renders world clouds. Selected it; no second cloud renderer was added."), *Existing->GetActorLabel());
        Select(Actors, {Existing});
        return Result;
    }

    FScopedTransaction Transaction(LOCTEXT("AddWorldCloudsTransaction", "OnlyClouds: Add Layered World Clouds"));
    World->Modify(); Level->Modify();
    const FCloudQualitySnapshot BeforeCreation = CaptureCloudQuality();
    AActor* Cloud = Actors->SpawnActorFromClass(Class, FVector::ZeroVector, FRotator::ZeroRotator, false);
    if (!IsValid(Cloud)) { Transaction.Cancel(); return Fail(TEXT("Unreal could not spawn BP_UDSOnlyClouds.")); }
    Cloud->SetFlags(RF_Transactional); Cloud->Modify(); Cloud->SetActorLabel(TEXT("BP_UDSOnlyClouds"));
    Cloud->MarkPackageDirty();
    TrackCreatedWorldCloud(Cloud, BeforeCreation);
    Select(Actors, {Cloud});
    FOnlyCloudsEditorActionResult Result;
    Result.bSuccess = true; Result.bCreated = true; Result.Actors.Add(Cloud);
    Result.Message = TEXT("Added BP_UDSOnlyClouds at the world origin. Its cloud layers are ready to edit.");
    return Result;
}

FOnlyCloudsEditorActionResult UOnlyCloudsEditorLibrary::AddCloudPreset()
{
    using namespace OnlyCloudsEditor;
    UWorld* World; ULevel* Level; UEditorActorSubsystem* Actors; FString Error;
    if (!GetDestination(World, Level, Actors, Error)) return Fail(Error);
    UClass* Class = LoadClass<ACloudGeneratorActor>(nullptr, PresetCloudClassPath);
    UCloudRecipePreset* Preset = LoadObject<UCloudRecipePreset>(nullptr, CumulusPath);
    if (!Class || !Preset || Preset->Recipe.Guides.IsEmpty())
        return Fail(TEXT("BP_CloudPreset or its saved Cumulus recipe could not be loaded."));
    const ACloudGeneratorActor* Defaults = Class->GetDefaultObject<ACloudGeneratorActor>();
    if (!Defaults || Defaults->Preset != Preset || !Defaults->bUseDefaultPresetOnFirstPlacement)
        return Fail(TEXT("BP_CloudPreset is missing its first-placement Cumulus configuration."));

    const TArray<AActor*> PreviousSelection = Actors->GetSelectedLevelActors();
    FScopedTransaction Transaction(LOCTEXT("AddCloudPresetTransaction", "OnlyClouds: Add Cloud Preset"));
    World->Modify(); Level->Modify();
    ACloudGeneratorActor* Cloud = Cast<ACloudGeneratorActor>(Actors->SpawnActorFromClass(Class, FVector::ZeroVector, FRotator::ZeroRotator, false));
    if (!IsValid(Cloud)) { Transaction.Cancel(); return Fail(TEXT("Unreal could not spawn BP_CloudPreset.")); }
    // Its native one-shot OnConstruction initializer applies the recipe synchronously.
    // Never apply again: that would replace the just-created guides and create redundant undo work.
    if (Cloud->Guides.Num() != Preset->Recipe.Guides.Num())
    {
        World->EditorDestroyActor(Cloud, true);
        Transaction.Cancel(); Select(Actors, PreviousSelection);
        return Fail(TEXT("The Cumulus preset did not initialize completely. The incomplete cloud was removed."));
    }
    Cloud->SetFlags(RF_Transactional); Cloud->Modify(); Cloud->SetActorLabel(TEXT("BP_CloudPreset"));
    Cloud->MarkPackageDirty();
    Select(Actors, {Cloud});
    FOnlyCloudsEditorActionResult Result;
    Result.bSuccess = true; Result.bCreated = true; Result.Actors.Add(Cloud);
    Result.Message = TEXT("Added BP_CloudPreset with the saved Cumulus cloud and editable guides.");
    return Result;
}

void UOnlyCloudsEditorLibrary::ReportActionResult(const FOnlyCloudsEditorActionResult& Result)
{
    OnlyCloudsEditor::ReportResult(Result);
}

FOnlyCloudsEditorActionResult UOnlyCloudsEditorLibrary::ExecuteRegisteredMenuAction(FName EntryName)
{
    using namespace OnlyCloudsEditor;
    UToolMenu* Menu = UToolMenus::Get()->FindMenu(MenuName);
    FToolMenuEntry* Entry = FindMenuEntry(Menu, EntryName);
    if (!Entry) return Fail(TEXT("The requested OnlyClouds menu entry is not registered."));
    ResetLastActionResult();
    // The public ToolMenus API checks the stored delegate and its CanExecute
    // condition, then invokes that exact menu action with this context.
    if (!Entry->TryExecuteToolUIAction(FToolMenuContext()))
        return Fail(TEXT("The OnlyClouds menu action is unavailable in the current editor state."));
    return TakeLastActionResult();
}

FString UOnlyCloudsEditorLibrary::DescribeRegisteredMenu()
{
    using namespace OnlyCloudsEditor;
    TSharedRef<FJsonObject> Data = MakeShared<FJsonObject>();
    UToolMenu* Toolbar = UToolMenus::Get()->FindMenu(ToolbarName);
    UToolMenu* Menu = UToolMenus::Get()->FindMenu(MenuName);
    FToolMenuSection* Section = Toolbar ? Toolbar->FindSection(SectionName) : nullptr;
    FToolMenuEntry* Button = FindMenuEntry(Toolbar, ToolbarEntryName);
    Data->SetStringField(TEXT("toolbar"), ToolbarName.ToString());
    Data->SetStringField(TEXT("section"), SectionName.ToString());
    Data->SetStringField(TEXT("menu"), MenuName.ToString());
    Data->SetBoolField(TEXT("registered"), Menu != nullptr);
    Data->SetBoolField(TEXT("viewport_toolbar_registered"), Button != nullptr && Section != nullptr);
    Data->SetStringField(TEXT("widget"), TEXT("/QuickWidgetTools/EditorWidgets/WBP_08_FX_Tools.WBP_08_FX_Tools"));
    Data->SetStringField(TEXT("toolbar_label"), Button ? Button->Label.Get().ToString() : TEXT(""));
    Data->SetStringField(TEXT("insert_after"), Section ? Section->InsertPosition.Name.ToString() : TEXT(""));
    Data->SetBoolField(TEXT("works_without_uds"), Menu != nullptr);
    TArray<TSharedPtr<FJsonValue>> Entries;
    for (FName Name : { FName(TEXT("AddBasicLightRigg")), FName(TEXT("AddLayeredWorldClouds")), FName(TEXT("AddCloudPreset")) })
    {
        TSharedRef<FJsonObject> Info = MakeShared<FJsonObject>();
        const FToolMenuEntry* Entry = FindMenuEntry(Menu, Name);
        Info->SetStringField(TEXT("name"), Name.ToString());
        Info->SetBoolField(TEXT("registered"), Entry != nullptr);
        Info->SetStringField(TEXT("label"), Entry ? Entry->Label.Get().ToString() : TEXT(""));
        Info->SetStringField(TEXT("dispatch_method"), TEXT("FToolMenuEntry::TryExecuteToolUIAction"));
        Entries.Add(MakeShared<FJsonValueObject>(Info));
    }
    Data->SetArrayField(TEXT("entries"), Entries);
    FString Json; FJsonSerializer::Serialize(Data, TJsonWriterFactory<>::Create(&Json)); return Json;
}

bool UOnlyCloudsEditorLibrary::UndoLastEditorTransaction()
{
    return GEditor && !GEditor->PlayWorld && GEditor->UndoTransaction();
}

bool UOnlyCloudsEditorLibrary::RedoLastEditorTransaction()
{
    return GEditor && !GEditor->PlayWorld && GEditor->RedoTransaction();
}

#undef LOCTEXT_NAMESPACE
