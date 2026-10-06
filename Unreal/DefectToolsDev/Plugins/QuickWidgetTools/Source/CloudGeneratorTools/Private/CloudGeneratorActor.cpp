#include "CloudGeneratorActor.h"

#include "Components/HeterogeneousVolumeComponent.h"
#include "Engine/Texture2D.h"
#include "Engine/VolumeTexture.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Misc/App.h"
#include "HAL/FileManager.h"
#include "PrimitiveDrawingUtils.h"
#include "PrimitiveSceneProxy.h"
#include "SceneManagement.h"
#include "TextureResource.h"
#include "UObject/Package.h"
#if WITH_EDITOR
#include "Editor.h"
#include "ScopedTransaction.h"
#include "AssetToolsModule.h"
#include "IAssetTools.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "UObject/SavePackage.h"
#include "ObjectTools.h"
#endif

#define LOCTEXT_NAMESPACE "CloudGeneratorTools"
DEFINE_LOG_CATEGORY_STATIC(LogCloudGeneratorTools, Log, All);

namespace CloudGenerator
{
    constexpr double GuideUnitRadius = 100.0;
    constexpr double MaxDimensionCm = 10000000.0;
    constexpr double MaxPositionCm = 1000000000.0;

    bool FiniteVector(const FVector& V)
    {
        return FMath::IsFinite(V.X) && FMath::IsFinite(V.Y) && FMath::IsFinite(V.Z);
    }
    bool FiniteQuat(const FQuat& Q)
    {
        return FMath::IsFinite(Q.X) && FMath::IsFinite(Q.Y) && FMath::IsFinite(Q.Z) && FMath::IsFinite(Q.W);
    }
    float SafeFloat(float Value, float Default, float Min, float Max)
    {
        return FMath::Clamp(FMath::IsFinite(Value) ? Value : Default, Min, Max);
    }
    FLinearColor SafeColor(const FLinearColor& C)
    {
        return FLinearColor(SafeFloat(C.R, 0.95f, 0.0f, 1.0f), SafeFloat(C.G, 0.97f, 0.0f, 1.0f),
            SafeFloat(C.B, 1.0f, 0.0f, 1.0f), 1.0f);
    }
    FVector RotatedExtent(const FQuat& Q, const FVector& Radii, bool bEllipsoid)
    {
        const FVector X = Q.GetAxisX() * Radii.X;
        const FVector Y = Q.GetAxisY() * Radii.Y;
        const FVector Z = Q.GetAxisZ() * Radii.Z;
        if (bEllipsoid)
        {
            return FVector(FMath::Sqrt(X.X * X.X + Y.X * Y.X + Z.X * Z.X),
                FMath::Sqrt(X.Y * X.Y + Y.Y * Y.Y + Z.Y * Z.Y),
                FMath::Sqrt(X.Z * X.Z + Y.Z * Y.Z + Z.Z * Z.Z));
        }
        return X.GetAbs() + Y.GetAbs() + Z.GetAbs();
    }

#if WITH_EDITOR
    class FGuideSceneProxy final : public FPrimitiveSceneProxy
    {
    public:
        explicit FGuideSceneProxy(const UCloudGuideShapeComponent* Component)
            : FPrimitiveSceneProxy(Component)
        {
            bWillEverBeLit = false;
            if (const ACloudGuideActor* Guide = Cast<ACloudGuideActor>(Component->GetOwner()))
            {
                Shape = Guide->Shape;
                Color = !Guide->bEnabled ? FLinearColor(0.35f, 0.35f, 0.35f) :
                    (Guide->Operation == ECloudGuideOperation::Subtract ? FLinearColor(1.0f, 0.3f, 0.1f) : FLinearColor(0.1f, 0.65f, 1.0f));
            }
        }
        virtual SIZE_T GetTypeHash() const override
        {
            static size_t Unique;
            return reinterpret_cast<SIZE_T>(&Unique);
        }
        virtual void GetDynamicMeshElements(const TArray<const FSceneView*>& Views, const FSceneViewFamily& ViewFamily,
            uint32 VisibilityMap, FMeshElementCollector& Collector) const override
        {
            if (ViewFamily.EngineShowFlags.Game)
            {
                return;
            }
            for (int32 ViewIndex = 0; ViewIndex < Views.Num(); ++ViewIndex)
            {
                if ((VisibilityMap & (1u << ViewIndex)) == 0)
                {
                    continue;
                }
                FPrimitiveDrawInterface* PDI = Collector.GetPDI(ViewIndex);
                const float Thickness = IsSelected() ? 2.0f : 1.0f;
                const FLinearColor DrawColor = IsSelected() ? FLinearColor(1.0f, 0.8f, 0.15f) : Color;
                if (Shape == ECloudGuideShape::Box)
                {
                    DrawWireBox(PDI, GetLocalToWorld(), FBox(FVector(-GuideUnitRadius), FVector(GuideUnitRadius)),
                        DrawColor, SDPG_World, Thickness);
                }
                else
                {
                    // Unlike a collision SphereComponent, this outline retains nonuniform scale.
                    // Pixel widths keep distant guides readable instead of shrinking with perspective.
                    const float SphereThicknessPixels = IsSelected() ? 3.0f : 2.0f;
                    DrawWireSphere(PDI, FTransform(GetLocalToWorld()), DrawColor, GuideUnitRadius, 48,
                        SDPG_World, SphereThicknessPixels, 0.0f, true);
                }
            }
        }
        virtual FPrimitiveViewRelevance GetViewRelevance(const FSceneView* View) const override
        {
            FPrimitiveViewRelevance Result;
            Result.bDrawRelevance = IsShown(View) && !View->Family->EngineShowFlags.Game;
            Result.bDynamicRelevance = true;
            Result.bShadowRelevance = false;
            Result.bEditorPrimitiveRelevance = UseEditorCompositing(View);
            return Result;
        }
        virtual uint32 GetMemoryFootprint() const override { return sizeof(*this) + GetAllocatedSize(); }
    private:
        ECloudGuideShape Shape = ECloudGuideShape::Sphere;
        FLinearColor Color = FLinearColor::White;
    };
#endif
}

UCloudGuideShapeComponent::UCloudGuideShapeComponent()
{
    SetCollisionEnabled(ECollisionEnabled::NoCollision);
    SetGenerateOverlapEvents(false);
    SetCanEverAffectNavigation(false);
    SetHiddenInGame(true);
    CastShadow = false;
    bUseAsOccluder = false;
    PrimaryComponentTick.bCanEverTick = false;
}

FPrimitiveSceneProxy* UCloudGuideShapeComponent::CreateSceneProxy()
{
#if WITH_EDITOR
    return new CloudGenerator::FGuideSceneProxy(this);
#else
    return nullptr;
#endif
}

FBoxSphereBounds UCloudGuideShapeComponent::CalcBounds(const FTransform& LocalToWorld) const
{
    return FBoxSphereBounds(FBox(FVector(-CloudGenerator::GuideUnitRadius), FVector(CloudGenerator::GuideUnitRadius))).TransformBy(LocalToWorld);
}

ACloudGuideActor::ACloudGuideActor()
{
    PrimaryActorTick.bCanEverTick = false;
    GuideShape = CreateDefaultSubobject<UCloudGuideShapeComponent>(TEXT("GuideShape"));
    RootComponent = GuideShape;
}

void ACloudGuideActor::NotifyGenerator()
{
    if (IsTemplate() || IsActorBeingDestroyed() || bNotifyingGenerator)
    {
        return;
    }
    TGuardValue<bool> Guard(bNotifyingGenerator, true);
    ACloudGeneratorActor* Previous = LastNotifiedGenerator.Get();
    if (IsValid(Previous) && !Previous->IsActorBeingDestroyed() && Previous->bLocked && Previous != Generator)
    {
        Generator = Previous;
    }
    if (IsValid(Previous) && Previous != Generator)
    {
        Previous->UnregisterGuide(this);
    }
    LastNotifiedGenerator = Generator;
    if (IsValid(Generator))
    {
        Generator->RegisterGuide(this);
        Generator->RefreshCloud();
    }
    if (GuideShape)
    {
        GuideShape->MarkRenderStateDirty();
    }
}

void ACloudGuideActor::OnConstruction(const FTransform& Transform)
{
    Super::OnConstruction(Transform);
    NotifyGenerator();
}

void ACloudGuideActor::PostRegisterAllComponents()
{
    Super::PostRegisterAllComponents();
    NotifyGenerator();
}

