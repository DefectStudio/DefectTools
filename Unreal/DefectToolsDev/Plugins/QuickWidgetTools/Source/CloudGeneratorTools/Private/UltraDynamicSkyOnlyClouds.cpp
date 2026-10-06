#include "UltraDynamicSkyOnlyClouds.h"

#include "Components/SceneComponent.h"
#include "Components/VolumetricCloudComponent.h"
#include "Engine/Texture.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "Math/Float16Color.h"
#include "RHITypes.h"
#include "TextureResource.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialParameterCollection.h"
#include "Materials/MaterialParameterCollectionInstance.h"
#if WITH_EDITOR
#include "ScopedTransaction.h"
#endif

DEFINE_LOG_CATEGORY_STATIC(LogOnlyClouds, Log, All);

namespace OnlyCloudsLayers
{
    static constexpr int32 Width = 6;
    static constexpr int32 Height = 1000;
    static constexpr int32 MaxLayers = 32;
    static TMap<TWeakObjectPtr<UWorld>, TWeakObjectPtr<AUltraDynamicSkyOnlyClouds>> Controllers;

    static float DensityFromCoverage(float Coverage)
    {
        const float C = FMath::Clamp(Coverage, 0.0f, 10.0f) * 0.3f;
        return FMath::Clamp((C - FMath::Lerp(0.2f, 0.0f, FMath::Clamp(C / 0.2f, 0.0f, 1.0f))) * 1.15f, -0.2f, 3.0f);
    }
}

namespace OnlyCloudsQuality
{
    struct FSavedCVar
    {
        FString Name;
        FString Previous;
        FString Applied;
        EConsoleVariableFlags AppliedPriority = ECVF_Default;
    };

    // The renderer is process-wide. Keeping leases shared also covers editor + PIE worlds.
    static TSet<TWeakObjectPtr<AUltraDynamicSkyOnlyClouds>> Requesters;
    static TArray<FSavedCVar> Saved;

    static void RemoveExpiredRequests()
    {
        for (auto It = Requesters.CreateIterator(); It; ++It)
        {
            if (!It->IsValid())
            {
                It.RemoveCurrent();
            }
        }
    }

    static void RestoreIfUnused()
    {
        RemoveExpiredRequests();
        if (!Requesters.IsEmpty())
        {
            return;
        }
        for (const FSavedCVar& State : Saved)
        {
            if (IConsoleVariable* CVar = IConsoleManager::Get().FindConsoleVariable(*State.Name))
            {
                // A user's later console/scalability edit must win over our cleanup.
                if (CVar->GetString() == State.Applied
                    && (CVar->GetFlags() & ECVF_SetByMask) == State.AppliedPriority)
                {
                    CVar->ReplaceCurrentPriorityAndTag(*State.Previous);
                }
            }
        }
        Saved.Reset();
    }

    static void Acquire(AUltraDynamicSkyOnlyClouds* Actor)
    {
        RestoreIfUnused();
        if (Requesters.Contains(Actor))
        {
            return;
        }
        if (Requesters.IsEmpty())
        {
            // These are the cloud-only UDS Cinematic / Offline renderer changes.
            // Intentionally no sky, fog, light, ambient, auto-exposure or PPV changes.
            const TPair<const TCHAR*, int32> Settings[] = {
                {TEXT("r.VolumetricRenderTarget"), 1},
                {TEXT("r.VolumetricRenderTarget.Mode"), 3},
                {TEXT("r.VolumetricCloud.ViewRaySampleMaxCount"), 10000},
                {TEXT("r.VolumetricCloud.StepSizeOnZeroConservativeDensity"), 1}
            };
            for (const auto& Setting : Settings)
            {
                if (IConsoleVariable* CVar = IConsoleManager::Get().FindConsoleVariable(Setting.Key))
                {
                    FSavedCVar State;
                    State.Name = Setting.Key;
                    State.Previous = CVar->GetString();
                    CVar->ReplaceCurrentPriorityAndTag(Setting.Value);
                    State.Applied = CVar->GetString();
                    State.AppliedPriority = static_cast<EConsoleVariableFlags>(CVar->GetFlags() & ECVF_SetByMask);
                    Saved.Add(MoveTemp(State));
                }
            }
        }
        Requesters.Add(Actor);
    }

    static void Release(AUltraDynamicSkyOnlyClouds* Actor)
    {
        Requesters.Remove(Actor);
        RestoreIfUnused();
    }
}

AUltraDynamicSkyOnlyClouds::AUltraDynamicSkyOnlyClouds()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.bStartWithTickEnabled = true;
    PrimaryActorTick.TickGroup = TG_PrePhysics;

    USceneComponent* SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("CloudRoot"));
    SetRootComponent(SceneRoot);
    VolumetricCloud = CreateDefaultSubobject<UVolumetricCloudComponent>(TEXT("VolumetricCloud"));
    VolumetricCloud->SetupAttachment(SceneRoot);
    VolumetricCloud->SetMobility(EComponentMobility::Movable);
    CloudMaterial = TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(
        TEXT("/QuickWidgetTools/OnlyClouds/WorldClouds/Materials/M_UDS_OnlyClouds.M_UDS_OnlyClouds")));
    LayeredCloudMaterial = TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(
        TEXT("/QuickWidgetTools/OnlyClouds/WorldClouds/Materials/M_UDS_OnlyClouds_Layers.M_UDS_OnlyClouds_Layers")));
    CloudParameters = TSoftObjectPtr<UMaterialParameterCollection>(FSoftObjectPath(
        TEXT("/QuickWidgetTools/OnlyClouds/WorldClouds/Materials/MPC_UDS_OnlyClouds.MPC_UDS_OnlyClouds")));
}

