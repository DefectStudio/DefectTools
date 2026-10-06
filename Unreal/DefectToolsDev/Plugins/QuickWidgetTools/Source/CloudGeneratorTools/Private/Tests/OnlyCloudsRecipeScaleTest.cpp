#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "CloudGeneratorActor.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "Serialization/MemoryReader.h"
#include "Serialization/MemoryWriter.h"
#include "Serialization/ObjectAndNameAsStringProxyArchive.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FOnlyCloudsRecipeScaleTest,
    "OnlyClouds.PlacedClouds.RecipeScalePersistence",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FOnlyCloudsRecipeScaleTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::Editor, false, TEXT("OnlyCloudsRecipeScaleTest"));
    if (!TestNotNull(TEXT("Isolated test world"), World)) return false;
    ON_SCOPE_EXIT { World->DestroyWorld(false); };
    ACloudGeneratorActor* Source = World->SpawnActor<ACloudGeneratorActor>();
    ACloudGeneratorActor* FreshTarget = World->SpawnActor<ACloudGeneratorActor>();
    ACloudGeneratorActor* ExistingTarget = World->SpawnActor<ACloudGeneratorActor>();
    if (!TestTrue(TEXT("Test generators spawned"), Source && FreshTarget && ExistingTarget)) return false;

    const FVector AuthoredScale(1.0, 1.552108, 1.0);
    Source->SetActorLocation(FVector(400.0, 800.0, -100.0));
    Source->SetActorScale3D(AuthoredScale);
    FCloudRecipe LegacyRecipe;
    TestEqual(TEXT("Unversioned legacy struct still defaults to v1"), LegacyRecipe.Version, 1);
    LegacyRecipe.CloudMaterial = Source->CloudMaterial;
    LegacyRecipe.BillowSizeCm = 314.0f;
    LegacyRecipe.TextureOffsetCm = FVector(25.0, -43.0, 90.0);
    FCloudGuideRecipe& Guide = LegacyRecipe.Guides.AddDefaulted_GetRef();
    Guide.LocalTransform = FTransform(FRotator(17.0, 23.0, 5.0), FVector(120.0, 260.0, 350.0), FVector(2.0, 3.0, 4.0));
    if (!TestTrue(TEXT("Legacy recipe loads on authored source scale"), Source->ApplyRecipe(LegacyRecipe))) return false;
    TestTrue(TEXT("Legacy load preserves authored scale"), Source->GetActorScale3D().Equals(AuthoredScale));
    const FCloudRecipe Captured = Source->CaptureRecipe();
    TestEqual(TEXT("New capture uses recipe v2"), Captured.Version, 2);
    TestTrue(TEXT("New capture includes nonuniform scale"), Captured.GeneratorScale.Equals(AuthoredScale));

    // Round-trip the actual reflected preset data without creating project files.
    UCloudRecipePreset* SavedPreset = NewObject<UCloudRecipePreset>();
    SavedPreset->Recipe = Captured;
    TArray<uint8> Bytes;
    {
        FMemoryWriter Writer(Bytes, true);
        FObjectAndNameAsStringProxyArchive Archive(Writer, false);
        SavedPreset->Serialize(Archive);
    }
    UCloudRecipePreset* ReloadedPreset = NewObject<UCloudRecipePreset>();
    {
        FMemoryReader Reader(Bytes, true);
        FObjectAndNameAsStringProxyArchive Archive(Reader, true);
        ReloadedPreset->Serialize(Archive);
        if (!TestFalse(TEXT("Preset serialization reload succeeds"), Archive.IsError())) return false;
    }
    const FCloudRecipe& Reloaded = ReloadedPreset->Recipe;
    TestEqual(TEXT("Preset reload preserves v2"), Reloaded.Version, 2);
    TestTrue(TEXT("Preset reload preserves nonuniform scale"), Reloaded.GeneratorScale.Equals(AuthoredScale));
    TestEqual(TEXT("Preset reload preserves guides"), Reloaded.Guides.Num(), Captured.Guides.Num());

    const FVector FreshLocation(3000.0, -200.0, 600.0);
    FreshTarget->SetActorLocation(FreshLocation);
    if (!TestTrue(TEXT("Saved recipe loads onto a fresh unit-scale target"), FreshTarget->ApplyRecipe(Reloaded))) return false;
    TestTrue(TEXT("Fresh target restores authored scale"), FreshTarget->GetActorScale3D().Equals(AuthoredScale));
    TestTrue(TEXT("Fresh target keeps its placement"), FreshTarget->GetActorLocation().Equals(FreshLocation));
    TestTrue(TEXT("Fresh guide matches authored world size"), FreshTarget->Guides[0]->GetActorScale3D().Equals(Source->Guides[0]->GetActorScale3D(), 0.0001));
    TestTrue(TEXT("Fresh guide matches authored offset"),
        (FreshTarget->Guides[0]->GetActorLocation() - FreshTarget->GetActorLocation()).Equals(
         Source->Guides[0]->GetActorLocation() - Source->GetActorLocation(), 0.0001));
    TestEqual(TEXT("World-space billow size is unchanged"), FreshTarget->BillowSizeCm, LegacyRecipe.BillowSizeCm);
    TestTrue(TEXT("World-space animation offset is unchanged"), FreshTarget->TextureOffsetCm.Equals(LegacyRecipe.TextureOffsetCm));

    ExistingTarget->SetActorTransform(FTransform(FRotator(3.0, 46.0, 11.0), FVector(-900.0, 450.0, 10.0), FVector(4.0, 0.5, 2.5)));
    const FVector ExistingLocation = ExistingTarget->GetActorLocation();
    const FQuat ExistingRotation = ExistingTarget->GetActorQuat();
    if (!TestTrue(TEXT("Saved recipe loads onto an already-scaled target"), ExistingTarget->ApplyRecipe(Reloaded))) return false;
    TestTrue(TEXT("Existing target replaces scale rather than multiplying it"), ExistingTarget->GetActorScale3D().Equals(AuthoredScale));
    TestTrue(TEXT("Existing target preserves location"), ExistingTarget->GetActorLocation().Equals(ExistingLocation));
    TestTrue(TEXT("Existing target preserves rotation"), ExistingTarget->GetActorQuat().Equals(ExistingRotation));
    const FTransform ExpectedGuide = Reloaded.Guides[0].LocalTransform * ExistingTarget->GetActorTransform();
    TestTrue(TEXT("Existing target reconstructs the authored guide at its placement"), ExistingTarget->Guides[0]->GetActorTransform().Equals(ExpectedGuide, 0.0001));

    FCloudRecipe Invalid = Reloaded;
    Invalid.GeneratorScale.Y = 0.0;
    const TArray<TObjectPtr<ACloudGuideActor>> PriorGuides = ExistingTarget->Guides;
    TestFalse(TEXT("Invalid v2 scale is rejected"), ExistingTarget->ApplyRecipe(Invalid));
    TestTrue(TEXT("Rejected scale preserves prior generator scale"), ExistingTarget->GetActorScale3D().Equals(AuthoredScale));
    TestTrue(TEXT("Rejected scale preserves prior guides"), ExistingTarget->Guides == PriorGuides);

    const FVector LegacyTargetScale(2.0, 0.75, 3.0);
    ExistingTarget->SetActorScale3D(LegacyTargetScale);
    TestTrue(TEXT("Legacy v1 recipe remains loadable"), ExistingTarget->ApplyRecipe(LegacyRecipe));
    TestTrue(TEXT("Legacy v1 load leaves target scale unchanged"), ExistingTarget->GetActorScale3D().Equals(LegacyTargetScale));
    return !HasAnyErrors();
}

#endif
