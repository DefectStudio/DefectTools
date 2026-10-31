#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "CloudGeneratorActor.h"
#include "Components/HeterogeneousVolumeComponent.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "Materials/MaterialInterface.h"
#include "Serialization/MemoryReader.h"
#include "Serialization/MemoryWriter.h"
#include "Serialization/ObjectAndNameAsStringProxyArchive.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FOnlyCloudsLowFogTest,
    "OnlyClouds.LowFog.RecipeAndBoundsPersistence",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FOnlyCloudsLowFogTest::RunTest(const FString& Parameters)
{
    TestEqual(TEXT("Legacy Sphere enum is stable"), static_cast<uint8>(ECloudGuideShape::Sphere), uint8(0));
    TestEqual(TEXT("Legacy Box enum is stable"), static_cast<uint8>(ECloudGuideShape::Box), uint8(1));
    TestEqual(TEXT("Cylinder appends a new enum value"), static_cast<uint8>(ECloudGuideShape::Cylinder), uint8(2));

    UWorld* World = UWorld::CreateWorld(EWorldType::Editor, false, TEXT("OnlyCloudsLowFogTest"));
    if (!TestNotNull(TEXT("Isolated test world"), World)) return false;
    ON_SCOPE_EXIT { World->DestroyWorld(false); };
    ALowFogGeneratorActor* Source = World->SpawnActor<ALowFogGeneratorActor>();
    ALowFogGeneratorActor* Target = World->SpawnActor<ALowFogGeneratorActor>();
    ACloudGeneratorActor* LegacyCloud = World->SpawnActor<ACloudGeneratorActor>();
    if (!TestTrue(TEXT("Test actors spawned"), Source && Target && LegacyCloud)) return false;
    TestTrue(TEXT("Low-fog class enables grounding"), Source->bGroundFog);
    TestFalse(TEXT("Existing cloud class keeps grounding disabled"), LegacyCloud->bGroundFog);

    FCloudRecipe Recipe;
    Recipe.Version = 2;
    Recipe.bGroundFog = true;
    Recipe.GroundOffsetCm = 7.25f;
    Recipe.GroundFadeCm = 2.5f;
    Recipe.FogHeightCm = 82.03125f;
    Recipe.HeightFalloff = 2.25f;
    Recipe.bAnimated = true;
    Recipe.OffsetSpeedX = 8.0f;
    Recipe.PhaseSpeed = 0.07f;
    Recipe.BillowDepthCm = 35.0f;
    Recipe.UnionGrowthLimitCm = 7.5f;
    // Empty materials keep this native test independent of shader compilation.
    Recipe.CloudMaterial.Reset();
    FCloudGuideRecipe& Cylinder = Recipe.Guides.AddDefaulted_GetRef();
    Cylinder.Shape = ECloudGuideShape::Cylinder;
    Cylinder.LocalTransform = FTransform(FQuat::Identity,
        FVector(0.0, 0.0, Recipe.GroundOffsetCm + Recipe.FogHeightCm * 0.5),
        FVector(3.28125, 3.28125, 0.41015625));
    FCloudGuideRecipe& Sphere = Recipe.Guides.AddDefaulted_GetRef();
    Sphere.Shape = ECloudGuideShape::Sphere;
    Sphere.Operation = ECloudGuideOperation::Subtract;
    FCloudGuideRecipe& Box = Recipe.Guides.AddDefaulted_GetRef();
    Box.Shape = ECloudGuideShape::Box;
    Box.Operation = ECloudGuideOperation::Subtract;
    Source->SetActorLocation(FVector(1200.0, -500.0, 30.0));
    if (!TestTrue(TEXT("Cylinder fog recipe applies"), Source->ApplyRecipe(Recipe))) return false;
    const TArray<FLinearColor> Encoded = Source->GetEncodedGuideData();
    if (!TestTrue(TEXT("Three enabled guides encoded"), Encoded.Num() >= 9 && Source->ActiveGuideCount == 3)) return false;
    TestEqual(TEXT("Cylinder shader kind is three"), Encoded[0].A, 3.0f);
    TestEqual(TEXT("Subtractive sphere shader kind remains minus one"), Encoded[3].A, -1.0f);
    TestEqual(TEXT("Subtractive box shader kind remains minus two"), Encoded[6].A, -2.0f);
    TestTrue(TEXT("Low fog retains shallow per-axis bounds"), Source->BoundsHalfExtentsCm.Z < Source->BoundsHalfExtentsCm.X * 0.2);
    TestTrue(TEXT("Volume scale matches the reported per-axis bounds"),
        Source->CloudVolume->GetComponentScale().Equals(Source->BoundsHalfExtentsCm / 64.0, 0.0001));
    TestTrue(TEXT("Bounds center uses the anchored ground plane"), FMath::Abs(
        Source->BoundsCenterRelativeToAnchorCm.Z - (Recipe.GroundOffsetCm + Recipe.FogHeightCm * 0.5)) < 0.0001);

    const FSoftObjectPath FogMaterialPath(TEXT("/QuickWidgetTools/OnlyClouds/LowFog/Materials/M_LowFogVolume.M_LowFogVolume"));
    Source->CloudMaterial = TSoftObjectPtr<UMaterialInterface>(FogMaterialPath);
    UCloudRecipePreset* Saved = NewObject<UCloudRecipePreset>();
    Saved->Recipe = Source->CaptureRecipe();
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
        if (!TestFalse(TEXT("Serialized preset reload succeeds"), Archive.IsError())) return false;
    }
    TestTrue(TEXT("Grounding persists in the preset"), Reloaded->Recipe.bGroundFog);
    TestEqual(TEXT("Ground offset persists"), Reloaded->Recipe.GroundOffsetCm, Recipe.GroundOffsetCm);
    TestEqual(TEXT("Ground fade persists"), Reloaded->Recipe.GroundFadeCm, Recipe.GroundFadeCm);
    TestEqual(TEXT("Fog height persists"), Reloaded->Recipe.FogHeightCm, Recipe.FogHeightCm);
    TestEqual(TEXT("Height falloff persists"), Reloaded->Recipe.HeightFalloff, Recipe.HeightFalloff);
    TestTrue(TEXT("Dedicated fog material persists"), Reloaded->Recipe.CloudMaterial.ToSoftObjectPath() == FogMaterialPath);
    TestTrue(TEXT("Cylinder guide shape persists"), Reloaded->Recipe.Guides[0].Shape == ECloudGuideShape::Cylinder);
    FCloudRecipe NativeReload = Reloaded->Recipe;
    NativeReload.CloudMaterial.Reset();
    Target->SetActorLocation(FVector(-2000.0, 300.0, -70.0));
    if (!TestTrue(TEXT("Reloaded fog recipe applies at another placement"), Target->ApplyRecipe(NativeReload))) return false;
    TestEqual(TEXT("Actor receives saved grounding controls"), Target->GroundOffsetCm, Recipe.GroundOffsetCm);
    TestTrue(TEXT("Reloaded guide keeps its authored size"), Target->Guides[0]->GetActorScale3D().Equals(Source->Guides[0]->GetActorScale3D(), 0.0001));
    TestTrue(TEXT("Reloaded volume keeps shallow bounds"), Target->BoundsHalfExtentsCm.Equals(Source->BoundsHalfExtentsCm, 0.0001));

    FCloudRecipe LegacyRecipe;
    LegacyRecipe.CloudMaterial.Reset();
    FCloudGuideRecipe& LegacyGuide = LegacyRecipe.Guides.AddDefaulted_GetRef();
    LegacyGuide.LocalTransform = FTransform(FQuat::Identity, FVector(0.0, 0.0, 700.0), FVector(3.0, 2.0, 1.0));
    if (!TestTrue(TEXT("Legacy cloud recipe still applies"), LegacyCloud->ApplyRecipe(LegacyRecipe))) return false;
    TestTrue(TEXT("Existing clouds keep their cubic bounds"), LegacyCloud->BoundsHalfExtentsCm.Equals(FVector(LegacyCloud->BoundsHalfExtentCm), 0.0001));
    TestEqual(TEXT("Legacy additive sphere shader kind remains one"), LegacyCloud->GetEncodedGuideData()[0].A, 1.0f);
    return !HasAnyErrors();
}

#endif
