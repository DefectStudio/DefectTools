#pragma once

#include "CoreMinimal.h"
#include "Components/PrimitiveComponent.h"
#include "GameFramework/Actor.h"
#include "Engine/DataAsset.h"
#include "CloudGeneratorActor.generated.h"

class UHeterogeneousVolumeComponent;
class UMaterialInterface;
class UMaterialInstanceDynamic;
class UTexture2D;
class UVolumeTexture;
class ACloudGeneratorActor;
class ACloudGuideActor;

UENUM(BlueprintType)
enum class ECloudGuideShape : uint8
{
    Sphere UMETA(DisplayName = "Sphere"),
    Box UMETA(DisplayName = "Box")
};

UENUM(BlueprintType)
enum class ECloudGuideOperation : uint8
{
    Add UMETA(DisplayName = "Additive"),
    Subtract UMETA(DisplayName = "Subtractive")
};

UENUM(BlueprintType)
enum class ECloudPreviewQuality : uint8
{
    Preview UMETA(DisplayName = "Preview"),
    Cinematic UMETA(DisplayName = "Cinematic")
};

UENUM(BlueprintType)
enum class ECloudStyle : uint8
{
    Cumulus UMETA(DisplayName = "Cumulus"),
    Cumulonimbus UMETA(DisplayName = "Cumulonimbus"),
    Cirrus UMETA(DisplayName = "Cirrus")
};

UENUM(BlueprintType)
enum class ECloudBillowStyle : uint8
{
    Classic = 0 UMETA(DisplayName = "Classic"),
    Cauliflower = 1 UMETA(DisplayName = "Cauliflower"),
    SoftRolling = 2 UMETA(DisplayName = "Soft Rolling"),
    Turbulent = 3 UMETA(DisplayName = "Turbulent")
};

UENUM(BlueprintType)
enum class ECloudNoiseLayout : uint8
{
    PackedRGB = 0 UMETA(DisplayName = "Packed RGB"),
    Grayscale = 1 UMETA(DisplayName = "Grayscale (Red Channel)")
};

/** One guide in a portable recipe. Transforms are relative to the generator. */
USTRUCT(BlueprintType)
struct CLOUDGENERATORTOOLS_API FCloudGuideRecipe
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") FTransform LocalTransform = FTransform::Identity;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") ECloudGuideShape Shape = ECloudGuideShape::Sphere;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") ECloudGuideOperation Operation = ECloudGuideOperation::Add;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float SoftnessCm = 55.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") bool bEnabled = true;
    UPROPERTY() FGuid GuideId;
};

/** Deterministic editable recipe, independent of actor location and render quality. */
USTRUCT(BlueprintType)
struct CLOUDGENERATORTOOLS_API FCloudRecipe
{
    GENERATED_BODY()
    // Keep the struct default at 1: legacy serialized assets may omit this value.
    // CaptureRecipe explicitly creates version 2 recipes with authored generator scale.
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Cloud") int32 Version = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud", meta = (ToolTip = "Version 2 recipes restore this generator scale. Location and rotation stay where you place the cloud. Version 1 recipes keep the target actor's existing scale.")) FVector GeneratorScale = FVector::OneVector;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") TArray<FCloudGuideRecipe> Guides;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float Density = 2.6f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float Seed = 1.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") FLinearColor CloudColor = FLinearColor(0.95f, 0.97f, 1.0f, 1.0f);
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float SkyFill = 0.45f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float BillowSizeCm = 228.78f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float BillowDepthCm = 550.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float BillowStrength = 1.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float DetailSizeCm = 76.26f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float DetailStrength = 0.45f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") ECloudBillowStyle BillowStyle = ECloudBillowStyle::Classic;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") TSoftObjectPtr<UVolumeTexture> CustomShapeNoiseTexture;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") TSoftObjectPtr<UVolumeTexture> CustomDetailNoiseTexture;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") ECloudNoiseLayout ShapeNoiseLayout = ECloudNoiseLayout::PackedRGB;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") ECloudNoiseLayout DetailNoiseLayout = ECloudNoiseLayout::PackedRGB;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") FVector NoiseTiling = FVector::OneVector;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float NoiseContrast = 1.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float NoiseBrightness = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float NoiseTextureContrast = 1.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float LevelsInputLow = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float LevelsInputMid = 1.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float LevelsInputHigh = 1.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float LevelsOutputLow = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float LevelsOutputHigh = 1.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float WarpAmount = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") bool bAnimated = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float OffsetSpeedX = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float OffsetSpeedY = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float OffsetSpeedZ = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float PhaseSpeed = 0.1f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") FVector TextureOffsetCm = FVector::ZeroVector;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float NoisePhase = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float LargeBreakupAmount = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float LargeBreakupScaleX = 1000.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float LargeBreakupScaleY = 1000.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float LargeBreakupScaleZ = 1000.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float LargeBreakupBrightness = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float LargeBreakupContrast = 1.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float UnionBlendCm = 55.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float UnionGrowthLimitCm = 27.5f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") ECloudStyle CloudStyle = ECloudStyle::Cumulus;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float WispStrength = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") FVector WispStretch = FVector::OneVector;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float WispDirectionDegrees = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float InteriorVariation = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float VerticalDensityGradient = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") float VerticalReferenceHeightCm = 3000.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud") TSoftObjectPtr<UMaterialInterface> CloudMaterial;
};