bool AUltraDynamicSkyOnlyClouds::TryAcquireController()
{
    UWorld* World = GetWorld();
    if (!IsCloudWorld())
    {
        return false;
    }
    for (auto It = OnlyCloudsLayers::Controllers.CreateIterator(); It; ++It)
    {
        if (!It.Key().IsValid() || !It.Value().IsValid())
        {
            It.RemoveCurrent();
        }
    }
    TWeakObjectPtr<AUltraDynamicSkyOnlyClouds>& CloudControllerOwner = OnlyCloudsLayers::Controllers.FindOrAdd(World);
    if (CloudControllerOwner.IsValid() && CloudControllerOwner.Get() != this)
    {
        bWaitingForController = true;
        bCloudReady = false;
        VolumetricCloud->SetVisibility(false);
        ReleaseQualityRequest();
        CloudStatus = FString::Printf(TEXT("Inactive: %s already controls this world's clouds. Add cloud layers on that actor instead."), *CloudControllerOwner->GetActorNameOrLabel());
        return false;
    }
    CloudControllerOwner = this;
    bWaitingForController = false;
    ControllerRetrySeconds = 0.0f;
    return true;
}

void AUltraDynamicSkyOnlyClouds::ReleaseController()
{
    if (TWeakObjectPtr<AUltraDynamicSkyOnlyClouds>* CloudControllerOwner = OnlyCloudsLayers::Controllers.Find(GetWorld()))
    {
        if (CloudControllerOwner->Get() == this || !CloudControllerOwner->IsValid())
        {
            OnlyCloudsLayers::Controllers.Remove(GetWorld());
        }
    }
}

bool AUltraDynamicSkyOnlyClouds::IsCloudWorld() const
{
    const UWorld* World = GetWorld();
    return !IsTemplate() && IsValid(World) && !IsRunningCommandlet()
        && (World->WorldType == EWorldType::Editor || World->WorldType == EWorldType::PIE
            || World->WorldType == EWorldType::Game || World->WorldType == EWorldType::GamePreview);
}