void ACloudGuideActor::Destroyed()
{
    ACloudGeneratorActor* Previous = Generator;
    Generator = nullptr;
    LastNotifiedGenerator.Reset();
    if (IsValid(Previous))
    {
        Previous->UnregisterGuide(this);
    }
    Super::Destroyed();
}

#if WITH_EDITOR
bool ACloudGuideActor::CanDeleteSelectedActor(FText& OutReason) const
{
    if (IsValid(Generator) && !Generator->IsActorBeingDestroyed() && Generator->bLocked)
    {
        OutReason = LOCTEXT("LockedCloudGuideDelete", "Unlock the cloud before deleting one of its guides.");
        return false;
    }
    return Super::CanDeleteSelectedActor(OutReason);
}
void ACloudGuideActor::PostEditMove(bool bFinished)
{
    Super::PostEditMove(bFinished);
    NotifyGenerator();
}
void ACloudGuideActor::PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent)
{
    Super::PostEditChangeProperty(PropertyChangedEvent);
    NotifyGenerator();
}
void ACloudGuideActor::PostEditUndo()
{
    Super::PostEditUndo();
    NotifyGenerator();
}
#endif

ACloudGeneratorActor::ACloudGeneratorActor()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.bStartWithTickEnabled = true;
    SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
    RootComponent = SceneRoot;
    CloudVolume = CreateDefaultSubobject<UHeterogeneousVolumeComponent>(TEXT("CloudVolume"));
    CloudVolume->SetupAttachment(SceneRoot);
    CloudVolume->SetAbsolute(true, true, true);
    CloudVolume->VolumeResolution = FIntVector(128);
    CloudVolume->bPivotAtCentroid = true;
    CloudVolume->bPlaying = false;
    CloudVolume->bLooping = false;
    CloudVolume->PrimaryComponentTick.bCanEverTick = false;
    CloudVolume->SetVisibility(false);
    CloudVolume->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    CloudVolume->SetCanEverAffectNavigation(false);
    CloudMaterial = TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(TEXT("/QuickWidgetTools/OnlyClouds/PlacedClouds/Materials/M_CloudVolume_FlexibleGuides.M_CloudVolume_FlexibleGuides")));
}

void ACloudGeneratorActor::RegisterGuide(ACloudGuideActor* Guide)
{
    if (bDestroyingGenerator || !IsValid(Guide) || Guide->GetWorld() != GetWorld())
    {
        return;
    }
    if (bLocked && !bRestoringRecipe && !Guides.Contains(Guide))
    {
        WorkflowStatus = TEXT("Cloud is locked. Unlock it before adding or reassigning guides.");
        return;
    }
    if (!Guide->GuideId.IsValid() || Guides.ContainsByPredicate([Guide](const TObjectPtr<ACloudGuideActor>& Other)
        { return IsValid(Other) && Other != Guide && Other->GuideId == Guide->GuideId; }))
    {
        Guide->GuideId = FGuid::NewGuid();
    }
    if (Guides.Contains(Guide))
    {
        if (Guide->GetAttachParentActor() != this)
        {
            Guide->AttachToComponent(SceneRoot, FAttachmentTransformRules::KeepWorldTransform);
        }
        return;
    }
    Guides.RemoveAll([](const TObjectPtr<ACloudGuideActor>& Item) { return !IsValid(Item); });
    if (Guides.Num() >= MaxGuides)
    {
        if (!bWarnedGuideLimit)
        {
            UE_LOG(LogCloudGeneratorTools, Warning, TEXT("%s: the cloud preview supports at most %d guides."), *GetName(), MaxGuides);
            bWarnedGuideLimit = true;
        }
        return;
    }
#if WITH_EDITOR
    if (GetWorld() && GetWorld()->WorldType == EWorldType::Editor)
    {
        Modify();
    }
#endif
    Guides.Add(Guide);
    Guide->AttachToComponent(SceneRoot, FAttachmentTransformRules::KeepWorldTransform);
}

void ACloudGeneratorActor::UnregisterGuide(ACloudGuideActor* Guide)
{
    if (bDestroyingGenerator || !Guides.Contains(Guide))
    {
        return;
    }
#if WITH_EDITOR
    if (GetWorld() && GetWorld()->WorldType == EWorldType::Editor)
    {
        Modify();
    }
#endif
    Guides.Remove(Guide);
    if (IsValid(Guide) && Guide->GetAttachParentActor() == this)
    {
        Guide->DetachFromActor(FDetachmentTransformRules::KeepWorldTransform);
    }
    RefreshCloud();
}

void ACloudGeneratorActor::AddGuide()
{
    if (bLocked)
    {
        WorkflowStatus = TEXT("Cloud is locked. Unlock it before adding guides.");
        return;
    }
    UWorld* World = GetWorld();
    if (IsTemplate() || !World || IsActorBeingDestroyed() || !CloudGenerator::FiniteVector(GetActorLocation()))
    {
        return;
    }
    Guides.RemoveAll([](const TObjectPtr<ACloudGuideActor>& Item) { return !IsValid(Item); });
    if (Guides.Num() >= MaxGuides)
    {
        PreviewStatus = FString::Printf(TEXT("Guide limit reached (%d). Remove a guide before adding another."), MaxGuides);
        UE_LOG(LogCloudGeneratorTools, Warning, TEXT("%s: %s"), *GetName(), *PreviewStatus);
        return;
    }
#if WITH_EDITOR
    TUniquePtr<FScopedTransaction> Transaction;
    if (World->WorldType == EWorldType::Editor && !IsRunningCommandlet())
    {
        Transaction = MakeUnique<FScopedTransaction>(LOCTEXT("AddGuideTransaction", "Add Cloud Guide"));
        Modify();
    }
#endif
    FTransform SpawnTransform(FQuat::Identity, GetActorLocation() + FVector(0.0, 0.0, 700.0), FVector(6.0));
    for (int32 Index = Guides.Num() - 1; Index >= 0; --Index)
    {
        const ACloudGuideActor* Previous = Guides[Index];
        if (IsValid(Previous) && Previous->bEnabled && Previous->Operation == ECloudGuideOperation::Add &&
            CloudGenerator::FiniteVector(Previous->GetActorLocation()) && CloudGenerator::FiniteVector(Previous->GetActorScale3D()))
        {
            const FVector Scale = Previous->GetActorScale3D().GetAbs().ComponentMax(FVector(0.001));
            const double Offset = FMath::Max(50.0, Scale.GetMin() * CloudGenerator::GuideUnitRadius * 0.85);
            SpawnTransform = FTransform(Previous->GetActorQuat(), Previous->GetActorLocation() + FVector(Offset, 0.0, 0.0), Scale);
            break;
        }
    }
    FActorSpawnParameters Params;
    Params.OverrideLevel = GetLevel();
    Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    Params.ObjectFlags |= RF_Transactional;
    ACloudGuideActor* Guide = World->SpawnActor<ACloudGuideActor>(ACloudGuideActor::StaticClass(), SpawnTransform, Params);
    if (!Guide)
    {
        PreviewStatus = TEXT("The guide could not be created.");
        return;
    }
    Guide->Generator = this;
    Guide->AttachToComponent(SceneRoot, FAttachmentTransformRules::KeepWorldTransform);
    RegisterGuide(Guide);
    Guide->NotifyGenerator();
#if WITH_EDITOR
    Guide->SetActorLabel(FString::Printf(TEXT("Cloud Guide %02d"), Guides.Num()));
    if (GEditor && World->WorldType == EWorldType::Editor && !IsRunningCommandlet())
    {
        GEditor->SelectNone(false, true);
        GEditor->SelectActor(Guide, true, true, true);
    }
#endif
    RefreshCloud();
}