/** A saved cloud recipe; it remains editable and is not a baked volume texture. */
UCLASS(BlueprintType)
class CLOUDGENERATORTOOLS_API UCloudRecipePreset : public UDataAsset
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Preset") FCloudRecipe Recipe;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Preset", meta = (MultiLine = "true")) FString Description;
};

/** An editor wire outline; the actual shape is evaluated in the cloud material. */
UCLASS(ClassGroup = Rendering, meta = (BlueprintSpawnableComponent))
class CLOUDGENERATORTOOLS_API UCloudGuideShapeComponent : public UPrimitiveComponent
{
    GENERATED_BODY()
public:
    UCloudGuideShapeComponent();
    virtual FPrimitiveSceneProxy* CreateSceneProxy() override;
    virtual FBoxSphereBounds CalcBounds(const FTransform& LocalToWorld) const override;
};

/** Runtime-present authoring guide. Nonuniform sphere scale produces an ellipsoid. */
UCLASS(Blueprintable, hidecategories = (Replication, Networking, Input, Collision, HLOD, Physics))
class CLOUDGENERATORTOOLS_API ACloudGuideActor : public AActor
{
    GENERATED_BODY()
public:
    ACloudGuideActor();

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Cloud Guide")
    TObjectPtr<UCloudGuideShapeComponent> GuideShape;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Guide")
    ECloudGuideShape Shape = ECloudGuideShape::Sphere;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Guide")
    ECloudGuideOperation Operation = ECloudGuideOperation::Add;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Guide", meta = (ClampMin = "0", UIMin = "0", UIMax = "200", Units = "cm", DisplayName = "Edge Softness"))
    float SoftnessCm = 55.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Guide", meta = (DisplayName = "Enabled"))
    bool bEnabled = true;

    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category = "Cloud Guide")
    TObjectPtr<ACloudGeneratorActor> Generator;

    UPROPERTY() FGuid GuideId;

    UFUNCTION(BlueprintCallable, Category = "Cloud Guide")
    void NotifyGenerator();

    virtual void OnConstruction(const FTransform& Transform) override;
    virtual void PostRegisterAllComponents() override;
    virtual void Destroyed() override;
#if WITH_EDITOR
    virtual bool CanDeleteSelectedActor(FText& OutReason) const override;
    virtual void PostEditMove(bool bFinished) override;
    virtual void PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent) override;
    virtual void PostEditUndo() override;
#endif
private:
    TWeakObjectPtr<ACloudGeneratorActor> LastNotifiedGenerator;
    bool bNotifyingGenerator = false;
};

/** One rendered cloud volume, driven by up to 64 independently editable shape guides. */
UCLASS(Blueprintable, hidecategories = (Replication, Networking, Input, Collision, HLOD, Physics))
class CLOUDGENERATORTOOLS_API ACloudGeneratorActor : public AActor
{
    GENERATED_BODY()
public:
    static constexpr int32 MaxGuides = 64;
    static constexpr int32 GuideDataWidth = 3;

