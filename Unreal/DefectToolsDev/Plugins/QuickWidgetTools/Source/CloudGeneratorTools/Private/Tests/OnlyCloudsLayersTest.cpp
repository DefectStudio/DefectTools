#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

#include "UltraDynamicSkyOnlyClouds.h"
#include "Components/VolumetricCloudComponent.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Math/Float16Color.h"
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "RenderingThread.h"

// This test creates and destroys its own world. It never opens or edits an editor map.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FOnlyCloudsLayersDataTest,
    "CloudGenerator.OnlyClouds.Layers.ActualTextureData",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FOnlyCloudsLayersDataTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::Editor, false, TEXT("OnlyCloudsLayerDataTest"));
    if (!TestNotNull(TEXT("Isolated test world"), World)) return false;
    ON_SCOPE_EXIT { World->DestroyWorld(false); };

    AUltraDynamicSkyOnlyClouds* Actor = World->SpawnActor<AUltraDynamicSkyOnlyClouds>();
    if (!TestNotNull(TEXT("Test controller"), Actor)) return false;
    Actor->RestorePreviousCloudQuality();
    Actor->LayerBottomAltitudeKm = 0.2f;
    Actor->LayerHeightKm = 0.3f;
    Actor->CloudCoverage = 4.0f;
    Actor->Extinction = 11.0f;
    Actor->FormationTextureScale = 1.0f;
    Actor->RefreshClouds();
    if (!TestTrue(TEXT("Single-layer controller ready"), Actor->CloudStatus.StartsWith(TEXT("Ready:")))) return false;
    UMaterialInstanceDynamic* SingleMID = Cast<UMaterialInstanceDynamic>(Actor->VolumetricCloud->GetMaterial());
    if (!TestNotNull(TEXT("Single-layer material assigned"), SingleMID)) return false;
    TestTrue(TEXT("Empty array retains original material"), SingleMID->Parent == Actor->CloudMaterial.LoadSynchronous());

    FUDSOnlyCloudLayer Middle;
    Middle.Name = TEXT("Middle test deck");
    Middle.BottomAltitudeKm = 1.0f;
    Middle.HeightKm = 0.4f;
    Middle.CloudCoverage = 8.0f;
    Middle.Extinction = 20.0f;
    Middle.FormationTextureScale = 2.0f;
    Middle.FormationPhase = 3.0f;
    Middle.FormationMipOffset = 1.0f;
    FUDSOnlyCloudLayer Upper;
    Upper.Name = TEXT("Upper test deck");
    Upper.BottomAltitudeKm = 2.0f;
    Upper.HeightKm = 0.2f;
    Upper.CloudCoverage = 2.0f;
    Upper.Extinction = 6.0f;
    Upper.FormationTextureScale = 0.5f;
    Upper.FormationPhase = 4.0f;
    Upper.FormationMipOffset = 2.0f;
    Actor->AdditionalCloudLayers = {Middle, Upper};
    Actor->RefreshClouds();
    if (!TestTrue(TEXT("Three-layer controller ready"), Actor->CloudStatus.StartsWith(TEXT("Ready:")))) return false;
    TestTrue(TEXT("Full-stack bottom"), FMath::IsNearlyEqual(Actor->VolumetricCloud->LayerBottomAltitude, 0.2f));
    TestTrue(TEXT("Full-stack thickness"), FMath::IsNearlyEqual(Actor->VolumetricCloud->LayerHeight, 2.0f));

    UTexture2D* LastTexture = nullptr;
    const auto ReadPixels = [this, Actor, &LastTexture](TArray<FFloat16Color>& Out)
    {
        FlushRenderingCommands();
        UMaterialInstanceDynamic* MID = Cast<UMaterialInstanceDynamic>(Actor->VolumetricCloud->GetMaterial());
        if (!TestNotNull(TEXT("Layered material assigned"), MID)) return false;
        if (!TestTrue(TEXT("Layered parent selected"), MID->Parent == Actor->LayeredCloudMaterial.LoadSynchronous())) return false;
        UTexture2D* Texture = Cast<UTexture2D>(MID->K2_GetTextureParameterValue(TEXT("OnlyCloudsLayerMap")));
        if (!TestNotNull(TEXT("Actual transient layer texture bound"), Texture)) return false;
        LastTexture = Texture;
        TestTrue(TEXT("Layer map is linear"), !Texture->SRGB);
        TestTrue(TEXT("Layer map is transient"), Texture->HasAnyFlags(RF_Transient));
        TestEqual(TEXT("Layer map width"), Texture->GetSizeX(), 6);
        TestEqual(TEXT("Layer map height"), Texture->GetSizeY(), 1000);
        FTexturePlatformData* Data = Texture->GetPlatformData();
        if (!TestTrue(TEXT("Actual mip data available"), Data && Data->Mips.Num() == 1)) return false;
        FTexture2DMipMap& Mip = Data->Mips[0];
        const int64 ExpectedBytes = 6000 * sizeof(FFloat16Color);
        if (!TestEqual(TEXT("Actual CPU mip byte count"), Mip.BulkData.GetBulkDataSize(), ExpectedBytes)) return false;
        const void* Bytes = Mip.BulkData.LockReadOnly();
        if (!Bytes) { Mip.BulkData.Unlock(); AddError(TEXT("Layer texture bulk data could not be read")); return false; }
        Out.SetNumUninitialized(6000);
        FMemory::Memcpy(Out.GetData(), Bytes, ExpectedBytes);
        Mip.BulkData.Unlock();
        return true;
    };
    const auto Sample = [Actor](const TArray<FFloat16Color>& Pixels, float AltitudeKm, int32 Stripe)
    {
        const float H = (AltitudeKm - Actor->VolumetricCloud->LayerBottomAltitude) / Actor->VolumetricCloud->LayerHeight;
        const int32 Row = FMath::Clamp(FMath::FloorToInt((1.0f - H) * 1000.0f), 0, 999);
        return Pixels[Row * 6 + Stripe * 2].GetFloats();
    };
    const auto Near = [this](const TCHAR* Label, float Value, float Expected, float Tolerance = 0.015f)
    {
        TestTrue(FString::Printf(TEXT("%s: actual %.6f expected %.6f"), Label, Value, Expected), FMath::Abs(Value - Expected) <= Tolerance);
    };

    TArray<FFloat16Color> Pixels;
    if (!ReadPixels(Pixels)) return false;
    // Expected densities are independently chosen simple points of the installed UDS coverage curve.
    Near(TEXT("Base coverage"), Sample(Pixels, 0.35f, 1).G, 1.38f);
    Near(TEXT("Middle coverage"), Sample(Pixels, 1.20f, 1).G, 2.76f);
    Near(TEXT("Upper coverage"), Sample(Pixels, 2.10f, 1).G, 0.69f);
    Near(TEXT("First physical gap empty"), Sample(Pixels, 0.75f, 1).G, 0.0f, 0.0f);
    Near(TEXT("Second physical gap empty"), Sample(Pixels, 1.70f, 1).G, 0.0f, 0.0f);
    Near(TEXT("Base local profile midpoint"), Sample(Pixels, 0.35f, 0).B, 0.5f);
    Near(TEXT("Middle local profile midpoint"), Sample(Pixels, 1.20f, 0).B, 0.5f);
    Near(TEXT("Upper local profile midpoint"), Sample(Pixels, 2.10f, 0).B, 0.5f);
    Near(TEXT("Middle local profile quarter"), Sample(Pixels, 1.10f, 0).B, 0.25f);
    Near(TEXT("Middle local profile three quarters"), Sample(Pixels, 1.30f, 0).B, 0.75f);
    Near(TEXT("Larger formation size lowers frequency"), Sample(Pixels, 1.20f, 0).R, 0.5f);
    Near(TEXT("Smaller formation size raises frequency"), Sample(Pixels, 2.10f, 0).R, 2.0f);
    Near(TEXT("Independent extinction"), Sample(Pixels, 1.20f, 2).R, 20.0f);
    Near(TEXT("Independent phase"), Sample(Pixels, 1.20f, 2).G, 3.0f);
    Near(TEXT("Independent mip"), Sample(Pixels, 1.20f, 2).B, 1.0f);
    bool bAllFinite = true;
    bool bPairsIdentical = true;
    for (int32 I = 0; I < Pixels.Num(); I += 2)
    {
        const FLinearColor A = Pixels[I].GetFloats();
        const FLinearColor B = Pixels[I + 1].GetFloats();
        bAllFinite &= FMath::IsFinite(A.R) && FMath::IsFinite(A.G) && FMath::IsFinite(A.B) && FMath::IsFinite(A.A);
        bPairsIdentical &= A == B;
    }
    TestTrue(TEXT("Entire table finite"), bAllFinite);
    TestTrue(TEXT("All sampler column pairs identical"), bPairsIdentical);

    UTexture2D* OriginalTexture = LastTexture;
    Actor->AdditionalCloudLayers[0].CloudCoverage = 2.0f;
    Actor->RefreshClouds();
    if (!ReadPixels(Pixels)) return false;
    TestTrue(TEXT("Editing reuses private texture"), OriginalTexture == LastTexture);
    Near(TEXT("Changed layer coverage updated"), Sample(Pixels, 1.20f, 1).G, 0.69f);
    Near(TEXT("Unedited base remains intact"), Sample(Pixels, 0.35f, 1).G, 1.38f);
    Near(TEXT("Unedited upper remains intact"), Sample(Pixels, 2.10f, 1).G, 0.69f);
    Actor->AdditionalCloudLayers[0].bEnabled = false;
    Actor->RefreshClouds();
    if (!ReadPixels(Pixels)) return false;
    Near(TEXT("Disabled layer leaves no stale coverage"), Sample(Pixels, 1.20f, 1).G, 0.0f, 0.0f);

    // Ordering is altitude-based, not array-position-based, for separate decks.
    Actor->AdditionalCloudLayers = {Upper, Middle};
    Actor->RefreshClouds();
    if (!ReadPixels(Pixels)) return false;
    Near(TEXT("Reordered middle preserved"), Sample(Pixels, 1.20f, 1).G, 2.76f);
    Near(TEXT("Reordered upper preserved"), Sample(Pixels, 2.10f, 1).G, 0.69f);

    Actor->CloudScale = 2.0f;
    Actor->RefreshClouds();
    if (!ReadPixels(Pixels)) return false;
    Near(TEXT("Scale applies to bottom"), Actor->VolumetricCloud->LayerBottomAltitude, 0.4f);
    Near(TEXT("Scale applies to full span"), Actor->VolumetricCloud->LayerHeight, 4.0f);
    Near(TEXT("Scaled physical gap empty"), Sample(Pixels, 1.50f, 1).G, 0.0f, 0.0f);
    Near(TEXT("Scale preserves local profile"), Sample(Pixels, 2.40f, 0).B, 0.5f);

    Actor->CloudScale = 1.0f;
    Actor->AdditionalCloudLayers = {Middle};
    Actor->AdditionalCloudLayers[0].BottomAltitudeKm = -1.0f;
    Actor->RefreshClouds();
    if (!ReadPixels(Pixels)) return false;
    Near(TEXT("Negative deck sets signed bounds"), Actor->VolumetricCloud->LayerBottomAltitude, -1.0f);
    Near(TEXT("Negative deck profile remains local"), Sample(Pixels, -0.8f, 0).B, 0.5f);
    Near(TEXT("Gap above negative deck empty"), Sample(Pixels, -0.3f, 1).G, 0.0f, 0.0f);

    Actor->AdditionalCloudLayers.Reset();
    Actor->RefreshClouds();
    UMaterialInstanceDynamic* RestoredMID = Cast<UMaterialInstanceDynamic>(Actor->VolumetricCloud->GetMaterial());
    TestTrue(TEXT("Removing last layer restores original parent"), RestoredMID && RestoredMID->Parent == Actor->CloudMaterial.LoadSynchronous());
    Near(TEXT("Removing last layer restores base bottom"), Actor->VolumetricCloud->LayerBottomAltitude, 0.2f);
    Near(TEXT("Removing last layer restores base height"), Actor->VolumetricCloud->LayerHeight, 0.3f);
    World->DestroyActor(Actor);
    return !HasAnyErrors();
}

#endif
