#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "OnlyCloudsEditorLibrary.h"
#include "CloudGeneratorActor.h"
#include "Components/Button.h"
#include "Editor.h"
#include "Editor/Transactor.h"
#include "EditorUtilityWidget.h"
#include "Engine/Level.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Misc/App.h"
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "Subsystems/EditorActorSubsystem.h"
#include "UObject/Package.h"
#include "UObject/StrongObjectPtr.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FOnlyCloudsLowFogEditorTest,
    "OnlyClouds.LowFog.EditorActionAndWidget",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FOnlyCloudsLowFogEditorTest::RunTest(const FString& Parameters)
{
    if (FString(FApp::GetProjectName()) != TEXT("OnlyCloudsLowFogTest"))
    {
        AddInfo(TEXT("Skipped: this transaction and widget integration test requires the isolated OnlyCloudsLowFogTest project."));
        return true;
    }
    UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    UEditorActorSubsystem* Actors = GEditor ? GEditor->GetEditorSubsystem<UEditorActorSubsystem>() : nullptr;
    if (!TestTrue(TEXT("Isolated editable editor context is available"), World && Actors && GEditor->Trans &&
        World->WorldType == EWorldType::Editor && !GEditor->PlayWorld && World->GetCurrentLevel())) return false;
    if (GEditor->Trans->GetUndoCount() != 0)
    {
        AddInfo(TEXT("Skipped: the isolated editor already has redo history; it will not be discarded by this test."));
        return true;
    }
    TSet<AActor*> Baseline;
    for (TActorIterator<AActor> It(World); It; ++It)
        if (IsValid(*It) && !It->IsActorBeingDestroyed()) Baseline.Add(*It);
    const TArray<AActor*> PriorSelection = Actors->GetSelectedLevelActors();
    UPackage* LevelPackage = World->GetCurrentLevel()->GetOutermost();
    const bool bWasDirty = LevelPackage->IsDirty();
    auto NewActors = [&]()
    {
        TArray<AActor*> Added;
        for (TActorIterator<AActor> It(World); It; ++It)
            if (IsValid(*It) && !It->IsActorBeingDestroyed() && !Baseline.Contains(*It)) Added.Add(*It);
        return Added;
    };
    ON_SCOPE_EXIT
    {
        const TArray<AActor*> Added = NewActors();
        // Guide destruction first avoids retaining detached guides during failed-test cleanup.
        for (AActor* Actor : Added) if (Actor->IsA<ACloudGuideActor>()) World->EditorDestroyActor(Actor, true);
        for (AActor* Actor : Added) if (IsValid(Actor) && !Actor->IsActorBeingDestroyed()) World->EditorDestroyActor(Actor, true);
        Actors->SetSelectedLevelActors(PriorSelection);
        LevelPackage->SetDirtyFlag(bWasDirty);
    };
    auto VerifyFog = [&](const TCHAR* Context)
    {
        const TArray<AActor*> Added = NewActors();
        if (!TestEqual(FString(Context) + TEXT(": exactly fog and one guide added"), Added.Num(), 2)) return false;
        ALowFogGeneratorActor* Fog = nullptr;
        for (AActor* Actor : Added) if (ALowFogGeneratorActor* Candidate = Cast<ALowFogGeneratorActor>(Actor)) Fog = Candidate;
        if (!TestNotNull(FString(Context) + TEXT(": low-fog actor exists"), Fog)) return false;
        if (!TestEqual(FString(Context) + TEXT(": one initialized recipe guide"), Fog->Guides.Num(), 1)) return false;
        ACloudGuideActor* Guide = Fog->Guides[0];
        TestTrue(FString(Context) + TEXT(": guide ownership and attachment restored"),
            IsValid(Guide) && Guide->Generator == Fog && Guide->GetAttachParentActor() == Fog && Added.Contains(Guide));
        TestTrue(FString(Context) + TEXT(": saved cylinder shape loaded"), IsValid(Guide) && Guide->Shape == ECloudGuideShape::Cylinder);
        TestTrue(FString(Context) + TEXT(": ground-fog recipe loaded"), Fog->bGroundFog && IsValid(Fog->Preset));
        TestEqual(FString(Context) + TEXT(": dedicated fog material loaded"), Fog->CloudMaterial.ToSoftObjectPath().ToString(),
            FString(TEXT("/QuickWidgetTools/OnlyClouds/LowFog/Materials/M_LowFogVolume.M_LowFogVolume")));
        return !HasAnyErrors();
    };
    auto VerifyUndoRedo = [&](const FGuid& ActionId, const TCHAR* Context)
    {
        if (!TestTrue(FString(Context) + TEXT(": latest transaction belongs to this action"),
            ActionId.IsValid() && GEditor->Trans->GetUndoContext().TransactionId == ActionId)) return false;
        if (!TestTrue(FString(Context) + TEXT(": Undo succeeds"), UOnlyCloudsEditorLibrary::UndoLastEditorTransaction())) return false;
        if (!TestEqual(FString(Context) + TEXT(": one Undo removes fog and guide"), NewActors().Num(), 0)) return false;
        if (!TestTrue(FString(Context) + TEXT(": Redo targets this action"), GEditor->Trans->GetRedoContext().TransactionId == ActionId)) return false;
        if (!TestTrue(FString(Context) + TEXT(": Redo succeeds"), UOnlyCloudsEditorLibrary::RedoLastEditorTransaction())) return false;
        if (!VerifyFog(Context)) return false;
        if (!TestTrue(FString(Context) + TEXT(": cleanup Undo still targets this action"),
            GEditor->Trans->GetUndoContext().TransactionId == ActionId)) return false;
        if (!TestTrue(FString(Context) + TEXT(": cleanup Undo succeeds"), UOnlyCloudsEditorLibrary::UndoLastEditorTransaction())) return false;
        return TestEqual(FString(Context) + TEXT(": baseline restored"), NewActors().Num(), 0);
    };

    const FGuid PreviousId = GEditor->Trans->GetUndoContext(false).TransactionId;
    const FOnlyCloudsEditorActionResult Result = UOnlyCloudsEditorLibrary::AddLowFogPreset();
    if (!TestTrue(TEXT("Native Add Low Fog Preset succeeds"), Result.bSuccess && Result.bCreated))
    {
        AddError(Result.Message);
        return false;
    }
    TestEqual(TEXT("Native action returns its new generator"), Result.Actors.Num(), 1);
    const FGuid NativeId = GEditor->Trans->GetUndoContext().TransactionId;
    if (!TestTrue(TEXT("Native action creates a new transaction"), NativeId != PreviousId) ||
        !VerifyFog(TEXT("Native action")) || !VerifyUndoRedo(NativeId, TEXT("Native action"))) return false;

    UClass* WidgetClass = LoadClass<UEditorUtilityWidget>(nullptr,
        TEXT("/QuickWidgetTools/EditorWidgets/WBP_08_FX_Tools.WBP_08_FX_Tools_C"));
    if (!TestNotNull(TEXT("Actual FX Tools widget class loads"), WidgetClass)) return false;
    TStrongObjectPtr<UEditorUtilityWidget> Widget(CreateWidget<UEditorUtilityWidget>(World, WidgetClass));
    if (!TestNotNull(TEXT("Actual FX Tools widget instance initializes without a window"), Widget.Get())) return false;
    UButton* Button = Cast<UButton>(Widget->GetWidgetFromName(TEXT("Add_LowFog_Preset_Button")));
    if (!TestNotNull(TEXT("Actual Low Fog button exists"), Button) ||
        !TestTrue(TEXT("Actual Low Fog button has its Blueprint OnClicked binding"), Button->OnClicked.IsBound())) return false;
    Button->OnClicked.Broadcast();
    const FGuid WidgetId = GEditor->Trans->GetUndoContext().TransactionId;
    if (!TestTrue(TEXT("Actual widget click creates its own transaction"), WidgetId.IsValid() && WidgetId != NativeId) ||
        !VerifyFog(TEXT("Widget click")) || !VerifyUndoRedo(WidgetId, TEXT("Widget click"))) return false;
    AddInfo(TEXT("Verified native action result, actual Blueprint button click, and complete single-action Undo/Redo for both."));
    return !HasAnyErrors();
}

#endif