    ACloudGeneratorActor();

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Cloud Generator")
    TObjectPtr<USceneComponent> SceneRoot;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Cloud Generator")
    TObjectPtr<UHeterogeneousVolumeComponent> CloudVolume;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "Cloud Guides")
    TArray<TObjectPtr<ACloudGuideActor>> Guides;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Appearance", meta = (ClampMin = "0", UIMin = "0", UIMax = "8"))
    float Density = 2.6f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Appearance")
    float Seed = 1.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Appearance")
    FLinearColor CloudColor = FLinearColor(0.95f, 0.97f, 1.0f, 1.0f);
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Appearance", meta = (ClampMin = "0", UIMin = "0", UIMax = "2"))
    float SkyFill = 0.45f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Detail", meta = (ClampMin = "0.1", Units = "cm", DisplayName = "Billow Size"))
    float BillowSizeCm = 228.78f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Detail", meta = (ClampMin = "0", Units = "cm", DisplayName = "Billow Depth"))
    float BillowDepthCm = 550.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Detail", meta = (ClampMin = "0", ClampMax = "1", UIMin = "0", UIMax = "1"))
    float BillowStrength = 1.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Detail", meta = (ClampMin = "0.1", Units = "cm", DisplayName = "Detail Size"))
    float DetailSizeCm = 76.26f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Detail", meta = (ClampMin = "0", ClampMax = "1", UIMin = "0", UIMax = "1"))
    float DetailStrength = 0.45f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Noise", meta = (ToolTip = "Changes the billow pattern independently of the cloud family and shape guides. Classic preserves the original noise."))
    ECloudBillowStyle BillowStyle = ECloudBillowStyle::Classic;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Noise", AdvancedDisplay, meta = (DisplayName = "Custom Shape Noise Texture", ToolTip = "Optional seamless, linear 3D Volume Texture for large billows. Clear to use the cloud material's default. Ordinary 2D textures are not accepted."))
    TSoftObjectPtr<UVolumeTexture> CustomShapeNoiseTexture;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Noise", AdvancedDisplay, meta = (DisplayName = "Custom Detail Noise Texture", ToolTip = "Optional seamless, linear 3D Volume Texture for fine erosion and wisps. Clear to use the cloud material's default. Ordinary 2D textures are not accepted."))
    TSoftObjectPtr<UVolumeTexture> CustomDetailNoiseTexture;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Noise", AdvancedDisplay, meta = (ToolTip = "Packed RGB reads different noise patterns from red, green and blue. Grayscale reads only red and reuses it for all three channels."))
    ECloudNoiseLayout ShapeNoiseLayout = ECloudNoiseLayout::PackedRGB;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Noise", AdvancedDisplay, meta = (ToolTip = "Packed RGB reads different erosion patterns from red, green and blue. Grayscale reads only red and reuses it for all three channels."))
    ECloudNoiseLayout DetailNoiseLayout = ECloudNoiseLayout::PackedRGB;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Noise", meta = (ToolTip = "Independent world-axis X, Y and Z noise frequency multipliers. 1 keeps normal size, 0.5 stretches features to twice their length, and 2 halves their length. Type any finite value: negative mirrors the pattern and zero freezes sampling along that axis. Affects the texture pattern, never the guide shape."))
    FVector NoiseTiling = FVector::OneVector;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Noise", meta = (DisplayName = "Billow Contrast", ClampMin = "0.1", ClampMax = "4", UIMin = "0.1", UIMax = "3", ToolTip = "Contrast of the large billow formation after texture adjustments. This is the existing Noise Contrast control; 1 preserves its original contrast."))
    float NoiseContrast = 1.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Noise|Texture Adjustments", meta = (DisplayName = "Noise Texture Brightness", UIMin = "-1", UIMax = "1", ToolTip = "Adds brightness to sampled noise values. Zero is neutral. The slider covers -1 to 1, but typed values may extend beyond it."))
    float NoiseBrightness = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Noise|Texture Adjustments", meta = (DisplayName = "Noise Texture Contrast", ClampMin = "0", UIMin = "0", UIMax = "4", ToolTip = "Contrasts sampled noise around 0.5 before Levels. 1 is neutral; 0 produces a constant value. Typed values may exceed the slider range."))
    float NoiseTextureContrast = 1.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Noise|Texture Adjustments", meta = (DisplayName = "Levels Input Low", ClampMin = "0", ClampMax = "1", UIMin = "0", UIMax = "1", ToolTip = "Input black point in normalized 0 to 1 noise values. If Input High is at or below Input Low, Levels uses a hard threshold at Input Low."))
    float LevelsInputLow = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Noise|Texture Adjustments", meta = (DisplayName = "Levels Input Mid", ClampMin = "0.001", ClampMax = "1000", UIMin = "0.1", UIMax = "3", ToolTip = "Photoshop-style midtone gamma. 1 is neutral, values above 1 brighten midtones, and values below 1 darken them."))
    float LevelsInputMid = 1.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Noise|Texture Adjustments", meta = (DisplayName = "Levels Input High", ClampMin = "0", ClampMax = "1", UIMin = "0", UIMax = "1", ToolTip = "Input white point in normalized 0 to 1 noise values. If at or below Input Low, Levels uses a hard threshold at Input Low."))
    float LevelsInputHigh = 1.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Noise|Texture Adjustments", meta = (DisplayName = "Levels Output Low", ClampMin = "0", ClampMax = "1", UIMin = "0", UIMax = "1", ToolTip = "Output black-point value from 0 to 1. Output Low may exceed Output High to invert the noise."))
    float LevelsOutputLow = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Noise|Texture Adjustments", meta = (DisplayName = "Levels Output High", ClampMin = "0", ClampMax = "1", UIMin = "0", UIMax = "1", ToolTip = "Output white-point value from 0 to 1. Output High may be below Output Low to invert the noise."))
    float LevelsOutputHigh = 1.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Noise", meta = (ClampMin = "0", ClampMax = "1", UIMin = "0", UIMax = "1", ToolTip = "Warps the noise sampling coordinates for irregular billows without changing guide positions. Zero adds no artist-controlled warp."))
    float WarpAmount = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Cloud Animation", meta = (DisplayName = "Animated", DisplayPriority = "0", ToolTip = "Animates the 3D noise inside the fixed guides. Works in a realtime editor viewport and in play. Turning this off freezes the current appearance. Lock Cloud also freezes animation."))
    bool bAnimated = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Cloud Animation", meta = (DisplayName = "Offset Speed X", DisplayPriority = "1", Units = "cm/s", ToolTip = "Noise travel along world X in centimeters per second. Negative values reverse travel. The guides stay in place."))
    float OffsetSpeedX = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Cloud Animation", meta = (DisplayName = "Offset Speed Y", DisplayPriority = "2", Units = "cm/s", ToolTip = "Noise travel along world Y in centimeters per second. Negative values reverse travel. The guides stay in place."))
    float OffsetSpeedY = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Cloud Animation", meta = (DisplayName = "Offset Speed Z", DisplayPriority = "3", Units = "cm/s", ToolTip = "Noise travel along world Z in centimeters per second. Negative values reverse travel. The guides stay in place."))
    float OffsetSpeedZ = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Cloud Animation", meta = (DisplayName = "Phase Speed", DisplayPriority = "4", ToolTip = "Noise evolution in phase units per second. Different noise layers move at different rates to reshape the billows. Zero stops evolution; negative values reverse it."))
    float PhaseSpeed = 0.1f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, AdvancedDisplay, Category = "Cloud Animation", meta = (DisplayName = "Texture Offset", Units = "cm", ToolTip = "Current saved noise travel in world-axis centimeters. With Animated off, key this directly in Sequencer for deterministic animation and scrubbing."))
    FVector TextureOffsetCm = FVector::ZeroVector;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, AdvancedDisplay, Category = "Cloud Animation", meta = (DisplayName = "Noise Phase", ToolTip = "Current saved noise evolution. With Animated off, key this directly in Sequencer for deterministic animation and scrubbing. Zero with zero Texture Offset preserves the original cloud."))
    float NoisePhase = 0.0f;

    UFUNCTION(CallInEditor, BlueprintCallable, Category = "Cloud Animation", meta = (DisplayName = "Reset Cloud Animation", ToolTip = "Resets Texture Offset and Noise Phase to zero without changing speeds, guides, or appearance controls. Unlock the cloud first."))
    void ResetCloudAnimation();


    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Large Breakup", meta = (DisplayName = "Amount", ClampMin = "0", ClampMax = "1", UIMin = "0", UIMax = "1", DisplayPriority = "0", ToolTip = "Independent subtractive 3D noise through the whole cloud, including its solid interior. 0 disables breakup; 1 allows fully open gaps. Does not change the guides."))
    float LargeBreakupAmount = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Large Breakup", meta = (DisplayName = "Scale X", ClampMin = "0.01", Units = "cm", DisplayPriority = "1", ToolTip = "Approximate breakup feature size along world X, in centimeters. Larger values stretch the gaps along this axis. Independent of billow tiling and guide scale."))
    float LargeBreakupScaleX = 1000.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Large Breakup", meta = (DisplayName = "Scale Y", ClampMin = "0.01", Units = "cm", DisplayPriority = "2", ToolTip = "Approximate breakup feature size along world Y, in centimeters. Larger values stretch the gaps along this axis. Independent of billow tiling and guide scale."))
    float LargeBreakupScaleY = 1000.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Large Breakup", meta = (DisplayName = "Scale Z", ClampMin = "0.01", Units = "cm", DisplayPriority = "3", ToolTip = "Approximate breakup feature size along world Z, in centimeters. Larger values stretch the gaps along this axis. Independent of billow tiling and guide scale."))
    float LargeBreakupScaleZ = 1000.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Large Breakup", meta = (DisplayName = "Brightness", UIMin = "-1", UIMax = "1", DisplayPriority = "4", ToolTip = "Brightness of the subtractive mask. Higher values remove more cloud; lower values preserve more. 0 is neutral. Independent of the existing noise texture adjustments."))
    float LargeBreakupBrightness = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Large Breakup", meta = (DisplayName = "Contrast", ClampMin = "0", UIMin = "0", UIMax = "8", DisplayPriority = "5", ToolTip = "Contrast of the subtractive mask around 0.5. Higher values separate solid masses from gaps more sharply. 1 is neutral. Typed values may exceed the slider range."))
    float LargeBreakupContrast = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Guides", meta = (ClampMin = "0", Units = "cm", DisplayName = "Guide Blend"))
    float UnionBlendCm = 55.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Guides", AdvancedDisplay, meta = (ClampMin = "0", Units = "cm", DisplayName = "Maximum Blend Expansion"))
    float UnionGrowthLimitCm = 27.5f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Quality", meta = (ToolTip = "Cinematic improves volume and shadow sampling. It preserves the shape, seed and density and costs more to render."))
    ECloudPreviewQuality Quality = ECloudPreviewQuality::Preview;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Appearance", meta = (ToolTip = "The cloud family. Load a preset to also arrange its shape guides."))
    ECloudStyle CloudStyle = ECloudStyle::Cumulus;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Detail", meta = (ClampMin = "0", ClampMax = "1", UIMin = "0", UIMax = "1", ToolTip = "Adds directional wisps while retaining the guide shape."))
    float WispStrength = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Detail", meta = (ToolTip = "Stretches only the wisp pattern, independently of guide scale. Use a larger X for long cirrus strands."))
    FVector WispStretch = FVector::OneVector;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Detail", meta = (Units = "deg", UIMin = "-180", UIMax = "180", DisplayName = "Wisp Direction"))
    float WispDirectionDegrees = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Detail", meta = (ClampMin = "0", ClampMax = "1", UIMin = "0", UIMax = "1", ToolTip = "Adds density variation inside the cloud without changing its outer guide shape."))
    float InteriorVariation = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Detail", meta = (ClampMin = "-1", ClampMax = "1", UIMin = "-1", UIMax = "1", ToolTip = "Changes density from the bottom to the top. Zero preserves even density."))
    float VerticalDensityGradient = 0.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Detail", meta = (ClampMin = "1", Units = "cm", ToolTip = "Height of the vertical density profile above the generator. This stays fixed when guides move."))
    float VerticalReferenceHeightCm = 3000.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Presets", meta = (ToolTip = "Choose a saved cloud, then press Load Preset. Location and rotation stay unchanged; new recipes restore their authored generator scale."))
    TObjectPtr<UCloudRecipePreset> Preset;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Cloud Presets", AdvancedDisplay, meta = (ToolTip = "Apply the assigned Preset once when a new actor is placed or spawned. Existing saved actors and reconstructed actors are never reset. Requires a valid Preset and no existing guides."))
    bool bUseDefaultPresetOnFirstPlacement = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Presets", meta = (ToolTip = "Name for Save Preset. A new unique asset is created in Preset Save Folder; existing presets are never overwritten."))
    FString PresetName = TEXT("MyCloud");
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Presets", AdvancedDisplay, meta = (DisplayName = "Preset Save Folder", ToolTip = "Project Content folder for newly saved recipes, expressed as /Game/Folder. Plugin content is never overwritten. Defaults to /Game/OnlyClouds/Presets."))
    FString PresetSaveDirectory = TEXT("/Game/OnlyClouds/Presets");
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "Cloud Presets", meta = (DisplayName = "Locked", ToolTip = "Lock protects the recipe and guides. You can still move the complete generator or change rendering quality."))
    bool bLocked = false;
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category = "Cloud Presets")
    FString WorkflowStatus;

    UFUNCTION(CallInEditor, BlueprintCallable, Category = "Cloud Presets", meta = (DisplayName = "Generate Variation"))
    void GenerateVariation();
    UFUNCTION(CallInEditor, BlueprintCallable, Category = "Cloud Presets", meta = (DisplayName = "Save Preset"))
    void SavePreset();
    UFUNCTION(CallInEditor, BlueprintCallable, Category = "Cloud Presets", meta = (DisplayName = "Load Preset"))
    void LoadPreset();
    UFUNCTION(CallInEditor, BlueprintCallable, Category = "Cloud Presets", meta = (DisplayName = "Lock Cloud"))
    void LockCloud();
    UFUNCTION(CallInEditor, BlueprintCallable, Category = "Cloud Presets", meta = (DisplayName = "Unlock Cloud"))
    void UnlockCloud();
    UFUNCTION(BlueprintPure, Category = "Cloud Generator|Recipe")
    FCloudRecipe CaptureRecipe() const;
    UFUNCTION(BlueprintCallable, Category = "Cloud Generator|Recipe")
    bool ApplyRecipe(const FCloudRecipe& Recipe);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloud Generator", AdvancedDisplay)
    TSoftObjectPtr<UMaterialInterface> CloudMaterial;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category = "Cloud Generator", meta = (DisplayName = "Preview Status"))
    FString PreviewStatus;
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category = "Cloud Generator", AdvancedDisplay)
    int32 ActiveGuideCount = 0;
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category = "Cloud Generator", AdvancedDisplay)
    float BoundsHalfExtentCm = 0.0f;
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category = "Cloud Generator", AdvancedDisplay)
    FVector BoundsCenterRelativeToAnchorCm = FVector::ZeroVector;
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category = "Cloud Generator", AdvancedDisplay)
    float ComputedExtinctionScale = 0.0f;
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, DuplicateTransient, Category = "Cloud Generator", AdvancedDisplay)
    TObjectPtr<UTexture2D> GuideDataTexture;

    UFUNCTION(CallInEditor, BlueprintCallable, Category = "Cloud Guides", meta = (DisplayName = "+ Add Guide"))
    void AddGuide();

    UFUNCTION(CallInEditor, BlueprintCallable, Category = "Cloud Generator", meta = (DisplayName = "Refresh Cloud"))
    void RefreshCloud();

    /** A copy of the 3-by-64 texels, row-major, for inspection and automation. */
    UFUNCTION(BlueprintPure, Category = "Cloud Generator|Inspection")
    TArray<FLinearColor> GetEncodedGuideData() const { return EncodedGuideData; }

    void RegisterGuide(ACloudGuideActor* Guide);
    void UnregisterGuide(ACloudGuideActor* Guide);

    virtual void PostActorCreated() override;
    virtual void OnConstruction(const FTransform& Transform) override;
    virtual void PostRegisterAllComponents() override;
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual bool ShouldTickIfViewportsOnly() const override;
    virtual void Destroyed() override;
