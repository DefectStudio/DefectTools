#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "QuickWidgetToolsHDRILibrary.generated.h"

class UTextureCube;
class UTextureRenderTargetCube;

/** Editor-only HDR cubemap helpers for the Quick Widget Tools snapshot button. */
UCLASS()
class QUICKWIDGETTOOLS_API UQuickWidgetToolsHDRILibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Creates a transient linear RGBA16F cube target. FaceSize must be a power of two from 16 to 8192. */
	UFUNCTION(BlueprintCallable, Category = "Quick Widget Tools|HDRI")
	static UTextureRenderTargetCube* CreateHDRCubeRenderTarget(int32 FaceSize);

	/** Waits for queued capture rendering before the cube is converted to a texture asset. */
	UFUNCTION(BlueprintCallable, Category = "Quick Widget Tools|HDRI")
	static void FlushHDRICaptureRendering();

	/** Reads six HDR faces into a new asset at an unused long package path; the caller saves the returned asset. */
	UFUNCTION(BlueprintCallable, Category = "Quick Widget Tools|HDRI")
	static UTextureCube* CreateHDRTextureCube(UTextureRenderTargetCube* RenderTarget, const FString& PackagePath);

	/** Releases the transient cube's GPU resource after the capture component has detached it. */
	UFUNCTION(BlueprintCallable, Category = "Quick Widget Tools|HDRI")
	static void ReleaseHDRCubeRenderTarget(UTextureRenderTargetCube* RenderTarget);

	/** Returns the stored source face width, independently of texture streaming or preview LODs. */
	UFUNCTION(BlueprintPure, Category = "Quick Widget Tools|HDRI")
	static int32 GetHDRCubeSourceSize(UTextureCube* TextureCube);

	/** Returns the stored source slice count; an HDR cubemap must contain six faces. */
	UFUNCTION(BlueprintPure, Category = "Quick Widget Tools|HDRI")
	static int32 GetHDRCubeSourceSliceCount(UTextureCube* TextureCube);
};
