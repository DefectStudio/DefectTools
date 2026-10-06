#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "UltraDynamicSkyOnlyClouds.generated.h"

class UMaterialInterface;
class UMaterialInstanceDynamic;
class UMaterialParameterCollection;
class UMaterialParameterCollectionInstance;
class UTexture;
class UTexture2D;
class UVolumetricCloudComponent;

/** One extra cloud deck, rendered together with the original base layer. */
USTRUCT(BlueprintType)
struct CLOUDGENERATORTOOLS_API FUDSOnlyCloudLayer
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Cloud Layer")
    FName Name = TEXT("Cloud Layer");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Cloud Layer")
    bool bEnabled = true;

    /** Signed altitude. Overall Cloud Scale applies to this value and to thickness. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Cloud Layer", meta=(UIMin="-10", UIMax="10", Units="km"))
    float BottomAltitudeKm = 1.5f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Cloud Layer", meta=(ClampMin="0.1", UIMax="5", Units="km"))
    float HeightKm = 0.7f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Cloud Layer", meta=(ClampMin="0", ClampMax="10"))
    float CloudCoverage = 3.8f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Cloud Layer", meta=(ClampMin="0.001", UIMax="30"))
    float Extinction = 10.0f;

    /** Larger values make larger formation features, matching the base-layer Formation Texture Scale control. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Cloud Layer", meta=(ClampMin="0.001", UIMin="0.1", UIMax="5"))
    float FormationTextureScale = 1.0f;

    /** Independent formation variation, added to the shared cloud animation phase. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Cloud Layer", meta=(UIMin="0", UIMax="100"))
    float FormationPhase = 0.0f;

    /** Added formation texture mip level; higher values soften this layer's formation. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Cloud Layer", meta=(UIMin="0", UIMax="5"))
    float FormationMipOffset = 0.0f;
};

/**
 * Standalone UDS volume renderer. Owns no lighting or environment components.
 * Use one active OnlyClouds actor per world: its isolated parameter collection is world-wide,
 * matching Unreal's single active sky-cloud layer. Original UDS collections are never written.
 */