void AUltraDynamicSkyOnlyClouds::RefreshClouds()
{
    if (!IsCloudWorld() || !IsValid(VolumetricCloud))
    {
        return;
    }

    bNeedsRefresh = false;
    bCloudReady = false;
    LastInterpolatedStateHash = GetInterpolatedStateHash();
    if (!TryAcquireController())
    {
        return;
    }
    // Prevent accidental writes into the original pack's shared collection.
    const FString ParameterPackage = CloudParameters.ToSoftObjectPath().GetLongPackageName();
    if (!ParameterPackage.StartsWith(TEXT("/Game/CloudGenerator/OnlyClouds/")) &&
        !ParameterPackage.StartsWith(TEXT("/QuickWidgetTools/OnlyClouds/WorldClouds/")))
    {
        CloudStatus = TEXT("Assign the private OnlyClouds parameter collection. Original UDS collections are never modified.");
        VolumetricCloud->SetVisibility(false);
        ReleaseQualityRequest();
        ReleaseController();
        return;
    }

    const bool bUseLayeredMaterial = AdditionalCloudLayers.ContainsByPredicate([](const FUDSOnlyCloudLayer& Layer) { return Layer.bEnabled; });
    UMaterialInterface* ParentMaterial = bUseLayeredMaterial ? LayeredCloudMaterial.LoadSynchronous() : CloudMaterial.LoadSynchronous();
    UMaterialParameterCollection* Parameters = CloudParameters.LoadSynchronous();
    if (!IsValid(ParentMaterial) || !IsValid(Parameters))
    {
        CloudStatus = bUseLayeredMaterial
            ? TEXT("Missing OnlyClouds layered material or private parameter collection. No single-layer fallback is applied.")
            : TEXT("Missing OnlyClouds material or private parameter collection.");
        VolumetricCloud->SetVisibility(false);
        ReleaseQualityRequest();
        ReleaseController();
        return;
    }

    CollectionInstance = GetWorld()->GetParameterCollectionInstance(Parameters);
    if (!IsValid(CollectionInstance))
    {
        bNeedsRefresh = true;
        CloudStatus = TEXT("Waiting for the world's cloud parameter collection.");
        VolumetricCloud->SetVisibility(false);
        ReleaseQualityRequest();
        return;
    }

    if (!IsValid(CloudMID) || LastMaterial.Get() != ParentMaterial)
    {
        CloudMID = UMaterialInstanceDynamic::Create(ParentMaterial, this);
        CloudMID->SetFlags(RF_Transient);
        LastMaterial = ParentMaterial;
        VolumetricCloud->SetMaterial(CloudMID);
    }
    // Clearing overrides makes removing an optional texture restore the asset's default.
    CloudMID->ClearParameterValues();
    if (UTexture* Texture = FormationTexture.LoadSynchronous())
    {
        CloudMID->SetTextureParameterValue(TEXT("Formation Texture"), Texture);
    }
    if (UTexture* Texture = DetailNoiseTexture.LoadSynchronous())
    {
        CloudMID->SetTextureParameterValue(TEXT("3D_Texture"), Texture);
    }
    if (UTexture* Texture = CloudProfileTexture.LoadSynchronous())
    {
        CloudMID->SetTextureParameterValue(TEXT("Cloud_Profile"), Texture);
    }

    // Reset every private value before artist/advanced overrides so deleted overrides do not linger.
    for (const FCollectionScalarParameter& Parameter : Parameters->ScalarParameters)
    {
        CollectionInstance->SetScalarParameterValue(Parameter.ParameterName, Parameter.DefaultValue);
    }
    for (const FCollectionVectorParameter& Parameter : Parameters->VectorParameters)
    {
        CollectionInstance->SetVectorParameterValue(Parameter.ParameterName, Parameter.DefaultValue);
    }
    const auto Scalar = [this](const TCHAR* Name, float Value)
    {
        CollectionInstance->SetScalarParameterValue(FName(Name), Value);
    };
    const auto Vector = [this](const TCHAR* Name, const FLinearColor& Value)
    {
        CollectionInstance->SetVectorParameterValue(FName(Name), Value);
    };

    const float Scale = FMath::Max(CloudScale, 0.001f);
    const float BottomKm = LayerBottomAltitudeKm * Scale;
    const float HeightKm = FMath::Max(LayerHeightKm, 0.1f) * Scale;
    const float HeightScale = FMath::Max(LayerHeightKm, 0.1f) / 0.7f;
    const float Coverage = FMath::Clamp(CloudCoverage, 0.0f, 10.0f) * 0.3f;
    const float CoverageCorrection = FMath::Lerp(0.2f, 0.0f, FMath::Clamp(Coverage / 0.2f, 0.0f, 1.0f));
    const float ExtinctionScale = FMath::Max(Extinction, 0.001f) / Scale;

    Scalar(TEXT("Cloud Density"), FMath::Clamp((Coverage - CoverageCorrection) * 1.15f, -0.2f, 3.0f));
    Scalar(TEXT("Clouds Scale"), FMath::Max(FormationTextureScale, 0.001f) * 1200000.0f * Scale);
    Scalar(TEXT("Clouds Mip Level"), FMath::Max(FormationMipLevel, 0.0f));
    Scalar(TEXT("Macro Variation"), MacroVariation * FMath::Clamp(Coverage / 0.3f, 0.0f, 1.0f));
    Scalar(TEXT("Macro Scale"), FMath::Max(MacroScale, 0.001f) * 1.35f);
    Scalar(TEXT("Macro Offset"), MacroOffset);
    Scalar(TEXT("Z Formation Shift"), FormationZShift * HeightScale);
    Scalar(TEXT("Bottom Altitude"), BottomKm * 100000.0f);
    Scalar(TEXT("Top Altitude"), (BottomKm + HeightKm) * 100000.0f);
    Scalar(TEXT("Shadows Altitude"), (BottomKm + HeightKm * 0.25f) * 100000.0f);
    // UDS's profile-coordinate height is 1 km at its default 0.7 km physical thickness.
    Scalar(TEXT("Cloud Layer Height"), 100000.0f * Scale * HeightScale);
    Scalar(TEXT("Cloud Shadow Falloff"), 15000.0f * Scale * HeightScale);
    const float NoiseScale = FMath::Max(Noise3DScale, 0.001f) * Scale;
    Vector(TEXT("3D Noise Scale"), FLinearColor(133333.333f * NoiseScale, 133333.333f * NoiseScale, 77333.333f * NoiseScale, 1.0f));
    Scalar(TEXT("3D Erosion"), FMath::Max(Erosion3D, 0.0f));
    Scalar(TEXT("3D Erosion Power"), FMath::Max(ErosionPower, 0.01f));
    Scalar(TEXT("Minimum Erosion"), FMath::Max(MinimumErosion, 0.0f));
    Scalar(TEXT("High Frequency Noise"), FMath::Max(HighFrequencyNoise, 0.0f));
    Scalar(TEXT("HF Octaves"), static_cast<float>(FMath::Clamp(HighFrequencyNoiseLevels, 0, 4)));
    Scalar(TEXT("HF Distortion"), FMath::Max(HighFrequencyDistortion, 0.0f));
    Scalar(TEXT("HF Octave Zero Distance"), FMath::Max(HighFrequencyNoiseDistance, 1.0f) * Scale * (bCinematicOffline ? 2.0f : 1.0f));
    Scalar(TEXT("Extinction Scale"), ExtinctionScale);
    Scalar(TEXT("Outer Emit Limit"), FMath::Max(ExtinctionScale / 10.0f, 1.0f) * 0.07f);
    Scalar(TEXT("Ambient Occlusion"), FMath::Clamp(AmbientOcclusion, 0.0f, 1.0f));
    Scalar(TEXT("PhaseG"), FMath::Clamp(PhaseG, -0.99f, 0.99f));
    Scalar(TEXT("PhaseG2"), FMath::Clamp(PhaseG2, -0.99f, 0.99f));
    Scalar(TEXT("Phase Blend"), FMath::Clamp(PhaseBlend, 0.0f, 1.0f));
    Scalar(TEXT("MultiScattering Contribution"), FMath::Clamp(MultiScatteringContribution, 0.0f, 1.0f));
    Scalar(TEXT("MultiScattering Occlusion"), FMath::Clamp(MultiScatteringOcclusion, 0.0f, 1.0f));
    Scalar(TEXT("Eccentricity"), FMath::Clamp(MultiScatteringEccentricity, 0.0f, 1.0f));
    Vector(TEXT("Albedo"), Albedo);
    Vector(TEXT("Top Emissive Color"), TopEmissiveColor);
    Vector(TEXT("Bottom Emissive Color"), BottomEmissiveColor);
    Scalar(TEXT("Lerp to Simplified"), 0.0f);
    Scalar(TEXT("Volumetric Cloud Target Active"), 0.0f);
    float RendererBottomKm = BottomKm;
    float RendererHeightKm = HeightKm;
    FString LayerWarning;
    if (bUseLayeredMaterial)
    {
        if (!UpdateLayerData(RendererBottomKm, RendererHeightKm, LayerWarning))
        {
            CloudStatus = LayerWarning;
            VolumetricCloud->SetVisibility(false);
            ReleaseQualityRequest();
            ReleaseController();
            return;
        }
        // The layered shader uses normalized height over the entire stack.
        // Its private map supplies absolute per-deck density and extinction.
        Scalar(TEXT("Bottom Altitude"), RendererBottomKm * 100000.0f);
        Scalar(TEXT("Top Altitude"), (RendererBottomKm + RendererHeightKm) * 100000.0f);
        Scalar(TEXT("Extinction Scale"), 1.0f / Scale);
        CloudMID->SetTextureParameterValue(TEXT("OnlyCloudsLayerMap"), LayerDataTexture);
    }
    UpdateMotionParameters();

    for (const TPair<FName, float>& Override : ScalarOverrides)
    {
        CollectionInstance->SetScalarParameterValue(Override.Key, Override.Value);
    }
    for (const TPair<FName, FLinearColor>& Override : VectorOverrides)
    {
        CollectionInstance->SetVectorParameterValue(Override.Key, Override.Value);
    }

    VolumetricCloud->SetLayerBottomAltitude(RendererBottomKm);
    VolumetricCloud->SetLayerHeight(RendererHeightKm);
    VolumetricCloud->SetPlanetRadius(FMath::Clamp(PlanetRadiusKm, 0.1f, 10000.0f));
    VolumetricCloud->SetTracingMaxDistance(FMath::Max(TracingMaxDistanceKm, 0.1f) * Scale);
    VolumetricCloud->SetTracingStartMaxDistance(FMath::Max(TracingStartMaxDistanceKm, 1.0f) * Scale);
    VolumetricCloud->SetViewSampleCountScale(FMath::Max(bCinematicOffline ? CinematicViewSampleScale : RealtimeViewSampleScale, 0.05f));
    VolumetricCloud->SetShadowViewSampleCountScale(FMath::Max(ShadowViewSampleScale, 0.05f));
    VolumetricCloud->SetReflectionViewSampleCountScale(FMath::Max(ReflectionViewSampleScale, 0.05f));
    VolumetricCloud->SetShadowReflectionViewSampleCountScale(FMath::Max(ShadowReflectionSampleScale, 0.05f));
    VolumetricCloud->SetShadowTracingDistance(FMath::Max(ShadowTracingDistanceKm, 0.01f) * Scale);
    VolumetricCloud->SetStopTracingTransmittanceThreshold(FMath::Clamp(StopTracingTransmittanceThreshold, 0.0f, 1.0f));
    VolumetricCloud->SetbUsePerSampleAtmosphericLightTransmittance(bPerSampleAtmosphereTransmittance);
    VolumetricCloud->SetVisibleInRealTimeSkyCaptures(bVisibleInSkyLightCaptures);
    VolumetricCloud->SetVisibility(true);
    bCloudReady = true;
    const int32 LayerCount = 1 + AdditionalCloudLayers.FilterByPredicate([](const FUDSOnlyCloudLayer& Layer) { return Layer.bEnabled; }).Num();
    CloudStatus = FString::Printf(TEXT("Ready: %d cloud layer%s in one volume. %s"), LayerCount, LayerCount == 1 ? TEXT("") : TEXT("s"), *LayerWarning);
    UpdateQualityRequest();
}