bool ACloudGeneratorActor::UploadGuideTexture(const TArray<FLinearColor>& NewData)
{
    static_assert(sizeof(FLinearColor) == 4 * sizeof(float), "Guide texels must contain four 32-bit floats.");
    const int64 Bytes = NewData.Num() * sizeof(FLinearColor);
    if (!GuideDataTexture)
    {
        GuideDataTexture = UTexture2D::CreateTransient(GuideDataWidth, MaxGuides, PF_A32B32G32R32F);
        if (!GuideDataTexture)
        {
            return false;
        }
        GuideDataTexture->SRGB = false;
        GuideDataTexture->NeverStream = true;
        GuideDataTexture->Filter = TF_Nearest;
        GuideDataTexture->AddressX = TA_Clamp;
        GuideDataTexture->AddressY = TA_Clamp;
#if WITH_EDITORONLY_DATA
        GuideDataTexture->MipGenSettings = TMGS_NoMipmaps;
#endif
        FTexture2DMipMap& Mip = GuideDataTexture->GetPlatformData()->Mips[0];
        void* InitialData = Mip.BulkData.Lock(LOCK_READ_WRITE);
        FMemory::Memcpy(InitialData, NewData.GetData(), Bytes);
        Mip.BulkData.Unlock();
        GuideDataTexture->UpdateResource();
        UploadedGuideData = NewData;
        return true;
    }
    if (UploadedGuideData.Num() == NewData.Num() && FMemory::Memcmp(UploadedGuideData.GetData(), NewData.GetData(), Bytes) == 0)
    {
        return true;
    }
    if (FApp::CanEverRender() && GuideDataTexture->GetResource())
    {
        // Own each upload until the RHI thread has consumed it. No actor or mutable array is captured.
        uint8* Upload = new uint8[Bytes];
        FMemory::Memcpy(Upload, NewData.GetData(), Bytes);
        FUpdateTextureRegion2D* Region = new FUpdateTextureRegion2D(0, 0, 0, 0, GuideDataWidth, MaxGuides);
        GuideDataTexture->UpdateTextureRegions(0, 1, Region, GuideDataWidth * sizeof(FLinearColor), sizeof(FLinearColor), Upload,
            [](uint8* Data, const FUpdateTextureRegion2D* Regions)
            {
                delete[] Data;
                delete Regions;
            });
    }
    else
    {
        // NullRHI/headless has no render resource; retain a correct CPU mip for inspection/later creation.
        FTexture2DMipMap& Mip = GuideDataTexture->GetPlatformData()->Mips[0];
        void* Data = Mip.BulkData.Lock(LOCK_READ_WRITE);
        FMemory::Memcpy(Data, NewData.GetData(), Bytes);
        Mip.BulkData.Unlock();
        if (FApp::CanEverRender())
        {
            GuideDataTexture->UpdateResource();
        }
    }
    UploadedGuideData = NewData;
    return true;
}

bool ACloudGeneratorActor::UpdateMaterial()
{
    UMaterialInterface* Material = CloudMaterial.LoadSynchronous();
    if (!Material)
    {
        PreviewStatus = TEXT("Choose a cloud volume material to enable the preview.");
        return false;
    }
    if (!DynamicMaterial || CurrentBaseMaterial != Material)
    {
        DynamicMaterial = UMaterialInstanceDynamic::Create(Material, this);
        CurrentBaseMaterial = Material;
        bAnimationMaterialInitialized = false;
        CloudVolume->SetMaterial(0, DynamicMaterial);
    }
    if (!DynamicMaterial)
    {
        return false;
    }
    // Resolve defaults from the base material, not the MID that may still contain an old override.
    auto ResolveNoiseTexture = [Material](const TSoftObjectPtr<UVolumeTexture>& Override, FName ParameterName) -> UTexture*
    {
        if (UVolumeTexture* Texture = Override.LoadSynchronous())
        {
            return Texture;
        }
        UTexture* DefaultTexture = nullptr;
        Material->GetTextureParameterValue(FMaterialParameterInfo(ParameterName), DefaultTexture);
        return DefaultTexture;
    };
    UTexture* ShapeNoiseTexture = ResolveNoiseTexture(CustomShapeNoiseTexture, TEXT("ShapeNoise"));
    UTexture* DetailNoiseTexture = ResolveNoiseTexture(CustomDetailNoiseTexture, TEXT("ErosionNoise"));
    // UE ignores a null SetTextureParameterValue. Clear all owned overrides only for a missing
    // base default, then repopulate them below, so clearing a custom slot can never leave it stale.
    UTexture* PreviousShapeNoise = nullptr;
    UTexture* PreviousDetailNoise = nullptr;
    DynamicMaterial->GetTextureParameterValue(FMaterialParameterInfo(TEXT("ShapeNoise")), PreviousShapeNoise);
    DynamicMaterial->GetTextureParameterValue(FMaterialParameterInfo(TEXT("ErosionNoise")), PreviousDetailNoise);
    if ((!ShapeNoiseTexture && PreviousShapeNoise) || (!DetailNoiseTexture && PreviousDetailNoise))
    {
        DynamicMaterial->ClearParameterValues();
    }
    if (ShapeNoiseTexture)
    {
        DynamicMaterial->SetTextureParameterValue(TEXT("ShapeNoise"), ShapeNoiseTexture);
    }
    if (DetailNoiseTexture)
    {
        DynamicMaterial->SetTextureParameterValue(TEXT("ErosionNoise"), DetailNoiseTexture);
    }
    DynamicMaterial->SetTextureParameterValue(TEXT("GuideData"), GuideDataTexture);
    DynamicMaterial->SetScalarParameterValue(TEXT("GuideCount"), ActiveGuideCount);
    DynamicMaterial->SetScalarParameterValue(TEXT("BoundsHalfExtentCm"), BoundsHalfExtentCm);
    DynamicMaterial->SetVectorParameterValue(TEXT("BoundsCenterRelativeToAnchor"), FLinearColor(
        BoundsCenterRelativeToAnchorCm.X, BoundsCenterRelativeToAnchorCm.Y, BoundsCenterRelativeToAnchorCm.Z, 0.0f));
    DynamicMaterial->SetScalarParameterValue(TEXT("ExtinctionScale"), ComputedExtinctionScale);
    DynamicMaterial->SetScalarParameterValue(TEXT("Density"), CloudGenerator::SafeFloat(Density, 2.6f, 0.0f, 100.0f));
    DynamicMaterial->SetScalarParameterValue(TEXT("Seed"), CloudGenerator::SafeFloat(Seed, 1.0f, -1000000.0f, 1000000.0f));
    DynamicMaterial->SetScalarParameterValue(TEXT("BillowSizeCm"), CloudGenerator::SafeFloat(BillowSizeCm, 228.78f, 0.1f, CloudGenerator::MaxDimensionCm));
    DynamicMaterial->SetScalarParameterValue(TEXT("BillowDepthCm"), CloudGenerator::SafeFloat(BillowDepthCm, 550.0f, 0.0f, CloudGenerator::MaxDimensionCm));
    DynamicMaterial->SetScalarParameterValue(TEXT("BillowStrength"), CloudGenerator::SafeFloat(BillowStrength, 1.0f, 0.0f, 1.0f));
    DynamicMaterial->SetScalarParameterValue(TEXT("DetailSizeCm"), CloudGenerator::SafeFloat(DetailSizeCm, 76.26f, 0.1f, CloudGenerator::MaxDimensionCm));
    DynamicMaterial->SetScalarParameterValue(TEXT("DetailStrength"), CloudGenerator::SafeFloat(DetailStrength, 0.45f, 0.0f, 1.0f));
    const uint8 BillowStyleValue = static_cast<uint8>(BillowStyle);
    DynamicMaterial->SetScalarParameterValue(TEXT("BillowStyle"), BillowStyleValue <= static_cast<uint8>(ECloudBillowStyle::Turbulent) ? BillowStyleValue : 0);
    DynamicMaterial->SetScalarParameterValue(TEXT("ShapeNoiseLayout"), ShapeNoiseLayout == ECloudNoiseLayout::Grayscale ? 1.0f : 0.0f);
    DynamicMaterial->SetScalarParameterValue(TEXT("DetailNoiseLayout"), DetailNoiseLayout == ECloudNoiseLayout::Grayscale ? 1.0f : 0.0f);
    // Artist tiling has no range restriction; guard only shader-float representability.
    auto SafeTilingAxis = [](double Value)
    {
        const double MaxShaderFloat = static_cast<double>(TNumericLimits<float>::Max());
        return FMath::Clamp(FMath::IsFinite(Value) ? Value : 1.0, -MaxShaderFloat, MaxShaderFloat);
    };
    DynamicMaterial->SetVectorParameterValue(TEXT("NoiseTiling"), FLinearColor(SafeTilingAxis(NoiseTiling.X), SafeTilingAxis(NoiseTiling.Y), SafeTilingAxis(NoiseTiling.Z), 0.0f));
    DynamicMaterial->SetScalarParameterValue(TEXT("NoiseContrast"), CloudGenerator::SafeFloat(NoiseContrast, 1.0f, 0.1f, 4.0f));
    DynamicMaterial->SetScalarParameterValue(TEXT("NoiseBrightness"), CloudGenerator::SafeFloat(NoiseBrightness, 0.0f, -1000000.0f, 1000000.0f));
    DynamicMaterial->SetScalarParameterValue(TEXT("NoiseTextureContrast"), CloudGenerator::SafeFloat(NoiseTextureContrast, 1.0f, 0.0f, 1000000.0f));
    DynamicMaterial->SetScalarParameterValue(TEXT("LevelsInputLow"), CloudGenerator::SafeFloat(LevelsInputLow, 0.0f, 0.0f, 1.0f));
    DynamicMaterial->SetScalarParameterValue(TEXT("LevelsInputMid"), CloudGenerator::SafeFloat(LevelsInputMid, 1.0f, 0.001f, 1000.0f));
    DynamicMaterial->SetScalarParameterValue(TEXT("LevelsInputHigh"), CloudGenerator::SafeFloat(LevelsInputHigh, 1.0f, 0.0f, 1.0f));
    DynamicMaterial->SetScalarParameterValue(TEXT("LevelsOutputLow"), CloudGenerator::SafeFloat(LevelsOutputLow, 0.0f, 0.0f, 1.0f));
    DynamicMaterial->SetScalarParameterValue(TEXT("LevelsOutputHigh"), CloudGenerator::SafeFloat(LevelsOutputHigh, 1.0f, 0.0f, 1.0f));
    DynamicMaterial->SetScalarParameterValue(TEXT("WarpAmount"), CloudGenerator::SafeFloat(WarpAmount, 0.0f, 0.0f, 1.0f));
    DynamicMaterial->SetScalarParameterValue(TEXT("LargeBreakupAmount"), CloudGenerator::SafeFloat(LargeBreakupAmount, 0.0f, 0.0f, 1.0f));
    // Limit only invalid scales and extreme values that cannot safely reach the shader.
    DynamicMaterial->SetVectorParameterValue(TEXT("LargeBreakupScaleCm"), FLinearColor(
        CloudGenerator::SafeFloat(LargeBreakupScaleX, 1000.0f, 0.01f, 1.0e30f),
        CloudGenerator::SafeFloat(LargeBreakupScaleY, 1000.0f, 0.01f, 1.0e30f),
        CloudGenerator::SafeFloat(LargeBreakupScaleZ, 1000.0f, 0.01f, 1.0e30f), 0.0f));
    DynamicMaterial->SetScalarParameterValue(TEXT("LargeBreakupBrightness"), CloudGenerator::SafeFloat(LargeBreakupBrightness, 0.0f, -1000000.0f, 1000000.0f));
    DynamicMaterial->SetScalarParameterValue(TEXT("LargeBreakupContrast"), CloudGenerator::SafeFloat(LargeBreakupContrast, 1.0f, 0.0f, 1000000.0f));
    DynamicMaterial->SetScalarParameterValue(TEXT("UnionBlendCm"), CloudGenerator::SafeFloat(UnionBlendCm, 55.0f, 0.0f, CloudGenerator::MaxDimensionCm));
    DynamicMaterial->SetScalarParameterValue(TEXT("UnionGrowthLimitCm"), CloudGenerator::SafeFloat(UnionGrowthLimitCm, 27.5f, 0.0f, CloudGenerator::MaxDimensionCm));
    DynamicMaterial->SetScalarParameterValue(TEXT("SkyFill"), CloudGenerator::SafeFloat(SkyFill, 0.45f, 0.0f, 8.0f));
    DynamicMaterial->SetVectorParameterValue(TEXT("CloudColor"), CloudGenerator::SafeColor(CloudColor));
    DynamicMaterial->SetScalarParameterValue(TEXT("CloudStyle"), static_cast<uint8>(CloudStyle));
    DynamicMaterial->SetScalarParameterValue(TEXT("WispStrength"), CloudGenerator::SafeFloat(WispStrength, 0.0f, 0.0f, 1.0f));
    const FVector SafeStretch = CloudGenerator::FiniteVector(WispStretch) ? WispStretch.GetAbs().ComponentMax(FVector(0.05)).ComponentMin(FVector(1000.0)) : FVector::OneVector;
    DynamicMaterial->SetVectorParameterValue(TEXT("WispStretch"), FLinearColor(SafeStretch.X, SafeStretch.Y, SafeStretch.Z, 0.0f));
    DynamicMaterial->SetScalarParameterValue(TEXT("WispDirectionDegrees"), CloudGenerator::SafeFloat(WispDirectionDegrees, 0.0f, -36000.0f, 36000.0f));
    DynamicMaterial->SetScalarParameterValue(TEXT("InteriorVariation"), CloudGenerator::SafeFloat(InteriorVariation, 0.0f, 0.0f, 1.0f));
    DynamicMaterial->SetScalarParameterValue(TEXT("VerticalDensityGradient"), CloudGenerator::SafeFloat(VerticalDensityGradient, 0.0f, -1.0f, 1.0f));
    DynamicMaterial->SetScalarParameterValue(TEXT("VerticalReferenceHeightCm"), CloudGenerator::SafeFloat(VerticalReferenceHeightCm, 3000.0f, 1.0f, CloudGenerator::MaxDimensionCm));
    UpdateAnimationMaterial(true);
    return true;
}