#if WITH_EDITOR
    virtual void PostEditMove(bool bFinished) override;
    virtual void PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent) override;
    virtual void PostEditUndo() override;
#endif
private:
    // Serialized so duplication and Blueprint reinstancing retain this decision.
    UPROPERTY()
    bool bDefaultPresetPlacementHandled = false;
    // Only PostActorCreated can arm the initializer; loading old maps never does.
    bool bPendingDefaultPresetPlacement = false;
    void ApplyDefaultPresetOnFirstPlacement();

    UPROPERTY()
    FCloudRecipe LockedRecipe;
    bool bRestoringRecipe = false;
    void RestoreLockedRecipe();
    void ApplyAppearance(const FCloudRecipe& Recipe);
    void ApplyQuality();
    ACloudGuideActor* SpawnRecipeGuide(const FCloudGuideRecipe& Recipe);

    UPROPERTY(Transient, DuplicateTransient)
    TObjectPtr<UMaterialInstanceDynamic> DynamicMaterial;
    UPROPERTY(Transient, DuplicateTransient)
    TObjectPtr<UMaterialInterface> CurrentBaseMaterial;
    FVector LastMaterialTextureOffsetCm = FVector::ZeroVector;
    float LastMaterialNoisePhase = 0.0f;
    bool bAnimationMaterialInitialized = false;
    TArray<FLinearColor> EncodedGuideData;
    TArray<FLinearColor> UploadedGuideData;
    bool bRefreshing = false;
    bool bWarnedGuideLimit = false;
    bool bDestroyingGenerator = false;

    bool UploadGuideTexture(const TArray<FLinearColor>& NewData);
    bool UpdateMaterial();
    void UpdateAnimationMaterial(bool bForce = false);
    bool IsAnimationWorld() const;
};


