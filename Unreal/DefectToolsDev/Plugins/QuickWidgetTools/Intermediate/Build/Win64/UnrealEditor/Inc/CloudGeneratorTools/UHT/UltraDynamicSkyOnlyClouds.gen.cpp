// Copyright Epic Games, Inc. All Rights Reserved.
/*===========================================================================
	Generated code exported from UnrealHeaderTool.
	DO NOT modify this manually! Edit the corresponding .h files instead!
===========================================================================*/

#include "UObject/GeneratedCppIncludes.h"
#include "UltraDynamicSkyOnlyClouds.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS
static_assert(!UE_WITH_CONSTINIT_UOBJECT, "This generated code can only be compiled with !UE_WITH_CONSTINIT_UOBJECT");
void EmptyLinkFunctionForGeneratedCodeUltraDynamicSkyOnlyClouds() {}

// ********** Begin Cross Module References ********************************************************
COREUOBJECT_API UScriptStruct* Z_Construct_UScriptStruct_FLinearColor(ETypeConstructPhase);
COREUOBJECT_API UScriptStruct* Z_Construct_UScriptStruct_FVector(ETypeConstructPhase);
ENGINE_API UClass* Z_Construct_UClass_AActor(ETypeConstructPhase);
ENGINE_API UClass* Z_Construct_UClass_UMaterialInstanceDynamic(ETypeConstructPhase);
ENGINE_API UClass* Z_Construct_UClass_UMaterialInterface(ETypeConstructPhase);
ENGINE_API UClass* Z_Construct_UClass_UMaterialParameterCollection(ETypeConstructPhase);
ENGINE_API UClass* Z_Construct_UClass_UMaterialParameterCollectionInstance(ETypeConstructPhase);
ENGINE_API UClass* Z_Construct_UClass_UTexture(ETypeConstructPhase);
ENGINE_API UClass* Z_Construct_UClass_UTexture2D(ETypeConstructPhase);
ENGINE_API UClass* Z_Construct_UClass_UVolumetricCloudComponent(ETypeConstructPhase);
// ********** End Cross Module References **********************************************************

// ********** Begin Same Module References *********************************************************
UPackage* Z_Construct_UPackage__Script_CloudGeneratorTools(ETypeConstructPhase);
CLOUDGENERATORTOOLS_API UScriptStruct* Z_Construct_UScriptStruct_FUDSOnlyCloudLayer(ETypeConstructPhase);
CLOUDGENERATORTOOLS_API UClass* Z_Construct_UClass_AUltraDynamicSkyOnlyClouds(ETypeConstructPhase);
CLOUDGENERATORTOOLS_API UClass* Z_Construct_UClass_AUltraDynamicSkyOnlyClouds(ETypeConstructPhase);
// ********** End Same Module References ***********************************************************
#define UHT_STRUCT_BASE(INIT) UE::CodeGen::ConstInit::TCompiledInObjectPtr<const FStructBaseChain>(UE::Private::AsStructBaseChain(INIT))

// ********** Begin ScriptStruct FUDSOnlyCloudLayer ************************************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UScriptStruct_FUDSOnlyCloudLayer_Statics
struct UHT_STATICS
{
	static inline consteval int32 GetStructSize() { return DataSizeOf<FUDSOnlyCloudLayer>(); }
	static inline consteval int16 GetStructAlignment() { return alignof(FUDSOnlyCloudLayer); }
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "BlueprintType", "true" },
		{ "Comment", "/** One extra cloud deck, rendered together with the original base layer. */" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "ToolTip", "One extra cloud deck, rendered together with the original base layer." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Name_MetaData[] = {
		{ "Category", "Cloud Layer" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_bEnabled_MetaData[] = {
		{ "Category", "Cloud Layer" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_BottomAltitudeKm_MetaData[] = {
		{ "Category", "Cloud Layer" },
		{ "Comment", "/** Signed altitude. Overall Cloud Scale applies to this value and to thickness. */" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "ToolTip", "Signed altitude. Overall Cloud Scale applies to this value and to thickness." },
		{ "UIMax", "10" },
		{ "UIMin", "-10" },
		{ "Units", "km" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_HeightKm_MetaData[] = {
		{ "Category", "Cloud Layer" },
		{ "ClampMin", "0.1" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "UIMax", "5" },
		{ "Units", "km" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_CloudCoverage_MetaData[] = {
		{ "Category", "Cloud Layer" },
		{ "ClampMax", "10" },
		{ "ClampMin", "0" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Extinction_MetaData[] = {
		{ "Category", "Cloud Layer" },
		{ "ClampMin", "0.001" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "UIMax", "30" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_FormationTextureScale_MetaData[] = {
		{ "Category", "Cloud Layer" },
		{ "ClampMin", "0.001" },
		{ "Comment", "/** Larger values make larger formation features, matching the base-layer Formation Texture Scale control. */" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "ToolTip", "Larger values make larger formation features, matching the base-layer Formation Texture Scale control." },
		{ "UIMax", "5" },
		{ "UIMin", "0.1" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_FormationPhase_MetaData[] = {
		{ "Category", "Cloud Layer" },
		{ "Comment", "/** Independent formation variation, added to the shared cloud animation phase. */" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "ToolTip", "Independent formation variation, added to the shared cloud animation phase." },
		{ "UIMax", "100" },
		{ "UIMin", "0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_FormationMipOffset_MetaData[] = {
		{ "Category", "Cloud Layer" },
		{ "Comment", "/** Added formation texture mip level; higher values soften this layer's formation. */" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "ToolTip", "Added formation texture mip level; higher values soften this layer's formation." },
		{ "UIMax", "5" },
		{ "UIMin", "0" },
	};
#endif // WITH_METADATA

// ********** Begin ScriptStruct FUDSOnlyCloudLayer constinit property declarations ****************
	static const UECodeGen_Private::FNamePropertyParams NewProp_Name;
	static void NewProp_bEnabled_SetBit(void* Obj)
	{
		((FUDSOnlyCloudLayer*)Obj)->bEnabled = 1;
	}
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bEnabled;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_BottomAltitudeKm;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_HeightKm;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_CloudCoverage;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_Extinction;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_FormationTextureScale;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_FormationPhase;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_FormationMipOffset;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
// ********** End ScriptStruct FUDSOnlyCloudLayer constinit property declarations ******************
	static void* NewStructOps()
	{
		return (UScriptStruct::ICppStructOps*)new UScriptStruct::TCppStructOps<FUDSOnlyCloudLayer>();
	}
	static const UECodeGen_Private::FStructParams StructParams;
}; // struct UHT_STATICS

// ********** Begin ScriptStruct FUDSOnlyCloudLayer Property Definitions ***************************
const UECodeGen_Private::FNamePropertyParams UHT_STATICS::NewProp_Name = { "Name", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Name, nullptr, nullptr, 1, STRUCT_OFFSET(FUDSOnlyCloudLayer, Name), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Name_MetaData), NewProp_Name_MetaData) };
const UECodeGen_Private::FBoolPropertyParams UHT_STATICS::NewProp_bEnabled = { "bEnabled", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, nullptr, nullptr, 1, sizeof(bool), sizeof(FUDSOnlyCloudLayer), &UHT_STATICS::NewProp_bEnabled_SetBit, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_bEnabled_MetaData), NewProp_bEnabled_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_BottomAltitudeKm = { "BottomAltitudeKm", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FUDSOnlyCloudLayer, BottomAltitudeKm), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_BottomAltitudeKm_MetaData), NewProp_BottomAltitudeKm_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_HeightKm = { "HeightKm", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FUDSOnlyCloudLayer, HeightKm), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_HeightKm_MetaData), NewProp_HeightKm_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_CloudCoverage = { "CloudCoverage", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FUDSOnlyCloudLayer, CloudCoverage), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_CloudCoverage_MetaData), NewProp_CloudCoverage_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_Extinction = { "Extinction", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FUDSOnlyCloudLayer, Extinction), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Extinction_MetaData), NewProp_Extinction_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_FormationTextureScale = { "FormationTextureScale", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FUDSOnlyCloudLayer, FormationTextureScale), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_FormationTextureScale_MetaData), NewProp_FormationTextureScale_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_FormationPhase = { "FormationPhase", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FUDSOnlyCloudLayer, FormationPhase), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_FormationPhase_MetaData), NewProp_FormationPhase_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_FormationMipOffset = { "FormationMipOffset", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FUDSOnlyCloudLayer, FormationMipOffset), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_FormationMipOffset_MetaData), NewProp_FormationMipOffset_MetaData) };
const UECodeGen_Private::FPropertyParamsBase* const UHT_STATICS::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Name,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_bEnabled,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_BottomAltitudeKm,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_HeightKm,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_CloudCoverage,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Extinction,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_FormationTextureScale,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_FormationPhase,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_FormationMipOffset,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::PropPointers) < 2048);
// ********** End ScriptStruct FUDSOnlyCloudLayer Property Definitions *****************************
const UECodeGen_Private::FStructParams UHT_STATICS::StructParams = {
	(FTypeConstructFunc*)Z_Construct_UPackage__Script_CloudGeneratorTools,
	nullptr,
	&NewStructOps,
	"UDSOnlyCloudLayer",
	UHT_STATICS::PropPointers,
	UE_ARRAY_COUNT(UHT_STATICS::PropPointers),
	DataSizeOf<FUDSOnlyCloudLayer>(),
	alignof(FUDSOnlyCloudLayer),
	RF_Public|RF_Transient|RF_MarkAsNative,
	EStructFlags(0x00000201),
	METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)
};
static FStructRegistrationInfo Z_Registration_Info_UScriptStruct_FUDSOnlyCloudLayer;
UScriptStruct* Z_Construct_UScriptStruct_FUDSOnlyCloudLayer(ETypeConstructPhase Phase)
{
	if (Phase == ETypeConstructPhase::Outer)
	{
		if (!Z_Registration_Info_UScriptStruct_FUDSOnlyCloudLayer.OuterSingleton)
		{
			Z_Registration_Info_UScriptStruct_FUDSOnlyCloudLayer.OuterSingleton = GetStaticStruct(Z_Construct_UScriptStruct_FUDSOnlyCloudLayer, (UObject*)Z_Construct_UPackage__Script_CloudGeneratorTools(ETypeConstructPhase::Outer), TEXT("UDSOnlyCloudLayer"));
		}
		return Z_Registration_Info_UScriptStruct_FUDSOnlyCloudLayer.OuterSingleton;
	}
	if (!Z_Registration_Info_UScriptStruct_FUDSOnlyCloudLayer.InnerSingleton)
	{
		UECodeGen_Private::ConstructUScriptStruct(Z_Registration_Info_UScriptStruct_FUDSOnlyCloudLayer.InnerSingleton, UHT_STATICS::StructParams);
	}
	return CastChecked<UScriptStruct>(Z_Registration_Info_UScriptStruct_FUDSOnlyCloudLayer.InnerSingleton);
}
#undef UHT_STATICS
// ********** End ScriptStruct FUDSOnlyCloudLayer **************************************************

// ********** Begin Class AUltraDynamicSkyOnlyClouds Function AddCloudLayer ************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_AUltraDynamicSkyOnlyClouds_AddCloudLayer_Statics
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "CallInEditor", "true" },
		{ "Category", "Only Clouds|Cloud Layers" },
		{ "Comment", "/** Adds an independently adjustable deck above the current stack, preserving the original base layer. */" },
		{ "DisplayName", "+ Add Cloud Layer" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "ToolTip", "Adds an independently adjustable deck above the current stack, preserving the original base layer." },
	};