bool ACloudGeneratorActor::IsAnimationWorld() const
{
    const UWorld* World = GetWorld();
    return !IsTemplate() && !IsActorBeingDestroyed() && !bDestroyingGenerator && !IsRunningCommandlet() && World &&
        (World->WorldType == EWorldType::Editor || World->WorldType == EWorldType::PIE ||
            World->WorldType == EWorldType::Game || World->WorldType == EWorldType::GamePreview);
}

bool ACloudGeneratorActor::ShouldTickIfViewportsOnly() const
{
    // Manual values can also be driven by Sequencer while automatic animation is off.
    return IsAnimationWorld();
}

void ACloudGeneratorActor::UpdateAnimationMaterial(bool bForce)
{
    if (!DynamicMaterial)
    {
        return;
    }
    // Sanitize shader inputs, without rewriting the artist's manually keyed properties.
    const FVector SafeOffset(
        FMath::IsFinite(TextureOffsetCm.X) ? FMath::Clamp(TextureOffsetCm.X, -1.0e9, 1.0e9) : 0.0,
        FMath::IsFinite(TextureOffsetCm.Y) ? FMath::Clamp(TextureOffsetCm.Y, -1.0e9, 1.0e9) : 0.0,
        FMath::IsFinite(TextureOffsetCm.Z) ? FMath::Clamp(TextureOffsetCm.Z, -1.0e9, 1.0e9) : 0.0);
    const float SafePhase = CloudGenerator::SafeFloat(NoisePhase, 0.0f, -1.0e9f, 1.0e9f);
    if (bForce || !bAnimationMaterialInitialized || SafeOffset != LastMaterialTextureOffsetCm)
    {
        DynamicMaterial->SetVectorParameterValue(TEXT("NoiseOffsetCm"), FLinearColor(SafeOffset.X, SafeOffset.Y, SafeOffset.Z, 0.0f));
        LastMaterialTextureOffsetCm = SafeOffset;
    }
    if (bForce || !bAnimationMaterialInitialized || SafePhase != LastMaterialNoisePhase)
    {
        DynamicMaterial->SetScalarParameterValue(TEXT("NoisePhase"), SafePhase);
        LastMaterialNoisePhase = SafePhase;
    }
    bAnimationMaterialInitialized = true;
}