bool AUltraDynamicSkyOnlyClouds::UpdateLayerData(float& OutBottomKm, float& OutHeightKm, FString& OutWarning)
{
    TArray<FUDSOnlyCloudLayer> EnabledCloudDecks;
    FUDSOnlyCloudLayer Base;
    Base.Name = TEXT("Base Layer");
    Base.BottomAltitudeKm = LayerBottomAltitudeKm;
    Base.HeightKm = FMath::Max(LayerHeightKm, 0.1f);
    Base.CloudCoverage = CloudCoverage;
    Base.Extinction = Extinction;
    Base.FormationTextureScale = FormationTextureScale;
    EnabledCloudDecks.Add(Base);
    for (const FUDSOnlyCloudLayer& Layer : AdditionalCloudLayers)
    {
        if (Layer.bEnabled)
        {
            EnabledCloudDecks.Add(Layer);
        }
    }
    if (!FMath::IsFinite(CloudScale) || !FMath::IsFinite(FormationTextureScale))
    {
        OutWarning = TEXT("Cloud Scale and Formation Texture Scale must be finite numbers.");
        return false;
    }
    for (const FUDSOnlyCloudLayer& Layer : EnabledCloudDecks)
    {
        if (!FMath::IsFinite(Layer.BottomAltitudeKm) || !FMath::IsFinite(Layer.HeightKm)
            || !FMath::IsFinite(Layer.CloudCoverage) || !FMath::IsFinite(Layer.Extinction)
            || !FMath::IsFinite(Layer.FormationTextureScale) || !FMath::IsFinite(Layer.FormationPhase)
            || !FMath::IsFinite(Layer.FormationMipOffset)
            || !FMath::IsFinite(Layer.BottomAltitudeKm + FMath::Max(Layer.HeightKm, 0.1f)))
        {
            OutWarning = FString::Printf(TEXT("%s contains a non-finite or overflowing value. Correct its layer controls before rendering."), *Layer.Name.ToString());
            return false;
        }
    }
    if (EnabledCloudDecks.Num() > OnlyCloudsLayers::MaxLayers)
    {
        OutWarning = FString::Printf(TEXT("Too many enabled cloud layers: %d. The supported maximum is %d including the base. Disable or remove an extra layer."), EnabledCloudDecks.Num(), OnlyCloudsLayers::MaxLayers);
        return false;
    }
    EnabledCloudDecks.StableSort([](const FUDSOnlyCloudLayer& A, const FUDSOnlyCloudLayer& B)
    {
        return A.BottomAltitudeKm < B.BottomAltitudeKm;
    });

    float Minimum = EnabledCloudDecks[0].BottomAltitudeKm;
    float Maximum = Minimum + FMath::Max(EnabledCloudDecks[0].HeightKm, 0.1f);
    uint32 DataHash = 0;
    const auto HashValue = [&DataHash](const auto& Value)
    {
        DataHash = HashCombineFast(DataHash, GetTypeHash(Value));
    };
    for (const FUDSOnlyCloudLayer& Layer : EnabledCloudDecks)
    {
        Minimum = FMath::Min(Minimum, Layer.BottomAltitudeKm);
        Maximum = FMath::Max(Maximum, Layer.BottomAltitudeKm + FMath::Max(Layer.HeightKm, 0.1f));
        HashValue(Layer.BottomAltitudeKm);
        HashValue(Layer.HeightKm);
        HashValue(Layer.CloudCoverage);
        HashValue(Layer.Extinction);
        HashValue(Layer.FormationTextureScale);
        HashValue(Layer.FormationPhase);
        HashValue(Layer.FormationMipOffset);
    }
    HashValue(FormationTextureScale);
    const float Span = FMath::Max(Maximum - Minimum, 0.1f);
    const float Scale = FMath::Max(CloudScale, 0.001f);
    OutBottomKm = Minimum * Scale;
    OutHeightKm = Span * Scale;
    if (!FMath::IsFinite(Span) || !FMath::IsFinite(OutBottomKm) || !FMath::IsFinite(OutHeightKm)
        || !FMath::IsFinite(OutBottomKm * 100000.0f)
        || !FMath::IsFinite((OutBottomKm + OutHeightKm) * 100000.0f))
    {
        OutWarning = TEXT("The cloud stack bounds exceed the supported numeric range. Reduce altitude, thickness or overall Cloud Scale.");
        return false;
    }
    for (const FUDSOnlyCloudLayer& Layer : EnabledCloudDecks)
    {
        if (FMath::Max(Layer.HeightKm, 0.1f) / Span < 0.005f)
        {
            OutWarning = TEXT("A layer is very thin compared with the full stack; reduce spacing or increase its thickness to avoid losing detail in the layer map.");
            break;
        }
    }
    if (bHasLayerData && IsValid(LayerDataTexture) && LastLayerDataHash == DataHash)
    {
        OutWarning = CachedLayerDataWarning;
        return true;
    }

    // Reproduce the UDS CloudLayerMapBrush into a private 6x1000 linear float table.
    // Each pair of columns is identical; bilinear samples land between the pair.
    TArray<FFloat16Color> Pixels;
    Pixels.SetNumUninitialized(OnlyCloudsLayers::Width * OnlyCloudsLayers::Height);
    bool bClampedHalfFloat = false;
    const auto HalfSafe = [&bClampedHalfFloat](double Value)
    {
        constexpr double HalfMaximum = 65504.0;
        if (Value < -HalfMaximum || Value > HalfMaximum)
        {
            bClampedHalfFloat = true;
        }
        return static_cast<float>(FMath::Clamp(Value, -HalfMaximum, HalfMaximum));
    };
    for (int32 Row = 0; Row < OnlyCloudsLayers::Height; ++Row)
    {
        const float H = 1.0f - (static_cast<float>(Row) + 0.5f) / static_cast<float>(OnlyCloudsLayers::Height);
        FLinearColor Stripe1(0, 0, 0, 1);
        FLinearColor Stripe2(0, 0, 0, 1);
        FLinearColor Stripe3(0, 0, 0, 1);
        float PreviousTop = 0.0f;
        for (int32 Index = 0; Index < EnabledCloudDecks.Num(); ++Index)
        {
            const FUDSOnlyCloudLayer& Layer = EnabledCloudDecks[Index];
            const float B = (Layer.BottomAltitudeKm - Minimum) / Span;
            const float T = (Layer.BottomAltitudeKm + FMath::Max(Layer.HeightKm, 0.1f) - Minimum) / Span;
            const float BlendTop = Index == 0 ? 0.0f : FMath::Max(B, PreviousTop);
            const float Blend = BlendTop > B + SMALL_NUMBER
                ? FMath::Clamp((H - B) / (BlendTop - B), 0.0f, 1.0f)
                : (H >= B ? 1.0f : 0.0f);
            const float AltitudeDenominator = FMath::Max(T - B - 0.002f, SMALL_NUMBER);
            const float LocalAltitude = FMath::Clamp((H - B - 0.001f) / AltitudeDenominator, 0.0f, 1.0f);
            const float CoverageMask = H > B + 0.002f && H <= T - 0.001f ? 1.0f : 0.0f;
            const float FormationFrequency = HalfSafe(static_cast<double>(FMath::Max(FormationTextureScale, 0.001f)) / FMath::Max(Layer.FormationTextureScale, 0.001f));
            const FLinearColor New1(FormationFrequency, FormationFrequency, LocalAltitude, 1.0f);
            const FLinearColor New2(0.0f, OnlyCloudsLayers::DensityFromCoverage(Layer.CloudCoverage) * CoverageMask, 0.0f, 1.0f);
            const FLinearColor New3(HalfSafe(FMath::Max(Layer.Extinction, 0.001f)), HalfSafe(Layer.FormationPhase), HalfSafe(Layer.FormationMipOffset), 1.0f);
            Stripe1 = FMath::Lerp(Stripe1, New1, Blend);
            Stripe2 = FMath::Lerp(Stripe2, New2, Blend);
            Stripe3 = FMath::Lerp(Stripe3, New3, Blend);
            PreviousTop = T;
        }
        const int32 Start = Row * OnlyCloudsLayers::Width;
        Pixels[Start] = Pixels[Start + 1] = FFloat16Color(Stripe1);
        Pixels[Start + 2] = Pixels[Start + 3] = FFloat16Color(Stripe2);
        Pixels[Start + 4] = Pixels[Start + 5] = FFloat16Color(Stripe3);
    }
    if (bClampedHalfFloat)
    {
        OutWarning += TEXT(" Extreme formation frequency, phase, mip or extinction values were limited to the layer map's finite +/-65504 range.");
    }

    if (!IsValid(LayerDataTexture))
    {
        LayerDataTexture = UTexture2D::CreateTransient(OnlyCloudsLayers::Width, OnlyCloudsLayers::Height, PF_FloatRGBA);
        if (!IsValid(LayerDataTexture))
        {
            OutWarning = TEXT("Could not create the private cloud-layer texture.");
            return false;
        }
        LayerDataTexture->SRGB = false;
        LayerDataTexture->NeverStream = true;
        LayerDataTexture->Filter = TF_Bilinear;
        LayerDataTexture->AddressX = TA_Clamp;
        LayerDataTexture->AddressY = TA_Clamp;
        LayerDataTexture->CompressionSettings = TC_HDR;
#if WITH_EDITORONLY_DATA
        LayerDataTexture->MipGenSettings = TMGS_NoMipmaps;
#endif
    }
    const uint32 ByteCount = Pixels.Num() * sizeof(FFloat16Color);
    FTexture2DMipMap& Mip = LayerDataTexture->GetPlatformData()->Mips[0];
    Mip.BulkData.Lock(LOCK_READ_WRITE);
    // A texture resource can discard its bulk copy after initialization.
    // Reallocate explicitly before retaining the latest table for resource recreation.
    void* StoredPixels = Mip.BulkData.Realloc(ByteCount);
    FMemory::Memcpy(StoredPixels, Pixels.GetData(), ByteCount);
    Mip.BulkData.Unlock();
    if (!LayerDataTexture->GetResource())
    {
        LayerDataTexture->UpdateResource();
    }
    else
    {
        uint8* Upload = static_cast<uint8*>(FMemory::Malloc(ByteCount));
        FMemory::Memcpy(Upload, Pixels.GetData(), ByteCount);
        FUpdateTextureRegion2D* Region = new FUpdateTextureRegion2D(0, 0, 0, 0, OnlyCloudsLayers::Width, OnlyCloudsLayers::Height);
        LayerDataTexture->UpdateTextureRegions(0, 1, Region, OnlyCloudsLayers::Width * sizeof(FFloat16Color), sizeof(FFloat16Color), Upload,
            [](uint8* Source, const FUpdateTextureRegion2D* Regions)
            {
                FMemory::Free(Source);
                delete Regions;
            });
    }
    LastLayerDataHash = DataHash;
    CachedLayerDataWarning = OutWarning;
    bHasLayerData = true;
    return true;
}