UCLASS(Blueprintable, HideCategories=(Input, Collision, Physics, Replication, Networking))
class CLOUDGENERATORTOOLS_API AUltraDynamicSkyOnlyClouds : public AActor
{
    GENERATED_BODY()

public:
    AUltraDynamicSkyOnlyClouds();

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Only Clouds")
    TObjectPtr<UVolumetricCloudComponent> VolumetricCloud;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category="Only Clouds")
    FString CloudStatus;

    /** Applies all controls. Interpolated artist controls update automatically; call after other Blueprint runtime edits. */
    UFUNCTION(BlueprintCallable, CallInEditor, Category="Only Clouds")
    void RefreshClouds();

    /** Enables only scene-wide cloud rendering CVars. No light, atmosphere, fog or exposure settings are changed. */
    UFUNCTION(BlueprintCallable, CallInEditor, Category="Only Clouds|Quality")
    void ApplyCinematicCloudQuality();

    /** Disables automatic global cloud quality and restores previous values when no other OnlyClouds actor needs them. */
    UFUNCTION(BlueprintCallable, CallInEditor, Category="Only Clouds|Quality")
    void RestorePreviousCloudQuality();

    /** Restore the deterministic phase without changing artist controls. */
    UFUNCTION(BlueprintCallable, CallInEditor, Category="Only Clouds|Motion")
    void ResetAnimationTime();

    /** Adds an independently adjustable deck above the current stack, preserving the original base layer. */
    UFUNCTION(BlueprintCallable, CallInEditor, Category="Only Clouds|Cloud Layers", meta=(DisplayName="+ Add Cloud Layer"))
    void AddCloudLayer();

    /** Extra decks share global detail, shading, motion and quality. Use the array controls to remove or duplicate a deck. Empty or disabled entries preserve the original single-layer renderer. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Only Clouds|Cloud Layers", meta=(TitleProperty="Name"))
    TArray<FUDSOnlyCloudLayer> AdditionalCloudLayers;

    /** Signed altitude relative to the cloud renderer's ground reference. Negative values lower the layer below it. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Layer", meta=(UIMin="-10.0", UIMax="10.0", Units="km"))
    float LayerBottomAltitudeKm = 0.6f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Layer", meta=(ClampMin="0.1", UIMax="5.0", Units="km"))
    float LayerHeightKm = 0.7f;

    /** Overall physical scale. Scales altitude, thickness, formation, detail and trace distances together. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Layer", meta=(ClampMin="0.001", UIMin="0.1", UIMax="10.0"))
    float CloudScale = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Only Clouds|Layer", meta=(ClampMin="0.1", ClampMax="10000", Units="km"))
    float PlanetRadiusKm = 6360.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Formation", meta=(ClampMin="0.0", ClampMax="10.0"))
    float CloudCoverage = 3.8f;

    /** UDS's large formation size: 1 equals 12 km before overall Cloud Scale. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Formation", meta=(ClampMin="0.001", UIMin="0.1", UIMax="5.0"))
    float FormationTextureScale = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Formation", meta=(UIMin="-2.0", UIMax="2.0"))
    float FormationZShift = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Formation", meta=(ClampMin="0", UIMax="1.0"))
    float MacroVariation = 0.16f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Formation", meta=(ClampMin="0.001", UIMin="0.1", UIMax="5.0"))
    float MacroScale = 1.3f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Formation", meta=(UIMin="-2.0", UIMax="2.0"))
    float MacroOffset = 0.52f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Only Clouds|Formation", meta=(ClampMin="0", UIMax="5.0"))
    float FormationMipLevel = 0.0f;

    /** Optional override. Leave empty to retain the isolated material's UDS formation texture. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Only Clouds|Textures", meta=(AllowedClasses="/Script/Engine.VolumeTexture"))
    TSoftObjectPtr<UTexture> FormationTexture;

    /** Optional override for UDS's 3D erosion texture. The supplied material uses the 128 detail texture. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Only Clouds|Textures", meta=(AllowedClasses="/Script/Engine.VolumeTexture"))
    TSoftObjectPtr<UTexture> DetailNoiseTexture;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Only Clouds|Textures", meta=(AllowedClasses="/Script/Engine.Texture2D"))
    TSoftObjectPtr<UTexture> CloudProfileTexture;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Detail", meta=(ClampMin="0.001", UIMin="0.1", UIMax="5.0"))
    float Noise3DScale = 0.9f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Detail", meta=(ClampMin="0", UIMax="3.0"))
    float Erosion3D = 1.2f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Detail", meta=(ClampMin="0.01", UIMax="8.0"))
    float ErosionPower = 3.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Detail", meta=(ClampMin="0", UIMax="1.0"))
    float MinimumErosion = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Detail", meta=(ClampMin="0", UIMax="1.0"))
    float HighFrequencyNoise = 0.24f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Only Clouds|Detail", meta=(ClampMin="0", ClampMax="4"))
    int32 HighFrequencyNoiseLevels = 2;

    /** Distance in cm at which high-frequency detail fades; doubled in Cinematic / Offline mode. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Detail", meta=(ClampMin="1", UIMax="1000000", Units="cm"))
    float HighFrequencyNoiseDistance = 150000.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Detail", meta=(ClampMin="0", UIMax="1.0"))
    float HighFrequencyDistortion = 0.21f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Shading", meta=(ClampMin="0.001", UIMax="30.0"))
    float Extinction = 10.0f;

    /** Neutral physical cloud color; illuminated by your own atmosphere directional light and sky light. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Shading", meta=(HideAlphaChannel))
    FLinearColor Albedo = FLinearColor::White;

    /** Explicit artist fill only. There is no automatic day/night or exposure-driven emission. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Shading", meta=(HideAlphaChannel))
    FLinearColor TopEmissiveColor = FLinearColor::Black;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Shading", meta=(HideAlphaChannel))
    FLinearColor BottomEmissiveColor = FLinearColor::Black;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Shading", meta=(ClampMin="0", ClampMax="1"))
    float AmbientOcclusion = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Shading", meta=(ClampMin="-0.99", ClampMax="0.99"))
    float PhaseG = 0.85f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Shading", meta=(ClampMin="-0.99", ClampMax="0.99"))
    float PhaseG2 = 0.4f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Shading", meta=(ClampMin="0", ClampMax="1"))
    float PhaseBlend = 0.65f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Shading", meta=(ClampMin="0", ClampMax="1"))
    float MultiScatteringContribution = 0.85f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Shading", meta=(ClampMin="0", ClampMax="1"))
    float MultiScatteringOcclusion = 0.5f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Shading", meta=(ClampMin="0", ClampMax="1"))
    float MultiScatteringEccentricity = 0.4f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Only Clouds|Shading")
    bool bPerSampleAtmosphereTransmittance = false;

    /** Deterministic formation phase. Does not depend on world time, UDS, or a random seed. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Motion", meta=(UIMin="0", UIMax="100"))
    float CloudPhase = 0.0f;

    /** Offset added to the formation coordinates, in centimeters. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Motion", meta=(Units="cm"))
    FVector FormationOffset = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Only Clouds|Motion")
    bool bAnimateClouds = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Motion", meta=(UIMin="0", UIMax="360", Units="deg"))
    float CloudDirection = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Motion", meta=(Units="cm/s", UIMin="0", UIMax="5000"))
    float CloudMovementSpeed = 100.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Motion", meta=(UIMin="0", UIMax="2"))
    float FormationChangeSpeed = 0.7f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category="Only Clouds|Motion", meta=(UIMin="-2", UIMax="2"))
    float NoiseVerticalMovement = 0.25f;

    /** High sample count, full formation material and extended fine detail distance. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Only Clouds|Quality", meta=(DisplayName="Cinematic / Offline"))
    bool bCinematicOffline = true;

    /** Opt-in persistent, scene-wide CLOUD-ONLY renderer settings. Uses the UDS offline renderer mode and sample caps. Restores prior values when no OnlyClouds actor needs them, if still unchanged by another system. No lighting/exposure CVars are touched. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Only Clouds|Quality", meta=(DisplayName="Apply Cinematic Cloud Renderer Settings"))
    bool bApplyCloudRendererQuality = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Only Clouds|Quality", meta=(ClampMin="0.05", UIMax="30"))
    float CinematicViewSampleScale = 25.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Only Clouds|Quality", meta=(ClampMin="0.05", UIMax="8"))
    float RealtimeViewSampleScale = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Only Clouds|Quality", meta=(ClampMin="0.05", UIMax="8"))
    float ShadowViewSampleScale = 0.6f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Only Clouds|Quality", meta=(ClampMin="0.05", UIMax="8"))
    float ReflectionViewSampleScale = 2.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Only Clouds|Quality", meta=(ClampMin="0.05", UIMax="8"))
    float ShadowReflectionSampleScale = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Only Clouds|Quality", meta=(ClampMin="0.1", UIMax="100", Units="km"))
    float TracingMaxDistanceKm = 20.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Only Clouds|Quality", meta=(ClampMin="1", UIMax="500", Units="km"))
    float TracingStartMaxDistanceKm = 350.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Only Clouds|Quality", meta=(ClampMin="0.01", UIMax="50", Units="km"))
    float ShadowTracingDistanceKm = 0.5f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Only Clouds|Quality", meta=(ClampMin="0", ClampMax="1"))
    float StopTracingTransmittanceThreshold = 0.005f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Only Clouds|Quality")
    bool bVisibleInSkyLightCaptures = true;

    /** Exact shader parameter overrides, applied after the artist controls. Removing an entry restores its normal/default value. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Only Clouds|Advanced Shader")
    TMap<FName, float> ScalarOverrides;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Only Clouds|Advanced Shader")
    TMap<FName, FLinearColor> VectorOverrides;

    /** Isolated UDS material only; never assign the original full-sky material. */
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Only Clouds|Assets")
    TSoftObjectPtr<UMaterialInterface> CloudMaterial;

    /** Isolated multilayer material; selected automatically when an extra enabled deck is present. */
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Only Clouds|Assets")
    TSoftObjectPtr<UMaterialInterface> LayeredCloudMaterial;

    /** Private OnlyClouds collection. Original UltraDynamicSky collections are rejected. */
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Only Clouds|Assets")
    TSoftObjectPtr<UMaterialParameterCollection> CloudParameters;

    virtual void OnConstruction(const FTransform& Transform) override;
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void PostLoad() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual void Destroyed() override;
    virtual void BeginDestroy() override;
    virtual bool ShouldTickIfViewportsOnly() const override { return true; }