void ACloudGeneratorActor::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (!IsAnimationWorld())
    {
        return;
    }
    if (bLocked)
    {
        // A Blueprint or Sequencer may write a property without PostEditChangeProperty.
        // Restore only animation state here; never rebuild guides on a frame tick.
        bAnimated = LockedRecipe.bAnimated;
        OffsetSpeedX = LockedRecipe.OffsetSpeedX;
        OffsetSpeedY = LockedRecipe.OffsetSpeedY;
        OffsetSpeedZ = LockedRecipe.OffsetSpeedZ;
        PhaseSpeed = LockedRecipe.PhaseSpeed;
        TextureOffsetCm = LockedRecipe.TextureOffsetCm;
        NoisePhase = LockedRecipe.NoisePhase;
    }
    else if (bAnimated && FMath::IsFinite(DeltaSeconds) && DeltaSeconds > 0.0f)
    {
#if WITH_EDITOR
        const FVector PreviousOffset = TextureOffsetCm;
        const float PreviousPhase = NoisePhase;
#endif
        auto Advance = [DeltaSeconds](double Value, float Speed)
        {
            const double SafeValue = FMath::IsFinite(Value) ? FMath::Clamp(Value, -1.0e9, 1.0e9) : 0.0;
            const double SafeSpeed = FMath::IsFinite(Speed) ? static_cast<double>(Speed) : 0.0;
            return FMath::Clamp(SafeValue + SafeSpeed * static_cast<double>(DeltaSeconds), -1.0e9, 1.0e9);
        };
        TextureOffsetCm = FVector(Advance(TextureOffsetCm.X, OffsetSpeedX), Advance(TextureOffsetCm.Y, OffsetSpeedY), Advance(TextureOffsetCm.Z, OffsetSpeedZ));
        NoisePhase = static_cast<float>(Advance(NoisePhase, PhaseSpeed));
#if WITH_EDITOR
        // Save All must capture the current frame even after a previous save during preview.
        // No editor transaction is created for per-frame advancement.
        if (GetWorld()->WorldType == EWorldType::Editor &&
            (TextureOffsetCm != PreviousOffset || NoisePhase != PreviousPhase) && !GetOutermost()->IsDirty())
        {
            MarkPackageDirty();
        }
#endif
    }
    UpdateAnimationMaterial();
}

void ACloudGeneratorActor::ResetCloudAnimation()
{
    if (IsTemplate() || IsActorBeingDestroyed() || bDestroyingGenerator || !GetWorld())
    {
        return;
    }
    if (bLocked)
    {
        WorkflowStatus = TEXT("Cloud is locked. Unlock it before resetting animation.");
        return;
    }
#if WITH_EDITOR
    TUniquePtr<FScopedTransaction> Transaction;
    if (GetWorld()->WorldType == EWorldType::Editor && !IsRunningCommandlet())
    {
        Transaction = MakeUnique<FScopedTransaction>(LOCTEXT("ResetCloudAnimation", "Reset Cloud Animation"));
    }
    Modify();
#endif
    TextureOffsetCm = FVector::ZeroVector;
    NoisePhase = 0.0f;
    UpdateAnimationMaterial();
    WorkflowStatus = TEXT("Animation offset and phase reset. Speeds, guides and cloud appearance controls were preserved.");
}

void ACloudGeneratorActor::RefreshCloud()
{
    if (IsTemplate() || IsActorBeingDestroyed() || bDestroyingGenerator || bRefreshing || bRestoringRecipe || !CloudVolume || !GetWorld())
    {
        return;
    }
    TGuardValue<bool> Guard(bRefreshing, true);
    if (bLocked && !bRestoringRecipe)
    {
        RestoreLockedRecipe();
    }
    ApplyQuality();
    TArray<FLinearColor> NewData;
    NewData.SetNumZeroed(GuideDataWidth * MaxGuides);
    ActiveGuideCount = 0;
    BoundsHalfExtentCm = 0.0f;
    BoundsCenterRelativeToAnchorCm = FVector::ZeroVector;
    ComputedExtinctionScale = 0.0f;
    const FVector Anchor = GetActorLocation();
    if (!CloudGenerator::FiniteVector(Anchor))
    {
        CloudVolume->SetVisibility(false);
        PreviewStatus = TEXT("The generator position is invalid.");
        return;
    }
    const double Growth = CloudGenerator::SafeFloat(UnionGrowthLimitCm, 27.5f, 0.0f, CloudGenerator::MaxDimensionCm);
    const double Depth = CloudGenerator::SafeFloat(BillowDepthCm, 550.0f, 0.0f, CloudGenerator::MaxDimensionCm);
    const double Strength = CloudGenerator::SafeFloat(BillowStrength, 1.0f, 0.0f, 1.0f);
    const double Padding = Growth + 0.23 * Depth * Strength;
    FBox PositiveBounds(ForceInit);
    int32 SkippedGuides = 0;
    int32 PositiveCount = 0;
    TSet<const ACloudGuideActor*> Seen;
    Guides.RemoveAll([](const TObjectPtr<ACloudGuideActor>& Item) { return !IsValid(Item); });
    for (ACloudGuideActor* Guide : Guides)
    {
        if (!IsValid(Guide) || Guide->IsActorBeingDestroyed() || Seen.Contains(Guide))
        {
            continue;
        }
        Seen.Add(Guide);
        if (Guide->GetWorld() != GetWorld() || (IsValid(Guide->Generator) && Guide->Generator != this))
        {
            ++SkippedGuides;
            continue;
        }
        if (!Guide->Generator)
        {
            Guide->Generator = this;
        }
        if (!Guide->bEnabled)
        {
            continue;
        }
        if (ActiveGuideCount == MaxGuides)
        {
            ++SkippedGuides;
            continue;
        }
        const FVector Center = Guide->GetActorLocation() - Anchor;
        const FVector Scale = Guide->GetActorScale3D();
        FQuat Rotation = Guide->GetActorQuat();
        if (!CloudGenerator::FiniteVector(Center) || !CloudGenerator::FiniteVector(Scale) || !CloudGenerator::FiniteQuat(Rotation) ||
            !FMath::IsFinite(Guide->SoftnessCm) || Center.GetAbsMax() > CloudGenerator::MaxPositionCm)
        {
            ++SkippedGuides;
            continue;
        }
        FVector Radii = (Scale.GetAbs() * CloudGenerator::GuideUnitRadius).ComponentMax(FVector(0.1));
        if (Radii.GetMax() > CloudGenerator::MaxDimensionCm || Rotation.SizeSquared() < UE_SMALL_NUMBER)
        {
            ++SkippedGuides;
            continue;
        }
        Rotation.Normalize();
        const bool bSphere = Guide->Shape == ECloudGuideShape::Sphere;
        const bool bPositive = Guide->Operation == ECloudGuideOperation::Add;
        FVector Extent = FVector::ZeroVector;
        if (bPositive)
        {
            if (bSphere)
            {
                // Conservative for the shader's approximate ellipsoid signed distance, including thin ellipsoids.
                const FVector InflatedRadii = Radii * (1.0 + Padding / Radii.GetMin());
                Extent = CloudGenerator::RotatedExtent(Rotation, InflatedRadii, true);
            }
            else
            {
                Extent = CloudGenerator::RotatedExtent(Rotation, Radii, false) + FVector(Padding);
            }
            if (!CloudGenerator::FiniteVector(Extent) || Extent.GetMax() > CloudGenerator::MaxPositionCm)
            {
                ++SkippedGuides;
                continue;
            }
            PositiveBounds += FBox(Center - Extent, Center + Extent);
            ++PositiveCount;
        }
        const int32 Row = ActiveGuideCount++ * GuideDataWidth;
        const float Kind = (bSphere ? 1.0f : 2.0f) * (bPositive ? 1.0f : -1.0f);
        NewData[Row] = FLinearColor(Center.X, Center.Y, Center.Z, Kind);
        NewData[Row + 1] = FLinearColor(Radii.X, Radii.Y, Radii.Z, FMath::Clamp(Guide->SoftnessCm, 0.0f, static_cast<float>(CloudGenerator::MaxDimensionCm)));
        NewData[Row + 2] = FLinearColor(Rotation.X, Rotation.Y, Rotation.Z, Rotation.W);
    }
    EncodedGuideData = NewData;
    if (!UploadGuideTexture(NewData))
    {
        CloudVolume->SetVisibility(false);
        PreviewStatus = TEXT("The guide preview data could not be created.");
        return;
    }
    if (Guides.Num() > MaxGuides)
    {
        if (!bWarnedGuideLimit)
        {
            UE_LOG(LogCloudGeneratorTools, Warning, TEXT("%s: only the first %d enabled valid guides can be previewed."), *GetName(), MaxGuides);
            bWarnedGuideLimit = true;
        }
    }
    else
    {
        bWarnedGuideLimit = false;
    }
    if (PositiveCount == 0 || !PositiveBounds.IsValid)
    {
        CloudVolume->SetVisibility(false);
        PreviewStatus = TEXT("Add or enable an additive guide to create a cloud.");
        if (DynamicMaterial)
        {
            DynamicMaterial->SetScalarParameterValue(TEXT("GuideCount"), 0.0f);
        }
        return;
    }
    const double RawHalfExtent = FMath::Max(0.1, PositiveBounds.GetExtent().GetMax());
    // Two voxel widths plus a small numerical margin around the analytically inflated bounds.
    const double HalfExtent = FMath::Max(50.0, RawHalfExtent * (1.0 + 2.0 / 64.0) + 1.0);
    if (!FMath::IsFinite(HalfExtent) || HalfExtent > CloudGenerator::MaxPositionCm)
    {
        CloudVolume->SetVisibility(false);
        PreviewStatus = TEXT("The guide bounds are too large. Reduce guide scale or billow depth.");
        return;
    }
    BoundsHalfExtentCm = static_cast<float>(HalfExtent);
    BoundsCenterRelativeToAnchorCm = PositiveBounds.GetCenter();
    ComputedExtinctionScale = static_cast<float>(0.08 * HalfExtent / 1271.0);
    CloudVolume->SetWorldLocationAndRotation(Anchor + BoundsCenterRelativeToAnchorCm, FQuat::Identity, false, nullptr, ETeleportType::TeleportPhysics);
    CloudVolume->SetWorldScale3D(FVector(HalfExtent / 64.0));
    if (!UpdateMaterial())
    {
        CloudVolume->SetVisibility(false);
        return;
    }
    CloudVolume->SetVisibility(true);
    PreviewStatus = SkippedGuides > 0 ? FString::Printf(TEXT("Preview ready; %d invalid or excess guide(s) skipped."), SkippedGuides) :
        FString::Printf(TEXT("Preview ready: %d guide(s)."), ActiveGuideCount);
}