void AUltraDynamicSkyOnlyClouds::AddCloudLayer()
{
    if (IsTemplate())
    {
        return;
    }
    const int32 EnabledExtras = AdditionalCloudLayers.FilterByPredicate([](const FUDSOnlyCloudLayer& Layer) { return Layer.bEnabled; }).Num();
    if (EnabledExtras >= OnlyCloudsLayers::MaxLayers - 1)
    {
        CloudStatus = FString::Printf(TEXT("Maximum of %d active layers reached. Disable or remove an extra layer first."), OnlyCloudsLayers::MaxLayers);
        return;
    }
#if WITH_EDITOR
    TUniquePtr<FScopedTransaction> Transaction;
    if (GetWorld() && GetWorld()->WorldType == EWorldType::Editor)
    {
        Transaction = MakeUnique<FScopedTransaction>(NSLOCTEXT("OnlyClouds", "AddCloudLayer", "Add Cloud Layer"));
    }
#endif
    Modify();
    float HighestTop = LayerBottomAltitudeKm + FMath::Max(LayerHeightKm, 0.1f);
    for (const FUDSOnlyCloudLayer& Layer : AdditionalCloudLayers)
    {
        if (Layer.bEnabled)
        {
            HighestTop = FMath::Max(HighestTop, Layer.BottomAltitudeKm + FMath::Max(Layer.HeightKm, 0.1f));
        }
    }
    FUDSOnlyCloudLayer Layer;
    int32 NameIndex = AdditionalCloudLayers.Num() + 2;
    do
    {
        Layer.Name = FName(*FString::Printf(TEXT("Cloud Layer %02d"), NameIndex++));
    }
    while (AdditionalCloudLayers.ContainsByPredicate([&Layer](const FUDSOnlyCloudLayer& Existing) { return Existing.Name == Layer.Name; }));
    Layer.BottomAltitudeKm = HighestTop + 0.2f;
    Layer.HeightKm = FMath::Max(LayerHeightKm, 0.1f);
    Layer.CloudCoverage = CloudCoverage;
    Layer.Extinction = Extinction;
    Layer.FormationTextureScale = FormationTextureScale;
    AdditionalCloudLayers.Add(Layer);
    RefreshClouds();
}