#endif // WITH_METADATA

// ********** Begin Function AddCloudLayer constinit property declarations *************************
// ********** End Function AddCloudLayer constinit property declarations ***************************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_AUltraDynamicSkyOnlyClouds, nullptr, "AddCloudLayer", nullptr, 0, 0, RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04020401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
UFunction* Z_Construct_UFunction_AUltraDynamicSkyOnlyClouds_AddCloudLayer(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(AUltraDynamicSkyOnlyClouds::execAddCloudLayer)
{
	P_FINISH;
	P_NATIVE_BEGIN;
	P_THIS->AddCloudLayer();
	P_NATIVE_END;
}
// ********** End Class AUltraDynamicSkyOnlyClouds Function AddCloudLayer **************************

// ********** Begin Class AUltraDynamicSkyOnlyClouds Function ApplyCinematicCloudQuality ***********
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_AUltraDynamicSkyOnlyClouds_ApplyCinematicCloudQuality_Statics
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "CallInEditor", "true" },
		{ "Category", "Only Clouds|Quality" },
		{ "Comment", "/** Enables only scene-wide cloud rendering CVars. No light, atmosphere, fog or exposure settings are changed. */" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "ToolTip", "Enables only scene-wide cloud rendering CVars. No light, atmosphere, fog or exposure settings are changed." },
	};
#endif // WITH_METADATA

// ********** Begin Function ApplyCinematicCloudQuality constinit property declarations ************
// ********** End Function ApplyCinematicCloudQuality constinit property declarations **************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_AUltraDynamicSkyOnlyClouds, nullptr, "ApplyCinematicCloudQuality", nullptr, 0, 0, RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04020401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
UFunction* Z_Construct_UFunction_AUltraDynamicSkyOnlyClouds_ApplyCinematicCloudQuality(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(AUltraDynamicSkyOnlyClouds::execApplyCinematicCloudQuality)
{
	P_FINISH;
	P_NATIVE_BEGIN;
	P_THIS->ApplyCinematicCloudQuality();
	P_NATIVE_END;
}
// ********** End Class AUltraDynamicSkyOnlyClouds Function ApplyCinematicCloudQuality *************

// ********** Begin Class AUltraDynamicSkyOnlyClouds Function RefreshClouds ************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_AUltraDynamicSkyOnlyClouds_RefreshClouds_Statics
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "CallInEditor", "true" },
		{ "Category", "Only Clouds" },
		{ "Comment", "/** Applies all controls. Interpolated artist controls update automatically; call after other Blueprint runtime edits. */" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "ToolTip", "Applies all controls. Interpolated artist controls update automatically; call after other Blueprint runtime edits." },
	};
#endif // WITH_METADATA

// ********** Begin Function RefreshClouds constinit property declarations *************************
// ********** End Function RefreshClouds constinit property declarations ***************************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_AUltraDynamicSkyOnlyClouds, nullptr, "RefreshClouds", nullptr, 0, 0, RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04020401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
UFunction* Z_Construct_UFunction_AUltraDynamicSkyOnlyClouds_RefreshClouds(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(AUltraDynamicSkyOnlyClouds::execRefreshClouds)
{
	P_FINISH;
	P_NATIVE_BEGIN;
	P_THIS->RefreshClouds();
	P_NATIVE_END;
}
// ********** End Class AUltraDynamicSkyOnlyClouds Function RefreshClouds **************************

// ********** Begin Class AUltraDynamicSkyOnlyClouds Function ResetAnimationTime *******************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_AUltraDynamicSkyOnlyClouds_ResetAnimationTime_Statics
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "CallInEditor", "true" },
		{ "Category", "Only Clouds|Motion" },
		{ "Comment", "/** Restore the deterministic phase without changing artist controls. */" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "ToolTip", "Restore the deterministic phase without changing artist controls." },
	};
#endif // WITH_METADATA

// ********** Begin Function ResetAnimationTime constinit property declarations ********************
// ********** End Function ResetAnimationTime constinit property declarations **********************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_AUltraDynamicSkyOnlyClouds, nullptr, "ResetAnimationTime", nullptr, 0, 0, RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04020401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
UFunction* Z_Construct_UFunction_AUltraDynamicSkyOnlyClouds_ResetAnimationTime(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(AUltraDynamicSkyOnlyClouds::execResetAnimationTime)
{
	P_FINISH;
	P_NATIVE_BEGIN;
	P_THIS->ResetAnimationTime();
	P_NATIVE_END;
}
// ********** End Class AUltraDynamicSkyOnlyClouds Function ResetAnimationTime *********************

// ********** Begin Class AUltraDynamicSkyOnlyClouds Function RestorePreviousCloudQuality **********
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_AUltraDynamicSkyOnlyClouds_RestorePreviousCloudQuality_Statics
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "CallInEditor", "true" },
		{ "Category", "Only Clouds|Quality" },
		{ "Comment", "/** Disables automatic global cloud quality and restores previous values when no other OnlyClouds actor needs them. */" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "ToolTip", "Disables automatic global cloud quality and restores previous values when no other OnlyClouds actor needs them." },
	};