void ACloudGeneratorActor::PostActorCreated()
{
    Super::PostActorCreated();
    // Do not initialize loaded levels, asset previews, templates or commandlets.
    // PostActorCreated runs for fresh spawns, before their construction scripts.
    const UWorld* World = GetWorld();
    bPendingDefaultPresetPlacement = bUseDefaultPresetOnFirstPlacement &&
        !bDefaultPresetPlacementHandled && !IsTemplate() && !IsRunningCommandlet() &&
        !HasAnyFlags(RF_Transient | RF_WasLoaded) && World &&
        (World->WorldType == EWorldType::Editor || World->WorldType == EWorldType::PIE ||
         World->WorldType == EWorldType::Game || World->WorldType == EWorldType::GamePreview);
#if WITH_EDITOR
    bPendingDefaultPresetPlacement &= !bIsEditorPreviewActor;
#endif
}

void ACloudGeneratorActor::ApplyDefaultPresetOnFirstPlacement()
{
    if (!bPendingDefaultPresetPlacement || IsTemplate() || !GetWorld())
    {
        return;
    }
    // Disarm before ApplyRecipe: spawning and registering guides can re-enter updates.
    bPendingDefaultPresetPlacement = false;
#if WITH_EDITOR
    Modify();
#endif
    bDefaultPresetPlacementHandled = true;
    if (bLocked || !Guides.IsEmpty())
    {
        return;
    }
    if (!IsValid(Preset))
    {
        WorkflowStatus = TEXT("The default cloud preset is missing. Choose a preset and press Load Preset.");
        return;
    }
    ApplyRecipe(Preset->Recipe);
}

void ACloudGeneratorActor::OnConstruction(const FTransform& Transform)
{
    Super::OnConstruction(Transform);
    ApplyDefaultPresetOnFirstPlacement();
    RefreshCloud();
}
void ACloudGeneratorActor::PostRegisterAllComponents()
{
    Super::PostRegisterAllComponents();
    RefreshCloud();
}
void ACloudGeneratorActor::BeginPlay()
{
    Super::BeginPlay();
    RefreshCloud();
}
void ACloudGeneratorActor::Destroyed()
{
    bDestroyingGenerator = true;
    for (ACloudGuideActor* Guide : Guides)
    {
        if (IsValid(Guide) && Guide->Generator == this)
        {
#if WITH_EDITOR
            Guide->Modify();
            if (USceneComponent* GuideRoot = Guide->GetRootComponent())
            {
                GuideRoot->Modify();
            }
#endif
            Guide->Generator = nullptr;
            Guide->DetachFromActor(FDetachmentTransformRules::KeepWorldTransform);
        }
    }
    Super::Destroyed();
}
#if WITH_EDITOR
void ACloudGeneratorActor::PostEditMove(bool bFinished)
{
    Super::PostEditMove(bFinished);
    RefreshCloud();
}
void ACloudGeneratorActor::PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent)
{
    Super::PostEditChangeProperty(PropertyChangedEvent);
    RefreshCloud();
}
void ACloudGeneratorActor::PostEditUndo()
{
    // This transient C++ guard is not restored by the editor transaction.
    bDestroyingGenerator = false;
    Super::PostEditUndo();
    RefreshCloud();
}
#endif


void ACloudGeneratorActor::ApplyQuality()
{
    // Fixed volume resolution keeps local coordinates, density and all shape data identical.
    const float Step = Quality == ECloudPreviewQuality::Cinematic ? 0.5f : 1.0f;
    const float ShadowStep = Quality == ECloudPreviewQuality::Cinematic ? 1.0f : 2.0f;
    const float Lighting = Quality == ECloudPreviewQuality::Cinematic ? 1.0f : 2.0f;
    if (CloudVolume->StepFactor != Step || CloudVolume->ShadowStepFactor != ShadowStep ||
        CloudVolume->LightingDownsampleFactor != Lighting || CloudVolume->VolumeResolution != FIntVector(128))
    {
        CloudVolume->StepFactor = Step;
        CloudVolume->ShadowStepFactor = ShadowStep;
        CloudVolume->LightingDownsampleFactor = Lighting;
        CloudVolume->VolumeResolution = FIntVector(128);
        CloudVolume->MarkRenderStateDirty();
    }
}

FCloudRecipe ACloudGeneratorActor::CaptureRecipe() const
{
    FCloudRecipe Recipe;
    Recipe.Version = 2;
    Recipe.GeneratorScale = GetActorScale3D();
#define COPY_CLOUD_FIELD(Name) Recipe.Name = Name;
    COPY_CLOUD_FIELD(Density) COPY_CLOUD_FIELD(Seed) COPY_CLOUD_FIELD(CloudColor) COPY_CLOUD_FIELD(SkyFill)
    COPY_CLOUD_FIELD(BillowSizeCm) COPY_CLOUD_FIELD(BillowDepthCm) COPY_CLOUD_FIELD(BillowStrength)
    COPY_CLOUD_FIELD(DetailSizeCm) COPY_CLOUD_FIELD(DetailStrength) COPY_CLOUD_FIELD(UnionBlendCm) COPY_CLOUD_FIELD(UnionGrowthLimitCm)
    COPY_CLOUD_FIELD(BillowStyle) COPY_CLOUD_FIELD(CustomShapeNoiseTexture) COPY_CLOUD_FIELD(CustomDetailNoiseTexture)
    COPY_CLOUD_FIELD(ShapeNoiseLayout) COPY_CLOUD_FIELD(DetailNoiseLayout) COPY_CLOUD_FIELD(NoiseTiling) COPY_CLOUD_FIELD(NoiseContrast) COPY_CLOUD_FIELD(WarpAmount)
    COPY_CLOUD_FIELD(NoiseBrightness) COPY_CLOUD_FIELD(NoiseTextureContrast)
    COPY_CLOUD_FIELD(bAnimated) COPY_CLOUD_FIELD(OffsetSpeedX) COPY_CLOUD_FIELD(OffsetSpeedY) COPY_CLOUD_FIELD(OffsetSpeedZ) COPY_CLOUD_FIELD(PhaseSpeed)
    COPY_CLOUD_FIELD(TextureOffsetCm) COPY_CLOUD_FIELD(NoisePhase)
    COPY_CLOUD_FIELD(LargeBreakupAmount) COPY_CLOUD_FIELD(LargeBreakupScaleX) COPY_CLOUD_FIELD(LargeBreakupScaleY) COPY_CLOUD_FIELD(LargeBreakupScaleZ) COPY_CLOUD_FIELD(LargeBreakupBrightness) COPY_CLOUD_FIELD(LargeBreakupContrast)
    COPY_CLOUD_FIELD(LevelsInputLow) COPY_CLOUD_FIELD(LevelsInputMid) COPY_CLOUD_FIELD(LevelsInputHigh) COPY_CLOUD_FIELD(LevelsOutputLow) COPY_CLOUD_FIELD(LevelsOutputHigh)
    COPY_CLOUD_FIELD(CloudStyle) COPY_CLOUD_FIELD(WispStrength) COPY_CLOUD_FIELD(WispStretch) COPY_CLOUD_FIELD(WispDirectionDegrees)
    COPY_CLOUD_FIELD(InteriorVariation) COPY_CLOUD_FIELD(VerticalDensityGradient) COPY_CLOUD_FIELD(VerticalReferenceHeightCm) COPY_CLOUD_FIELD(CloudMaterial)
#undef COPY_CLOUD_FIELD
    for (const ACloudGuideActor* Guide : Guides)
    {
        if (!IsValid(Guide) || Guide->IsActorBeingDestroyed() || Guide->Generator != this || Recipe.Guides.Num() >= MaxGuides)
        {
            continue;
        }
        FCloudGuideRecipe& SavedGuide = Recipe.Guides.AddDefaulted_GetRef();
        SavedGuide.LocalTransform = Guide->GetActorTransform().GetRelativeTransform(GetActorTransform());
        SavedGuide.Shape = Guide->Shape;
        SavedGuide.Operation = Guide->Operation;
        SavedGuide.SoftnessCm = Guide->SoftnessCm;
        SavedGuide.bEnabled = Guide->bEnabled;
        SavedGuide.GuideId = Guide->GuideId;
    }
    return Recipe;
}