void AUltraDynamicSkyOnlyClouds::UpdateMotionParameters()
{
    const TWeakObjectPtr<AUltraDynamicSkyOnlyClouds>* CloudControllerOwner = OnlyCloudsLayers::Controllers.Find(GetWorld());
    if (!IsValid(CollectionInstance) || !CloudControllerOwner || CloudControllerOwner->Get() != this)
    {
        return;
    }
    const double Scale = FMath::Max(CloudScale, 0.001f);
    const double Angle = FMath::DegreesToRadians(static_cast<double>(CloudDirection) - 180.0);
    const FVector Direction(FMath::Cos(Angle), FMath::Sin(Angle), 0.0);
    const FVector PhaseDirection(Direction.X, Direction.Y, -NoiseVerticalMovement);
    const FVector PhaseVector = PhaseDirection * (0.02 * FMath::Max(FormationTextureScale, 0.001f) * 1200000.0 * Scale);
    const FVector Movement = Direction * (AnimationSeconds * CloudMovementSpeed);
    const double BottomCm = LayerBottomAltitudeKm * Scale * 100000.0;
    const FVector Position = FormationOffset + Movement - GetActorLocation() - FVector(0.0, 0.0, BottomCm) + PhaseVector * CloudPhase;
    CollectionInstance->SetVectorParameterValue(TEXT("Clouds Position"), FLinearColor(Position.X, Position.Y, Position.Z, 1.0f));
    CollectionInstance->SetVectorParameterValue(TEXT("Clouds Position Phase"), FLinearColor::Transparent);
    CollectionInstance->SetScalarParameterValue(TEXT("Clouds B Time"), static_cast<float>(AnimationSeconds) + CloudPhase);
    CollectionInstance->SetScalarParameterValue(TEXT("Clouds B Speed"), FormationChangeSpeed);
    // Advanced shader overrides keep their advertised final precedence while animating.
    for (const FName Name : {FName(TEXT("Clouds B Time")), FName(TEXT("Clouds B Speed"))})
    {
        if (const float* Value = ScalarOverrides.Find(Name))
        {
            CollectionInstance->SetScalarParameterValue(Name, *Value);
        }
    }
    for (const FName Name : {FName(TEXT("Clouds Position")), FName(TEXT("Clouds Position Phase"))})
    {
        if (const FLinearColor* Value = VectorOverrides.Find(Name))
        {
            CollectionInstance->SetVectorParameterValue(Name, *Value);
        }
    }
}

