// Copyright Epic Games, Inc. All Rights Reserved.
/*===========================================================================
	Generated code exported from UnrealHeaderTool.
	DO NOT modify this manually! Edit the corresponding .h files instead!
===========================================================================*/

#include "UObject/GeneratedCppIncludes.h"
#include "QuickWidgetToolsHDRILibrary.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS
static_assert(!UE_WITH_CONSTINIT_UOBJECT, "This generated code can only be compiled with !UE_WITH_CONSTINIT_UOBJECT");
void EmptyLinkFunctionForGeneratedCodeQuickWidgetToolsHDRILibrary() {}

// ********** Begin Cross Module References ********************************************************
ENGINE_API UClass* Z_Construct_UClass_UBlueprintFunctionLibrary(ETypeConstructPhase);
ENGINE_API UClass* Z_Construct_UClass_UTextureCube(ETypeConstructPhase);
ENGINE_API UClass* Z_Construct_UClass_UTextureRenderTargetCube(ETypeConstructPhase);
// ********** End Cross Module References **********************************************************

// ********** Begin Same Module References *********************************************************
UPackage* Z_Construct_UPackage__Script_QuickWidgetTools(ETypeConstructPhase);
QUICKWIDGETTOOLS_API UClass* Z_Construct_UClass_UQuickWidgetToolsHDRILibrary(ETypeConstructPhase);
QUICKWIDGETTOOLS_API UClass* Z_Construct_UClass_UQuickWidgetToolsHDRILibrary(ETypeConstructPhase);
// ********** End Same Module References ***********************************************************
#define UHT_STRUCT_BASE(INIT) UE::CodeGen::ConstInit::TCompiledInObjectPtr<const FStructBaseChain>(UE::Private::AsStructBaseChain(INIT))

// ********** Begin Class UQuickWidgetToolsHDRILibrary Function CreateHDRCubeRenderTarget **********
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_UQuickWidgetToolsHDRILibrary_CreateHDRCubeRenderTarget_Statics
struct UHT_STATICS
{
	struct QuickWidgetToolsHDRILibrary_eventCreateHDRCubeRenderTarget_Parms
	{
		int32 FaceSize;
		UTextureRenderTargetCube* ReturnValue;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "Category", "Quick Widget Tools|HDRI" },
		{ "Comment", "/** Creates a transient linear RGBA16F cube target. FaceSize must be a power of two from 16 to 8192. */" },
		{ "ModuleRelativePath", "Public/QuickWidgetToolsHDRILibrary.h" },
		{ "ToolTip", "Creates a transient linear RGBA16F cube target. FaceSize must be a power of two from 16 to 8192." },
	};
#endif // WITH_METADATA

// ********** Begin Function CreateHDRCubeRenderTarget constinit property declarations *************
	static const UECodeGen_Private::FIntPropertyParams NewProp_FaceSize;
	static const UECodeGen_Private::FObjectPropertyParams NewProp_ReturnValue;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
// ********** End Function CreateHDRCubeRenderTarget constinit property declarations ***************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};