void ACloudGeneratorActor::ApplyAppearance(const FCloudRecipe& Recipe)
{
#define COPY_CLOUD_FIELD(Name) Name = Recipe.Name;
    COPY_CLOUD_FIELD(Density) COPY_CLOUD_FIELD(Seed) COPY_CLOUD_FIELD(CloudColor) COPY_CLOUD_FIELD(SkyFill)
    COPY_CLOUD_FIELD(BillowSizeCm) COPY_CLOUD_FIELD(BillowDepthCm) COPY_CLOUD_FIELD(BillowStrength)
    COPY_CLOUD_FIELD(DetailSizeCm) COPY_CLOUD_FIELD(DetailStrength) COPY_CLOUD_FIELD(UnionBlendCm) COPY_CLOUD_FIELD(UnionGrowthLimitCm)
    COPY_CLOUD_FIELD(BillowStyle) COPY_CLOUD_FIELD(CustomShapeNoiseTexture) COPY_CLOUD_FIELD(CustomDetailNoiseTexture)
    COPY_CLOUD_FIELD(ShapeNoiseLayout) COPY_CLOUD_FIELD(DetailNoiseLayout) COPY_CLOUD_FIELD(NoiseTiling) COPY_CLOUD_FIELD(NoiseContrast) COPY_CLOUD_FIELD(WarpAmount)
    COPY_CLOUD_FIELD(NoiseBrightness) COPY_CLOUD_FIELD(NoiseTextureContrast)
    COPY_CLOUD_FIELD(bAnimated) COPY_CLOUD_FIELD(OffsetSpeedX) COPY_CLOUD_FIELD(OffsetSpeedY) COPY_CLOUD_FIELD(OffsetSpeedZ) COPY_CLOUD_FIELD(PhaseSpeed)
    COPY_CLOUD_FIELD(TextureOffsetCm) COPY_CLOUD_FIELD(NoisePhase)
    COPY_CLOUD_FIELD(LargeBreakupAmount) COPY_CLOUD_FIELD(LargeBreakupScaleX) COPY_CLOUD_FIELD(LargeBreakupScaleY) COPY_CLOUD_FIELD(LargeBreakupScaleZ) COPY_CLOUD_FIELD(LargeBreakupBrightness) COPY_CLOUD_FIELD(LargeBreakupContrast)
    COPY_CLOUD_FIELD(LevelsInputLow) COPY_CLOUD_FIELD(LevelsInputMid) COPY_CLOUD_FIELD(LevelsInputHigh) COPY_CLOUD_FIELD(LevelsOutputLow) COPY_CLOUD_FIELD(LevelsOutputHigh)
    COPY_CLOUD_FIELD(CloudStyle) COPY_CLOUD_FIELD(WispStrength) COPY_CLOUD_FIELD(WispStretch) COPY_CLOUD_FIELD(WispDirectionDegrees)
    COPY_CLOUD_FIELD(InteriorVariation) COPY_CLOUD_FIELD(VerticalDensityGradient) COPY_CLOUD_FIELD(VerticalReferenceHeightCm) COPY_CLOUD_FIELD(CloudMaterial)
#undef COPY_CLOUD_FIELD
    UpdateAnimationMaterial();
}

ACloudGuideActor* ACloudGeneratorActor::SpawnRecipeGuide(const FCloudGuideRecipe& Recipe)
{
    FActorSpawnParameters Params;
    Params.OverrideLevel = GetLevel();
    Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    Params.ObjectFlags |= RF_Transactional;
    Params.bAllowDuringConstructionScript = true;
    ACloudGuideActor* Guide = GetWorld()->SpawnActor<ACloudGuideActor>(ACloudGuideActor::StaticClass(), Recipe.LocalTransform * GetActorTransform(), Params);
    if (!Guide)
    {
        return nullptr;
    }
    Guide->Generator = this;
    Guide->GuideId = Recipe.GuideId.IsValid() ? Recipe.GuideId : FGuid::NewGuid();
    Guide->Shape = Recipe.Shape;
    Guide->Operation = Recipe.Operation;
    Guide->SoftnessCm = Recipe.SoftnessCm;
    Guide->bEnabled = Recipe.bEnabled;
    Guide->AttachToComponent(SceneRoot, FAttachmentTransformRules::KeepWorldTransform);
    Guide->SetActorRelativeTransform(Recipe.LocalTransform);
    RegisterGuide(Guide);
#if WITH_EDITOR
    Guide->SetActorLabel(FString::Printf(TEXT("Cloud Guide %02d"), Guides.Num()));
#endif
    Guide->NotifyGenerator();
    return Guide;
}

bool ACloudGeneratorActor::ApplyRecipe(const FCloudRecipe& Recipe)
{
    if (IsTemplate() || !GetWorld() || IsActorBeingDestroyed() || bDestroyingGenerator || bRestoringRecipe || bLocked)
    {
        WorkflowStatus = bLocked ? TEXT("Cloud is locked. Unlock it before loading a preset.") : TEXT("The cloud is not ready to load a preset.");
        return false;
    }
    if ((Recipe.Version != 1 && Recipe.Version != 2) || Recipe.Guides.Num() > MaxGuides)
    {
        WorkflowStatus = TEXT("This recipe version or guide count is not supported.");
        return false;
    }
    if (Recipe.Version >= 2 && (!CloudGenerator::FiniteVector(Recipe.GeneratorScale) ||
        Recipe.GeneratorScale.GetAbsMin() < UE_SMALL_NUMBER))
    {
        WorkflowStatus = TEXT("The preset contains an invalid or zero generator scale. The previous cloud was preserved.");
        return false;
    }
    for (const FCloudGuideRecipe& Guide : Recipe.Guides)
    {
        if (Guide.LocalTransform.ContainsNaN() || !Guide.LocalTransform.GetRotation().IsNormalized() || !FMath::IsFinite(Guide.SoftnessCm))
        {
            WorkflowStatus = TEXT("The preset contains an invalid guide transform or softness.");
            return false;
        }
    }
#if WITH_EDITOR
    TUniquePtr<FScopedTransaction> Transaction;
    if (GetWorld()->WorldType == EWorldType::Editor && !IsRunningCommandlet())
    {
        Transaction = MakeUnique<FScopedTransaction>(LOCTEXT("LoadCloudRecipe", "Load Cloud Preset"));
    }
    Modify();
#endif
    // Copy first: callers may pass data owned by this actor or a preset in an editor transaction.
    const FCloudRecipe RecipeCopy = Recipe;
    const FVector PreviousGeneratorScale = GetActorScale3D();
    bool bCreatedAllGuides = true;
    {
        TGuardValue<bool> Guard(bRestoringRecipe, true);
        const TArray<TObjectPtr<ACloudGuideActor>> PreviousGuides = Guides;
        Guides.Reset();
        if (RecipeCopy.Version >= 2)
        {
#if WITH_EDITOR
            if (SceneRoot) SceneRoot->Modify();
#endif
            // Scale belongs to the authored shape. Preserve this instance's placement
            // and rotation, and leave world-space noise size/animation unchanged.
            SetActorScale3D(RecipeCopy.GeneratorScale);
        }
        // Stage replacement actors first; failed creation preserves the complete old recipe.
        for (const FCloudGuideRecipe& Guide : RecipeCopy.Guides)
        {
            if (!SpawnRecipeGuide(Guide))
            {
                bCreatedAllGuides = false;
                break;
            }
        }
        const TArray<TObjectPtr<ACloudGuideActor>> ToRemove = bCreatedAllGuides ? PreviousGuides : Guides;
        for (ACloudGuideActor* Guide : ToRemove)
        {
            if (IsValid(Guide) && Guide->Generator == this)
            {
#if WITH_EDITOR
                Guide->Modify();
#endif
                Guide->Generator = nullptr;
                GetWorld()->DestroyActor(Guide);
            }
        }
        if (bCreatedAllGuides)
        {
            ApplyAppearance(RecipeCopy);
        }
        else
        {
            Guides = PreviousGuides;
            SetActorScale3D(PreviousGeneratorScale);
        }
    }
    if (!bCreatedAllGuides)
    {
        RefreshCloud();
        WorkflowStatus = TEXT("A preset guide could not be created. The previous cloud was preserved.");
        return false;
    }
    RefreshCloud();
    WorkflowStatus = FString::Printf(TEXT("Loaded %d guide(s). The cloud remains editable."), Guides.Num());
    return true;
}

