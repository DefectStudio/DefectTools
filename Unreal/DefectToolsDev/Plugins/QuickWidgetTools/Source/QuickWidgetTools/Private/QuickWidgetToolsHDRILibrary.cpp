#include "QuickWidgetToolsHDRILibrary.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "Engine/TextureCube.h"
#include "Engine/TextureRenderTargetCube.h"
#include "Misc/PackageName.h"
#include "RHITypes.h"
#include "RenderingThread.h"
#include "TextureResource.h"
#include "UObject/Package.h"

UTextureRenderTargetCube* UQuickWidgetToolsHDRILibrary::CreateHDRCubeRenderTarget(int32 FaceSize)
{
	if (FaceSize < 16 || FaceSize > 8192 || !FMath::IsPowerOfTwo(FaceSize))
	{
		UE_LOG(LogTemp, Error, TEXT("Quick Widget Tools HDRI: face size must be a power of two from 16 to 8192 (received %d)."), FaceSize);
		return nullptr;
	}

	UTextureRenderTargetCube* RenderTarget = NewObject<UTextureRenderTargetCube>(GetTransientPackage(), NAME_None, RF_Transient);
	RenderTarget->bHDR = true;
	RenderTarget->bForceLinearGamma = true;
	RenderTarget->bAutoGenerateMips = false;
	RenderTarget->ClearColor = FLinearColor::Black;
	RenderTarget->InitAutoFormat(static_cast<uint32>(FaceSize));
	RenderTarget->UpdateResourceImmediate(true);
	FlushRenderingCommands();
	return RenderTarget;
}

void UQuickWidgetToolsHDRILibrary::FlushHDRICaptureRendering()
{
	FlushRenderingCommands();
}

UTextureCube* UQuickWidgetToolsHDRILibrary::CreateHDRTextureCube(UTextureRenderTargetCube* RenderTarget, const FString& PackagePath)
{
	if (!IsValid(RenderTarget) || RenderTarget->GetFormat() != PF_FloatRGBA)
	{
		UE_LOG(LogTemp, Error, TEXT("Quick Widget Tools HDRI: a valid RGBA16F cube render target is required."));
		return nullptr;
	}

	const int32 FaceSize = RenderTarget->SizeX;
	if (FaceSize < 16 || FaceSize > 8192 || !FMath::IsPowerOfTwo(FaceSize)
		|| !PackagePath.StartsWith(TEXT("/Game/")) || !FPackageName::IsValidLongPackageName(PackagePath)
		|| FPackageName::DoesPackageExist(PackagePath) || FindPackage(nullptr, *PackagePath))
	{
		UE_LOG(LogTemp, Error, TEXT("Quick Widget Tools HDRI: invalid cube size or package path, or the destination already exists: %s"), *PackagePath);
		return nullptr;
	}

	FlushRenderingCommands();
	FTextureRenderTargetResource* Resource = RenderTarget->GameThread_GetRenderTargetResource();
	if (!Resource)
	{
		UE_LOG(LogTemp, Error, TEXT("Quick Widget Tools HDRI: the cube render target resource has been released."));
		return nullptr;
	}

	UPackage* Package = CreatePackage(*PackagePath);
	UTextureCube* TextureCube = NewObject<UTextureCube>(Package, *FPackageName::GetLongPackageAssetName(PackagePath), RF_Public | RF_Standalone);
	TextureCube->PreEditChange(nullptr);
	TextureCube->Source.Init(FaceSize, FaceSize, 6, 1, TSF_RGBA16F);
	uint8* SourceData = TextureCube->Source.LockMip(0);
	const int64 FaceBytes = static_cast<int64>(FaceSize) * FaceSize * sizeof(FFloat16Color);
	bool bReadSuccess = SourceData != nullptr;

	// UE's general render-target conversion allocates a 32-bit byte array for
	// all faces. Read one face at a time to support the 3 GiB 8192px HDR source.
	TArray<FFloat16Color> FacePixels;
	for (int32 FaceIndex = 0; bReadSuccess && FaceIndex < 6; ++FaceIndex)
	{
		FReadSurfaceDataFlags ReadFlags(RCM_MinMax, static_cast<ECubeFace>(FaceIndex));
		ReadFlags.SetLinearToGamma(false);
		bReadSuccess = Resource->ReadFloat16Pixels(FacePixels, ReadFlags)
			&& FacePixels.Num() == FaceSize * FaceSize;
		if (bReadSuccess)
		{
			for (FFloat16Color& Pixel : FacePixels)
			{
				Pixel.A.SetOne();
			}
			FMemory::Memcpy(SourceData + static_cast<int64>(FaceIndex) * FaceBytes, FacePixels.GetData(), static_cast<SIZE_T>(FaceBytes));
		}
	}
	FacePixels.Empty();
	if (SourceData)
	{
		TextureCube->Source.UnlockMip(0);
	}
	if (!bReadSuccess)
	{
		UE_LOG(LogTemp, Error, TEXT("Quick Widget Tools HDRI: failed to read all six cube faces."));
		TextureCube->ClearFlags(RF_Public | RF_Standalone);
		TextureCube->MarkAsGarbage();
		return nullptr;
	}

	TextureCube->SRGB = false;
	TextureCube->CompressionSettings = TC_HDR_Compressed;
	TextureCube->LODGroup = TEXTUREGROUP_Skybox;
	TextureCube->LODBias = 0;
	TextureCube->MaxTextureSize = FaceSize;
	TextureCube->MipGenSettings = TMGS_FromTextureGroup;
	TextureCube->NeverStream = true;
	TextureCube->PostEditChange();
	FAssetRegistryModule::AssetCreated(TextureCube);
	TextureCube->MarkPackageDirty();
	return TextureCube;
}

void UQuickWidgetToolsHDRILibrary::ReleaseHDRCubeRenderTarget(UTextureRenderTargetCube* RenderTarget)
{
	if (IsValid(RenderTarget))
	{
		RenderTarget->ReleaseResource();
		FlushRenderingCommands();
	}
}

int32 UQuickWidgetToolsHDRILibrary::GetHDRCubeSourceSize(UTextureCube* TextureCube)
{
	return IsValid(TextureCube) && TextureCube->Source.IsValid() ? TextureCube->Source.GetSizeX() : 0;
}

int32 UQuickWidgetToolsHDRILibrary::GetHDRCubeSourceSliceCount(UTextureCube* TextureCube)
{
	return IsValid(TextureCube) && TextureCube->Source.IsValid() ? TextureCube->Source.GetNumSlices() : 0;
}
