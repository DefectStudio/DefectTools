#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "CloudGeneratorActor.h"
#include "Components/HeterogeneousVolumeComponent.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "Serialization/MemoryReader.h"
#include "Serialization/MemoryWriter.h"
#include "Serialization/ObjectAndNameAsStringProxyArchive.h"
#include <limits>

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FOnlyCloudsDetailEdgeTest,
    "OnlyClouds.LowFog.ResolutionAndEdgeFalloffPersistence",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FOnlyCloudsDetailEdgeTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::Editor, false, TEXT("OnlyCloudsDetailEdgeTest"));
    if (!TestNotNull(TEXT("Isolated test world"), World)) return false;
    ON_SCOPE_EXIT { World->DestroyWorld(false); };
    ACloudGeneratorActor* Cloud = World->SpawnActor<ACloudGeneratorActor>();
    ALowFogGeneratorActor* Fog = World->SpawnActor<ALowFogGeneratorActor>();
    if (!TestTrue(TEXT("Test generators spawn"), Cloud && Fog)) return false;
    TestEqual(TEXT("Existing clouds retain 128 voxels per axis"), Cloud->VolumeResolution, 128);
    TestFalse(TEXT("Existing clouds retain disabled edge falloff"), Cloud->bEdgeFallOff);
    TestTrue(TEXT("New native fog defaults enable edge falloff"), Fog->bEdgeFallOff);
    TestEqual(TEXT("New native fog uses an 80cm edge distance"), Fog->EdgeFallOffDistanceCm, 80.0f);

    FCloudRecipe Recipe;
    Recipe.Version = 2;
    Recipe.CloudMaterial.Reset(); // Native geometry tests do not need shader compilation.
    Recipe.bGroundFog = true;
    Recipe.FogHeightCm = 82.03125f;
    Recipe.BillowDepthCm = 35.0f;
    Recipe.UnionGrowthLimitCm = 7.5f;
    Recipe.bEdgeFallOff = true;
    Recipe.EdgeFallOffDistanceCm = 75.0f;
    Recipe.EdgeFallOffContrast = 2.5f;
    Recipe.BillowSizeCm = 137.0f;
    Recipe.DetailSizeCm = 21.0f;
    FCloudGuideRecipe& Guide = Recipe.Guides.AddDefaulted_GetRef();
    Guide.Shape = ECloudGuideShape::Cylinder;
    Guide.LocalTransform = FTransform(FQuat::Identity, FVector(0.0, 0.0, 41.015625), FVector(3.28125, 3.28125, 0.41015625));
    Fog->SetActorLocation(FVector(1200.0, -450.0, 25.0));
    if (!TestTrue(TEXT("Fog test recipe applies"), Fog->ApplyRecipe(Recipe))) return false;

    auto VerifyResolutionInvariance = [&](ACloudGeneratorActor* Actor, const TCHAR* Context)
    {
        Actor->VolumeResolution = 128;
        Actor->RefreshCloud();
        const FVector AuthoredHalfExtents = Actor->BoundsHalfExtentsCm;
        const FBoxSphereBounds AuthoredBounds = Actor->CloudVolume->CalcBounds(Actor->CloudVolume->GetComponentTransform());
        const TArray<FLinearColor> AuthoredGuideData = Actor->GetEncodedGuideData();
        const float ExtinctionTimesResolution = Actor->ComputedExtinctionScale * 128.0f;
        const float AuthoredDensity = Actor->Density;
        for (int32 Resolution : {32, 64, 128, 192, 256, 512})
        {
            Actor->VolumeResolution = Resolution;
            Actor->Quality = Resolution >= 256 ? ECloudPreviewQuality::Cinematic : ECloudPreviewQuality::Preview;
            Actor->RefreshCloud();
            const FString Label = FString::Printf(TEXT("%s %d"), Context, Resolution);
            TestTrue(Label + TEXT(": all component axes use artist resolution"), Actor->CloudVolume->VolumeResolution == FIntVector(Resolution));
            TestTrue(Label + TEXT(": analytic bounds stay fixed"), Actor->BoundsHalfExtentsCm.Equals(AuthoredHalfExtents, 0.0001));
            const FBoxSphereBounds Bounds = Actor->CloudVolume->CalcBounds(Actor->CloudVolume->GetComponentTransform());
            TestTrue(Label + TEXT(": physical footprint stays fixed"), Bounds.Origin.Equals(AuthoredBounds.Origin, 0.0001) && Bounds.BoxExtent.Equals(AuthoredBounds.BoxExtent, 0.0001));
            TestTrue(Label + TEXT(": guide encoding stays fixed"), Actor->GetEncodedGuideData() == AuthoredGuideData);
            TestEqual(Label + TEXT(": artist density stays fixed"), Actor->Density, AuthoredDensity);
            TestTrue(Label + TEXT(": integrated local-space extinction stays fixed"), FMath::IsNearlyEqual(Actor->ComputedExtinctionScale * Resolution, ExtinctionTimesResolution, 0.0001f));
            TestTrue(Label + TEXT(": local boundary maps to the same world centimeters"),
                (Actor->CloudVolume->GetComponentScale() * (Resolution * 0.5)).Equals(AuthoredHalfExtents, 0.0001));
        }
    };
    VerifyResolutionInvariance(Fog, TEXT("Low fog"));
    TestEqual(TEXT("Resolution leaves billow size in world centimeters"), Fog->BillowSizeCm, Recipe.BillowSizeCm);
    TestEqual(TEXT("Resolution leaves detail size in world centimeters"), Fog->DetailSizeCm, Recipe.DetailSizeCm);
    FCloudRecipe CloudRecipe = Recipe;
    CloudRecipe.bGroundFog = false;
    CloudRecipe.bEdgeFallOff = false;
    CloudRecipe.Guides[0].Shape = ECloudGuideShape::Sphere;
    if (!TestTrue(TEXT("Ordinary cloud test recipe applies"), Cloud->ApplyRecipe(CloudRecipe))) return false;
    VerifyResolutionInvariance(Cloud, TEXT("Ordinary cloud"));

    Fog->VolumeResolution = 192;
    UCloudRecipePreset* Saved = NewObject<UCloudRecipePreset>();
    Saved->Recipe = Fog->CaptureRecipe();
    TArray<uint8> Bytes;
    {
        FMemoryWriter Writer(Bytes, true);
        FObjectAndNameAsStringProxyArchive Archive(Writer, false);
        Saved->Serialize(Archive);
    }
    UCloudRecipePreset* Reloaded = NewObject<UCloudRecipePreset>();
    {
        FMemoryReader Reader(Bytes, true);
        FObjectAndNameAsStringProxyArchive Archive(Reader, true);
        Reloaded->Serialize(Archive);
        if (!TestFalse(TEXT("Preset serialization reload succeeds"), Archive.IsError())) return false;
    }
    TestEqual(TEXT("Preset preserves artist resolution"), Reloaded->Recipe.VolumeResolution, 192);
    TestTrue(TEXT("Preset preserves edge toggle"), Reloaded->Recipe.bEdgeFallOff);
    TestEqual(TEXT("Preset preserves inward falloff distance"), Reloaded->Recipe.EdgeFallOffDistanceCm, 75.0f);
    TestEqual(TEXT("Preset preserves falloff contrast"), Reloaded->Recipe.EdgeFallOffContrast, 2.5f);
    if (!TestTrue(TEXT("Serialized settings load back onto an actor"), Fog->ApplyRecipe(Reloaded->Recipe))) return false;
    TestEqual(TEXT("Actor restores saved resolution"), Fog->VolumeResolution, 192);
    TestEqual(TEXT("Actor restores saved edge distance"), Fog->EdgeFallOffDistanceCm, 75.0f);

    Fog->LockCloud();
    Fog->VolumeResolution = 256;
    Fog->EdgeFallOffDistanceCm = 1.0f;
    Fog->RefreshCloud();
    TestEqual(TEXT("Locked volume still allows rendering-resolution changes"), Fog->VolumeResolution, 256);
    TestEqual(TEXT("Locked volume protects edge appearance"), Fog->EdgeFallOffDistanceCm, 75.0f);
    Fog->UnlockCloud();
    FCloudRecipe Invalid = Reloaded->Recipe;
    Invalid.VolumeResolution = -1;
    Invalid.EdgeFallOffDistanceCm = -50.0f;
    Invalid.EdgeFallOffContrast = std::numeric_limits<float>::quiet_NaN();
    if (!TestTrue(TEXT("Out-of-range settings load with safe clamps"), Fog->ApplyRecipe(Invalid))) return false;
    TestEqual(TEXT("Invalid low resolution clamps to 32"), Fog->VolumeResolution, 32);
    TestTrue(TEXT("Component receives clamped minimum resolution"), Fog->CloudVolume->VolumeResolution == FIntVector(32));
    TestEqual(TEXT("Negative edge distance clamps to zero"), Fog->EdgeFallOffDistanceCm, 0.0f);
    TestEqual(TEXT("Nonfinite contrast restores neutral linear curve"), Fog->EdgeFallOffContrast, 1.0f);
    Invalid.VolumeResolution = 999999;
    Invalid.EdgeFallOffDistanceCm = std::numeric_limits<float>::infinity();
    Invalid.EdgeFallOffContrast = -2.0f;
    if (!TestTrue(TEXT("Extreme settings load with safe clamps"), Fog->ApplyRecipe(Invalid))) return false;
    TestEqual(TEXT("High resolution clamps to 512"), Fog->VolumeResolution, 512);
    TestEqual(TEXT("Nonfinite edge distance restores its safe default"), Fog->EdgeFallOffDistanceCm, 100.0f);
    TestEqual(TEXT("Negative contrast clamps above zero"), Fog->EdgeFallOffContrast, 0.01f);
    Fog->VolumeResolution = 0;
    TestEqual(TEXT("Direct capture cannot save an invalid voxel resolution"), Fog->CaptureRecipe().VolumeResolution, 32);
    return !HasAnyErrors();
}

#endif