void ACloudGeneratorActor::GenerateVariation()
{
    if (IsTemplate() || bLocked)
    {
        WorkflowStatus = TEXT("Cloud is locked. Unlock it before generating a variation.");
        return;
    }
#if WITH_EDITOR
    TUniquePtr<FScopedTransaction> Transaction;
    if (GetWorld() && GetWorld()->WorldType == EWorldType::Editor && !IsRunningCommandlet())
    {
        Transaction = MakeUnique<FScopedTransaction>(LOCTEXT("CloudVariation", "Generate Cloud Variation"));
    }
    Modify();
#endif
    const float PreviousSeed = Seed;
    Seed = static_cast<float>(FMath::RandRange(1, 999999));
    if (Seed == PreviousSeed)
    {
        Seed = Seed < 999999.0f ? Seed + 1.0f : 1.0f;
    }
    RefreshCloud();
    WorkflowStatus = TEXT("New variation generated. Guide shapes and appearance settings were preserved.");
}

void ACloudGeneratorActor::SavePreset()
{
#if WITH_EDITOR
    if (IsTemplate() || !GetWorld() || IsActorBeingDestroyed())
    {
        return;
    }
    RefreshCloud();
    FString SafeName = ObjectTools::SanitizeObjectName(PresetName.TrimStartAndEnd());
    if (SafeName.IsEmpty())
    {
        SafeName = TEXT("MyCloud");
    }
    SafeName = SafeName.Left(80);
    if (!SafeName.StartsWith(TEXT("CP_")))
    {
        SafeName = TEXT("CP_") + SafeName;
    }
    FString SaveDirectory = PresetSaveDirectory.TrimStartAndEnd().Replace(TEXT("\\"), TEXT("/"));
    while (SaveDirectory.RemoveFromEnd(TEXT("/"))) {}
    FText InvalidPathReason;
    if (!(SaveDirectory == TEXT("/Game") || SaveDirectory.StartsWith(TEXT("/Game/"))) ||
        !FPackageName::IsValidLongPackageName(SaveDirectory + TEXT("/") + SafeName, false, &InvalidPathReason))
    {
        WorkflowStatus = TEXT("Preset Save Folder must be a valid project Content path, such as /Game/OnlyClouds/Presets. Nothing was saved.");
        return;
    }
    FString PackageName;
    FString AssetName;
    FAssetToolsModule& AssetTools = FModuleManager::LoadModuleChecked<FAssetToolsModule>(TEXT("AssetTools"));
    AssetTools.Get().CreateUniqueAssetName(SaveDirectory + TEXT("/") + SafeName, TEXT(""), PackageName, AssetName);
    UPackage* Package = CreatePackage(*PackageName);
    UCloudRecipePreset* SavedPreset = NewObject<UCloudRecipePreset>(Package, *AssetName, RF_Public | RF_Standalone | RF_Transactional);
    SavedPreset->Recipe = CaptureRecipe();
    SavedPreset->Description = TEXT("Editable cloud recipe: guides, generator scale, appearance, seed and animation state. Rendering quality, location and rotation are chosen on the generator.");
    FAssetRegistryModule::AssetCreated(SavedPreset);
    SavedPreset->MarkPackageDirty();
    const FString Filename = FPackageName::LongPackageNameToFilename(PackageName, FPackageName::GetAssetPackageExtension());
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(Filename), true);
    FSavePackageArgs SaveArgs;
    SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
    SaveArgs.SaveFlags = SAVE_NoError;
    if (!UPackage::SavePackage(Package, SavedPreset, *Filename, SaveArgs))
    {
        WorkflowStatus = TEXT("Preset created but could not be saved to disk. Check folder access and save the asset in the Content Browser.");
        return;
    }
    Modify();
    Preset = SavedPreset;
    WorkflowStatus = FString::Printf(TEXT("Saved %s. Existing presets were preserved."), *SavedPreset->GetPathName());
#else
    WorkflowStatus = TEXT("Save Preset is available in the Unreal Editor.");
#endif
}

void ACloudGeneratorActor::LoadPreset()
{
    if (!Preset)
    {
        WorkflowStatus = TEXT("Choose a preset asset, then press Load Preset.");
        return;
    }
    ApplyRecipe(Preset->Recipe);
}

void ACloudGeneratorActor::LockCloud()
{
    if (IsTemplate() || bLocked || !GetWorld())
    {
        return;
    }
    RefreshCloud();
#if WITH_EDITOR
    TUniquePtr<FScopedTransaction> Transaction;
    if (GetWorld()->WorldType == EWorldType::Editor && !IsRunningCommandlet())
    {
        Transaction = MakeUnique<FScopedTransaction>(LOCTEXT("LockCloud", "Lock Cloud"));
    }
    Modify();
#endif
    LockedRecipe = CaptureRecipe();
    bLocked = true;
    WorkflowStatus = TEXT("Cloud locked at the current animation frame. Move the whole generator or change quality; unlock to edit or resume animation.");
}

void ACloudGeneratorActor::UnlockCloud()
{
    if (IsTemplate() || !bLocked)
    {
        return;
    }
#if WITH_EDITOR
    TUniquePtr<FScopedTransaction> Transaction;
    if (GetWorld() && GetWorld()->WorldType == EWorldType::Editor && !IsRunningCommandlet())
    {
        Transaction = MakeUnique<FScopedTransaction>(LOCTEXT("UnlockCloud", "Unlock Cloud"));
    }
    Modify();
#endif
    bLocked = false;
    WorkflowStatus = TEXT("Cloud unlocked and ready to edit.");
}

void ACloudGeneratorActor::RestoreLockedRecipe()
{
    TGuardValue<bool> Guard(bRestoringRecipe, true);
    ApplyAppearance(LockedRecipe);
    TArray<TObjectPtr<ACloudGuideActor>> RestoredGuides;
    for (const FCloudGuideRecipe& Recipe : LockedRecipe.Guides)
    {
        ACloudGuideActor* Guide = nullptr;
        for (ACloudGuideActor* Candidate : Guides)
        {
            if (IsValid(Candidate) && !Candidate->IsActorBeingDestroyed() && Candidate->GuideId == Recipe.GuideId && !RestoredGuides.Contains(Candidate))
            {
                Guide = Candidate;
                break;
            }
        }
        if (!Guide)
        {
            // Deleting a protected guide recreates it from the persistent recipe snapshot.
            Guide = SpawnRecipeGuide(Recipe);
        }
        if (!Guide)
        {
            WorkflowStatus = TEXT("A locked guide could not be restored. Press Refresh Cloud to retry.");
            continue;
        }
        Guide->Generator = this;
        Guide->Shape = Recipe.Shape;
        Guide->Operation = Recipe.Operation;
        Guide->SoftnessCm = Recipe.SoftnessCm;
        Guide->bEnabled = Recipe.bEnabled;
        if (Guide->GetAttachParentActor() != this)
        {
            Guide->AttachToComponent(SceneRoot, FAttachmentTransformRules::KeepWorldTransform);
        }
        if (!Guide->GetRootComponent()->GetRelativeTransform().Equals(Recipe.LocalTransform, 0.0001))
        {
            Guide->SetActorRelativeTransform(Recipe.LocalTransform);
        }
        Guide->GuideShape->MarkRenderStateDirty();
        RestoredGuides.Add(Guide);
    }
    Guides = MoveTemp(RestoredGuides);
}

#undef LOCTEXT_NAMESPACE