// ********** Begin Function CreateHDRCubeRenderTarget Property Definitions ************************
const UECodeGen_Private::FIntPropertyParams UHT_STATICS::NewProp_FaceSize = { "FaceSize", nullptr, (EPropertyFlags)0x0010000000000080, UECodeGen_Private::EPropertyGenFlags::Int, nullptr, nullptr, 1, STRUCT_OFFSET(QuickWidgetToolsHDRILibrary_eventCreateHDRCubeRenderTarget_Parms, FaceSize), METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FObjectPropertyParams UHT_STATICS::NewProp_ReturnValue = { "ReturnValue", nullptr, (EPropertyFlags)0x0010000000000580, UECodeGen_Private::EPropertyGenFlags::Object, nullptr, nullptr, 1, STRUCT_OFFSET(QuickWidgetToolsHDRILibrary_eventCreateHDRCubeRenderTarget_Parms, ReturnValue), Z_Construct_UClass_UTextureRenderTargetCube, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FPropertyParamsBase* const UHT_STATICS::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_FaceSize,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ReturnValue,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::PropPointers) < 2048);
// ********** End Function CreateHDRCubeRenderTarget Property Definitions **************************
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_UQuickWidgetToolsHDRILibrary, nullptr, "CreateHDRCubeRenderTarget", UHT_STATICS::PropPointers, UE_ARRAY_COUNT(UHT_STATICS::PropPointers), DataSizeOf<UHT_STATICS::QuickWidgetToolsHDRILibrary_eventCreateHDRCubeRenderTarget_Parms>(), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04022401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
static_assert(sizeof(UHT_STATICS::QuickWidgetToolsHDRILibrary_eventCreateHDRCubeRenderTarget_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_UQuickWidgetToolsHDRILibrary_CreateHDRCubeRenderTarget(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(UQuickWidgetToolsHDRILibrary::execCreateHDRCubeRenderTarget)
{
	P_GET_PROPERTY(FIntProperty,Z_Param_FaceSize);
	P_FINISH;
	P_NATIVE_BEGIN;
	*(UTextureRenderTargetCube**)Z_Param__Result=UQuickWidgetToolsHDRILibrary::CreateHDRCubeRenderTarget(Z_Param_FaceSize);
	P_NATIVE_END;
}
// ********** End Class UQuickWidgetToolsHDRILibrary Function CreateHDRCubeRenderTarget ************

// ********** Begin Class UQuickWidgetToolsHDRILibrary Function CreateHDRTextureCube ***************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_UQuickWidgetToolsHDRILibrary_CreateHDRTextureCube_Statics
struct UHT_STATICS
{
	struct QuickWidgetToolsHDRILibrary_eventCreateHDRTextureCube_Parms
	{
		UTextureRenderTargetCube* RenderTarget;
		FString PackagePath;
		UTextureCube* ReturnValue;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "Category", "Quick Widget Tools|HDRI" },
		{ "Comment", "/** Reads six HDR faces into a new asset at an unused long package path; the caller saves the returned asset. */" },
		{ "ModuleRelativePath", "Public/QuickWidgetToolsHDRILibrary.h" },
		{ "ToolTip", "Reads six HDR faces into a new asset at an unused long package path; the caller saves the returned asset." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_PackagePath_MetaData[] = {
		{ "NativeConst", "" },
	};
#endif // WITH_METADATA

// ********** Begin Function CreateHDRTextureCube constinit property declarations ******************
	static const UECodeGen_Private::FObjectPropertyParams NewProp_RenderTarget;
	static const UECodeGen_Private::FStrPropertyParams NewProp_PackagePath;
	static const UECodeGen_Private::FObjectPropertyParams NewProp_ReturnValue;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
// ********** End Function CreateHDRTextureCube constinit property declarations ********************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};

// ********** Begin Function CreateHDRTextureCube Property Definitions *****************************
const UECodeGen_Private::FObjectPropertyParams UHT_STATICS::NewProp_RenderTarget = { "RenderTarget", nullptr, (EPropertyFlags)0x0010000000000080, UECodeGen_Private::EPropertyGenFlags::Object, nullptr, nullptr, 1, STRUCT_OFFSET(QuickWidgetToolsHDRILibrary_eventCreateHDRTextureCube_Parms, RenderTarget), Z_Construct_UClass_UTextureRenderTargetCube, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FStrPropertyParams UHT_STATICS::NewProp_PackagePath = { "PackagePath", nullptr, (EPropertyFlags)0x0010000000000080, UECodeGen_Private::EPropertyGenFlags::Str, nullptr, nullptr, 1, STRUCT_OFFSET(QuickWidgetToolsHDRILibrary_eventCreateHDRTextureCube_Parms, PackagePath), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_PackagePath_MetaData), NewProp_PackagePath_MetaData) };
const UECodeGen_Private::FObjectPropertyParams UHT_STATICS::NewProp_ReturnValue = { "ReturnValue", nullptr, (EPropertyFlags)0x0010000000000580, UECodeGen_Private::EPropertyGenFlags::Object, nullptr, nullptr, 1, STRUCT_OFFSET(QuickWidgetToolsHDRILibrary_eventCreateHDRTextureCube_Parms, ReturnValue), Z_Construct_UClass_UTextureCube, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FPropertyParamsBase* const UHT_STATICS::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_RenderTarget,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_PackagePath,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ReturnValue,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::PropPointers) < 2048);
// ********** End Function CreateHDRTextureCube Property Definitions *******************************
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_UQuickWidgetToolsHDRILibrary, nullptr, "CreateHDRTextureCube", UHT_STATICS::PropPointers, UE_ARRAY_COUNT(UHT_STATICS::PropPointers), DataSizeOf<UHT_STATICS::QuickWidgetToolsHDRILibrary_eventCreateHDRTextureCube_Parms>(), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04022401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
static_assert(sizeof(UHT_STATICS::QuickWidgetToolsHDRILibrary_eventCreateHDRTextureCube_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_UQuickWidgetToolsHDRILibrary_CreateHDRTextureCube(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(UQuickWidgetToolsHDRILibrary::execCreateHDRTextureCube)
{
	P_GET_OBJECT(UTextureRenderTargetCube,Z_Param_RenderTarget);
	P_GET_PROPERTY(FStrProperty,Z_Param_PackagePath);
	P_FINISH;
	P_NATIVE_BEGIN;
	*(UTextureCube**)Z_Param__Result=UQuickWidgetToolsHDRILibrary::CreateHDRTextureCube(Z_Param_RenderTarget,Z_Param_PackagePath);
	P_NATIVE_END;
}
// ********** End Class UQuickWidgetToolsHDRILibrary Function CreateHDRTextureCube *****************

// ********** Begin Class UQuickWidgetToolsHDRILibrary Function FlushHDRICaptureRendering **********
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_UQuickWidgetToolsHDRILibrary_FlushHDRICaptureRendering_Statics
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "Category", "Quick Widget Tools|HDRI" },
		{ "Comment", "/** Waits for queued capture rendering before the cube is converted to a texture asset. */" },
		{ "ModuleRelativePath", "Public/QuickWidgetToolsHDRILibrary.h" },
		{ "ToolTip", "Waits for queued capture rendering before the cube is converted to a texture asset." },
	};
#endif // WITH_METADATA

// ********** Begin Function FlushHDRICaptureRendering constinit property declarations *************
// ********** End Function FlushHDRICaptureRendering constinit property declarations ***************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_UQuickWidgetToolsHDRILibrary, nullptr, "FlushHDRICaptureRendering", nullptr, 0, 0, RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04022401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
UFunction* Z_Construct_UFunction_UQuickWidgetToolsHDRILibrary_FlushHDRICaptureRendering(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(UQuickWidgetToolsHDRILibrary::execFlushHDRICaptureRendering)
{
	P_FINISH;
	P_NATIVE_BEGIN;
	UQuickWidgetToolsHDRILibrary::FlushHDRICaptureRendering();
	P_NATIVE_END;
}
// ********** End Class UQuickWidgetToolsHDRILibrary Function FlushHDRICaptureRendering ************

// ********** Begin Class UQuickWidgetToolsHDRILibrary Function GetHDRCubeSourceSize ***************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_UQuickWidgetToolsHDRILibrary_GetHDRCubeSourceSize_Statics
struct UHT_STATICS
{
	struct QuickWidgetToolsHDRILibrary_eventGetHDRCubeSourceSize_Parms
	{
		UTextureCube* TextureCube;
		int32 ReturnValue;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "Category", "Quick Widget Tools|HDRI" },
		{ "Comment", "/** Returns the stored source face width, independently of texture streaming or preview LODs. */" },
		{ "ModuleRelativePath", "Public/QuickWidgetToolsHDRILibrary.h" },
		{ "ToolTip", "Returns the stored source face width, independently of texture streaming or preview LODs." },
	};
#endif // WITH_METADATA

// ********** Begin Function GetHDRCubeSourceSize constinit property declarations ******************
	static const UECodeGen_Private::FObjectPropertyParams NewProp_TextureCube;
	static const UECodeGen_Private::FIntPropertyParams NewProp_ReturnValue;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
// ********** End Function GetHDRCubeSourceSize constinit property declarations ********************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};

// ********** Begin Function GetHDRCubeSourceSize Property Definitions *****************************
const UECodeGen_Private::FObjectPropertyParams UHT_STATICS::NewProp_TextureCube = { "TextureCube", nullptr, (EPropertyFlags)0x0010000000000080, UECodeGen_Private::EPropertyGenFlags::Object, nullptr, nullptr, 1, STRUCT_OFFSET(QuickWidgetToolsHDRILibrary_eventGetHDRCubeSourceSize_Parms, TextureCube), Z_Construct_UClass_UTextureCube, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FIntPropertyParams UHT_STATICS::NewProp_ReturnValue = { "ReturnValue", nullptr, (EPropertyFlags)0x0010000000000580, UECodeGen_Private::EPropertyGenFlags::Int, nullptr, nullptr, 1, STRUCT_OFFSET(QuickWidgetToolsHDRILibrary_eventGetHDRCubeSourceSize_Parms, ReturnValue), METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FPropertyParamsBase* const UHT_STATICS::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_TextureCube,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ReturnValue,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::PropPointers) < 2048);
// ********** End Function GetHDRCubeSourceSize Property Definitions *******************************
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_UQuickWidgetToolsHDRILibrary, nullptr, "GetHDRCubeSourceSize", UHT_STATICS::PropPointers, UE_ARRAY_COUNT(UHT_STATICS::PropPointers), DataSizeOf<UHT_STATICS::QuickWidgetToolsHDRILibrary_eventGetHDRCubeSourceSize_Parms>(), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x14022401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
static_assert(sizeof(UHT_STATICS::QuickWidgetToolsHDRILibrary_eventGetHDRCubeSourceSize_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_UQuickWidgetToolsHDRILibrary_GetHDRCubeSourceSize(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(UQuickWidgetToolsHDRILibrary::execGetHDRCubeSourceSize)
{
	P_GET_OBJECT(UTextureCube,Z_Param_TextureCube);
	P_FINISH;
	P_NATIVE_BEGIN;
	*(int32*)Z_Param__Result=UQuickWidgetToolsHDRILibrary::GetHDRCubeSourceSize(Z_Param_TextureCube);
	P_NATIVE_END;
}
// ********** End Class UQuickWidgetToolsHDRILibrary Function GetHDRCubeSourceSize *****************

// ********** Begin Class UQuickWidgetToolsHDRILibrary Function GetHDRCubeSourceSliceCount *********
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_UQuickWidgetToolsHDRILibrary_GetHDRCubeSourceSliceCount_Statics
struct UHT_STATICS
{
	struct QuickWidgetToolsHDRILibrary_eventGetHDRCubeSourceSliceCount_Parms
	{
		UTextureCube* TextureCube;
		int32 ReturnValue;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "Category", "Quick Widget Tools|HDRI" },
		{ "Comment", "/** Returns the stored source slice count; an HDR cubemap must contain six faces. */" },
		{ "ModuleRelativePath", "Public/QuickWidgetToolsHDRILibrary.h" },
		{ "ToolTip", "Returns the stored source slice count; an HDR cubemap must contain six faces." },
	};
#endif // WITH_METADATA

// ********** Begin Function GetHDRCubeSourceSliceCount constinit property declarations ************
	static const UECodeGen_Private::FObjectPropertyParams NewProp_TextureCube;
	static const UECodeGen_Private::FIntPropertyParams NewProp_ReturnValue;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
// ********** End Function GetHDRCubeSourceSliceCount constinit property declarations **************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};

// ********** Begin Function GetHDRCubeSourceSliceCount Property Definitions ***********************
const UECodeGen_Private::FObjectPropertyParams UHT_STATICS::NewProp_TextureCube = { "TextureCube", nullptr, (EPropertyFlags)0x0010000000000080, UECodeGen_Private::EPropertyGenFlags::Object, nullptr, nullptr, 1, STRUCT_OFFSET(QuickWidgetToolsHDRILibrary_eventGetHDRCubeSourceSliceCount_Parms, TextureCube), Z_Construct_UClass_UTextureCube, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FIntPropertyParams UHT_STATICS::NewProp_ReturnValue = { "ReturnValue", nullptr, (EPropertyFlags)0x0010000000000580, UECodeGen_Private::EPropertyGenFlags::Int, nullptr, nullptr, 1, STRUCT_OFFSET(QuickWidgetToolsHDRILibrary_eventGetHDRCubeSourceSliceCount_Parms, ReturnValue), METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FPropertyParamsBase* const UHT_STATICS::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_TextureCube,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ReturnValue,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::PropPointers) < 2048);
// ********** End Function GetHDRCubeSourceSliceCount Property Definitions *************************
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_UQuickWidgetToolsHDRILibrary, nullptr, "GetHDRCubeSourceSliceCount", UHT_STATICS::PropPointers, UE_ARRAY_COUNT(UHT_STATICS::PropPointers), DataSizeOf<UHT_STATICS::QuickWidgetToolsHDRILibrary_eventGetHDRCubeSourceSliceCount_Parms>(), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x14022401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
static_assert(sizeof(UHT_STATICS::QuickWidgetToolsHDRILibrary_eventGetHDRCubeSourceSliceCount_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_UQuickWidgetToolsHDRILibrary_GetHDRCubeSourceSliceCount(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(UQuickWidgetToolsHDRILibrary::execGetHDRCubeSourceSliceCount)
{
	P_GET_OBJECT(UTextureCube,Z_Param_TextureCube);
	P_FINISH;
	P_NATIVE_BEGIN;
	*(int32*)Z_Param__Result=UQuickWidgetToolsHDRILibrary::GetHDRCubeSourceSliceCount(Z_Param_TextureCube);
	P_NATIVE_END;
}
// ********** End Class UQuickWidgetToolsHDRILibrary Function GetHDRCubeSourceSliceCount ***********

// ********** Begin Class UQuickWidgetToolsHDRILibrary Function ReleaseHDRCubeRenderTarget *********
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_UQuickWidgetToolsHDRILibrary_ReleaseHDRCubeRenderTarget_Statics
struct UHT_STATICS
{
	struct QuickWidgetToolsHDRILibrary_eventReleaseHDRCubeRenderTarget_Parms
	{
		UTextureRenderTargetCube* RenderTarget;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "Category", "Quick Widget Tools|HDRI" },
		{ "Comment", "/** Releases the transient cube's GPU resource after the capture component has detached it. */" },
		{ "ModuleRelativePath", "Public/QuickWidgetToolsHDRILibrary.h" },
		{ "ToolTip", "Releases the transient cube's GPU resource after the capture component has detached it." },
	};
#endif // WITH_METADATA

// ********** Begin Function ReleaseHDRCubeRenderTarget constinit property declarations ************
	static const UECodeGen_Private::FObjectPropertyParams NewProp_RenderTarget;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
// ********** End Function ReleaseHDRCubeRenderTarget constinit property declarations **************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};

// ********** Begin Function ReleaseHDRCubeRenderTarget Property Definitions ***********************
const UECodeGen_Private::FObjectPropertyParams UHT_STATICS::NewProp_RenderTarget = { "RenderTarget", nullptr, (EPropertyFlags)0x0010000000000080, UECodeGen_Private::EPropertyGenFlags::Object, nullptr, nullptr, 1, STRUCT_OFFSET(QuickWidgetToolsHDRILibrary_eventReleaseHDRCubeRenderTarget_Parms, RenderTarget), Z_Construct_UClass_UTextureRenderTargetCube, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FPropertyParamsBase* const UHT_STATICS::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_RenderTarget,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::PropPointers) < 2048);
// ********** End Function ReleaseHDRCubeRenderTarget Property Definitions *************************
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_UQuickWidgetToolsHDRILibrary, nullptr, "ReleaseHDRCubeRenderTarget", UHT_STATICS::PropPointers, UE_ARRAY_COUNT(UHT_STATICS::PropPointers), DataSizeOf<UHT_STATICS::QuickWidgetToolsHDRILibrary_eventReleaseHDRCubeRenderTarget_Parms>(), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04022401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
static_assert(sizeof(UHT_STATICS::QuickWidgetToolsHDRILibrary_eventReleaseHDRCubeRenderTarget_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_UQuickWidgetToolsHDRILibrary_ReleaseHDRCubeRenderTarget(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(UQuickWidgetToolsHDRILibrary::execReleaseHDRCubeRenderTarget)
{
	P_GET_OBJECT(UTextureRenderTargetCube,Z_Param_RenderTarget);
	P_FINISH;
	P_NATIVE_BEGIN;
	UQuickWidgetToolsHDRILibrary::ReleaseHDRCubeRenderTarget(Z_Param_RenderTarget);
	P_NATIVE_END;
}
// ********** End Class UQuickWidgetToolsHDRILibrary Function ReleaseHDRCubeRenderTarget ***********

// ********** Begin Class UQuickWidgetToolsHDRILibrary *********************************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UClass_UQuickWidgetToolsHDRILibrary_Statics
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "Comment", "/** Editor-only HDR cubemap helpers for the Quick Widget Tools snapshot button. */" },
		{ "IncludePath", "QuickWidgetToolsHDRILibrary.h" },
		{ "ModuleRelativePath", "Public/QuickWidgetToolsHDRILibrary.h" },
		{ "ToolTip", "Editor-only HDR cubemap helpers for the Quick Widget Tools snapshot button." },
	};
#endif // WITH_METADATA

// ********** Begin Class UQuickWidgetToolsHDRILibrary constinit property declarations *************
// ********** End Class UQuickWidgetToolsHDRILibrary constinit property declarations ***************
	static constexpr UE::CodeGen::FClassNativeFunction Funcs[] = {
		{ .NameUTF8 = UTF8TEXT("CreateHDRCubeRenderTarget"), .Pointer = &UQuickWidgetToolsHDRILibrary::execCreateHDRCubeRenderTarget },
		{ .NameUTF8 = UTF8TEXT("CreateHDRTextureCube"), .Pointer = &UQuickWidgetToolsHDRILibrary::execCreateHDRTextureCube },
		{ .NameUTF8 = UTF8TEXT("FlushHDRICaptureRendering"), .Pointer = &UQuickWidgetToolsHDRILibrary::execFlushHDRICaptureRendering },
		{ .NameUTF8 = UTF8TEXT("GetHDRCubeSourceSize"), .Pointer = &UQuickWidgetToolsHDRILibrary::execGetHDRCubeSourceSize },
		{ .NameUTF8 = UTF8TEXT("GetHDRCubeSourceSliceCount"), .Pointer = &UQuickWidgetToolsHDRILibrary::execGetHDRCubeSourceSliceCount },
		{ .NameUTF8 = UTF8TEXT("ReleaseHDRCubeRenderTarget"), .Pointer = &UQuickWidgetToolsHDRILibrary::execReleaseHDRCubeRenderTarget },
	};
	static FTypeConstructFunc* DependentSingletons[];
	static constexpr FClassFunctionLinkInfo FuncInfo[] = {
		{ &Z_Construct_UFunction_UQuickWidgetToolsHDRILibrary_CreateHDRCubeRenderTarget, "CreateHDRCubeRenderTarget" }, // d6898483007438f3cfeac6bac4492b8da03ba698
		{ &Z_Construct_UFunction_UQuickWidgetToolsHDRILibrary_CreateHDRTextureCube, "CreateHDRTextureCube" }, // 124dc7ad14dbbb40c868734cb5d12175d838280d
		{ &Z_Construct_UFunction_UQuickWidgetToolsHDRILibrary_FlushHDRICaptureRendering, "FlushHDRICaptureRendering" }, // bd7c60668676caa2ee494e97349cbe5cf9be5976
		{ &Z_Construct_UFunction_UQuickWidgetToolsHDRILibrary_GetHDRCubeSourceSize, "GetHDRCubeSourceSize" }, // e40c4e757c4b34e7c3af1b86e8ae0951a7e09dff
		{ &Z_Construct_UFunction_UQuickWidgetToolsHDRILibrary_GetHDRCubeSourceSliceCount, "GetHDRCubeSourceSliceCount" }, // fef9b25589498e35495d5889530448f3f951c514
		{ &Z_Construct_UFunction_UQuickWidgetToolsHDRILibrary_ReleaseHDRCubeRenderTarget, "ReleaseHDRCubeRenderTarget" }, // ad41fc4a6f498a728be035e93204e88a775b6d46
	};
	static_assert(UE_ARRAY_COUNT(FuncInfo) < 2048);
	static constexpr FCppClassTypeInfoStatic StaticCppClassTypeInfo = {
		TCppClassTypeTraits<UQuickWidgetToolsHDRILibrary>::IsAbstract,
	};
	static const UECodeGen_Private::FClassParams ClassParams;
}; // struct UHT_STATICS
FTypeConstructFunc* UHT_STATICS::DependentSingletons[] = {
	(FTypeConstructFunc*)Z_Construct_UClass_UBlueprintFunctionLibrary,
	(FTypeConstructFunc*)Z_Construct_UPackage__Script_QuickWidgetTools,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::DependentSingletons) < 16);
const UECodeGen_Private::FClassParams UHT_STATICS::ClassParams = {
	&Z_Construct_UClass_UQuickWidgetToolsHDRILibrary,
	nullptr,
	&StaticCppClassTypeInfo,
	DependentSingletons,
	FuncInfo,
	nullptr,
	nullptr,
	UE_ARRAY_COUNT(DependentSingletons),
	UE_ARRAY_COUNT(FuncInfo),
	0,
	0,
	0x001000A0u,
	METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)
};
static void UQuickWidgetToolsHDRILibrary_StaticRegisterNativesUQuickWidgetToolsHDRILibrary()
{
	UClass* Class = UQuickWidgetToolsHDRILibrary::StaticClass();
	FNativeFunctionRegistrar::RegisterFunctions(Class, 		MakeConstArrayView(UHT_STATICS::Funcs));
}
FClassRegistrationInfo Z_Registration_Info_UClass_UQuickWidgetToolsHDRILibrary;
UClass* Z_Construct_UClass_UQuickWidgetToolsHDRILibrary(ETypeConstructPhase Phase)
{
	if (Phase == ETypeConstructPhase::Inner)
	{
		using TClass = UQuickWidgetToolsHDRILibrary;
		if (!Z_Registration_Info_UClass_UQuickWidgetToolsHDRILibrary.InnerSingleton)
		{
			GetPrivateStaticClassBody(
				TClass::StaticPackage(),
				TEXT("QuickWidgetToolsHDRILibrary"),
				Z_Registration_Info_UClass_UQuickWidgetToolsHDRILibrary.InnerSingleton,
				UQuickWidgetToolsHDRILibrary_StaticRegisterNativesUQuickWidgetToolsHDRILibrary,
				DataSizeOf<TClass>(),
				alignof(TClass),
				TClass::StaticClassFlags,
				TClass::StaticClassCastFlags(),
				TClass::StaticConfigName(),
				(UClass::ClassConstructorType)InternalConstructor<TClass>,
				(UClass::ClassVTableHelperCtorCallerType)InternalVTableHelperCtorCaller<TClass>,
				UOBJECT_CPPCLASS_STATICFUNCTIONS_FORCLASS(TClass),
				&TClass::Super::StaticClass,
				&TClass::WithinClass::StaticClass
			);
		}
		return Z_Registration_Info_UClass_UQuickWidgetToolsHDRILibrary.InnerSingleton;
	}
	if (!Z_Registration_Info_UClass_UQuickWidgetToolsHDRILibrary.OuterSingleton)
	{
		UECodeGen_Private::ConstructUClass(Z_Registration_Info_UClass_UQuickWidgetToolsHDRILibrary.OuterSingleton, UHT_STATICS::ClassParams);
	}
	return Z_Registration_Info_UClass_UQuickWidgetToolsHDRILibrary.OuterSingleton;
}
#undef UHT_STATICS
UQuickWidgetToolsHDRILibrary::UQuickWidgetToolsHDRILibrary(const FObjectInitializer& ObjectInitializer) : Super(ObjectInitializer) {}
DEFINE_VTABLE_PTR_HELPER_CTOR_NS(, UQuickWidgetToolsHDRILibrary);
UQuickWidgetToolsHDRILibrary::~UQuickWidgetToolsHDRILibrary() {}
// ********** End Class UQuickWidgetToolsHDRILibrary ***********************************************

// ********** Begin Registration *******************************************************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_CompiledInDeferFile_FID_HostProject_Plugins_QuickWidgetTools_Source_QuickWidgetTools_Public_QuickWidgetToolsHDRILibrary_h__Script_QuickWidgetTools_Statics
struct UHT_STATICS
{
	static constexpr FClassRegisterCompiledInInfo ClassInfo[] = {
		{ Z_Construct_UClass_UQuickWidgetToolsHDRILibrary, TEXT("UQuickWidgetToolsHDRILibrary"), &Z_Registration_Info_UClass_UQuickWidgetToolsHDRILibrary, CONSTRUCT_RELOAD_VERSION_INFO(FClassReloadVersionInfo, sizeof(UQuickWidgetToolsHDRILibrary), 2540642633U) },
	};
}; // UHT_STATICS 
static FRegisterCompiledInInfo Z_CompiledInDeferFile_FID_HostProject_Plugins_QuickWidgetTools_Source_QuickWidgetTools_Public_QuickWidgetToolsHDRILibrary_h__Script_QuickWidgetTools_2bc224d0f46527f1da4a33aeffe412e532144097{
	TEXT("/Script/QuickWidgetTools"),
	UHT_STATICS::ClassInfo, UE_ARRAY_COUNT(UHT_STATICS::ClassInfo),
	nullptr, 0,
	nullptr, 0,
	nullptr, 0,
};
#undef UHT_STATICS
// ********** End Registration *********************************************************************
#undef UHT_STRUCT_BASE

PRAGMA_ENABLE_DEPRECATION_WARNINGS
