#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "CloudGeneratorActor.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"

// Run in a regular editor; owns an isolated world and never changes a user map.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FOnlyCloudsPresetPlacementTest,
    "OnlyClouds.PlacedClouds.PresetFirstPlacement",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FOnlyCloudsPresetPlacementTest::RunTest(const FString& Parameters)
{
    if (IsRunningCommandlet())
    {
        AddError(TEXT("First-placement initialization deliberately skips commandlets. Run this in a regular editor."));
        return false;
    }
    UWorld* World = UWorld::CreateWorld(EWorldType::Editor, false, TEXT("OnlyCloudsPresetPlacementTest"));
    if (!TestNotNull(TEXT("Isolated test world"), World)) return false;
    ON_SCOPE_EXIT { World->DestroyWorld(false); };

    UClass* CloudClass = LoadClass<ACloudGeneratorActor>(nullptr,
        TEXT("/QuickWidgetTools/OnlyClouds/PlacedClouds/BP_CloudPreset.BP_CloudPreset_C"));
    if (!TestNotNull(TEXT("Portable placed-cloud Blueprint"), CloudClass)) return false;
    ACloudGeneratorActor* Actor = World->SpawnActor<ACloudGeneratorActor>(CloudClass);
    if (!TestNotNull(TEXT("Fresh placed cloud"), Actor)) return false;
    TestTrue(TEXT("New Blueprint opts into automatic preset placement"), Actor->bUseDefaultPresetOnFirstPlacement);
    if (!TestNotNull(TEXT("Default preset"), Actor->Preset.Get())) return false;
    if (!TestTrue(TEXT("Default preset has guides"), !Actor->Preset->Recipe.Guides.IsEmpty())) return false;
    TestEqual(TEXT("Fresh actor immediately contains the preset guides"), Actor->Guides.Num(), Actor->Preset->Recipe.Guides.Num());
    TestEqual(TEXT("Fresh actor receives preset density"), Actor->Density, Actor->Preset->Recipe.Density);
    TestTrue(TEXT("Fresh actor receives preset material"), Actor->CloudMaterial == Actor->Preset->Recipe.CloudMaterial);
    TestEqual(TEXT("User presets default to project content"), Actor->PresetSaveDirectory, FString(TEXT("/Game/OnlyClouds/Presets")));
    if (!TestTrue(TEXT("Fresh actor has an editable guide"), !Actor->Guides.IsEmpty() && IsValid(Actor->Guides[0]))) return false;

    // Construction reruns are common during editing; they must preserve authored changes.
    const float EditedDensity = Actor->Density + 0.75f;
    Actor->Density = EditedDensity;
    const TArray<TObjectPtr<ACloudGuideActor>> OriginalGuides = Actor->Guides;
    ACloudGuideActor* FirstGuide = Actor->Guides[0];
    const FVector EditedLocation = FirstGuide->GetActorLocation() + FVector(137.0, -29.0, 53.0);
    FirstGuide->SetActorLocation(EditedLocation);
    Actor->RerunConstructionScripts();
    TestEqual(TEXT("Construction preserves edited density"), Actor->Density, EditedDensity);
    TestTrue(TEXT("Construction preserves guide identities and count"), Actor->Guides == OriginalGuides);
    TestTrue(TEXT("Construction preserves moved guide"), FirstGuide->GetActorLocation().Equals(EditedLocation));

    for (ACloudGuideActor* Guide : OriginalGuides)
    {
        if (IsValid(Guide)) World->DestroyActor(Guide);
    }
    Actor->RerunConstructionScripts();
    TestTrue(TEXT("Removing all guides does not reapply the initial preset"), Actor->Guides.IsEmpty());
    TestEqual(TEXT("Empty authored cloud retains its edited density"), Actor->Density, EditedDensity);

    // Enabling a default on an existing instance cannot arm the creation-only hook.
    ACloudGeneratorActor* Existing = World->SpawnActor<ACloudGeneratorActor>();
    if (!TestNotNull(TEXT("Native actor without opt-in"), Existing)) return false;
    TestFalse(TEXT("Existing native class does not opt in"), Existing->bUseDefaultPresetOnFirstPlacement);
    Existing->Preset = Actor->Preset;
    Existing->bUseDefaultPresetOnFirstPlacement = true;
    Existing->RerunConstructionScripts();
    TestTrue(TEXT("Reconstruction alone never applies a preset"), Existing->Guides.IsEmpty());

    FActorSpawnParameters PreviewParameters;
    PreviewParameters.ObjectFlags |= RF_Transient;
    ACloudGeneratorActor* Preview = World->SpawnActor<ACloudGeneratorActor>(CloudClass, FTransform::Identity, PreviewParameters);
    if (!TestNotNull(TEXT("Transient asset preview"), Preview)) return false;
    TestTrue(TEXT("Transient previews do not create persistent guides"), Preview->Guides.IsEmpty());

    Actor->PresetSaveDirectory = TEXT("/QuickWidgetTools/OnlyClouds/PlacedClouds/Presets");
    Actor->SavePreset();
    TestTrue(TEXT("Save Preset refuses plugin content"), Actor->WorkflowStatus.StartsWith(TEXT("Preset Save Folder must be a valid project Content path")));
    return !HasAnyErrors();
}

#endif