#if WITH_EDITOR
    virtual void PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent) override;
    virtual void PostEditUndo() override;
#endif

private:
    UPROPERTY(Transient, DuplicateTransient)
    TObjectPtr<UMaterialInstanceDynamic> CloudMID;

    UPROPERTY(Transient, DuplicateTransient)
    TObjectPtr<UMaterialParameterCollectionInstance> CollectionInstance;

    UPROPERTY(Transient, DuplicateTransient)
    TObjectPtr<UTexture2D> LayerDataTexture;

    TWeakObjectPtr<UMaterialInterface> LastMaterial;
    bool bNeedsRefresh = true;
    bool bCloudReady = false;
    bool bQualityRequested = false;
    double AnimationSeconds = 0.0;
    uint32 LastInterpolatedStateHash = 0;
    bool bWaitingForController = false;
    float ControllerRetrySeconds = 0.0f;
    uint32 LastLayerDataHash = 0;
    bool bHasLayerData = false;
    FString CachedLayerDataWarning;

    bool IsCloudWorld() const;
    uint32 GetInterpolatedStateHash() const;
    bool TryAcquireController();
    void ReleaseController();
    bool UpdateLayerData(float& OutBottomKm, float& OutHeightKm, FString& OutWarning);
    void UpdateMotionParameters();
    void UpdateQualityRequest();
    void ReleaseQualityRequest();
};