void AUltraDynamicSkyOnlyClouds::UpdateQualityRequest()
{
    const bool bWantsQuality = IsCloudWorld() && bCloudReady && IsValid(CloudMID)
        && IsValid(CollectionInstance) && bCinematicOffline && bApplyCloudRendererQuality;
    if (bWantsQuality && !bQualityRequested)
    {
        OnlyCloudsQuality::Acquire(this);
        bQualityRequested = true;
    }
    else if (!bWantsQuality && bQualityRequested)
    {
        ReleaseQualityRequest();
    }
}

void AUltraDynamicSkyOnlyClouds::ReleaseQualityRequest()
{
    OnlyCloudsQuality::Release(this);
    bQualityRequested = false;
}

void AUltraDynamicSkyOnlyClouds::ApplyCinematicCloudQuality()
{
    Modify();
    bCinematicOffline = true;
    bApplyCloudRendererQuality = true;
    RefreshClouds();
}

void AUltraDynamicSkyOnlyClouds::RestorePreviousCloudQuality()
{
    Modify();
    bApplyCloudRendererQuality = false;
    ReleaseQualityRequest();
}

void AUltraDynamicSkyOnlyClouds::ResetAnimationTime()
{
    AnimationSeconds = 0.0;
    UpdateMotionParameters();
}

