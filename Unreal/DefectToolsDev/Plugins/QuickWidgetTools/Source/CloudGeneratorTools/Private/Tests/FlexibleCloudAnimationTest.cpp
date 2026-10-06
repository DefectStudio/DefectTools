#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "CloudGeneratorActor.h"
#include "Components/HeterogeneousVolumeComponent.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"

// Run in a regular editor (NullRHI is supported), not a Python commandlet.
// This creates an isolated world and never opens, selects or edits a user map.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFlexibleCloudAnimationTest,
    "CloudGenerator.FlexibleGuides.Animation.StateAndMaterial",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FFlexibleCloudAnimationTest::RunTest(const FString& Parameters)
{
    if (IsRunningCommandlet())
    {
        AddError(TEXT("This test needs a regular editor world because animation is intentionally disabled in commandlets."));
        return false;
    }
    UWorld* World = UWorld::CreateWorld(EWorldType::Editor, false, TEXT("FlexibleCloudAnimationTest"));
    if (!TestNotNull(TEXT("Isolated test world"), World)) return false;
    ON_SCOPE_EXIT { World->DestroyWorld(false); };

    UClass* CloudClass = LoadClass<ACloudGeneratorActor>(nullptr,
        TEXT("/QuickWidgetTools/OnlyClouds/PlacedClouds/BP_CloudPreset.BP_CloudPreset_C"));
    if (!TestNotNull(TEXT("Actual FlexibleGuides Blueprint class"), CloudClass)) return false;
    ACloudGeneratorActor* Actor = World->SpawnActor<ACloudGeneratorActor>(CloudClass);
    if (!TestNotNull(TEXT("Test cloud"), Actor)) return false;
    FCloudRecipe Initial;
    // A portable recipe owns its material selection. A newly constructed struct has
    // no material asset, so retain the actual Blueprint's material for this fixture.
    Initial.CloudMaterial = Actor->CloudMaterial;
    Initial.Guides.AddDefaulted();
    if (!TestTrue(TEXT("Version 1 recipe with no animation fields remains loadable"), Actor->ApplyRecipe(Initial))) return false;
    TestFalse(TEXT("Existing recipes default to animation off"), Actor->bAnimated);
    TestTrue(TEXT("Existing recipes start at zero offset"), Actor->TextureOffsetCm.IsZero());
    TestEqual(TEXT("Existing recipes start at zero phase"), Actor->NoisePhase, 0.0f);
    TestTrue(TEXT("Actor is tick enabled"), Actor->PrimaryActorTick.bCanEverTick && Actor->IsActorTickEnabled());
    TestTrue(TEXT("Actual Blueprint starts with tick enabled"), Actor->PrimaryActorTick.bStartWithTickEnabled);
    TestTrue(TEXT("Editor viewport ticking is enabled"), Actor->ShouldTickIfViewportsOnly());

    UMaterialInstanceDynamic* MID = Cast<UMaterialInstanceDynamic>(Actor->CloudVolume->GetMaterial(0));
    if (!TestNotNull(TEXT("Per-cloud dynamic material"), MID)) return false;
    const auto CheckMaterial = [this, Actor, MID](const TCHAR* Context)
    {
        TestEqual(FString(Context) + TEXT(" phase reaches MID"), MID->K2_GetScalarParameterValue(TEXT("NoisePhase")), Actor->NoisePhase);
        const FLinearColor Actual = MID->K2_GetVectorParameterValue(TEXT("NoiseOffsetCm"));
        TestTrue(FString(Context) + TEXT(" offset reaches MID"), Actual.Equals(FLinearColor(Actor->TextureOffsetCm.X, Actor->TextureOffsetCm.Y, Actor->TextureOffsetCm.Z, 0.0f)));
    };
    CheckMaterial(TEXT("Initial"));
    const TArray<FLinearColor> GuideData = Actor->GetEncodedGuideData();
    UTexture2D* GuideTexture = Actor->GuideDataTexture;
    const FTransform VolumeTransform = Actor->CloudVolume->GetComponentTransform();
    Actor->bAnimated = true;
    Actor->OffsetSpeedX = 40.0f;
    Actor->OffsetSpeedY = -20.0f;
    Actor->OffsetSpeedZ = 10.0f;
    Actor->PhaseSpeed = 0.4f;
    Actor->Tick(0.25f);
    Actor->Tick(0.25f);
    TestTrue(TEXT("Offset integrates signed world-axis speed per second"), Actor->TextureOffsetCm.Equals(FVector(20.0, -10.0, 5.0)));
    TestTrue(TEXT("Phase integrates speed per second"), FMath::IsNearlyEqual(Actor->NoisePhase, 0.2f));
    CheckMaterial(TEXT("Animated"));
    TestTrue(TEXT("Tick preserves guide texture identity"), Actor->GuideDataTexture == GuideTexture);
    TestTrue(TEXT("Tick preserves packed guide data"), Actor->GetEncodedGuideData() == GuideData);
    TestTrue(TEXT("Tick leaves volume bounds in place"), Actor->CloudVolume->GetComponentTransform().Equals(VolumeTransform));
    TestFalse(TEXT("Noise animation does not enable sparse-volume playback"), Actor->CloudVolume->bPlaying);
    TestTrue(TEXT("Tick preserves per-cloud material identity"), Actor->CloudVolume->GetMaterial(0) == MID);

    Actor->bAnimated = false;
    Actor->Tick(2.0f);
    TestTrue(TEXT("Off freezes offset"), Actor->TextureOffsetCm.Equals(FVector(20.0, -10.0, 5.0)));
    TestTrue(TEXT("Off freezes phase"), FMath::IsNearlyEqual(Actor->NoisePhase, 0.2f));
    Actor->TextureOffsetCm = FVector(-30.0, 12.0, 7.0);
    Actor->NoisePhase = -0.7f;
    Actor->Tick(0.0f);
    CheckMaterial(TEXT("Manual/Sequencer"));

    Actor->bAnimated = true;
    const FCloudRecipe Snapshot = Actor->CaptureRecipe();
    TestTrue(TEXT("Recipe preserves automatic animation setting"), Snapshot.bAnimated);
    TestEqual(TEXT("Recipe preserves signed X speed"), Snapshot.OffsetSpeedX, 40.0f);
    TestEqual(TEXT("Recipe preserves signed Y speed"), Snapshot.OffsetSpeedY, -20.0f);
    TestEqual(TEXT("Recipe preserves signed Z speed"), Snapshot.OffsetSpeedZ, 10.0f);
    TestEqual(TEXT("Recipe preserves phase speed"), Snapshot.PhaseSpeed, 0.4f);
    TestTrue(TEXT("Recipe captures current offset"), Snapshot.TextureOffsetCm.Equals(Actor->TextureOffsetCm));
    TestEqual(TEXT("Recipe captures current phase"), Snapshot.NoisePhase, Actor->NoisePhase);
    Actor->LockCloud();
    Actor->TextureOffsetCm = FVector(900.0);
    Actor->NoisePhase = 900.0f;
    Actor->OffsetSpeedX = 999.0f;
    Actor->Tick(1.0f);
    TestTrue(TEXT("Lock restores captured offset without advancing"), Actor->TextureOffsetCm.Equals(Snapshot.TextureOffsetCm));
    TestEqual(TEXT("Lock restores captured phase without advancing"), Actor->NoisePhase, Snapshot.NoisePhase);
    TestEqual(TEXT("Lock protects animation controls"), Actor->OffsetSpeedX, Snapshot.OffsetSpeedX);
    CheckMaterial(TEXT("Locked"));
    Actor->ResetCloudAnimation();
    TestTrue(TEXT("Reset respects lock"), Actor->TextureOffsetCm.Equals(Snapshot.TextureOffsetCm));
    Actor->UnlockCloud();
    Actor->Tick(0.5f);
    TestTrue(TEXT("Unlock resumes from frozen offset"), Actor->TextureOffsetCm.Equals(Snapshot.TextureOffsetCm + FVector(20.0, -10.0, 5.0)));
    TestTrue(TEXT("Unlock resumes from frozen phase"), FMath::IsNearlyEqual(Actor->NoisePhase, Snapshot.NoisePhase + 0.2f));

    Actor->ResetCloudAnimation();
    TestTrue(TEXT("Reset clears offset"), Actor->TextureOffsetCm.IsZero());
    TestEqual(TEXT("Reset clears phase"), Actor->NoisePhase, 0.0f);
    TestTrue(TEXT("Reset preserves automatic animation setting"), Actor->bAnimated);
    TestEqual(TEXT("Reset preserves speed"), Actor->OffsetSpeedX, 40.0f);
    CheckMaterial(TEXT("Reset"));
    TestTrue(TEXT("Captured recipe can be loaded"), Actor->ApplyRecipe(Snapshot));
    TestTrue(TEXT("Recipe load restores offset"), Actor->TextureOffsetCm.Equals(Snapshot.TextureOffsetCm));
    TestEqual(TEXT("Recipe load restores phase"), Actor->NoisePhase, Snapshot.NoisePhase);
    CheckMaterial(TEXT("Reloaded"));
    Actor->Tick(-1.0f);
    TestEqual(TEXT("Negative delta cannot reverse the stored phase"), Actor->NoisePhase, Snapshot.NoisePhase);

    Actor->bAnimated = false;
    Actor->TextureOffsetCm = FVector(5.0);
    Actor->NoisePhase = 3.0f;
    TestTrue(TEXT("Legacy recipe remains loadable after animation"), Actor->ApplyRecipe(Initial));
    TestFalse(TEXT("Legacy recipe disables animation"), Actor->bAnimated);
    TestTrue(TEXT("Legacy recipe clears prior offset"), Actor->TextureOffsetCm.IsZero());
    TestEqual(TEXT("Legacy recipe clears prior phase"), Actor->NoisePhase, 0.0f);
    CheckMaterial(TEXT("Legacy reload"));
    return true;
}

#endif