#endif // WITH_METADATA

// ********** Begin Function RestorePreviousCloudQuality constinit property declarations ***********
// ********** End Function RestorePreviousCloudQuality constinit property declarations *************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_AUltraDynamicSkyOnlyClouds, nullptr, "RestorePreviousCloudQuality", nullptr, 0, 0, RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04020401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
UFunction* Z_Construct_UFunction_AUltraDynamicSkyOnlyClouds_RestorePreviousCloudQuality(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(AUltraDynamicSkyOnlyClouds::execRestorePreviousCloudQuality)
{
	P_FINISH;
	P_NATIVE_BEGIN;
	P_THIS->RestorePreviousCloudQuality();
	P_NATIVE_END;
}
// ********** End Class AUltraDynamicSkyOnlyClouds Function RestorePreviousCloudQuality ************

// ********** Begin Class AUltraDynamicSkyOnlyClouds ***********************************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UClass_AUltraDynamicSkyOnlyClouds_Statics
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "BlueprintType", "true" },
		{ "Comment", "/**\n * Standalone UDS volume renderer. Owns no lighting or environment components.\n * Use one active OnlyClouds actor per world: its isolated parameter collection is world-wide,\n * matching Unreal's single active sky-cloud layer. Original UDS collections are never written.\n */" },
		{ "HideCategories", "Input Collision Physics Replication Networking" },
		{ "IncludePath", "UltraDynamicSkyOnlyClouds.h" },
		{ "IsBlueprintBase", "true" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "ToolTip", "Standalone UDS volume renderer. Owns no lighting or environment components.\nUse one active OnlyClouds actor per world: its isolated parameter collection is world-wide,\nmatching Unreal's single active sky-cloud layer. Original UDS collections are never written." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_VolumetricCloud_MetaData[] = {
		{ "Category", "Only Clouds" },
		{ "EditInline", "true" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_CloudStatus_MetaData[] = {
		{ "Category", "Only Clouds" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_AdditionalCloudLayers_MetaData[] = {
		{ "Category", "Only Clouds|Cloud Layers" },
		{ "Comment", "/** Extra decks share global detail, shading, motion and quality. Use the array controls to remove or duplicate a deck. Empty or disabled entries preserve the original single-layer renderer. */" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "TitleProperty", "Name" },
		{ "ToolTip", "Extra decks share global detail, shading, motion and quality. Use the array controls to remove or duplicate a deck. Empty or disabled entries preserve the original single-layer renderer." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LayerBottomAltitudeKm_MetaData[] = {
		{ "Category", "Only Clouds|Layer" },
		{ "Comment", "/** Signed altitude relative to the cloud renderer's ground reference. Negative values lower the layer below it. */" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "ToolTip", "Signed altitude relative to the cloud renderer's ground reference. Negative values lower the layer below it." },
		{ "UIMax", "10.0" },
		{ "UIMin", "-10.0" },
		{ "Units", "km" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LayerHeightKm_MetaData[] = {
		{ "Category", "Only Clouds|Layer" },
		{ "ClampMin", "0.1" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "UIMax", "5.0" },
		{ "Units", "km" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_CloudScale_MetaData[] = {
		{ "Category", "Only Clouds|Layer" },
		{ "ClampMin", "0.001" },
		{ "Comment", "/** Overall physical scale. Scales altitude, thickness, formation, detail and trace distances together. */" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "ToolTip", "Overall physical scale. Scales altitude, thickness, formation, detail and trace distances together." },
		{ "UIMax", "10.0" },
		{ "UIMin", "0.1" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_PlanetRadiusKm_MetaData[] = {
		{ "Category", "Only Clouds|Layer" },
		{ "ClampMax", "10000" },
		{ "ClampMin", "0.1" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "Units", "km" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_CloudCoverage_MetaData[] = {
		{ "Category", "Only Clouds|Formation" },
		{ "ClampMax", "10.0" },
		{ "ClampMin", "0.0" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_FormationTextureScale_MetaData[] = {
		{ "Category", "Only Clouds|Formation" },
		{ "ClampMin", "0.001" },
		{ "Comment", "/** UDS's large formation size: 1 equals 12 km before overall Cloud Scale. */" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "ToolTip", "UDS's large formation size: 1 equals 12 km before overall Cloud Scale." },
		{ "UIMax", "5.0" },
		{ "UIMin", "0.1" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_FormationZShift_MetaData[] = {
		{ "Category", "Only Clouds|Formation" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "UIMax", "2.0" },
		{ "UIMin", "-2.0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_MacroVariation_MetaData[] = {
		{ "Category", "Only Clouds|Formation" },
		{ "ClampMin", "0" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "UIMax", "1.0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_MacroScale_MetaData[] = {
		{ "Category", "Only Clouds|Formation" },
		{ "ClampMin", "0.001" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "UIMax", "5.0" },
		{ "UIMin", "0.1" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_MacroOffset_MetaData[] = {
		{ "Category", "Only Clouds|Formation" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "UIMax", "2.0" },
		{ "UIMin", "-2.0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_FormationMipLevel_MetaData[] = {
		{ "Category", "Only Clouds|Formation" },
		{ "ClampMin", "0" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "UIMax", "5.0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_FormationTexture_MetaData[] = {
		{ "AllowedClasses", "/Script/Engine.VolumeTexture" },
		{ "Category", "Only Clouds|Textures" },
		{ "Comment", "/** Optional override. Leave empty to retain the isolated material's UDS formation texture. */" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "ToolTip", "Optional override. Leave empty to retain the isolated material's UDS formation texture." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_DetailNoiseTexture_MetaData[] = {
		{ "AllowedClasses", "/Script/Engine.VolumeTexture" },
		{ "Category", "Only Clouds|Textures" },
		{ "Comment", "/** Optional override for UDS's 3D erosion texture. The supplied material uses the 128 detail texture. */" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "ToolTip", "Optional override for UDS's 3D erosion texture. The supplied material uses the 128 detail texture." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_CloudProfileTexture_MetaData[] = {
		{ "AllowedClasses", "/Script/Engine.Texture2D" },
		{ "Category", "Only Clouds|Textures" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Noise3DScale_MetaData[] = {
		{ "Category", "Only Clouds|Detail" },
		{ "ClampMin", "0.001" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "UIMax", "5.0" },
		{ "UIMin", "0.1" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Erosion3D_MetaData[] = {
		{ "Category", "Only Clouds|Detail" },
		{ "ClampMin", "0" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "UIMax", "3.0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_ErosionPower_MetaData[] = {
		{ "Category", "Only Clouds|Detail" },
		{ "ClampMin", "0.01" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "UIMax", "8.0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_MinimumErosion_MetaData[] = {
		{ "Category", "Only Clouds|Detail" },
		{ "ClampMin", "0" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "UIMax", "1.0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_HighFrequencyNoise_MetaData[] = {
		{ "Category", "Only Clouds|Detail" },
		{ "ClampMin", "0" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "UIMax", "1.0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_HighFrequencyNoiseLevels_MetaData[] = {
		{ "Category", "Only Clouds|Detail" },
		{ "ClampMax", "4" },
		{ "ClampMin", "0" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_HighFrequencyNoiseDistance_MetaData[] = {
		{ "Category", "Only Clouds|Detail" },
		{ "ClampMin", "1" },
		{ "Comment", "/** Distance in cm at which high-frequency detail fades; doubled in Cinematic / Offline mode. */" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "ToolTip", "Distance in cm at which high-frequency detail fades; doubled in Cinematic / Offline mode." },
		{ "UIMax", "1000000" },
		{ "Units", "cm" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_HighFrequencyDistortion_MetaData[] = {
		{ "Category", "Only Clouds|Detail" },
		{ "ClampMin", "0" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "UIMax", "1.0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Extinction_MetaData[] = {
		{ "Category", "Only Clouds|Shading" },
		{ "ClampMin", "0.001" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "UIMax", "30.0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Albedo_MetaData[] = {
		{ "Category", "Only Clouds|Shading" },
		{ "Comment", "/** Neutral physical cloud color; illuminated by your own atmosphere directional light and sky light. */" },
		{ "HideAlphaChannel", "" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "ToolTip", "Neutral physical cloud color; illuminated by your own atmosphere directional light and sky light." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_TopEmissiveColor_MetaData[] = {
		{ "Category", "Only Clouds|Shading" },
		{ "Comment", "/** Explicit artist fill only. There is no automatic day/night or exposure-driven emission. */" },
		{ "HideAlphaChannel", "" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "ToolTip", "Explicit artist fill only. There is no automatic day/night or exposure-driven emission." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_BottomEmissiveColor_MetaData[] = {
		{ "Category", "Only Clouds|Shading" },
		{ "HideAlphaChannel", "" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_AmbientOcclusion_MetaData[] = {
		{ "Category", "Only Clouds|Shading" },
		{ "ClampMax", "1" },
		{ "ClampMin", "0" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_PhaseG_MetaData[] = {
		{ "Category", "Only Clouds|Shading" },
		{ "ClampMax", "0.99" },
		{ "ClampMin", "-0.99" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_PhaseG2_MetaData[] = {
		{ "Category", "Only Clouds|Shading" },
		{ "ClampMax", "0.99" },
		{ "ClampMin", "-0.99" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_PhaseBlend_MetaData[] = {
		{ "Category", "Only Clouds|Shading" },
		{ "ClampMax", "1" },
		{ "ClampMin", "0" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_MultiScatteringContribution_MetaData[] = {
		{ "Category", "Only Clouds|Shading" },
		{ "ClampMax", "1" },
		{ "ClampMin", "0" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_MultiScatteringOcclusion_MetaData[] = {
		{ "Category", "Only Clouds|Shading" },
		{ "ClampMax", "1" },
		{ "ClampMin", "0" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_MultiScatteringEccentricity_MetaData[] = {
		{ "Category", "Only Clouds|Shading" },
		{ "ClampMax", "1" },
		{ "ClampMin", "0" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_bPerSampleAtmosphereTransmittance_MetaData[] = {
		{ "Category", "Only Clouds|Shading" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_CloudPhase_MetaData[] = {
		{ "Category", "Only Clouds|Motion" },
		{ "Comment", "/** Deterministic formation phase. Does not depend on world time, UDS, or a random seed. */" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "ToolTip", "Deterministic formation phase. Does not depend on world time, UDS, or a random seed." },
		{ "UIMax", "100" },
		{ "UIMin", "0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_FormationOffset_MetaData[] = {
		{ "Category", "Only Clouds|Motion" },
		{ "Comment", "/** Offset added to the formation coordinates, in centimeters. */" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "ToolTip", "Offset added to the formation coordinates, in centimeters." },
		{ "Units", "cm" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_bAnimateClouds_MetaData[] = {
		{ "Category", "Only Clouds|Motion" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_CloudDirection_MetaData[] = {
		{ "Category", "Only Clouds|Motion" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "UIMax", "360" },
		{ "UIMin", "0" },
		{ "Units", "deg" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_CloudMovementSpeed_MetaData[] = {
		{ "Category", "Only Clouds|Motion" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "UIMax", "5000" },
		{ "UIMin", "0" },
		{ "Units", "cm/s" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_FormationChangeSpeed_MetaData[] = {
		{ "Category", "Only Clouds|Motion" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "UIMax", "2" },
		{ "UIMin", "0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_NoiseVerticalMovement_MetaData[] = {
		{ "Category", "Only Clouds|Motion" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "UIMax", "2" },
		{ "UIMin", "-2" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_bCinematicOffline_MetaData[] = {
		{ "Category", "Only Clouds|Quality" },
		{ "Comment", "/** High sample count, full formation material and extended fine detail distance. */" },
		{ "DisplayName", "Cinematic / Offline" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "ToolTip", "High sample count, full formation material and extended fine detail distance." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_bApplyCloudRendererQuality_MetaData[] = {
		{ "Category", "Only Clouds|Quality" },
		{ "Comment", "/** Opt-in persistent, scene-wide CLOUD-ONLY renderer settings. Uses the UDS offline renderer mode and sample caps. Restores prior values when no OnlyClouds actor needs them, if still unchanged by another system. No lighting/exposure CVars are touched. */" },
		{ "DisplayName", "Apply Cinematic Cloud Renderer Settings" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "ToolTip", "Opt-in persistent, scene-wide CLOUD-ONLY renderer settings. Uses the UDS offline renderer mode and sample caps. Restores prior values when no OnlyClouds actor needs them, if still unchanged by another system. No lighting/exposure CVars are touched." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_CinematicViewSampleScale_MetaData[] = {
		{ "Category", "Only Clouds|Quality" },
		{ "ClampMin", "0.05" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "UIMax", "30" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_RealtimeViewSampleScale_MetaData[] = {
		{ "Category", "Only Clouds|Quality" },
		{ "ClampMin", "0.05" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "UIMax", "8" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_ShadowViewSampleScale_MetaData[] = {
		{ "Category", "Only Clouds|Quality" },
		{ "ClampMin", "0.05" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "UIMax", "8" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_ReflectionViewSampleScale_MetaData[] = {
		{ "Category", "Only Clouds|Quality" },
		{ "ClampMin", "0.05" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "UIMax", "8" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_ShadowReflectionSampleScale_MetaData[] = {
		{ "Category", "Only Clouds|Quality" },
		{ "ClampMin", "0.05" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "UIMax", "8" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_TracingMaxDistanceKm_MetaData[] = {
		{ "Category", "Only Clouds|Quality" },
		{ "ClampMin", "0.1" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "UIMax", "100" },
		{ "Units", "km" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_TracingStartMaxDistanceKm_MetaData[] = {
		{ "Category", "Only Clouds|Quality" },
		{ "ClampMin", "1" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "UIMax", "500" },
		{ "Units", "km" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_ShadowTracingDistanceKm_MetaData[] = {
		{ "Category", "Only Clouds|Quality" },
		{ "ClampMin", "0.01" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "UIMax", "50" },
		{ "Units", "km" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_StopTracingTransmittanceThreshold_MetaData[] = {
		{ "Category", "Only Clouds|Quality" },
		{ "ClampMax", "1" },
		{ "ClampMin", "0" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_bVisibleInSkyLightCaptures_MetaData[] = {
		{ "Category", "Only Clouds|Quality" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_ScalarOverrides_MetaData[] = {
		{ "Category", "Only Clouds|Advanced Shader" },
		{ "Comment", "/** Exact shader parameter overrides, applied after the artist controls. Removing an entry restores its normal/default value. */" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "ToolTip", "Exact shader parameter overrides, applied after the artist controls. Removing an entry restores its normal/default value." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_VectorOverrides_MetaData[] = {
		{ "Category", "Only Clouds|Advanced Shader" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_CloudMaterial_MetaData[] = {
		{ "Category", "Only Clouds|Assets" },
		{ "Comment", "/** Isolated UDS material only; never assign the original full-sky material. */" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "ToolTip", "Isolated UDS material only; never assign the original full-sky material." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LayeredCloudMaterial_MetaData[] = {
		{ "Category", "Only Clouds|Assets" },
		{ "Comment", "/** Isolated multilayer material; selected automatically when an extra enabled deck is present. */" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "ToolTip", "Isolated multilayer material; selected automatically when an extra enabled deck is present." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_CloudParameters_MetaData[] = {
		{ "Category", "Only Clouds|Assets" },
		{ "Comment", "/** Private OnlyClouds collection. Original UltraDynamicSky collections are rejected. */" },
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
		{ "ToolTip", "Private OnlyClouds collection. Original UltraDynamicSky collections are rejected." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_CloudMID_MetaData[] = {
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_CollectionInstance_MetaData[] = {
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LayerDataTexture_MetaData[] = {
		{ "ModuleRelativePath", "Public/UltraDynamicSkyOnlyClouds.h" },
	};
#endif // WITH_METADATA

// ********** Begin Class AUltraDynamicSkyOnlyClouds constinit property declarations ***************
	static const UECodeGen_Private::FObjectPropertyParams NewProp_VolumetricCloud;
	static const UECodeGen_Private::FStrPropertyParams NewProp_CloudStatus;
	static const UECodeGen_Private::FStructPropertyParams NewProp_AdditionalCloudLayers_Inner;
	static const UECodeGen_Private::FArrayPropertyParams NewProp_AdditionalCloudLayers;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_LayerBottomAltitudeKm;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_LayerHeightKm;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_CloudScale;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_PlanetRadiusKm;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_CloudCoverage;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_FormationTextureScale;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_FormationZShift;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_MacroVariation;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_MacroScale;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_MacroOffset;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_FormationMipLevel;
	static const UECodeGen_Private::FSoftObjectPropertyParams NewProp_FormationTexture;
	static const UECodeGen_Private::FSoftObjectPropertyParams NewProp_DetailNoiseTexture;
	static const UECodeGen_Private::FSoftObjectPropertyParams NewProp_CloudProfileTexture;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_Noise3DScale;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_Erosion3D;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_ErosionPower;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_MinimumErosion;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_HighFrequencyNoise;
	static const UECodeGen_Private::FIntPropertyParams NewProp_HighFrequencyNoiseLevels;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_HighFrequencyNoiseDistance;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_HighFrequencyDistortion;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_Extinction;
	static const UECodeGen_Private::FStructPropertyParams NewProp_Albedo;
	static const UECodeGen_Private::FStructPropertyParams NewProp_TopEmissiveColor;
	static const UECodeGen_Private::FStructPropertyParams NewProp_BottomEmissiveColor;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_AmbientOcclusion;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_PhaseG;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_PhaseG2;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_PhaseBlend;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_MultiScatteringContribution;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_MultiScatteringOcclusion;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_MultiScatteringEccentricity;
	static void NewProp_bPerSampleAtmosphereTransmittance_SetBit(void* Obj)
	{
		((AUltraDynamicSkyOnlyClouds*)Obj)->bPerSampleAtmosphereTransmittance = 1;
	}
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bPerSampleAtmosphereTransmittance;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_CloudPhase;
	static const UECodeGen_Private::FStructPropertyParams NewProp_FormationOffset;
	static void NewProp_bAnimateClouds_SetBit(void* Obj)
	{
		((AUltraDynamicSkyOnlyClouds*)Obj)->bAnimateClouds = 1;
	}
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bAnimateClouds;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_CloudDirection;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_CloudMovementSpeed;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_FormationChangeSpeed;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_NoiseVerticalMovement;
	static void NewProp_bCinematicOffline_SetBit(void* Obj)
	{
		((AUltraDynamicSkyOnlyClouds*)Obj)->bCinematicOffline = 1;
	}
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bCinematicOffline;
	static void NewProp_bApplyCloudRendererQuality_SetBit(void* Obj)
	{
		((AUltraDynamicSkyOnlyClouds*)Obj)->bApplyCloudRendererQuality = 1;
	}
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bApplyCloudRendererQuality;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_CinematicViewSampleScale;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_RealtimeViewSampleScale;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_ShadowViewSampleScale;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_ReflectionViewSampleScale;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_ShadowReflectionSampleScale;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_TracingMaxDistanceKm;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_TracingStartMaxDistanceKm;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_ShadowTracingDistanceKm;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_StopTracingTransmittanceThreshold;
	static void NewProp_bVisibleInSkyLightCaptures_SetBit(void* Obj)
	{
		((AUltraDynamicSkyOnlyClouds*)Obj)->bVisibleInSkyLightCaptures = 1;
	}
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bVisibleInSkyLightCaptures;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_ScalarOverrides_ValueProp;
	static const UECodeGen_Private::FNamePropertyParams NewProp_ScalarOverrides_Key_KeyProp;
	static const UECodeGen_Private::FMapPropertyParams NewProp_ScalarOverrides;
	static const UECodeGen_Private::FStructPropertyParams NewProp_VectorOverrides_ValueProp;
	static const UECodeGen_Private::FNamePropertyParams NewProp_VectorOverrides_Key_KeyProp;
	static const UECodeGen_Private::FMapPropertyParams NewProp_VectorOverrides;
	static const UECodeGen_Private::FSoftObjectPropertyParams NewProp_CloudMaterial;
	static const UECodeGen_Private::FSoftObjectPropertyParams NewProp_LayeredCloudMaterial;
	static const UECodeGen_Private::FSoftObjectPropertyParams NewProp_CloudParameters;
	static const UECodeGen_Private::FObjectPropertyParams NewProp_CloudMID;
	static const UECodeGen_Private::FObjectPropertyParams NewProp_CollectionInstance;
	static const UECodeGen_Private::FObjectPropertyParams NewProp_LayerDataTexture;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
// ********** End Class AUltraDynamicSkyOnlyClouds constinit property declarations *****************
	static constexpr UE::CodeGen::FClassNativeFunction Funcs[] = {
		{ .NameUTF8 = UTF8TEXT("AddCloudLayer"), .Pointer = &AUltraDynamicSkyOnlyClouds::execAddCloudLayer },
		{ .NameUTF8 = UTF8TEXT("ApplyCinematicCloudQuality"), .Pointer = &AUltraDynamicSkyOnlyClouds::execApplyCinematicCloudQuality },
		{ .NameUTF8 = UTF8TEXT("RefreshClouds"), .Pointer = &AUltraDynamicSkyOnlyClouds::execRefreshClouds },
		{ .NameUTF8 = UTF8TEXT("ResetAnimationTime"), .Pointer = &AUltraDynamicSkyOnlyClouds::execResetAnimationTime },
		{ .NameUTF8 = UTF8TEXT("RestorePreviousCloudQuality"), .Pointer = &AUltraDynamicSkyOnlyClouds::execRestorePreviousCloudQuality },
	};
	static FTypeConstructFunc* DependentSingletons[];
	static constexpr FClassFunctionLinkInfo FuncInfo[] = {
		{ &Z_Construct_UFunction_AUltraDynamicSkyOnlyClouds_AddCloudLayer, "AddCloudLayer" }, // 243864b74a877e16ae29b7e48aee15458d8f9f1a
		{ &Z_Construct_UFunction_AUltraDynamicSkyOnlyClouds_ApplyCinematicCloudQuality, "ApplyCinematicCloudQuality" }, // c79f8700ae9f8f978f3eac2937df994a1a3ec2b4
		{ &Z_Construct_UFunction_AUltraDynamicSkyOnlyClouds_RefreshClouds, "RefreshClouds" }, // a9145e97fb5c8449ca44cfc37ff451b742e6881d
		{ &Z_Construct_UFunction_AUltraDynamicSkyOnlyClouds_ResetAnimationTime, "ResetAnimationTime" }, // 0d0a0a96e6ef53da3d042ec6aafa5dd44e62bc10
		{ &Z_Construct_UFunction_AUltraDynamicSkyOnlyClouds_RestorePreviousCloudQuality, "RestorePreviousCloudQuality" }, // a49e046a998c26e356ad87474b91f48dfa43f0c7
	};
	static_assert(UE_ARRAY_COUNT(FuncInfo) < 2048);
	static constexpr FCppClassTypeInfoStatic StaticCppClassTypeInfo = {
		TCppClassTypeTraits<AUltraDynamicSkyOnlyClouds>::IsAbstract,
	};
	static const UECodeGen_Private::FClassParams ClassParams;
}; // struct UHT_STATICS

// ********** Begin Class AUltraDynamicSkyOnlyClouds Property Definitions **************************
const UECodeGen_Private::FObjectPropertyParams UHT_STATICS::NewProp_VolumetricCloud = { "VolumetricCloud", nullptr, (EPropertyFlags)0x01140000000a001d, UECodeGen_Private::EPropertyGenFlags::Object | UECodeGen_Private::EPropertyGenFlags::ObjectPtr, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, VolumetricCloud), Z_Construct_UClass_UVolumetricCloudComponent, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_VolumetricCloud_MetaData), NewProp_VolumetricCloud_MetaData) };
const UECodeGen_Private::FStrPropertyParams UHT_STATICS::NewProp_CloudStatus = { "CloudStatus", nullptr, (EPropertyFlags)0x0010000000022815, UECodeGen_Private::EPropertyGenFlags::Str, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, CloudStatus), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_CloudStatus_MetaData), NewProp_CloudStatus_MetaData) };
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_AdditionalCloudLayers_Inner = { "AdditionalCloudLayers", nullptr, (EPropertyFlags)0x0000000000000000, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, 0, Z_Construct_UScriptStruct_FUDSOnlyCloudLayer, METADATA_PARAMS(0, nullptr) }; // 49db30341c4fa64097a440ef95355d7716f1dc8e
const UECodeGen_Private::FArrayPropertyParams UHT_STATICS::NewProp_AdditionalCloudLayers = { "AdditionalCloudLayers", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Array, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, AdditionalCloudLayers), EArrayPropertyFlags::None, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_AdditionalCloudLayers_MetaData), NewProp_AdditionalCloudLayers_MetaData) }; // 49db30341c4fa64097a440ef95355d7716f1dc8e
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_LayerBottomAltitudeKm = { "LayerBottomAltitudeKm", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, LayerBottomAltitudeKm), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LayerBottomAltitudeKm_MetaData), NewProp_LayerBottomAltitudeKm_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_LayerHeightKm = { "LayerHeightKm", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, LayerHeightKm), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LayerHeightKm_MetaData), NewProp_LayerHeightKm_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_CloudScale = { "CloudScale", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, CloudScale), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_CloudScale_MetaData), NewProp_CloudScale_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_PlanetRadiusKm = { "PlanetRadiusKm", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, PlanetRadiusKm), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_PlanetRadiusKm_MetaData), NewProp_PlanetRadiusKm_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_CloudCoverage = { "CloudCoverage", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, CloudCoverage), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_CloudCoverage_MetaData), NewProp_CloudCoverage_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_FormationTextureScale = { "FormationTextureScale", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, FormationTextureScale), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_FormationTextureScale_MetaData), NewProp_FormationTextureScale_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_FormationZShift = { "FormationZShift", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, FormationZShift), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_FormationZShift_MetaData), NewProp_FormationZShift_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_MacroVariation = { "MacroVariation", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, MacroVariation), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_MacroVariation_MetaData), NewProp_MacroVariation_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_MacroScale = { "MacroScale", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, MacroScale), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_MacroScale_MetaData), NewProp_MacroScale_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_MacroOffset = { "MacroOffset", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, MacroOffset), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_MacroOffset_MetaData), NewProp_MacroOffset_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_FormationMipLevel = { "FormationMipLevel", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, FormationMipLevel), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_FormationMipLevel_MetaData), NewProp_FormationMipLevel_MetaData) };
const UECodeGen_Private::FSoftObjectPropertyParams UHT_STATICS::NewProp_FormationTexture = { "FormationTexture", nullptr, (EPropertyFlags)0x0014000000000005, UECodeGen_Private::EPropertyGenFlags::SoftObject, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, FormationTexture), Z_Construct_UClass_UTexture, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_FormationTexture_MetaData), NewProp_FormationTexture_MetaData) };
const UECodeGen_Private::FSoftObjectPropertyParams UHT_STATICS::NewProp_DetailNoiseTexture = { "DetailNoiseTexture", nullptr, (EPropertyFlags)0x0014000000000005, UECodeGen_Private::EPropertyGenFlags::SoftObject, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, DetailNoiseTexture), Z_Construct_UClass_UTexture, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_DetailNoiseTexture_MetaData), NewProp_DetailNoiseTexture_MetaData) };
const UECodeGen_Private::FSoftObjectPropertyParams UHT_STATICS::NewProp_CloudProfileTexture = { "CloudProfileTexture", nullptr, (EPropertyFlags)0x0014000000000005, UECodeGen_Private::EPropertyGenFlags::SoftObject, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, CloudProfileTexture), Z_Construct_UClass_UTexture, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_CloudProfileTexture_MetaData), NewProp_CloudProfileTexture_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_Noise3DScale = { "Noise3DScale", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, Noise3DScale), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Noise3DScale_MetaData), NewProp_Noise3DScale_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_Erosion3D = { "Erosion3D", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, Erosion3D), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Erosion3D_MetaData), NewProp_Erosion3D_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_ErosionPower = { "ErosionPower", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, ErosionPower), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_ErosionPower_MetaData), NewProp_ErosionPower_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_MinimumErosion = { "MinimumErosion", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, MinimumErosion), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_MinimumErosion_MetaData), NewProp_MinimumErosion_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_HighFrequencyNoise = { "HighFrequencyNoise", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, HighFrequencyNoise), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_HighFrequencyNoise_MetaData), NewProp_HighFrequencyNoise_MetaData) };
const UECodeGen_Private::FIntPropertyParams UHT_STATICS::NewProp_HighFrequencyNoiseLevels = { "HighFrequencyNoiseLevels", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Int, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, HighFrequencyNoiseLevels), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_HighFrequencyNoiseLevels_MetaData), NewProp_HighFrequencyNoiseLevels_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_HighFrequencyNoiseDistance = { "HighFrequencyNoiseDistance", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, HighFrequencyNoiseDistance), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_HighFrequencyNoiseDistance_MetaData), NewProp_HighFrequencyNoiseDistance_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_HighFrequencyDistortion = { "HighFrequencyDistortion", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, HighFrequencyDistortion), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_HighFrequencyDistortion_MetaData), NewProp_HighFrequencyDistortion_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_Extinction = { "Extinction", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, Extinction), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Extinction_MetaData), NewProp_Extinction_MetaData) };
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_Albedo = { "Albedo", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, Albedo), Z_Construct_UScriptStruct_FLinearColor, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Albedo_MetaData), NewProp_Albedo_MetaData) };
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_TopEmissiveColor = { "TopEmissiveColor", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, TopEmissiveColor), Z_Construct_UScriptStruct_FLinearColor, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_TopEmissiveColor_MetaData), NewProp_TopEmissiveColor_MetaData) };
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_BottomEmissiveColor = { "BottomEmissiveColor", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, BottomEmissiveColor), Z_Construct_UScriptStruct_FLinearColor, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_BottomEmissiveColor_MetaData), NewProp_BottomEmissiveColor_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_AmbientOcclusion = { "AmbientOcclusion", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, AmbientOcclusion), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_AmbientOcclusion_MetaData), NewProp_AmbientOcclusion_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_PhaseG = { "PhaseG", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, PhaseG), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_PhaseG_MetaData), NewProp_PhaseG_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_PhaseG2 = { "PhaseG2", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, PhaseG2), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_PhaseG2_MetaData), NewProp_PhaseG2_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_PhaseBlend = { "PhaseBlend", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, PhaseBlend), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_PhaseBlend_MetaData), NewProp_PhaseBlend_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_MultiScatteringContribution = { "MultiScatteringContribution", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, MultiScatteringContribution), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_MultiScatteringContribution_MetaData), NewProp_MultiScatteringContribution_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_MultiScatteringOcclusion = { "MultiScatteringOcclusion", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, MultiScatteringOcclusion), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_MultiScatteringOcclusion_MetaData), NewProp_MultiScatteringOcclusion_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_MultiScatteringEccentricity = { "MultiScatteringEccentricity", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, MultiScatteringEccentricity), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_MultiScatteringEccentricity_MetaData), NewProp_MultiScatteringEccentricity_MetaData) };
const UECodeGen_Private::FBoolPropertyParams UHT_STATICS::NewProp_bPerSampleAtmosphereTransmittance = { "bPerSampleAtmosphereTransmittance", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, nullptr, nullptr, 1, sizeof(bool), sizeof(AUltraDynamicSkyOnlyClouds), &UHT_STATICS::NewProp_bPerSampleAtmosphereTransmittance_SetBit, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_bPerSampleAtmosphereTransmittance_MetaData), NewProp_bPerSampleAtmosphereTransmittance_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_CloudPhase = { "CloudPhase", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, CloudPhase), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_CloudPhase_MetaData), NewProp_CloudPhase_MetaData) };
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_FormationOffset = { "FormationOffset", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, FormationOffset), Z_Construct_UScriptStruct_FVector, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_FormationOffset_MetaData), NewProp_FormationOffset_MetaData) };
const UECodeGen_Private::FBoolPropertyParams UHT_STATICS::NewProp_bAnimateClouds = { "bAnimateClouds", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, nullptr, nullptr, 1, sizeof(bool), sizeof(AUltraDynamicSkyOnlyClouds), &UHT_STATICS::NewProp_bAnimateClouds_SetBit, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_bAnimateClouds_MetaData), NewProp_bAnimateClouds_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_CloudDirection = { "CloudDirection", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, CloudDirection), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_CloudDirection_MetaData), NewProp_CloudDirection_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_CloudMovementSpeed = { "CloudMovementSpeed", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, CloudMovementSpeed), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_CloudMovementSpeed_MetaData), NewProp_CloudMovementSpeed_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_FormationChangeSpeed = { "FormationChangeSpeed", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, FormationChangeSpeed), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_FormationChangeSpeed_MetaData), NewProp_FormationChangeSpeed_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_NoiseVerticalMovement = { "NoiseVerticalMovement", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, NoiseVerticalMovement), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_NoiseVerticalMovement_MetaData), NewProp_NoiseVerticalMovement_MetaData) };
const UECodeGen_Private::FBoolPropertyParams UHT_STATICS::NewProp_bCinematicOffline = { "bCinematicOffline", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, nullptr, nullptr, 1, sizeof(bool), sizeof(AUltraDynamicSkyOnlyClouds), &UHT_STATICS::NewProp_bCinematicOffline_SetBit, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_bCinematicOffline_MetaData), NewProp_bCinematicOffline_MetaData) };
const UECodeGen_Private::FBoolPropertyParams UHT_STATICS::NewProp_bApplyCloudRendererQuality = { "bApplyCloudRendererQuality", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, nullptr, nullptr, 1, sizeof(bool), sizeof(AUltraDynamicSkyOnlyClouds), &UHT_STATICS::NewProp_bApplyCloudRendererQuality_SetBit, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_bApplyCloudRendererQuality_MetaData), NewProp_bApplyCloudRendererQuality_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_CinematicViewSampleScale = { "CinematicViewSampleScale", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, CinematicViewSampleScale), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_CinematicViewSampleScale_MetaData), NewProp_CinematicViewSampleScale_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_RealtimeViewSampleScale = { "RealtimeViewSampleScale", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, RealtimeViewSampleScale), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_RealtimeViewSampleScale_MetaData), NewProp_RealtimeViewSampleScale_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_ShadowViewSampleScale = { "ShadowViewSampleScale", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, ShadowViewSampleScale), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_ShadowViewSampleScale_MetaData), NewProp_ShadowViewSampleScale_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_ReflectionViewSampleScale = { "ReflectionViewSampleScale", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, ReflectionViewSampleScale), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_ReflectionViewSampleScale_MetaData), NewProp_ReflectionViewSampleScale_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_ShadowReflectionSampleScale = { "ShadowReflectionSampleScale", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, ShadowReflectionSampleScale), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_ShadowReflectionSampleScale_MetaData), NewProp_ShadowReflectionSampleScale_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_TracingMaxDistanceKm = { "TracingMaxDistanceKm", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, TracingMaxDistanceKm), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_TracingMaxDistanceKm_MetaData), NewProp_TracingMaxDistanceKm_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_TracingStartMaxDistanceKm = { "TracingStartMaxDistanceKm", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, TracingStartMaxDistanceKm), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_TracingStartMaxDistanceKm_MetaData), NewProp_TracingStartMaxDistanceKm_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_ShadowTracingDistanceKm = { "ShadowTracingDistanceKm", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, ShadowTracingDistanceKm), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_ShadowTracingDistanceKm_MetaData), NewProp_ShadowTracingDistanceKm_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_StopTracingTransmittanceThreshold = { "StopTracingTransmittanceThreshold", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, StopTracingTransmittanceThreshold), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_StopTracingTransmittanceThreshold_MetaData), NewProp_StopTracingTransmittanceThreshold_MetaData) };
const UECodeGen_Private::FBoolPropertyParams UHT_STATICS::NewProp_bVisibleInSkyLightCaptures = { "bVisibleInSkyLightCaptures", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, nullptr, nullptr, 1, sizeof(bool), sizeof(AUltraDynamicSkyOnlyClouds), &UHT_STATICS::NewProp_bVisibleInSkyLightCaptures_SetBit, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_bVisibleInSkyLightCaptures_MetaData), NewProp_bVisibleInSkyLightCaptures_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_ScalarOverrides_ValueProp = { "ScalarOverrides", nullptr, (EPropertyFlags)0x0000000000000001, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, 1, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FNamePropertyParams UHT_STATICS::NewProp_ScalarOverrides_Key_KeyProp = { "ScalarOverrides_Key", nullptr, (EPropertyFlags)0x0000000000000001, UECodeGen_Private::EPropertyGenFlags::Name, nullptr, nullptr, 1, 0, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FMapPropertyParams UHT_STATICS::NewProp_ScalarOverrides = { "ScalarOverrides", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Map, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, ScalarOverrides), EMapPropertyFlags::None, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_ScalarOverrides_MetaData), NewProp_ScalarOverrides_MetaData) };
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_VectorOverrides_ValueProp = { "VectorOverrides", nullptr, (EPropertyFlags)0x0000000000000001, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, 1, Z_Construct_UScriptStruct_FLinearColor, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FNamePropertyParams UHT_STATICS::NewProp_VectorOverrides_Key_KeyProp = { "VectorOverrides_Key", nullptr, (EPropertyFlags)0x0000000000000001, UECodeGen_Private::EPropertyGenFlags::Name, nullptr, nullptr, 1, 0, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FMapPropertyParams UHT_STATICS::NewProp_VectorOverrides = { "VectorOverrides", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Map, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, VectorOverrides), EMapPropertyFlags::None, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_VectorOverrides_MetaData), NewProp_VectorOverrides_MetaData) };
const UECodeGen_Private::FSoftObjectPropertyParams UHT_STATICS::NewProp_CloudMaterial = { "CloudMaterial", nullptr, (EPropertyFlags)0x0014000000010015, UECodeGen_Private::EPropertyGenFlags::SoftObject, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, CloudMaterial), Z_Construct_UClass_UMaterialInterface, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_CloudMaterial_MetaData), NewProp_CloudMaterial_MetaData) };
const UECodeGen_Private::FSoftObjectPropertyParams UHT_STATICS::NewProp_LayeredCloudMaterial = { "LayeredCloudMaterial", nullptr, (EPropertyFlags)0x0014000000010015, UECodeGen_Private::EPropertyGenFlags::SoftObject, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, LayeredCloudMaterial), Z_Construct_UClass_UMaterialInterface, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LayeredCloudMaterial_MetaData), NewProp_LayeredCloudMaterial_MetaData) };
const UECodeGen_Private::FSoftObjectPropertyParams UHT_STATICS::NewProp_CloudParameters = { "CloudParameters", nullptr, (EPropertyFlags)0x0014000000010015, UECodeGen_Private::EPropertyGenFlags::SoftObject, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, CloudParameters), Z_Construct_UClass_UMaterialParameterCollection, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_CloudParameters_MetaData), NewProp_CloudParameters_MetaData) };
const UECodeGen_Private::FObjectPropertyParams UHT_STATICS::NewProp_CloudMID = { "CloudMID", nullptr, (EPropertyFlags)0x0144000000202000, UECodeGen_Private::EPropertyGenFlags::Object | UECodeGen_Private::EPropertyGenFlags::ObjectPtr, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, CloudMID), Z_Construct_UClass_UMaterialInstanceDynamic, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_CloudMID_MetaData), NewProp_CloudMID_MetaData) };
const UECodeGen_Private::FObjectPropertyParams UHT_STATICS::NewProp_CollectionInstance = { "CollectionInstance", nullptr, (EPropertyFlags)0x0144000000202000, UECodeGen_Private::EPropertyGenFlags::Object | UECodeGen_Private::EPropertyGenFlags::ObjectPtr, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, CollectionInstance), Z_Construct_UClass_UMaterialParameterCollectionInstance, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_CollectionInstance_MetaData), NewProp_CollectionInstance_MetaData) };
const UECodeGen_Private::FObjectPropertyParams UHT_STATICS::NewProp_LayerDataTexture = { "LayerDataTexture", nullptr, (EPropertyFlags)0x0144000000202000, UECodeGen_Private::EPropertyGenFlags::Object | UECodeGen_Private::EPropertyGenFlags::ObjectPtr, nullptr, nullptr, 1, STRUCT_OFFSET(AUltraDynamicSkyOnlyClouds, LayerDataTexture), Z_Construct_UClass_UTexture2D, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LayerDataTexture_MetaData), NewProp_LayerDataTexture_MetaData) };
const UECodeGen_Private::FPropertyParamsBase* const UHT_STATICS::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_VolumetricCloud,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_CloudStatus,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_AdditionalCloudLayers_Inner,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_AdditionalCloudLayers,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LayerBottomAltitudeKm,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LayerHeightKm,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_CloudScale,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_PlanetRadiusKm,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_CloudCoverage,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_FormationTextureScale,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_FormationZShift,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_MacroVariation,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_MacroScale,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_MacroOffset,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_FormationMipLevel,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_FormationTexture,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_DetailNoiseTexture,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_CloudProfileTexture,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Noise3DScale,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Erosion3D,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ErosionPower,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_MinimumErosion,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_HighFrequencyNoise,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_HighFrequencyNoiseLevels,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_HighFrequencyNoiseDistance,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_HighFrequencyDistortion,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Extinction,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Albedo,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_TopEmissiveColor,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_BottomEmissiveColor,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_AmbientOcclusion,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_PhaseG,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_PhaseG2,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_PhaseBlend,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_MultiScatteringContribution,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_MultiScatteringOcclusion,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_MultiScatteringEccentricity,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_bPerSampleAtmosphereTransmittance,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_CloudPhase,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_FormationOffset,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_bAnimateClouds,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_CloudDirection,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_CloudMovementSpeed,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_FormationChangeSpeed,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_NoiseVerticalMovement,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_bCinematicOffline,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_bApplyCloudRendererQuality,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_CinematicViewSampleScale,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_RealtimeViewSampleScale,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ShadowViewSampleScale,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ReflectionViewSampleScale,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ShadowReflectionSampleScale,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_TracingMaxDistanceKm,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_TracingStartMaxDistanceKm,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ShadowTracingDistanceKm,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_StopTracingTransmittanceThreshold,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_bVisibleInSkyLightCaptures,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ScalarOverrides_ValueProp,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ScalarOverrides_Key_KeyProp,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ScalarOverrides,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_VectorOverrides_ValueProp,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_VectorOverrides_Key_KeyProp,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_VectorOverrides,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_CloudMaterial,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LayeredCloudMaterial,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_CloudParameters,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_CloudMID,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_CollectionInstance,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LayerDataTexture,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::PropPointers) < 2048);
// ********** End Class AUltraDynamicSkyOnlyClouds Property Definitions ****************************
FTypeConstructFunc* UHT_STATICS::DependentSingletons[] = {
	(FTypeConstructFunc*)Z_Construct_UClass_AActor,
	(FTypeConstructFunc*)Z_Construct_UPackage__Script_CloudGeneratorTools,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::DependentSingletons) < 16);
const UECodeGen_Private::FClassParams UHT_STATICS::ClassParams = {
	&Z_Construct_UClass_AUltraDynamicSkyOnlyClouds,
	"Engine",
	&StaticCppClassTypeInfo,
	DependentSingletons,
	FuncInfo,
	UHT_STATICS::PropPointers,
	nullptr,
	UE_ARRAY_COUNT(DependentSingletons),
	UE_ARRAY_COUNT(FuncInfo),
	UE_ARRAY_COUNT(UHT_STATICS::PropPointers),
	0,
	0x009000A4u,
	METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)
};
static void AUltraDynamicSkyOnlyClouds_StaticRegisterNativesAUltraDynamicSkyOnlyClouds()
{
	UClass* Class = AUltraDynamicSkyOnlyClouds::StaticClass();
	FNativeFunctionRegistrar::RegisterFunctions(Class, 		MakeConstArrayView(UHT_STATICS::Funcs));
}
FClassRegistrationInfo Z_Registration_Info_UClass_AUltraDynamicSkyOnlyClouds;
UClass* Z_Construct_UClass_AUltraDynamicSkyOnlyClouds(ETypeConstructPhase Phase)
{
	if (Phase == ETypeConstructPhase::Inner)
	{
		using TClass = AUltraDynamicSkyOnlyClouds;
		if (!Z_Registration_Info_UClass_AUltraDynamicSkyOnlyClouds.InnerSingleton)
		{
			GetPrivateStaticClassBody(
				TClass::StaticPackage(),
				TEXT("UltraDynamicSkyOnlyClouds"),
				Z_Registration_Info_UClass_AUltraDynamicSkyOnlyClouds.InnerSingleton,
				AUltraDynamicSkyOnlyClouds_StaticRegisterNativesAUltraDynamicSkyOnlyClouds,
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
		return Z_Registration_Info_UClass_AUltraDynamicSkyOnlyClouds.InnerSingleton;
	}
	if (!Z_Registration_Info_UClass_AUltraDynamicSkyOnlyClouds.OuterSingleton)
	{
		UECodeGen_Private::ConstructUClass(Z_Registration_Info_UClass_AUltraDynamicSkyOnlyClouds.OuterSingleton, UHT_STATICS::ClassParams);
	}
	return Z_Registration_Info_UClass_AUltraDynamicSkyOnlyClouds.OuterSingleton;
}
#undef UHT_STATICS
DEFINE_VTABLE_PTR_HELPER_CTOR_NS(, AUltraDynamicSkyOnlyClouds);
AUltraDynamicSkyOnlyClouds::~AUltraDynamicSkyOnlyClouds() {}
// ********** End Class AUltraDynamicSkyOnlyClouds *************************************************

// ********** Begin Registration *******************************************************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_CompiledInDeferFile_FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_UltraDynamicSkyOnlyClouds_h__Script_CloudGeneratorTools_Statics
struct UHT_STATICS
{
	static constexpr FStructRegisterCompiledInInfo ScriptStructInfo[] = {
		{ Z_Construct_UScriptStruct_FUDSOnlyCloudLayer, Z_Construct_UScriptStruct_FUDSOnlyCloudLayer_Statics::NewStructOps, TEXT("UDSOnlyCloudLayer"),&Z_Registration_Info_UScriptStruct_FUDSOnlyCloudLayer, CONSTRUCT_RELOAD_VERSION_INFO(FStructReloadVersionInfo, sizeof(FUDSOnlyCloudLayer), 1239101492U) },
	};
	static constexpr FClassRegisterCompiledInInfo ClassInfo[] = {
		{ Z_Construct_UClass_AUltraDynamicSkyOnlyClouds, TEXT("AUltraDynamicSkyOnlyClouds"), &Z_Registration_Info_UClass_AUltraDynamicSkyOnlyClouds, CONSTRUCT_RELOAD_VERSION_INFO(FClassReloadVersionInfo, sizeof(AUltraDynamicSkyOnlyClouds), 3912384033U) },
	};
}; // UHT_STATICS 
static FRegisterCompiledInInfo Z_CompiledInDeferFile_FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_UltraDynamicSkyOnlyClouds_h__Script_CloudGeneratorTools_53ce7e83effd251db83429ee179eaf7bc8a950b3{
	TEXT("/Script/CloudGeneratorTools"),
	UHT_STATICS::ClassInfo, UE_ARRAY_COUNT(UHT_STATICS::ClassInfo),
	UHT_STATICS::ScriptStructInfo, UE_ARRAY_COUNT(UHT_STATICS::ScriptStructInfo),
	nullptr, 0,
	nullptr, 0,
};
#undef UHT_STATICS
// ********** End Registration *********************************************************************
#undef UHT_STRUCT_BASE

PRAGMA_ENABLE_DEPRECATION_WARNINGS