void AUltraDynamicSkyOnlyClouds::OnConstruction(const FTransform& Transform)
{
    Super::OnConstruction(Transform);
    RefreshClouds();
}

void AUltraDynamicSkyOnlyClouds::BeginPlay()
{
    Super::BeginPlay();
    AnimationSeconds = 0.0;
    RefreshClouds();
}

void AUltraDynamicSkyOnlyClouds::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (bWaitingForController)
    {
        ControllerRetrySeconds += FMath::Max(DeltaSeconds, 0.0f);
        if (ControllerRetrySeconds >= 0.25f)
        {
            bNeedsRefresh = true;
            ControllerRetrySeconds = 0.0f;
        }
    }
    if (bNeedsRefresh || GetInterpolatedStateHash() != LastInterpolatedStateHash)
    {
        RefreshClouds();
    }
    if (!IsCloudWorld())
    {
        return;
    }
    UpdateQualityRequest();
    if (bCloudReady && bAnimateClouds && IsValid(CollectionInstance))
    {
        AnimationSeconds += FMath::Max(DeltaSeconds, 0.0f);
        UpdateMotionParameters();
    }
}

uint32 AUltraDynamicSkyOnlyClouds::GetInterpolatedStateHash() const
{
    // Sequencer changes reflected Interp properties directly. Detect changes without
    // rebuilding the material or touching the collection on otherwise idle frames.
    uint32 Hash = 0;
    const auto Add = [&Hash](const auto& Value)
    {
        Hash = HashCombineFast(Hash, GetTypeHash(Value));
    };
    Add(LayerBottomAltitudeKm);
    Add(LayerHeightKm);
    Add(CloudScale);
    Add(CloudCoverage);
    Add(FormationTextureScale);
    Add(FormationZShift);
    Add(MacroVariation);
    Add(MacroScale);
    Add(MacroOffset);
    Add(Noise3DScale);
    Add(Erosion3D);
    Add(ErosionPower);
    Add(MinimumErosion);
    Add(HighFrequencyNoise);
    Add(HighFrequencyNoiseDistance);
    Add(HighFrequencyDistortion);
    Add(Extinction);
    Add(Albedo);
    Add(TopEmissiveColor);
    Add(BottomEmissiveColor);
    Add(AmbientOcclusion);
    Add(PhaseG);
    Add(PhaseG2);
    Add(PhaseBlend);
    Add(MultiScatteringContribution);
    Add(MultiScatteringOcclusion);
    Add(MultiScatteringEccentricity);
    Add(CloudPhase);
    Add(FormationOffset);
    Add(CloudDirection);
    Add(CloudMovementSpeed);
    Add(FormationChangeSpeed);
    Add(NoiseVerticalMovement);
    Add(AdditionalCloudLayers.Num());
    for (const FUDSOnlyCloudLayer& Layer : AdditionalCloudLayers)
    {
        Add(Layer.Name);
        Add(Layer.bEnabled);
        Add(Layer.BottomAltitudeKm);
        Add(Layer.HeightKm);
        Add(Layer.CloudCoverage);
        Add(Layer.Extinction);
        Add(Layer.FormationTextureScale);
        Add(Layer.FormationPhase);
        Add(Layer.FormationMipOffset);
    }
    return Hash;
}

void AUltraDynamicSkyOnlyClouds::PostLoad()
{
    Super::PostLoad();
    bNeedsRefresh = true;
}

void AUltraDynamicSkyOnlyClouds::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    ReleaseQualityRequest();
    ReleaseController();
    Super::EndPlay(EndPlayReason);
}

void AUltraDynamicSkyOnlyClouds::Destroyed()
{
    ReleaseQualityRequest();
    ReleaseController();
    Super::Destroyed();
}

void AUltraDynamicSkyOnlyClouds::BeginDestroy()
{
    // Editor map unloads can go directly through GC without gameplay EndPlay.
    ReleaseQualityRequest();
    ReleaseController();
    Super::BeginDestroy();
}

#if WITH_EDITOR
void AUltraDynamicSkyOnlyClouds::PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent)
{
    Super::PostEditChangeProperty(PropertyChangedEvent);
    if (IsValid(this))
    {
        RefreshClouds();
    }
}

void AUltraDynamicSkyOnlyClouds::PostEditUndo()
{
    Super::PostEditUndo();
    bNeedsRefresh = true;
}
#endif
