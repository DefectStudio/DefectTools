// Copyright Epic Games, Inc. All Rights Reserved.
/*===========================================================================
	Generated code exported from UnrealHeaderTool.
	DO NOT modify this manually! Edit the corresponding .h files instead!
===========================================================================*/

#include "UObject/GeneratedCppIncludes.h"
#include "CloudGeneratorActor.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS
static_assert(!UE_WITH_CONSTINIT_UOBJECT, "This generated code can only be compiled with !UE_WITH_CONSTINIT_UOBJECT");
void EmptyLinkFunctionForGeneratedCodeCloudGeneratorActor() {}

// ********** Begin Cross Module References ********************************************************
COREUOBJECT_API UScriptStruct* Z_Construct_UScriptStruct_FGuid(ETypeConstructPhase);
COREUOBJECT_API UScriptStruct* Z_Construct_UScriptStruct_FLinearColor(ETypeConstructPhase);
COREUOBJECT_API UScriptStruct* Z_Construct_UScriptStruct_FTransform(ETypeConstructPhase);
COREUOBJECT_API UScriptStruct* Z_Construct_UScriptStruct_FVector(ETypeConstructPhase);
ENGINE_API UClass* Z_Construct_UClass_AActor(ETypeConstructPhase);
ENGINE_API UClass* Z_Construct_UClass_UDataAsset(ETypeConstructPhase);
ENGINE_API UClass* Z_Construct_UClass_UPrimitiveComponent(ETypeConstructPhase);
ENGINE_API UClass* Z_Construct_UClass_UHeterogeneousVolumeComponent(ETypeConstructPhase);
ENGINE_API UClass* Z_Construct_UClass_UMaterialInstanceDynamic(ETypeConstructPhase);
ENGINE_API UClass* Z_Construct_UClass_UMaterialInterface(ETypeConstructPhase);
ENGINE_API UClass* Z_Construct_UClass_USceneComponent(ETypeConstructPhase);
ENGINE_API UClass* Z_Construct_UClass_UTexture2D(ETypeConstructPhase);
ENGINE_API UClass* Z_Construct_UClass_UVolumeTexture(ETypeConstructPhase);
// ********** End Cross Module References **********************************************************

// ********** Begin Same Module References *********************************************************
UPackage* Z_Construct_UPackage__Script_CloudGeneratorTools(ETypeConstructPhase);
CLOUDGENERATORTOOLS_API UClass* Z_Construct_UClass_ACloudGeneratorActor(ETypeConstructPhase);
CLOUDGENERATORTOOLS_API UClass* Z_Construct_UClass_ACloudGuideActor(ETypeConstructPhase);
CLOUDGENERATORTOOLS_API UScriptStruct* Z_Construct_UScriptStruct_FCloudGuideRecipe(ETypeConstructPhase);
CLOUDGENERATORTOOLS_API UClass* Z_Construct_UClass_UCloudGuideShapeComponent(ETypeConstructPhase);
CLOUDGENERATORTOOLS_API UScriptStruct* Z_Construct_UScriptStruct_FCloudRecipe(ETypeConstructPhase);
CLOUDGENERATORTOOLS_API UClass* Z_Construct_UClass_UCloudRecipePreset(ETypeConstructPhase);
CLOUDGENERATORTOOLS_API UEnum* Z_Construct_UEnum_CloudGeneratorTools_ECloudBillowStyle(ETypeConstructPhase);
CLOUDGENERATORTOOLS_API UEnum* Z_Construct_UEnum_CloudGeneratorTools_ECloudGuideOperation(ETypeConstructPhase);
CLOUDGENERATORTOOLS_API UEnum* Z_Construct_UEnum_CloudGeneratorTools_ECloudGuideShape(ETypeConstructPhase);
CLOUDGENERATORTOOLS_API UEnum* Z_Construct_UEnum_CloudGeneratorTools_ECloudNoiseLayout(ETypeConstructPhase);
CLOUDGENERATORTOOLS_API UEnum* Z_Construct_UEnum_CloudGeneratorTools_ECloudPreviewQuality(ETypeConstructPhase);
CLOUDGENERATORTOOLS_API UEnum* Z_Construct_UEnum_CloudGeneratorTools_ECloudStyle(ETypeConstructPhase);
CLOUDGENERATORTOOLS_API UClass* Z_Construct_UClass_ACloudGeneratorActor(ETypeConstructPhase);
CLOUDGENERATORTOOLS_API UClass* Z_Construct_UClass_ACloudGuideActor(ETypeConstructPhase);
CLOUDGENERATORTOOLS_API UClass* Z_Construct_UClass_UCloudGuideShapeComponent(ETypeConstructPhase);
CLOUDGENERATORTOOLS_API UClass* Z_Construct_UClass_UCloudRecipePreset(ETypeConstructPhase);
// ********** End Same Module References ***********************************************************
#define UHT_STRUCT_BASE(INIT) UE::CodeGen::ConstInit::TCompiledInObjectPtr<const FStructBaseChain>(UE::Private::AsStructBaseChain(INIT))

// ********** Begin Enum ECloudGuideShape **********************************************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UEnum_CloudGeneratorTools_ECloudGuideShape_Statics
template<> CLOUDGENERATORTOOLS_NON_ATTRIBUTED_API UEnum* StaticEnum<ECloudGuideShape>()
{
	return Z_Construct_UEnum_CloudGeneratorTools_ECloudGuideShape(ETypeConstructPhase::Outer);
}
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "BlueprintType", "true" },
		{ "Box.DisplayName", "Box" },
		{ "Box.Name", "ECloudGuideShape::Box" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "Sphere.DisplayName", "Sphere" },
		{ "Sphere.Name", "ECloudGuideShape::Sphere" },
	};
#endif // WITH_METADATA
	static constexpr UECodeGen_Private::FEnumeratorParam Enumerators[] = {
		{ "ECloudGuideShape::Sphere", (int64)ECloudGuideShape::Sphere },
		{ "ECloudGuideShape::Box", (int64)ECloudGuideShape::Box },
	};
	static const UECodeGen_Private::FEnumParams EnumParams;
}; // struct UHT_STATICS 
const UECodeGen_Private::FEnumParams UHT_STATICS::EnumParams = {
	(FTypeConstructFunc*)Z_Construct_UPackage__Script_CloudGeneratorTools,
	nullptr,
	"ECloudGuideShape",
	"ECloudGuideShape",
	UHT_STATICS::Enumerators,
	RF_Public|RF_Transient|RF_MarkAsNative,
	UE_ARRAY_COUNT(UHT_STATICS::Enumerators),
	EEnumFlags::None,
	(uint8)UEnum::ECppForm::EnumClass,
	(uint8)UEnum::EUnderlyingType::uint8,
	METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)
};
static FEnumRegistrationInfo ZRIE_ECloudGuideShape;
UEnum* Z_Construct_UEnum_CloudGeneratorTools_ECloudGuideShape(ETypeConstructPhase Phase)
{
	if (Phase == ETypeConstructPhase::Outer)
	{
		if (!ZRIE_ECloudGuideShape.OuterSingleton)
		{
			ZRIE_ECloudGuideShape.OuterSingleton = GetStaticEnum(Z_Construct_UEnum_CloudGeneratorTools_ECloudGuideShape, (UObject*)Z_Construct_UPackage__Script_CloudGeneratorTools(ETypeConstructPhase::Outer), TEXT("ECloudGuideShape"));
		}
		return ZRIE_ECloudGuideShape.OuterSingleton;
	}
	if (!ZRIE_ECloudGuideShape.InnerSingleton)
	{
		UECodeGen_Private::ConstructUEnum(ZRIE_ECloudGuideShape.InnerSingleton, UHT_STATICS::EnumParams);
	}
	return ZRIE_ECloudGuideShape.InnerSingleton;
}
#undef UHT_STATICS
// ********** End Enum ECloudGuideShape ************************************************************

// ********** Begin Enum ECloudGuideOperation ******************************************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UEnum_CloudGeneratorTools_ECloudGuideOperation_Statics
template<> CLOUDGENERATORTOOLS_NON_ATTRIBUTED_API UEnum* StaticEnum<ECloudGuideOperation>()
{
	return Z_Construct_UEnum_CloudGeneratorTools_ECloudGuideOperation(ETypeConstructPhase::Outer);
}
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "Add.DisplayName", "Additive" },
		{ "Add.Name", "ECloudGuideOperation::Add" },
		{ "BlueprintType", "true" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "Subtract.DisplayName", "Subtractive" },
		{ "Subtract.Name", "ECloudGuideOperation::Subtract" },
	};
#endif // WITH_METADATA
	static constexpr UECodeGen_Private::FEnumeratorParam Enumerators[] = {
		{ "ECloudGuideOperation::Add", (int64)ECloudGuideOperation::Add },
		{ "ECloudGuideOperation::Subtract", (int64)ECloudGuideOperation::Subtract },
	};
	static const UECodeGen_Private::FEnumParams EnumParams;
}; // struct UHT_STATICS 
const UECodeGen_Private::FEnumParams UHT_STATICS::EnumParams = {
	(FTypeConstructFunc*)Z_Construct_UPackage__Script_CloudGeneratorTools,
	nullptr,
	"ECloudGuideOperation",
	"ECloudGuideOperation",
	UHT_STATICS::Enumerators,
	RF_Public|RF_Transient|RF_MarkAsNative,
	UE_ARRAY_COUNT(UHT_STATICS::Enumerators),
	EEnumFlags::None,
	(uint8)UEnum::ECppForm::EnumClass,
	(uint8)UEnum::EUnderlyingType::uint8,
	METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)
};
static FEnumRegistrationInfo ZRIE_ECloudGuideOperation;
UEnum* Z_Construct_UEnum_CloudGeneratorTools_ECloudGuideOperation(ETypeConstructPhase Phase)
{
	if (Phase == ETypeConstructPhase::Outer)
	{
		if (!ZRIE_ECloudGuideOperation.OuterSingleton)
		{
			ZRIE_ECloudGuideOperation.OuterSingleton = GetStaticEnum(Z_Construct_UEnum_CloudGeneratorTools_ECloudGuideOperation, (UObject*)Z_Construct_UPackage__Script_CloudGeneratorTools(ETypeConstructPhase::Outer), TEXT("ECloudGuideOperation"));
		}
		return ZRIE_ECloudGuideOperation.OuterSingleton;
	}
	if (!ZRIE_ECloudGuideOperation.InnerSingleton)
	{
		UECodeGen_Private::ConstructUEnum(ZRIE_ECloudGuideOperation.InnerSingleton, UHT_STATICS::EnumParams);
	}
	return ZRIE_ECloudGuideOperation.InnerSingleton;
}
#undef UHT_STATICS
// ********** End Enum ECloudGuideOperation ********************************************************

// ********** Begin Enum ECloudPreviewQuality ******************************************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UEnum_CloudGeneratorTools_ECloudPreviewQuality_Statics
template<> CLOUDGENERATORTOOLS_NON_ATTRIBUTED_API UEnum* StaticEnum<ECloudPreviewQuality>()
{
	return Z_Construct_UEnum_CloudGeneratorTools_ECloudPreviewQuality(ETypeConstructPhase::Outer);
}
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "BlueprintType", "true" },
		{ "Cinematic.DisplayName", "Cinematic" },
		{ "Cinematic.Name", "ECloudPreviewQuality::Cinematic" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "Preview.DisplayName", "Preview" },
		{ "Preview.Name", "ECloudPreviewQuality::Preview" },
	};
#endif // WITH_METADATA
	static constexpr UECodeGen_Private::FEnumeratorParam Enumerators[] = {
		{ "ECloudPreviewQuality::Preview", (int64)ECloudPreviewQuality::Preview },
		{ "ECloudPreviewQuality::Cinematic", (int64)ECloudPreviewQuality::Cinematic },
	};
	static const UECodeGen_Private::FEnumParams EnumParams;
}; // struct UHT_STATICS 
const UECodeGen_Private::FEnumParams UHT_STATICS::EnumParams = {
	(FTypeConstructFunc*)Z_Construct_UPackage__Script_CloudGeneratorTools,
	nullptr,
	"ECloudPreviewQuality",
	"ECloudPreviewQuality",
	UHT_STATICS::Enumerators,
	RF_Public|RF_Transient|RF_MarkAsNative,
	UE_ARRAY_COUNT(UHT_STATICS::Enumerators),
	EEnumFlags::None,
	(uint8)UEnum::ECppForm::EnumClass,
	(uint8)UEnum::EUnderlyingType::uint8,
	METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)
};
static FEnumRegistrationInfo ZRIE_ECloudPreviewQuality;
UEnum* Z_Construct_UEnum_CloudGeneratorTools_ECloudPreviewQuality(ETypeConstructPhase Phase)
{
	if (Phase == ETypeConstructPhase::Outer)
	{
		if (!ZRIE_ECloudPreviewQuality.OuterSingleton)
		{
			ZRIE_ECloudPreviewQuality.OuterSingleton = GetStaticEnum(Z_Construct_UEnum_CloudGeneratorTools_ECloudPreviewQuality, (UObject*)Z_Construct_UPackage__Script_CloudGeneratorTools(ETypeConstructPhase::Outer), TEXT("ECloudPreviewQuality"));
		}
		return ZRIE_ECloudPreviewQuality.OuterSingleton;
	}
	if (!ZRIE_ECloudPreviewQuality.InnerSingleton)
	{
		UECodeGen_Private::ConstructUEnum(ZRIE_ECloudPreviewQuality.InnerSingleton, UHT_STATICS::EnumParams);
	}
	return ZRIE_ECloudPreviewQuality.InnerSingleton;
}
#undef UHT_STATICS
// ********** End Enum ECloudPreviewQuality ********************************************************

// ********** Begin Enum ECloudStyle ***************************************************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UEnum_CloudGeneratorTools_ECloudStyle_Statics
template<> CLOUDGENERATORTOOLS_NON_ATTRIBUTED_API UEnum* StaticEnum<ECloudStyle>()
{
	return Z_Construct_UEnum_CloudGeneratorTools_ECloudStyle(ETypeConstructPhase::Outer);
}
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "BlueprintType", "true" },
		{ "Cirrus.DisplayName", "Cirrus" },
		{ "Cirrus.Name", "ECloudStyle::Cirrus" },
		{ "Cumulonimbus.DisplayName", "Cumulonimbus" },
		{ "Cumulonimbus.Name", "ECloudStyle::Cumulonimbus" },
		{ "Cumulus.DisplayName", "Cumulus" },
		{ "Cumulus.Name", "ECloudStyle::Cumulus" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
#endif // WITH_METADATA
	static constexpr UECodeGen_Private::FEnumeratorParam Enumerators[] = {
		{ "ECloudStyle::Cumulus", (int64)ECloudStyle::Cumulus },
		{ "ECloudStyle::Cumulonimbus", (int64)ECloudStyle::Cumulonimbus },
		{ "ECloudStyle::Cirrus", (int64)ECloudStyle::Cirrus },
	};
	static const UECodeGen_Private::FEnumParams EnumParams;
}; // struct UHT_STATICS 
const UECodeGen_Private::FEnumParams UHT_STATICS::EnumParams = {
	(FTypeConstructFunc*)Z_Construct_UPackage__Script_CloudGeneratorTools,
	nullptr,
	"ECloudStyle",
	"ECloudStyle",
	UHT_STATICS::Enumerators,
	RF_Public|RF_Transient|RF_MarkAsNative,
	UE_ARRAY_COUNT(UHT_STATICS::Enumerators),
	EEnumFlags::None,
	(uint8)UEnum::ECppForm::EnumClass,
	(uint8)UEnum::EUnderlyingType::uint8,
	METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)
};
static FEnumRegistrationInfo ZRIE_ECloudStyle;
UEnum* Z_Construct_UEnum_CloudGeneratorTools_ECloudStyle(ETypeConstructPhase Phase)
{
	if (Phase == ETypeConstructPhase::Outer)
	{
		if (!ZRIE_ECloudStyle.OuterSingleton)
		{
			ZRIE_ECloudStyle.OuterSingleton = GetStaticEnum(Z_Construct_UEnum_CloudGeneratorTools_ECloudStyle, (UObject*)Z_Construct_UPackage__Script_CloudGeneratorTools(ETypeConstructPhase::Outer), TEXT("ECloudStyle"));
		}
		return ZRIE_ECloudStyle.OuterSingleton;
	}
	if (!ZRIE_ECloudStyle.InnerSingleton)
	{
		UECodeGen_Private::ConstructUEnum(ZRIE_ECloudStyle.InnerSingleton, UHT_STATICS::EnumParams);
	}
	return ZRIE_ECloudStyle.InnerSingleton;
}
#undef UHT_STATICS
// ********** End Enum ECloudStyle *****************************************************************

// ********** Begin Enum ECloudBillowStyle *********************************************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UEnum_CloudGeneratorTools_ECloudBillowStyle_Statics
template<> CLOUDGENERATORTOOLS_NON_ATTRIBUTED_API UEnum* StaticEnum<ECloudBillowStyle>()
{
	return Z_Construct_UEnum_CloudGeneratorTools_ECloudBillowStyle(ETypeConstructPhase::Outer);
}
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "BlueprintType", "true" },
		{ "Cauliflower.DisplayName", "Cauliflower" },
		{ "Cauliflower.Name", "ECloudBillowStyle::Cauliflower" },
		{ "Classic.DisplayName", "Classic" },
		{ "Classic.Name", "ECloudBillowStyle::Classic" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "SoftRolling.DisplayName", "Soft Rolling" },
		{ "SoftRolling.Name", "ECloudBillowStyle::SoftRolling" },
		{ "Turbulent.DisplayName", "Turbulent" },
		{ "Turbulent.Name", "ECloudBillowStyle::Turbulent" },
	};
#endif // WITH_METADATA
	static constexpr UECodeGen_Private::FEnumeratorParam Enumerators[] = {
		{ "ECloudBillowStyle::Classic", (int64)ECloudBillowStyle::Classic },
		{ "ECloudBillowStyle::Cauliflower", (int64)ECloudBillowStyle::Cauliflower },
		{ "ECloudBillowStyle::SoftRolling", (int64)ECloudBillowStyle::SoftRolling },
		{ "ECloudBillowStyle::Turbulent", (int64)ECloudBillowStyle::Turbulent },
	};
	static const UECodeGen_Private::FEnumParams EnumParams;
}; // struct UHT_STATICS 
const UECodeGen_Private::FEnumParams UHT_STATICS::EnumParams = {
	(FTypeConstructFunc*)Z_Construct_UPackage__Script_CloudGeneratorTools,
	nullptr,
	"ECloudBillowStyle",
	"ECloudBillowStyle",
	UHT_STATICS::Enumerators,
	RF_Public|RF_Transient|RF_MarkAsNative,
	UE_ARRAY_COUNT(UHT_STATICS::Enumerators),
	EEnumFlags::None,
	(uint8)UEnum::ECppForm::EnumClass,
	(uint8)UEnum::EUnderlyingType::uint8,
	METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)
};
static FEnumRegistrationInfo ZRIE_ECloudBillowStyle;
UEnum* Z_Construct_UEnum_CloudGeneratorTools_ECloudBillowStyle(ETypeConstructPhase Phase)
{
	if (Phase == ETypeConstructPhase::Outer)
	{
		if (!ZRIE_ECloudBillowStyle.OuterSingleton)
		{
			ZRIE_ECloudBillowStyle.OuterSingleton = GetStaticEnum(Z_Construct_UEnum_CloudGeneratorTools_ECloudBillowStyle, (UObject*)Z_Construct_UPackage__Script_CloudGeneratorTools(ETypeConstructPhase::Outer), TEXT("ECloudBillowStyle"));
		}
		return ZRIE_ECloudBillowStyle.OuterSingleton;
	}
	if (!ZRIE_ECloudBillowStyle.InnerSingleton)
	{
		UECodeGen_Private::ConstructUEnum(ZRIE_ECloudBillowStyle.InnerSingleton, UHT_STATICS::EnumParams);
	}
	return ZRIE_ECloudBillowStyle.InnerSingleton;
}
#undef UHT_STATICS
// ********** End Enum ECloudBillowStyle ***********************************************************

// ********** Begin Enum ECloudNoiseLayout *********************************************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UEnum_CloudGeneratorTools_ECloudNoiseLayout_Statics
template<> CLOUDGENERATORTOOLS_NON_ATTRIBUTED_API UEnum* StaticEnum<ECloudNoiseLayout>()
{
	return Z_Construct_UEnum_CloudGeneratorTools_ECloudNoiseLayout(ETypeConstructPhase::Outer);
}
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "BlueprintType", "true" },
		{ "Grayscale.DisplayName", "Grayscale (Red Channel)" },
		{ "Grayscale.Name", "ECloudNoiseLayout::Grayscale" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "PackedRGB.DisplayName", "Packed RGB" },
		{ "PackedRGB.Name", "ECloudNoiseLayout::PackedRGB" },
	};
#endif // WITH_METADATA
	static constexpr UECodeGen_Private::FEnumeratorParam Enumerators[] = {
		{ "ECloudNoiseLayout::PackedRGB", (int64)ECloudNoiseLayout::PackedRGB },
		{ "ECloudNoiseLayout::Grayscale", (int64)ECloudNoiseLayout::Grayscale },
	};
	static const UECodeGen_Private::FEnumParams EnumParams;
}; // struct UHT_STATICS 
const UECodeGen_Private::FEnumParams UHT_STATICS::EnumParams = {
	(FTypeConstructFunc*)Z_Construct_UPackage__Script_CloudGeneratorTools,
	nullptr,
	"ECloudNoiseLayout",
	"ECloudNoiseLayout",
	UHT_STATICS::Enumerators,
	RF_Public|RF_Transient|RF_MarkAsNative,
	UE_ARRAY_COUNT(UHT_STATICS::Enumerators),
	EEnumFlags::None,
	(uint8)UEnum::ECppForm::EnumClass,
	(uint8)UEnum::EUnderlyingType::uint8,
	METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)
};
static FEnumRegistrationInfo ZRIE_ECloudNoiseLayout;
UEnum* Z_Construct_UEnum_CloudGeneratorTools_ECloudNoiseLayout(ETypeConstructPhase Phase)
{
	if (Phase == ETypeConstructPhase::Outer)
	{
		if (!ZRIE_ECloudNoiseLayout.OuterSingleton)
		{
			ZRIE_ECloudNoiseLayout.OuterSingleton = GetStaticEnum(Z_Construct_UEnum_CloudGeneratorTools_ECloudNoiseLayout, (UObject*)Z_Construct_UPackage__Script_CloudGeneratorTools(ETypeConstructPhase::Outer), TEXT("ECloudNoiseLayout"));
		}
		return ZRIE_ECloudNoiseLayout.OuterSingleton;
	}
	if (!ZRIE_ECloudNoiseLayout.InnerSingleton)
	{
		UECodeGen_Private::ConstructUEnum(ZRIE_ECloudNoiseLayout.InnerSingleton, UHT_STATICS::EnumParams);
	}
	return ZRIE_ECloudNoiseLayout.InnerSingleton;
}
#undef UHT_STATICS
// ********** End Enum ECloudNoiseLayout ***********************************************************

// ********** Begin ScriptStruct FCloudGuideRecipe *************************************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UScriptStruct_FCloudGuideRecipe_Statics
struct UHT_STATICS
{
	static inline consteval int32 GetStructSize() { return DataSizeOf<FCloudGuideRecipe>(); }
	static inline consteval int16 GetStructAlignment() { return alignof(FCloudGuideRecipe); }
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "BlueprintType", "true" },
		{ "Comment", "/** One guide in a portable recipe. Transforms are relative to the generator. */" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "One guide in a portable recipe. Transforms are relative to the generator." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LocalTransform_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Shape_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Operation_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_SoftnessCm_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_bEnabled_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_GuideId_MetaData[] = {
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
#endif // WITH_METADATA

// ********** Begin ScriptStruct FCloudGuideRecipe constinit property declarations *****************
	static const UECodeGen_Private::FStructPropertyParams NewProp_LocalTransform;
	static const UECodeGen_Private::FBytePropertyParams NewProp_Shape_Underlying;
	static const UECodeGen_Private::FEnumPropertyParams NewProp_Shape;
	static const UECodeGen_Private::FBytePropertyParams NewProp_Operation_Underlying;
	static const UECodeGen_Private::FEnumPropertyParams NewProp_Operation;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_SoftnessCm;
	static void NewProp_bEnabled_SetBit(void* Obj)
	{
		((FCloudGuideRecipe*)Obj)->bEnabled = 1;
	}
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bEnabled;
	static const UECodeGen_Private::FStructPropertyParams NewProp_GuideId;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
// ********** End ScriptStruct FCloudGuideRecipe constinit property declarations *******************
	static void* NewStructOps()
	{
		return (UScriptStruct::ICppStructOps*)new UScriptStruct::TCppStructOps<FCloudGuideRecipe>();
	}
	static const UECodeGen_Private::FStructParams StructParams;
}; // struct UHT_STATICS

// ********** Begin ScriptStruct FCloudGuideRecipe Property Definitions ****************************
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_LocalTransform = { "LocalTransform", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudGuideRecipe, LocalTransform), Z_Construct_UScriptStruct_FTransform, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LocalTransform_MetaData), NewProp_LocalTransform_MetaData) };
const UECodeGen_Private::FBytePropertyParams UHT_STATICS::NewProp_Shape_Underlying = { "UnderlyingType", nullptr, (EPropertyFlags)0x0000000000000000, UECodeGen_Private::EPropertyGenFlags::Byte, nullptr, nullptr, 1, 0, nullptr, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FEnumPropertyParams UHT_STATICS::NewProp_Shape = { "Shape", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Enum, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudGuideRecipe, Shape), Z_Construct_UEnum_CloudGeneratorTools_ECloudGuideShape, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Shape_MetaData), NewProp_Shape_MetaData) }; // 6d71168086afd1364f37306fe0b7b4945e7177fa
const UECodeGen_Private::FBytePropertyParams UHT_STATICS::NewProp_Operation_Underlying = { "UnderlyingType", nullptr, (EPropertyFlags)0x0000000000000000, UECodeGen_Private::EPropertyGenFlags::Byte, nullptr, nullptr, 1, 0, nullptr, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FEnumPropertyParams UHT_STATICS::NewProp_Operation = { "Operation", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Enum, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudGuideRecipe, Operation), Z_Construct_UEnum_CloudGeneratorTools_ECloudGuideOperation, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Operation_MetaData), NewProp_Operation_MetaData) }; // 8a45f973b54fed74d1a9e7d7bf389916af6abf41
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_SoftnessCm = { "SoftnessCm", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudGuideRecipe, SoftnessCm), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_SoftnessCm_MetaData), NewProp_SoftnessCm_MetaData) };
const UECodeGen_Private::FBoolPropertyParams UHT_STATICS::NewProp_bEnabled = { "bEnabled", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, nullptr, nullptr, 1, sizeof(bool), sizeof(FCloudGuideRecipe), &UHT_STATICS::NewProp_bEnabled_SetBit, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_bEnabled_MetaData), NewProp_bEnabled_MetaData) };
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_GuideId = { "GuideId", nullptr, (EPropertyFlags)0x0010000000000000, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudGuideRecipe, GuideId), Z_Construct_UScriptStruct_FGuid, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_GuideId_MetaData), NewProp_GuideId_MetaData) };
const UECodeGen_Private::FPropertyParamsBase* const UHT_STATICS::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LocalTransform,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Shape_Underlying,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Shape,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Operation_Underlying,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Operation,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_SoftnessCm,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_bEnabled,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_GuideId,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::PropPointers) < 2048);
// ********** End ScriptStruct FCloudGuideRecipe Property Definitions ******************************
const UECodeGen_Private::FStructParams UHT_STATICS::StructParams = {
	(FTypeConstructFunc*)Z_Construct_UPackage__Script_CloudGeneratorTools,
	nullptr,
	&NewStructOps,
	"CloudGuideRecipe",
	UHT_STATICS::PropPointers,
	UE_ARRAY_COUNT(UHT_STATICS::PropPointers),
	DataSizeOf<FCloudGuideRecipe>(),
	alignof(FCloudGuideRecipe),
	RF_Public|RF_Transient|RF_MarkAsNative,
	EStructFlags(0x00000201),
	METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)
};
static FStructRegistrationInfo Z_Registration_Info_UScriptStruct_FCloudGuideRecipe;
UScriptStruct* Z_Construct_UScriptStruct_FCloudGuideRecipe(ETypeConstructPhase Phase)
{
	if (Phase == ETypeConstructPhase::Outer)
	{
		if (!Z_Registration_Info_UScriptStruct_FCloudGuideRecipe.OuterSingleton)
		{
			Z_Registration_Info_UScriptStruct_FCloudGuideRecipe.OuterSingleton = GetStaticStruct(Z_Construct_UScriptStruct_FCloudGuideRecipe, (UObject*)Z_Construct_UPackage__Script_CloudGeneratorTools(ETypeConstructPhase::Outer), TEXT("CloudGuideRecipe"));
		}
		return Z_Registration_Info_UScriptStruct_FCloudGuideRecipe.OuterSingleton;
	}
	if (!Z_Registration_Info_UScriptStruct_FCloudGuideRecipe.InnerSingleton)
	{
		UECodeGen_Private::ConstructUScriptStruct(Z_Registration_Info_UScriptStruct_FCloudGuideRecipe.InnerSingleton, UHT_STATICS::StructParams);
	}
	return CastChecked<UScriptStruct>(Z_Registration_Info_UScriptStruct_FCloudGuideRecipe.InnerSingleton);
}
#undef UHT_STATICS
// ********** End ScriptStruct FCloudGuideRecipe ***************************************************

// ********** Begin ScriptStruct FCloudRecipe ******************************************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UScriptStruct_FCloudRecipe_Statics
struct UHT_STATICS
{
	static inline consteval int32 GetStructSize() { return DataSizeOf<FCloudRecipe>(); }
	static inline consteval int16 GetStructAlignment() { return alignof(FCloudRecipe); }
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "BlueprintType", "true" },
		{ "Comment", "/** Deterministic editable recipe, independent of actor location and render quality. */" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Deterministic editable recipe, independent of actor location and render quality." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Version_MetaData[] = {
		{ "Category", "Cloud" },
		{ "Comment", "// Keep the struct default at 1: legacy serialized assets may omit this value.\n// CaptureRecipe explicitly creates version 2 recipes with authored generator scale.\n" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Keep the struct default at 1: legacy serialized assets may omit this value.\nCaptureRecipe explicitly creates version 2 recipes with authored generator scale." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_GeneratorScale_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Version 2 recipes restore this generator scale. Location and rotation stay where you place the cloud. Version 1 recipes keep the target actor's existing scale." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Guides_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Density_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Seed_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_CloudColor_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_SkyFill_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_BillowSizeCm_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_BillowDepthCm_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_BillowStrength_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_DetailSizeCm_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_DetailStrength_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_BillowStyle_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_CustomShapeNoiseTexture_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_CustomDetailNoiseTexture_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_ShapeNoiseLayout_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_DetailNoiseLayout_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_NoiseTiling_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_NoiseContrast_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_NoiseBrightness_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_NoiseTextureContrast_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LevelsInputLow_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LevelsInputMid_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LevelsInputHigh_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LevelsOutputLow_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LevelsOutputHigh_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_WarpAmount_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_bAnimated_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_OffsetSpeedX_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_OffsetSpeedY_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_OffsetSpeedZ_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_PhaseSpeed_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_TextureOffsetCm_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_NoisePhase_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LargeBreakupAmount_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LargeBreakupScaleX_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LargeBreakupScaleY_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LargeBreakupScaleZ_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LargeBreakupBrightness_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LargeBreakupContrast_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_UnionBlendCm_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_UnionGrowthLimitCm_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_CloudStyle_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_WispStrength_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_WispStretch_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_WispDirectionDegrees_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_InteriorVariation_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_VerticalDensityGradient_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_VerticalReferenceHeightCm_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_CloudMaterial_MetaData[] = {
		{ "Category", "Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
#endif // WITH_METADATA

// ********** Begin ScriptStruct FCloudRecipe constinit property declarations **********************
	static const UECodeGen_Private::FIntPropertyParams NewProp_Version;
	static const UECodeGen_Private::FStructPropertyParams NewProp_GeneratorScale;
	static const UECodeGen_Private::FStructPropertyParams NewProp_Guides_Inner;
	static const UECodeGen_Private::FArrayPropertyParams NewProp_Guides;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_Density;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_Seed;
	static const UECodeGen_Private::FStructPropertyParams NewProp_CloudColor;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_SkyFill;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_BillowSizeCm;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_BillowDepthCm;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_BillowStrength;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_DetailSizeCm;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_DetailStrength;
	static const UECodeGen_Private::FBytePropertyParams NewProp_BillowStyle_Underlying;
	static const UECodeGen_Private::FEnumPropertyParams NewProp_BillowStyle;
	static const UECodeGen_Private::FSoftObjectPropertyParams NewProp_CustomShapeNoiseTexture;
	static const UECodeGen_Private::FSoftObjectPropertyParams NewProp_CustomDetailNoiseTexture;
	static const UECodeGen_Private::FBytePropertyParams NewProp_ShapeNoiseLayout_Underlying;
	static const UECodeGen_Private::FEnumPropertyParams NewProp_ShapeNoiseLayout;
	static const UECodeGen_Private::FBytePropertyParams NewProp_DetailNoiseLayout_Underlying;
	static const UECodeGen_Private::FEnumPropertyParams NewProp_DetailNoiseLayout;
	static const UECodeGen_Private::FStructPropertyParams NewProp_NoiseTiling;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_NoiseContrast;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_NoiseBrightness;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_NoiseTextureContrast;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_LevelsInputLow;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_LevelsInputMid;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_LevelsInputHigh;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_LevelsOutputLow;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_LevelsOutputHigh;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_WarpAmount;
	static void NewProp_bAnimated_SetBit(void* Obj)
	{
		((FCloudRecipe*)Obj)->bAnimated = 1;
	}
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bAnimated;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_OffsetSpeedX;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_OffsetSpeedY;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_OffsetSpeedZ;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_PhaseSpeed;
	static const UECodeGen_Private::FStructPropertyParams NewProp_TextureOffsetCm;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_NoisePhase;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_LargeBreakupAmount;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_LargeBreakupScaleX;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_LargeBreakupScaleY;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_LargeBreakupScaleZ;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_LargeBreakupBrightness;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_LargeBreakupContrast;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_UnionBlendCm;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_UnionGrowthLimitCm;
	static const UECodeGen_Private::FBytePropertyParams NewProp_CloudStyle_Underlying;
	static const UECodeGen_Private::FEnumPropertyParams NewProp_CloudStyle;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_WispStrength;
	static const UECodeGen_Private::FStructPropertyParams NewProp_WispStretch;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_WispDirectionDegrees;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_InteriorVariation;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_VerticalDensityGradient;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_VerticalReferenceHeightCm;
	static const UECodeGen_Private::FSoftObjectPropertyParams NewProp_CloudMaterial;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
// ********** End ScriptStruct FCloudRecipe constinit property declarations ************************
	static void* NewStructOps()
	{
		return (UScriptStruct::ICppStructOps*)new UScriptStruct::TCppStructOps<FCloudRecipe>();
	}
	static const UECodeGen_Private::FStructParams StructParams;
}; // struct UHT_STATICS

// ********** Begin ScriptStruct FCloudRecipe Property Definitions *********************************
const UECodeGen_Private::FIntPropertyParams UHT_STATICS::NewProp_Version = { "Version", nullptr, (EPropertyFlags)0x0010000000020015, UECodeGen_Private::EPropertyGenFlags::Int, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, Version), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Version_MetaData), NewProp_Version_MetaData) };
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_GeneratorScale = { "GeneratorScale", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, GeneratorScale), Z_Construct_UScriptStruct_FVector, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_GeneratorScale_MetaData), NewProp_GeneratorScale_MetaData) };
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_Guides_Inner = { "Guides", nullptr, (EPropertyFlags)0x0000000000000000, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, 0, Z_Construct_UScriptStruct_FCloudGuideRecipe, METADATA_PARAMS(0, nullptr) }; // f97f8a0d47be9fa834ac59cc651602ce832a7d7d
const UECodeGen_Private::FArrayPropertyParams UHT_STATICS::NewProp_Guides = { "Guides", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Array, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, Guides), EArrayPropertyFlags::None, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Guides_MetaData), NewProp_Guides_MetaData) }; // f97f8a0d47be9fa834ac59cc651602ce832a7d7d
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_Density = { "Density", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, Density), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Density_MetaData), NewProp_Density_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_Seed = { "Seed", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, Seed), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Seed_MetaData), NewProp_Seed_MetaData) };
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_CloudColor = { "CloudColor", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, CloudColor), Z_Construct_UScriptStruct_FLinearColor, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_CloudColor_MetaData), NewProp_CloudColor_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_SkyFill = { "SkyFill", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, SkyFill), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_SkyFill_MetaData), NewProp_SkyFill_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_BillowSizeCm = { "BillowSizeCm", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, BillowSizeCm), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_BillowSizeCm_MetaData), NewProp_BillowSizeCm_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_BillowDepthCm = { "BillowDepthCm", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, BillowDepthCm), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_BillowDepthCm_MetaData), NewProp_BillowDepthCm_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_BillowStrength = { "BillowStrength", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, BillowStrength), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_BillowStrength_MetaData), NewProp_BillowStrength_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_DetailSizeCm = { "DetailSizeCm", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, DetailSizeCm), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_DetailSizeCm_MetaData), NewProp_DetailSizeCm_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_DetailStrength = { "DetailStrength", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, DetailStrength), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_DetailStrength_MetaData), NewProp_DetailStrength_MetaData) };
const UECodeGen_Private::FBytePropertyParams UHT_STATICS::NewProp_BillowStyle_Underlying = { "UnderlyingType", nullptr, (EPropertyFlags)0x0000000000000000, UECodeGen_Private::EPropertyGenFlags::Byte, nullptr, nullptr, 1, 0, nullptr, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FEnumPropertyParams UHT_STATICS::NewProp_BillowStyle = { "BillowStyle", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Enum, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, BillowStyle), Z_Construct_UEnum_CloudGeneratorTools_ECloudBillowStyle, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_BillowStyle_MetaData), NewProp_BillowStyle_MetaData) }; // fca5bcce7b2c07bbbece57424fa9d1487a2c5b2d
const UECodeGen_Private::FSoftObjectPropertyParams UHT_STATICS::NewProp_CustomShapeNoiseTexture = { "CustomShapeNoiseTexture", nullptr, (EPropertyFlags)0x0014000000000005, UECodeGen_Private::EPropertyGenFlags::SoftObject, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, CustomShapeNoiseTexture), Z_Construct_UClass_UVolumeTexture, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_CustomShapeNoiseTexture_MetaData), NewProp_CustomShapeNoiseTexture_MetaData) };
const UECodeGen_Private::FSoftObjectPropertyParams UHT_STATICS::NewProp_CustomDetailNoiseTexture = { "CustomDetailNoiseTexture", nullptr, (EPropertyFlags)0x0014000000000005, UECodeGen_Private::EPropertyGenFlags::SoftObject, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, CustomDetailNoiseTexture), Z_Construct_UClass_UVolumeTexture, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_CustomDetailNoiseTexture_MetaData), NewProp_CustomDetailNoiseTexture_MetaData) };
const UECodeGen_Private::FBytePropertyParams UHT_STATICS::NewProp_ShapeNoiseLayout_Underlying = { "UnderlyingType", nullptr, (EPropertyFlags)0x0000000000000000, UECodeGen_Private::EPropertyGenFlags::Byte, nullptr, nullptr, 1, 0, nullptr, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FEnumPropertyParams UHT_STATICS::NewProp_ShapeNoiseLayout = { "ShapeNoiseLayout", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Enum, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, ShapeNoiseLayout), Z_Construct_UEnum_CloudGeneratorTools_ECloudNoiseLayout, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_ShapeNoiseLayout_MetaData), NewProp_ShapeNoiseLayout_MetaData) }; // 0d4cd965bd2fedaaa6345e6a20296a243542bc54
const UECodeGen_Private::FBytePropertyParams UHT_STATICS::NewProp_DetailNoiseLayout_Underlying = { "UnderlyingType", nullptr, (EPropertyFlags)0x0000000000000000, UECodeGen_Private::EPropertyGenFlags::Byte, nullptr, nullptr, 1, 0, nullptr, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FEnumPropertyParams UHT_STATICS::NewProp_DetailNoiseLayout = { "DetailNoiseLayout", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Enum, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, DetailNoiseLayout), Z_Construct_UEnum_CloudGeneratorTools_ECloudNoiseLayout, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_DetailNoiseLayout_MetaData), NewProp_DetailNoiseLayout_MetaData) }; // 0d4cd965bd2fedaaa6345e6a20296a243542bc54
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_NoiseTiling = { "NoiseTiling", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, NoiseTiling), Z_Construct_UScriptStruct_FVector, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_NoiseTiling_MetaData), NewProp_NoiseTiling_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_NoiseContrast = { "NoiseContrast", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, NoiseContrast), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_NoiseContrast_MetaData), NewProp_NoiseContrast_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_NoiseBrightness = { "NoiseBrightness", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, NoiseBrightness), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_NoiseBrightness_MetaData), NewProp_NoiseBrightness_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_NoiseTextureContrast = { "NoiseTextureContrast", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, NoiseTextureContrast), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_NoiseTextureContrast_MetaData), NewProp_NoiseTextureContrast_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_LevelsInputLow = { "LevelsInputLow", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, LevelsInputLow), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LevelsInputLow_MetaData), NewProp_LevelsInputLow_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_LevelsInputMid = { "LevelsInputMid", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, LevelsInputMid), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LevelsInputMid_MetaData), NewProp_LevelsInputMid_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_LevelsInputHigh = { "LevelsInputHigh", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, LevelsInputHigh), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LevelsInputHigh_MetaData), NewProp_LevelsInputHigh_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_LevelsOutputLow = { "LevelsOutputLow", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, LevelsOutputLow), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LevelsOutputLow_MetaData), NewProp_LevelsOutputLow_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_LevelsOutputHigh = { "LevelsOutputHigh", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, LevelsOutputHigh), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LevelsOutputHigh_MetaData), NewProp_LevelsOutputHigh_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_WarpAmount = { "WarpAmount", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, WarpAmount), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_WarpAmount_MetaData), NewProp_WarpAmount_MetaData) };
const UECodeGen_Private::FBoolPropertyParams UHT_STATICS::NewProp_bAnimated = { "bAnimated", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, nullptr, nullptr, 1, sizeof(bool), sizeof(FCloudRecipe), &UHT_STATICS::NewProp_bAnimated_SetBit, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_bAnimated_MetaData), NewProp_bAnimated_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_OffsetSpeedX = { "OffsetSpeedX", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, OffsetSpeedX), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_OffsetSpeedX_MetaData), NewProp_OffsetSpeedX_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_OffsetSpeedY = { "OffsetSpeedY", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, OffsetSpeedY), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_OffsetSpeedY_MetaData), NewProp_OffsetSpeedY_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_OffsetSpeedZ = { "OffsetSpeedZ", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, OffsetSpeedZ), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_OffsetSpeedZ_MetaData), NewProp_OffsetSpeedZ_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_PhaseSpeed = { "PhaseSpeed", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, PhaseSpeed), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_PhaseSpeed_MetaData), NewProp_PhaseSpeed_MetaData) };
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_TextureOffsetCm = { "TextureOffsetCm", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, TextureOffsetCm), Z_Construct_UScriptStruct_FVector, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_TextureOffsetCm_MetaData), NewProp_TextureOffsetCm_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_NoisePhase = { "NoisePhase", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, NoisePhase), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_NoisePhase_MetaData), NewProp_NoisePhase_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_LargeBreakupAmount = { "LargeBreakupAmount", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, LargeBreakupAmount), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LargeBreakupAmount_MetaData), NewProp_LargeBreakupAmount_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_LargeBreakupScaleX = { "LargeBreakupScaleX", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, LargeBreakupScaleX), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LargeBreakupScaleX_MetaData), NewProp_LargeBreakupScaleX_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_LargeBreakupScaleY = { "LargeBreakupScaleY", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, LargeBreakupScaleY), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LargeBreakupScaleY_MetaData), NewProp_LargeBreakupScaleY_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_LargeBreakupScaleZ = { "LargeBreakupScaleZ", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, LargeBreakupScaleZ), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LargeBreakupScaleZ_MetaData), NewProp_LargeBreakupScaleZ_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_LargeBreakupBrightness = { "LargeBreakupBrightness", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, LargeBreakupBrightness), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LargeBreakupBrightness_MetaData), NewProp_LargeBreakupBrightness_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_LargeBreakupContrast = { "LargeBreakupContrast", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, LargeBreakupContrast), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LargeBreakupContrast_MetaData), NewProp_LargeBreakupContrast_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_UnionBlendCm = { "UnionBlendCm", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, UnionBlendCm), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_UnionBlendCm_MetaData), NewProp_UnionBlendCm_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_UnionGrowthLimitCm = { "UnionGrowthLimitCm", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, UnionGrowthLimitCm), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_UnionGrowthLimitCm_MetaData), NewProp_UnionGrowthLimitCm_MetaData) };
const UECodeGen_Private::FBytePropertyParams UHT_STATICS::NewProp_CloudStyle_Underlying = { "UnderlyingType", nullptr, (EPropertyFlags)0x0000000000000000, UECodeGen_Private::EPropertyGenFlags::Byte, nullptr, nullptr, 1, 0, nullptr, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FEnumPropertyParams UHT_STATICS::NewProp_CloudStyle = { "CloudStyle", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Enum, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, CloudStyle), Z_Construct_UEnum_CloudGeneratorTools_ECloudStyle, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_CloudStyle_MetaData), NewProp_CloudStyle_MetaData) }; // 38df397519e8039a981a5369f52fb9e26d032611
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_WispStrength = { "WispStrength", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, WispStrength), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_WispStrength_MetaData), NewProp_WispStrength_MetaData) };
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_WispStretch = { "WispStretch", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, WispStretch), Z_Construct_UScriptStruct_FVector, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_WispStretch_MetaData), NewProp_WispStretch_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_WispDirectionDegrees = { "WispDirectionDegrees", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, WispDirectionDegrees), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_WispDirectionDegrees_MetaData), NewProp_WispDirectionDegrees_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_InteriorVariation = { "InteriorVariation", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, InteriorVariation), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_InteriorVariation_MetaData), NewProp_InteriorVariation_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_VerticalDensityGradient = { "VerticalDensityGradient", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, VerticalDensityGradient), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_VerticalDensityGradient_MetaData), NewProp_VerticalDensityGradient_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_VerticalReferenceHeightCm = { "VerticalReferenceHeightCm", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, VerticalReferenceHeightCm), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_VerticalReferenceHeightCm_MetaData), NewProp_VerticalReferenceHeightCm_MetaData) };
const UECodeGen_Private::FSoftObjectPropertyParams UHT_STATICS::NewProp_CloudMaterial = { "CloudMaterial", nullptr, (EPropertyFlags)0x0014000000000005, UECodeGen_Private::EPropertyGenFlags::SoftObject, nullptr, nullptr, 1, STRUCT_OFFSET(FCloudRecipe, CloudMaterial), Z_Construct_UClass_UMaterialInterface, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_CloudMaterial_MetaData), NewProp_CloudMaterial_MetaData) };
const UECodeGen_Private::FPropertyParamsBase* const UHT_STATICS::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Version,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_GeneratorScale,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Guides_Inner,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Guides,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Density,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Seed,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_CloudColor,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_SkyFill,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_BillowSizeCm,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_BillowDepthCm,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_BillowStrength,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_DetailSizeCm,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_DetailStrength,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_BillowStyle_Underlying,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_BillowStyle,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_CustomShapeNoiseTexture,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_CustomDetailNoiseTexture,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ShapeNoiseLayout_Underlying,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ShapeNoiseLayout,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_DetailNoiseLayout_Underlying,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_DetailNoiseLayout,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_NoiseTiling,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_NoiseContrast,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_NoiseBrightness,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_NoiseTextureContrast,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LevelsInputLow,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LevelsInputMid,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LevelsInputHigh,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LevelsOutputLow,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LevelsOutputHigh,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_WarpAmount,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_bAnimated,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_OffsetSpeedX,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_OffsetSpeedY,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_OffsetSpeedZ,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_PhaseSpeed,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_TextureOffsetCm,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_NoisePhase,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LargeBreakupAmount,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LargeBreakupScaleX,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LargeBreakupScaleY,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LargeBreakupScaleZ,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LargeBreakupBrightness,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LargeBreakupContrast,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_UnionBlendCm,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_UnionGrowthLimitCm,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_CloudStyle_Underlying,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_CloudStyle,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_WispStrength,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_WispStretch,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_WispDirectionDegrees,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_InteriorVariation,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_VerticalDensityGradient,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_VerticalReferenceHeightCm,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_CloudMaterial,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::PropPointers) < 2048);
// ********** End ScriptStruct FCloudRecipe Property Definitions ***********************************
const UECodeGen_Private::FStructParams UHT_STATICS::StructParams = {
	(FTypeConstructFunc*)Z_Construct_UPackage__Script_CloudGeneratorTools,
	nullptr,
	&NewStructOps,
	"CloudRecipe",
	UHT_STATICS::PropPointers,
	UE_ARRAY_COUNT(UHT_STATICS::PropPointers),
	DataSizeOf<FCloudRecipe>(),
	alignof(FCloudRecipe),
	RF_Public|RF_Transient|RF_MarkAsNative,
	EStructFlags(0x00000201),
	METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)
};
static FStructRegistrationInfo Z_Registration_Info_UScriptStruct_FCloudRecipe;
UScriptStruct* Z_Construct_UScriptStruct_FCloudRecipe(ETypeConstructPhase Phase)
{
	if (Phase == ETypeConstructPhase::Outer)
	{
		if (!Z_Registration_Info_UScriptStruct_FCloudRecipe.OuterSingleton)
		{
			Z_Registration_Info_UScriptStruct_FCloudRecipe.OuterSingleton = GetStaticStruct(Z_Construct_UScriptStruct_FCloudRecipe, (UObject*)Z_Construct_UPackage__Script_CloudGeneratorTools(ETypeConstructPhase::Outer), TEXT("CloudRecipe"));
		}
		return Z_Registration_Info_UScriptStruct_FCloudRecipe.OuterSingleton;
	}
	if (!Z_Registration_Info_UScriptStruct_FCloudRecipe.InnerSingleton)
	{
		UECodeGen_Private::ConstructUScriptStruct(Z_Registration_Info_UScriptStruct_FCloudRecipe.InnerSingleton, UHT_STATICS::StructParams);
	}
	return CastChecked<UScriptStruct>(Z_Registration_Info_UScriptStruct_FCloudRecipe.InnerSingleton);
}
#undef UHT_STATICS
// ********** End ScriptStruct FCloudRecipe ********************************************************

// ********** Begin Class UCloudRecipePreset *******************************************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UClass_UCloudRecipePreset_Statics
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "BlueprintType", "true" },
		{ "Comment", "/** A saved cloud recipe; it remains editable and is not a baked volume texture. */" },
		{ "IncludePath", "CloudGeneratorActor.h" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "A saved cloud recipe; it remains editable and is not a baked volume texture." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Recipe_MetaData[] = {
		{ "Category", "Cloud Preset" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Description_MetaData[] = {
		{ "Category", "Cloud Preset" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "MultiLine", "true" },
	};
#endif // WITH_METADATA

// ********** Begin Class UCloudRecipePreset constinit property declarations ***********************
	static const UECodeGen_Private::FStructPropertyParams NewProp_Recipe;
	static const UECodeGen_Private::FStrPropertyParams NewProp_Description;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
// ********** End Class UCloudRecipePreset constinit property declarations *************************
	static FTypeConstructFunc* DependentSingletons[];
	static constexpr FCppClassTypeInfoStatic StaticCppClassTypeInfo = {
		TCppClassTypeTraits<UCloudRecipePreset>::IsAbstract,
	};
	static const UECodeGen_Private::FClassParams ClassParams;
}; // struct UHT_STATICS

// ********** Begin Class UCloudRecipePreset Property Definitions **********************************
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_Recipe = { "Recipe", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, STRUCT_OFFSET(UCloudRecipePreset, Recipe), Z_Construct_UScriptStruct_FCloudRecipe, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Recipe_MetaData), NewProp_Recipe_MetaData) }; // 24454c819ca86f61eca43e191606be15fa6d8b92
const UECodeGen_Private::FStrPropertyParams UHT_STATICS::NewProp_Description = { "Description", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Str, nullptr, nullptr, 1, STRUCT_OFFSET(UCloudRecipePreset, Description), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Description_MetaData), NewProp_Description_MetaData) };
const UECodeGen_Private::FPropertyParamsBase* const UHT_STATICS::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Recipe,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Description,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::PropPointers) < 2048);
// ********** End Class UCloudRecipePreset Property Definitions ************************************
FTypeConstructFunc* UHT_STATICS::DependentSingletons[] = {
	(FTypeConstructFunc*)Z_Construct_UClass_UDataAsset,
	(FTypeConstructFunc*)Z_Construct_UPackage__Script_CloudGeneratorTools,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::DependentSingletons) < 16);
const UECodeGen_Private::FClassParams UHT_STATICS::ClassParams = {
	&Z_Construct_UClass_UCloudRecipePreset,
	nullptr,
	&StaticCppClassTypeInfo,
	DependentSingletons,
	nullptr,
	UHT_STATICS::PropPointers,
	nullptr,
	UE_ARRAY_COUNT(DependentSingletons),
	0,
	UE_ARRAY_COUNT(UHT_STATICS::PropPointers),
	0,
	0x001000A0u,
	METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)
};
FClassRegistrationInfo Z_Registration_Info_UClass_UCloudRecipePreset;
UClass* Z_Construct_UClass_UCloudRecipePreset(ETypeConstructPhase Phase)
{
	if (Phase == ETypeConstructPhase::Inner)
	{
		using TClass = UCloudRecipePreset;
		if (!Z_Registration_Info_UClass_UCloudRecipePreset.InnerSingleton)
		{
			GetPrivateStaticClassBody(
				TClass::StaticPackage(),
				TEXT("CloudRecipePreset"),
				Z_Registration_Info_UClass_UCloudRecipePreset.InnerSingleton,
				nullptr,
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
		return Z_Registration_Info_UClass_UCloudRecipePreset.InnerSingleton;
	}
	if (!Z_Registration_Info_UClass_UCloudRecipePreset.OuterSingleton)
	{
		UECodeGen_Private::ConstructUClass(Z_Registration_Info_UClass_UCloudRecipePreset.OuterSingleton, UHT_STATICS::ClassParams);
	}
	return Z_Registration_Info_UClass_UCloudRecipePreset.OuterSingleton;
}
#undef UHT_STATICS
UCloudRecipePreset::UCloudRecipePreset(const FObjectInitializer& ObjectInitializer) : Super(ObjectInitializer) {}
DEFINE_VTABLE_PTR_HELPER_CTOR_NS(, UCloudRecipePreset);
UCloudRecipePreset::~UCloudRecipePreset() {}
// ********** End Class UCloudRecipePreset *********************************************************

// ********** Begin Class UCloudGuideShapeComponent ************************************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UClass_UCloudGuideShapeComponent_Statics
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "BlueprintSpawnableComponent", "" },
		{ "ClassGroupNames", "Rendering" },
		{ "Comment", "/** An editor wire outline; the actual shape is evaluated in the cloud material. */" },
		{ "HideCategories", "Mobility VirtualTexture Trigger" },
		{ "IncludePath", "CloudGeneratorActor.h" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "An editor wire outline; the actual shape is evaluated in the cloud material." },
	};
#endif // WITH_METADATA

// ********** Begin Class UCloudGuideShapeComponent constinit property declarations ****************
// ********** End Class UCloudGuideShapeComponent constinit property declarations ******************
	static FTypeConstructFunc* DependentSingletons[];
	static constexpr FCppClassTypeInfoStatic StaticCppClassTypeInfo = {
		TCppClassTypeTraits<UCloudGuideShapeComponent>::IsAbstract,
	};
	static const UECodeGen_Private::FClassParams ClassParams;
}; // struct UHT_STATICS
FTypeConstructFunc* UHT_STATICS::DependentSingletons[] = {
	(FTypeConstructFunc*)Z_Construct_UClass_UPrimitiveComponent,
	(FTypeConstructFunc*)Z_Construct_UPackage__Script_CloudGeneratorTools,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::DependentSingletons) < 16);
const UECodeGen_Private::FClassParams UHT_STATICS::ClassParams = {
	&Z_Construct_UClass_UCloudGuideShapeComponent,
	"Engine",
	&StaticCppClassTypeInfo,
	DependentSingletons,
	nullptr,
	nullptr,
	nullptr,
	UE_ARRAY_COUNT(DependentSingletons),
	0,
	0,
	0,
	0x00B000A4u,
	METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)
};
FClassRegistrationInfo Z_Registration_Info_UClass_UCloudGuideShapeComponent;
UClass* Z_Construct_UClass_UCloudGuideShapeComponent(ETypeConstructPhase Phase)
{
	if (Phase == ETypeConstructPhase::Inner)
	{
		using TClass = UCloudGuideShapeComponent;
		if (!Z_Registration_Info_UClass_UCloudGuideShapeComponent.InnerSingleton)
		{
			GetPrivateStaticClassBody(
				TClass::StaticPackage(),
				TEXT("CloudGuideShapeComponent"),
				Z_Registration_Info_UClass_UCloudGuideShapeComponent.InnerSingleton,
				nullptr,
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
		return Z_Registration_Info_UClass_UCloudGuideShapeComponent.InnerSingleton;
	}
	if (!Z_Registration_Info_UClass_UCloudGuideShapeComponent.OuterSingleton)
	{
		UECodeGen_Private::ConstructUClass(Z_Registration_Info_UClass_UCloudGuideShapeComponent.OuterSingleton, UHT_STATICS::ClassParams);
	}
	return Z_Registration_Info_UClass_UCloudGuideShapeComponent.OuterSingleton;
}
#undef UHT_STATICS
DEFINE_VTABLE_PTR_HELPER_CTOR_NS(, UCloudGuideShapeComponent);
UCloudGuideShapeComponent::~UCloudGuideShapeComponent() {}
// ********** End Class UCloudGuideShapeComponent **************************************************

// ********** Begin Class ACloudGuideActor Function NotifyGenerator ********************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_ACloudGuideActor_NotifyGenerator_Statics
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "Category", "Cloud Guide" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
#endif // WITH_METADATA

// ********** Begin Function NotifyGenerator constinit property declarations ***********************
// ********** End Function NotifyGenerator constinit property declarations *************************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_ACloudGuideActor, nullptr, "NotifyGenerator", nullptr, 0, 0, RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04020401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
UFunction* Z_Construct_UFunction_ACloudGuideActor_NotifyGenerator(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(ACloudGuideActor::execNotifyGenerator)
{
	P_FINISH;
	P_NATIVE_BEGIN;
	P_THIS->NotifyGenerator();
	P_NATIVE_END;
}
// ********** End Class ACloudGuideActor Function NotifyGenerator **********************************

// ********** Begin Class ACloudGuideActor *********************************************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UClass_ACloudGuideActor_Statics
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "BlueprintType", "true" },
		{ "Comment", "/** Runtime-present authoring guide. Nonuniform sphere scale produces an ellipsoid. */" },
		{ "HideCategories", "Replication Networking Input Collision HLOD Physics" },
		{ "IncludePath", "CloudGeneratorActor.h" },
		{ "IsBlueprintBase", "true" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Runtime-present authoring guide. Nonuniform sphere scale produces an ellipsoid." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_GuideShape_MetaData[] = {
		{ "Category", "Cloud Guide" },
		{ "EditInline", "true" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Shape_MetaData[] = {
		{ "Category", "Cloud Guide" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Operation_MetaData[] = {
		{ "Category", "Cloud Guide" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_SoftnessCm_MetaData[] = {
		{ "Category", "Cloud Guide" },
		{ "ClampMin", "0" },
		{ "DisplayName", "Edge Softness" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "UIMax", "200" },
		{ "UIMin", "0" },
		{ "Units", "cm" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_bEnabled_MetaData[] = {
		{ "Category", "Cloud Guide" },
		{ "DisplayName", "Enabled" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Generator_MetaData[] = {
		{ "Category", "Cloud Guide" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_GuideId_MetaData[] = {
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
#endif // WITH_METADATA

// ********** Begin Class ACloudGuideActor constinit property declarations *************************
	static const UECodeGen_Private::FObjectPropertyParams NewProp_GuideShape;
	static const UECodeGen_Private::FBytePropertyParams NewProp_Shape_Underlying;
	static const UECodeGen_Private::FEnumPropertyParams NewProp_Shape;
	static const UECodeGen_Private::FBytePropertyParams NewProp_Operation_Underlying;
	static const UECodeGen_Private::FEnumPropertyParams NewProp_Operation;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_SoftnessCm;
	static void NewProp_bEnabled_SetBit(void* Obj)
	{
		((ACloudGuideActor*)Obj)->bEnabled = 1;
	}
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bEnabled;
	static const UECodeGen_Private::FObjectPropertyParams NewProp_Generator;
	static const UECodeGen_Private::FStructPropertyParams NewProp_GuideId;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
// ********** End Class ACloudGuideActor constinit property declarations ***************************
	static constexpr UE::CodeGen::FClassNativeFunction Funcs[] = {
		{ .NameUTF8 = UTF8TEXT("NotifyGenerator"), .Pointer = &ACloudGuideActor::execNotifyGenerator },
	};
	static FTypeConstructFunc* DependentSingletons[];
	static constexpr FClassFunctionLinkInfo FuncInfo[] = {
		{ &Z_Construct_UFunction_ACloudGuideActor_NotifyGenerator, "NotifyGenerator" }, // 06c6188c756b0a60ce188eab5ebcfd1c058efd84
	};
	static_assert(UE_ARRAY_COUNT(FuncInfo) < 2048);
	static constexpr FCppClassTypeInfoStatic StaticCppClassTypeInfo = {
		TCppClassTypeTraits<ACloudGuideActor>::IsAbstract,
	};
	static const UECodeGen_Private::FClassParams ClassParams;
}; // struct UHT_STATICS

// ********** Begin Class ACloudGuideActor Property Definitions ************************************
const UECodeGen_Private::FObjectPropertyParams UHT_STATICS::NewProp_GuideShape = { "GuideShape", nullptr, (EPropertyFlags)0x01140000000a001d, UECodeGen_Private::EPropertyGenFlags::Object | UECodeGen_Private::EPropertyGenFlags::ObjectPtr, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGuideActor, GuideShape), Z_Construct_UClass_UCloudGuideShapeComponent, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_GuideShape_MetaData), NewProp_GuideShape_MetaData) };
const UECodeGen_Private::FBytePropertyParams UHT_STATICS::NewProp_Shape_Underlying = { "UnderlyingType", nullptr, (EPropertyFlags)0x0000000000000000, UECodeGen_Private::EPropertyGenFlags::Byte, nullptr, nullptr, 1, 0, nullptr, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FEnumPropertyParams UHT_STATICS::NewProp_Shape = { "Shape", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Enum, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGuideActor, Shape), Z_Construct_UEnum_CloudGeneratorTools_ECloudGuideShape, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Shape_MetaData), NewProp_Shape_MetaData) }; // 6d71168086afd1364f37306fe0b7b4945e7177fa
const UECodeGen_Private::FBytePropertyParams UHT_STATICS::NewProp_Operation_Underlying = { "UnderlyingType", nullptr, (EPropertyFlags)0x0000000000000000, UECodeGen_Private::EPropertyGenFlags::Byte, nullptr, nullptr, 1, 0, nullptr, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FEnumPropertyParams UHT_STATICS::NewProp_Operation = { "Operation", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Enum, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGuideActor, Operation), Z_Construct_UEnum_CloudGeneratorTools_ECloudGuideOperation, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Operation_MetaData), NewProp_Operation_MetaData) }; // 8a45f973b54fed74d1a9e7d7bf389916af6abf41
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_SoftnessCm = { "SoftnessCm", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGuideActor, SoftnessCm), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_SoftnessCm_MetaData), NewProp_SoftnessCm_MetaData) };
const UECodeGen_Private::FBoolPropertyParams UHT_STATICS::NewProp_bEnabled = { "bEnabled", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, nullptr, nullptr, 1, sizeof(bool), sizeof(ACloudGuideActor), &UHT_STATICS::NewProp_bEnabled_SetBit, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_bEnabled_MetaData), NewProp_bEnabled_MetaData) };
const UECodeGen_Private::FObjectPropertyParams UHT_STATICS::NewProp_Generator = { "Generator", nullptr, (EPropertyFlags)0x0114000000000805, UECodeGen_Private::EPropertyGenFlags::Object | UECodeGen_Private::EPropertyGenFlags::ObjectPtr, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGuideActor, Generator), Z_Construct_UClass_ACloudGeneratorActor, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Generator_MetaData), NewProp_Generator_MetaData) };
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_GuideId = { "GuideId", nullptr, (EPropertyFlags)0x0010000000000000, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGuideActor, GuideId), Z_Construct_UScriptStruct_FGuid, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_GuideId_MetaData), NewProp_GuideId_MetaData) };
const UECodeGen_Private::FPropertyParamsBase* const UHT_STATICS::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_GuideShape,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Shape_Underlying,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Shape,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Operation_Underlying,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Operation,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_SoftnessCm,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_bEnabled,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Generator,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_GuideId,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::PropPointers) < 2048);
// ********** End Class ACloudGuideActor Property Definitions **************************************
FTypeConstructFunc* UHT_STATICS::DependentSingletons[] = {
	(FTypeConstructFunc*)Z_Construct_UClass_AActor,
	(FTypeConstructFunc*)Z_Construct_UPackage__Script_CloudGeneratorTools,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::DependentSingletons) < 16);
const UECodeGen_Private::FClassParams UHT_STATICS::ClassParams = {
	&Z_Construct_UClass_ACloudGuideActor,
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
static void ACloudGuideActor_StaticRegisterNativesACloudGuideActor()
{
	UClass* Class = ACloudGuideActor::StaticClass();
	FNativeFunctionRegistrar::RegisterFunctions(Class, 		MakeConstArrayView(UHT_STATICS::Funcs));
}
FClassRegistrationInfo Z_Registration_Info_UClass_ACloudGuideActor;
UClass* Z_Construct_UClass_ACloudGuideActor(ETypeConstructPhase Phase)
{
	if (Phase == ETypeConstructPhase::Inner)
	{
		using TClass = ACloudGuideActor;
		if (!Z_Registration_Info_UClass_ACloudGuideActor.InnerSingleton)
		{
			GetPrivateStaticClassBody(
				TClass::StaticPackage(),
				TEXT("CloudGuideActor"),
				Z_Registration_Info_UClass_ACloudGuideActor.InnerSingleton,
				ACloudGuideActor_StaticRegisterNativesACloudGuideActor,
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
		return Z_Registration_Info_UClass_ACloudGuideActor.InnerSingleton;
	}
	if (!Z_Registration_Info_UClass_ACloudGuideActor.OuterSingleton)
	{
		UECodeGen_Private::ConstructUClass(Z_Registration_Info_UClass_ACloudGuideActor.OuterSingleton, UHT_STATICS::ClassParams);
	}
	return Z_Registration_Info_UClass_ACloudGuideActor.OuterSingleton;
}
#undef UHT_STATICS
DEFINE_VTABLE_PTR_HELPER_CTOR_NS(, ACloudGuideActor);
ACloudGuideActor::~ACloudGuideActor() {}
// ********** End Class ACloudGuideActor ***********************************************************

// ********** Begin Class ACloudGeneratorActor Function AddGuide ***********************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_ACloudGeneratorActor_AddGuide_Statics
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "CallInEditor", "true" },
		{ "Category", "Cloud Guides" },
		{ "DisplayName", "+ Add Guide" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
#endif // WITH_METADATA

// ********** Begin Function AddGuide constinit property declarations ******************************
// ********** End Function AddGuide constinit property declarations ********************************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_ACloudGeneratorActor, nullptr, "AddGuide", nullptr, 0, 0, RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04020401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
UFunction* Z_Construct_UFunction_ACloudGeneratorActor_AddGuide(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(ACloudGeneratorActor::execAddGuide)
{
	P_FINISH;
	P_NATIVE_BEGIN;
	P_THIS->AddGuide();
	P_NATIVE_END;
}
// ********** End Class ACloudGeneratorActor Function AddGuide *************************************

// ********** Begin Class ACloudGeneratorActor Function ApplyRecipe ********************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_ACloudGeneratorActor_ApplyRecipe_Statics
struct UHT_STATICS
{
	struct CloudGeneratorActor_eventApplyRecipe_Parms
	{
		FCloudRecipe Recipe;
		bool ReturnValue;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "Category", "Cloud Generator|Recipe" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Recipe_MetaData[] = {
		{ "NativeConst", "" },
	};
#endif // WITH_METADATA

// ********** Begin Function ApplyRecipe constinit property declarations ***************************
	static const UECodeGen_Private::FStructPropertyParams NewProp_Recipe;
	static void NewProp_ReturnValue_SetBit(void* Obj)
	{
		((CloudGeneratorActor_eventApplyRecipe_Parms*)Obj)->ReturnValue = 1;
	}
	static const UECodeGen_Private::FBoolPropertyParams NewProp_ReturnValue;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
// ********** End Function ApplyRecipe constinit property declarations *****************************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};

// ********** Begin Function ApplyRecipe Property Definitions **************************************
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_Recipe = { "Recipe", nullptr, (EPropertyFlags)0x0010000008000182, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, STRUCT_OFFSET(CloudGeneratorActor_eventApplyRecipe_Parms, Recipe), Z_Construct_UScriptStruct_FCloudRecipe, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Recipe_MetaData), NewProp_Recipe_MetaData) }; // 24454c819ca86f61eca43e191606be15fa6d8b92
const UECodeGen_Private::FBoolPropertyParams UHT_STATICS::NewProp_ReturnValue = { "ReturnValue", nullptr, (EPropertyFlags)0x0010000000000580, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, nullptr, nullptr, 1, sizeof(bool), sizeof(CloudGeneratorActor_eventApplyRecipe_Parms), &UHT_STATICS::NewProp_ReturnValue_SetBit, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FPropertyParamsBase* const UHT_STATICS::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Recipe,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ReturnValue,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::PropPointers) < 2048);
// ********** End Function ApplyRecipe Property Definitions ****************************************
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_ACloudGeneratorActor, nullptr, "ApplyRecipe", UHT_STATICS::PropPointers, UE_ARRAY_COUNT(UHT_STATICS::PropPointers), DataSizeOf<UHT_STATICS::CloudGeneratorActor_eventApplyRecipe_Parms>(), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04420401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
static_assert(sizeof(UHT_STATICS::CloudGeneratorActor_eventApplyRecipe_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_ACloudGeneratorActor_ApplyRecipe(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(ACloudGeneratorActor::execApplyRecipe)
{
	P_GET_STRUCT_REF(FCloudRecipe,Z_Param_Out_Recipe);
	P_FINISH;
	P_NATIVE_BEGIN;
	*(bool*)Z_Param__Result=P_THIS->ApplyRecipe(Z_Param_Out_Recipe);
	P_NATIVE_END;
}
// ********** End Class ACloudGeneratorActor Function ApplyRecipe **********************************

// ********** Begin Class ACloudGeneratorActor Function CaptureRecipe ******************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_ACloudGeneratorActor_CaptureRecipe_Statics
struct UHT_STATICS
{
	struct CloudGeneratorActor_eventCaptureRecipe_Parms
	{
		FCloudRecipe ReturnValue;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "Category", "Cloud Generator|Recipe" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
#endif // WITH_METADATA

// ********** Begin Function CaptureRecipe constinit property declarations *************************
	static const UECodeGen_Private::FStructPropertyParams NewProp_ReturnValue;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
// ********** End Function CaptureRecipe constinit property declarations ***************************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};

// ********** Begin Function CaptureRecipe Property Definitions ************************************
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_ReturnValue = { "ReturnValue", nullptr, (EPropertyFlags)0x0010000000000580, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, STRUCT_OFFSET(CloudGeneratorActor_eventCaptureRecipe_Parms, ReturnValue), Z_Construct_UScriptStruct_FCloudRecipe, METADATA_PARAMS(0, nullptr) }; // 24454c819ca86f61eca43e191606be15fa6d8b92
const UECodeGen_Private::FPropertyParamsBase* const UHT_STATICS::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ReturnValue,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::PropPointers) < 2048);
// ********** End Function CaptureRecipe Property Definitions **************************************
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_ACloudGeneratorActor, nullptr, "CaptureRecipe", UHT_STATICS::PropPointers, UE_ARRAY_COUNT(UHT_STATICS::PropPointers), DataSizeOf<UHT_STATICS::CloudGeneratorActor_eventCaptureRecipe_Parms>(), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x54020401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
static_assert(sizeof(UHT_STATICS::CloudGeneratorActor_eventCaptureRecipe_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_ACloudGeneratorActor_CaptureRecipe(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(ACloudGeneratorActor::execCaptureRecipe)
{
	P_FINISH;
	P_NATIVE_BEGIN;
	*(FCloudRecipe*)Z_Param__Result=P_THIS->CaptureRecipe();
	P_NATIVE_END;
}
// ********** End Class ACloudGeneratorActor Function CaptureRecipe ********************************

// ********** Begin Class ACloudGeneratorActor Function GenerateVariation **************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_ACloudGeneratorActor_GenerateVariation_Statics
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "CallInEditor", "true" },
		{ "Category", "Cloud Presets" },
		{ "DisplayName", "Generate Variation" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
#endif // WITH_METADATA

// ********** Begin Function GenerateVariation constinit property declarations *********************
// ********** End Function GenerateVariation constinit property declarations ***********************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_ACloudGeneratorActor, nullptr, "GenerateVariation", nullptr, 0, 0, RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04020401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
UFunction* Z_Construct_UFunction_ACloudGeneratorActor_GenerateVariation(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(ACloudGeneratorActor::execGenerateVariation)
{
	P_FINISH;
	P_NATIVE_BEGIN;
	P_THIS->GenerateVariation();
	P_NATIVE_END;
}
// ********** End Class ACloudGeneratorActor Function GenerateVariation ****************************

// ********** Begin Class ACloudGeneratorActor Function GetEncodedGuideData ************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_ACloudGeneratorActor_GetEncodedGuideData_Statics
struct UHT_STATICS
{
	struct CloudGeneratorActor_eventGetEncodedGuideData_Parms
	{
		TArray<FLinearColor> ReturnValue;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "Category", "Cloud Generator|Inspection" },
		{ "Comment", "/** A copy of the 3-by-64 texels, row-major, for inspection and automation. */" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "A copy of the 3-by-64 texels, row-major, for inspection and automation." },
	};
#endif // WITH_METADATA

// ********** Begin Function GetEncodedGuideData constinit property declarations *******************
	static const UECodeGen_Private::FStructPropertyParams NewProp_ReturnValue_Inner;
	static const UECodeGen_Private::FArrayPropertyParams NewProp_ReturnValue;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
// ********** End Function GetEncodedGuideData constinit property declarations *********************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};

// ********** Begin Function GetEncodedGuideData Property Definitions ******************************
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_ReturnValue_Inner = { "ReturnValue", nullptr, (EPropertyFlags)0x0000000000000000, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, 0, Z_Construct_UScriptStruct_FLinearColor, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FArrayPropertyParams UHT_STATICS::NewProp_ReturnValue = { "ReturnValue", nullptr, (EPropertyFlags)0x0010000000000580, UECodeGen_Private::EPropertyGenFlags::Array, nullptr, nullptr, 1, STRUCT_OFFSET(CloudGeneratorActor_eventGetEncodedGuideData_Parms, ReturnValue), EArrayPropertyFlags::None, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FPropertyParamsBase* const UHT_STATICS::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ReturnValue_Inner,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ReturnValue,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::PropPointers) < 2048);
// ********** End Function GetEncodedGuideData Property Definitions ********************************
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_ACloudGeneratorActor, nullptr, "GetEncodedGuideData", UHT_STATICS::PropPointers, UE_ARRAY_COUNT(UHT_STATICS::PropPointers), DataSizeOf<UHT_STATICS::CloudGeneratorActor_eventGetEncodedGuideData_Parms>(), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x54020401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
static_assert(sizeof(UHT_STATICS::CloudGeneratorActor_eventGetEncodedGuideData_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_ACloudGeneratorActor_GetEncodedGuideData(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(ACloudGeneratorActor::execGetEncodedGuideData)
{
	P_FINISH;
	P_NATIVE_BEGIN;
	*(TArray<FLinearColor>*)Z_Param__Result=P_THIS->GetEncodedGuideData();
	P_NATIVE_END;
}
// ********** End Class ACloudGeneratorActor Function GetEncodedGuideData **************************

// ********** Begin Class ACloudGeneratorActor Function LoadPreset *********************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_ACloudGeneratorActor_LoadPreset_Statics
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "CallInEditor", "true" },
		{ "Category", "Cloud Presets" },
		{ "DisplayName", "Load Preset" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
#endif // WITH_METADATA

// ********** Begin Function LoadPreset constinit property declarations ****************************
// ********** End Function LoadPreset constinit property declarations ******************************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_ACloudGeneratorActor, nullptr, "LoadPreset", nullptr, 0, 0, RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04020401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
UFunction* Z_Construct_UFunction_ACloudGeneratorActor_LoadPreset(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(ACloudGeneratorActor::execLoadPreset)
{
	P_FINISH;
	P_NATIVE_BEGIN;
	P_THIS->LoadPreset();
	P_NATIVE_END;
}
// ********** End Class ACloudGeneratorActor Function LoadPreset ***********************************

// ********** Begin Class ACloudGeneratorActor Function LockCloud **********************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_ACloudGeneratorActor_LockCloud_Statics
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "CallInEditor", "true" },
		{ "Category", "Cloud Presets" },
		{ "DisplayName", "Lock Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
#endif // WITH_METADATA

// ********** Begin Function LockCloud constinit property declarations *****************************
// ********** End Function LockCloud constinit property declarations *******************************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_ACloudGeneratorActor, nullptr, "LockCloud", nullptr, 0, 0, RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04020401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
UFunction* Z_Construct_UFunction_ACloudGeneratorActor_LockCloud(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(ACloudGeneratorActor::execLockCloud)
{
	P_FINISH;
	P_NATIVE_BEGIN;
	P_THIS->LockCloud();
	P_NATIVE_END;
}
// ********** End Class ACloudGeneratorActor Function LockCloud ************************************

// ********** Begin Class ACloudGeneratorActor Function RefreshCloud *******************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_ACloudGeneratorActor_RefreshCloud_Statics
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "CallInEditor", "true" },
		{ "Category", "Cloud Generator" },
		{ "DisplayName", "Refresh Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
#endif // WITH_METADATA

// ********** Begin Function RefreshCloud constinit property declarations **************************
// ********** End Function RefreshCloud constinit property declarations ****************************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_ACloudGeneratorActor, nullptr, "RefreshCloud", nullptr, 0, 0, RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04020401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
UFunction* Z_Construct_UFunction_ACloudGeneratorActor_RefreshCloud(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(ACloudGeneratorActor::execRefreshCloud)
{
	P_FINISH;
	P_NATIVE_BEGIN;
	P_THIS->RefreshCloud();
	P_NATIVE_END;
}
// ********** End Class ACloudGeneratorActor Function RefreshCloud *********************************

// ********** Begin Class ACloudGeneratorActor Function ResetCloudAnimation ************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_ACloudGeneratorActor_ResetCloudAnimation_Statics
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "CallInEditor", "true" },
		{ "Category", "Cloud Animation" },
		{ "DisplayName", "Reset Cloud Animation" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Resets Texture Offset and Noise Phase to zero without changing speeds, guides, or appearance controls. Unlock the cloud first." },
	};
#endif // WITH_METADATA

// ********** Begin Function ResetCloudAnimation constinit property declarations *******************
// ********** End Function ResetCloudAnimation constinit property declarations *********************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_ACloudGeneratorActor, nullptr, "ResetCloudAnimation", nullptr, 0, 0, RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04020401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
UFunction* Z_Construct_UFunction_ACloudGeneratorActor_ResetCloudAnimation(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(ACloudGeneratorActor::execResetCloudAnimation)
{
	P_FINISH;
	P_NATIVE_BEGIN;
	P_THIS->ResetCloudAnimation();
	P_NATIVE_END;
}
// ********** End Class ACloudGeneratorActor Function ResetCloudAnimation **************************

// ********** Begin Class ACloudGeneratorActor Function SavePreset *********************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_ACloudGeneratorActor_SavePreset_Statics
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "CallInEditor", "true" },
		{ "Category", "Cloud Presets" },
		{ "DisplayName", "Save Preset" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
#endif // WITH_METADATA

// ********** Begin Function SavePreset constinit property declarations ****************************
// ********** End Function SavePreset constinit property declarations ******************************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_ACloudGeneratorActor, nullptr, "SavePreset", nullptr, 0, 0, RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04020401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
UFunction* Z_Construct_UFunction_ACloudGeneratorActor_SavePreset(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(ACloudGeneratorActor::execSavePreset)
{
	P_FINISH;
	P_NATIVE_BEGIN;
	P_THIS->SavePreset();
	P_NATIVE_END;
}
// ********** End Class ACloudGeneratorActor Function SavePreset ***********************************

// ********** Begin Class ACloudGeneratorActor Function UnlockCloud ********************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_ACloudGeneratorActor_UnlockCloud_Statics
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "CallInEditor", "true" },
		{ "Category", "Cloud Presets" },
		{ "DisplayName", "Unlock Cloud" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
#endif // WITH_METADATA

// ********** Begin Function UnlockCloud constinit property declarations ***************************
// ********** End Function UnlockCloud constinit property declarations *****************************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_ACloudGeneratorActor, nullptr, "UnlockCloud", nullptr, 0, 0, RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04020401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
UFunction* Z_Construct_UFunction_ACloudGeneratorActor_UnlockCloud(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(ACloudGeneratorActor::execUnlockCloud)
{
	P_FINISH;
	P_NATIVE_BEGIN;
	P_THIS->UnlockCloud();
	P_NATIVE_END;
}
// ********** End Class ACloudGeneratorActor Function UnlockCloud **********************************

// ********** Begin Class ACloudGeneratorActor *****************************************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UClass_ACloudGeneratorActor_Statics
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "BlueprintType", "true" },
		{ "Comment", "/** One rendered cloud volume, driven by up to 64 independently editable shape guides. */" },
		{ "HideCategories", "Replication Networking Input Collision HLOD Physics" },
		{ "IncludePath", "CloudGeneratorActor.h" },
		{ "IsBlueprintBase", "true" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "One rendered cloud volume, driven by up to 64 independently editable shape guides." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_SceneRoot_MetaData[] = {
		{ "Category", "Cloud Generator" },
		{ "EditInline", "true" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_CloudVolume_MetaData[] = {
		{ "Category", "Cloud Generator" },
		{ "EditInline", "true" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Guides_MetaData[] = {
		{ "Category", "Cloud Guides" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Density_MetaData[] = {
		{ "Category", "Cloud Appearance" },
		{ "ClampMin", "0" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "UIMax", "8" },
		{ "UIMin", "0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Seed_MetaData[] = {
		{ "Category", "Cloud Appearance" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_CloudColor_MetaData[] = {
		{ "Category", "Cloud Appearance" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_SkyFill_MetaData[] = {
		{ "Category", "Cloud Appearance" },
		{ "ClampMin", "0" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "UIMax", "2" },
		{ "UIMin", "0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_BillowSizeCm_MetaData[] = {
		{ "Category", "Cloud Detail" },
		{ "ClampMin", "0.1" },
		{ "DisplayName", "Billow Size" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "Units", "cm" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_BillowDepthCm_MetaData[] = {
		{ "Category", "Cloud Detail" },
		{ "ClampMin", "0" },
		{ "DisplayName", "Billow Depth" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "Units", "cm" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_BillowStrength_MetaData[] = {
		{ "Category", "Cloud Detail" },
		{ "ClampMax", "1" },
		{ "ClampMin", "0" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "UIMax", "1" },
		{ "UIMin", "0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_DetailSizeCm_MetaData[] = {
		{ "Category", "Cloud Detail" },
		{ "ClampMin", "0.1" },
		{ "DisplayName", "Detail Size" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "Units", "cm" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_DetailStrength_MetaData[] = {
		{ "Category", "Cloud Detail" },
		{ "ClampMax", "1" },
		{ "ClampMin", "0" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "UIMax", "1" },
		{ "UIMin", "0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_BillowStyle_MetaData[] = {
		{ "Category", "Cloud Noise" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Changes the billow pattern independently of the cloud family and shape guides. Classic preserves the original noise." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_CustomShapeNoiseTexture_MetaData[] = {
		{ "Category", "Cloud Noise" },
		{ "DisplayName", "Custom Shape Noise Texture" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Optional seamless, linear 3D Volume Texture for large billows. Clear to use the cloud material's default. Ordinary 2D textures are not accepted." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_CustomDetailNoiseTexture_MetaData[] = {
		{ "Category", "Cloud Noise" },
		{ "DisplayName", "Custom Detail Noise Texture" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Optional seamless, linear 3D Volume Texture for fine erosion and wisps. Clear to use the cloud material's default. Ordinary 2D textures are not accepted." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_ShapeNoiseLayout_MetaData[] = {
		{ "Category", "Cloud Noise" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Packed RGB reads different noise patterns from red, green and blue. Grayscale reads only red and reuses it for all three channels." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_DetailNoiseLayout_MetaData[] = {
		{ "Category", "Cloud Noise" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Packed RGB reads different erosion patterns from red, green and blue. Grayscale reads only red and reuses it for all three channels." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_NoiseTiling_MetaData[] = {
		{ "Category", "Cloud Noise" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Independent world-axis X, Y and Z noise frequency multipliers. 1 keeps normal size, 0.5 stretches features to twice their length, and 2 halves their length. Type any finite value: negative mirrors the pattern and zero freezes sampling along that axis. Affects the texture pattern, never the guide shape." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_NoiseContrast_MetaData[] = {
		{ "Category", "Cloud Noise" },
		{ "ClampMax", "4" },
		{ "ClampMin", "0.1" },
		{ "DisplayName", "Billow Contrast" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Contrast of the large billow formation after texture adjustments. This is the existing Noise Contrast control; 1 preserves its original contrast." },
		{ "UIMax", "3" },
		{ "UIMin", "0.1" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_NoiseBrightness_MetaData[] = {
		{ "Category", "Cloud Noise|Texture Adjustments" },
		{ "DisplayName", "Noise Texture Brightness" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Adds brightness to sampled noise values. Zero is neutral. The slider covers -1 to 1, but typed values may extend beyond it." },
		{ "UIMax", "1" },
		{ "UIMin", "-1" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_NoiseTextureContrast_MetaData[] = {
		{ "Category", "Cloud Noise|Texture Adjustments" },
		{ "ClampMin", "0" },
		{ "DisplayName", "Noise Texture Contrast" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Contrasts sampled noise around 0.5 before Levels. 1 is neutral; 0 produces a constant value. Typed values may exceed the slider range." },
		{ "UIMax", "4" },
		{ "UIMin", "0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LevelsInputLow_MetaData[] = {
		{ "Category", "Cloud Noise|Texture Adjustments" },
		{ "ClampMax", "1" },
		{ "ClampMin", "0" },
		{ "DisplayName", "Levels Input Low" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Input black point in normalized 0 to 1 noise values. If Input High is at or below Input Low, Levels uses a hard threshold at Input Low." },
		{ "UIMax", "1" },
		{ "UIMin", "0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LevelsInputMid_MetaData[] = {
		{ "Category", "Cloud Noise|Texture Adjustments" },
		{ "ClampMax", "1000" },
		{ "ClampMin", "0.001" },
		{ "DisplayName", "Levels Input Mid" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Photoshop-style midtone gamma. 1 is neutral, values above 1 brighten midtones, and values below 1 darken them." },
		{ "UIMax", "3" },
		{ "UIMin", "0.1" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LevelsInputHigh_MetaData[] = {
		{ "Category", "Cloud Noise|Texture Adjustments" },
		{ "ClampMax", "1" },
		{ "ClampMin", "0" },
		{ "DisplayName", "Levels Input High" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Input white point in normalized 0 to 1 noise values. If at or below Input Low, Levels uses a hard threshold at Input Low." },
		{ "UIMax", "1" },
		{ "UIMin", "0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LevelsOutputLow_MetaData[] = {
		{ "Category", "Cloud Noise|Texture Adjustments" },
		{ "ClampMax", "1" },
		{ "ClampMin", "0" },
		{ "DisplayName", "Levels Output Low" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Output black-point value from 0 to 1. Output Low may exceed Output High to invert the noise." },
		{ "UIMax", "1" },
		{ "UIMin", "0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LevelsOutputHigh_MetaData[] = {
		{ "Category", "Cloud Noise|Texture Adjustments" },
		{ "ClampMax", "1" },
		{ "ClampMin", "0" },
		{ "DisplayName", "Levels Output High" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Output white-point value from 0 to 1. Output High may be below Output Low to invert the noise." },
		{ "UIMax", "1" },
		{ "UIMin", "0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_WarpAmount_MetaData[] = {
		{ "Category", "Cloud Noise" },
		{ "ClampMax", "1" },
		{ "ClampMin", "0" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Warps the noise sampling coordinates for irregular billows without changing guide positions. Zero adds no artist-controlled warp." },
		{ "UIMax", "1" },
		{ "UIMin", "0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_bAnimated_MetaData[] = {
		{ "Category", "Cloud Animation" },
		{ "DisplayName", "Animated" },
		{ "DisplayPriority", "0" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Animates the 3D noise inside the fixed guides. Works in a realtime editor viewport and in play. Turning this off freezes the current appearance. Lock Cloud also freezes animation." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_OffsetSpeedX_MetaData[] = {
		{ "Category", "Cloud Animation" },
		{ "DisplayName", "Offset Speed X" },
		{ "DisplayPriority", "1" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Noise travel along world X in centimeters per second. Negative values reverse travel. The guides stay in place." },
		{ "Units", "cm/s" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_OffsetSpeedY_MetaData[] = {
		{ "Category", "Cloud Animation" },
		{ "DisplayName", "Offset Speed Y" },
		{ "DisplayPriority", "2" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Noise travel along world Y in centimeters per second. Negative values reverse travel. The guides stay in place." },
		{ "Units", "cm/s" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_OffsetSpeedZ_MetaData[] = {
		{ "Category", "Cloud Animation" },
		{ "DisplayName", "Offset Speed Z" },
		{ "DisplayPriority", "3" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Noise travel along world Z in centimeters per second. Negative values reverse travel. The guides stay in place." },
		{ "Units", "cm/s" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_PhaseSpeed_MetaData[] = {
		{ "Category", "Cloud Animation" },
		{ "DisplayName", "Phase Speed" },
		{ "DisplayPriority", "4" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Noise evolution in phase units per second. Different noise layers move at different rates to reshape the billows. Zero stops evolution; negative values reverse it." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_TextureOffsetCm_MetaData[] = {
		{ "Category", "Cloud Animation" },
		{ "DisplayName", "Texture Offset" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Current saved noise travel in world-axis centimeters. With Animated off, key this directly in Sequencer for deterministic animation and scrubbing." },
		{ "Units", "cm" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_NoisePhase_MetaData[] = {
		{ "Category", "Cloud Animation" },
		{ "DisplayName", "Noise Phase" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Current saved noise evolution. With Animated off, key this directly in Sequencer for deterministic animation and scrubbing. Zero with zero Texture Offset preserves the original cloud." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LargeBreakupAmount_MetaData[] = {
		{ "Category", "Large Breakup" },
		{ "ClampMax", "1" },
		{ "ClampMin", "0" },
		{ "DisplayName", "Amount" },
		{ "DisplayPriority", "0" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Independent subtractive 3D noise through the whole cloud, including its solid interior. 0 disables breakup; 1 allows fully open gaps. Does not change the guides." },
		{ "UIMax", "1" },
		{ "UIMin", "0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LargeBreakupScaleX_MetaData[] = {
		{ "Category", "Large Breakup" },
		{ "ClampMin", "0.01" },
		{ "DisplayName", "Scale X" },
		{ "DisplayPriority", "1" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Approximate breakup feature size along world X, in centimeters. Larger values stretch the gaps along this axis. Independent of billow tiling and guide scale." },
		{ "Units", "cm" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LargeBreakupScaleY_MetaData[] = {
		{ "Category", "Large Breakup" },
		{ "ClampMin", "0.01" },
		{ "DisplayName", "Scale Y" },
		{ "DisplayPriority", "2" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Approximate breakup feature size along world Y, in centimeters. Larger values stretch the gaps along this axis. Independent of billow tiling and guide scale." },
		{ "Units", "cm" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LargeBreakupScaleZ_MetaData[] = {
		{ "Category", "Large Breakup" },
		{ "ClampMin", "0.01" },
		{ "DisplayName", "Scale Z" },
		{ "DisplayPriority", "3" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Approximate breakup feature size along world Z, in centimeters. Larger values stretch the gaps along this axis. Independent of billow tiling and guide scale." },
		{ "Units", "cm" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LargeBreakupBrightness_MetaData[] = {
		{ "Category", "Large Breakup" },
		{ "DisplayName", "Brightness" },
		{ "DisplayPriority", "4" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Brightness of the subtractive mask. Higher values remove more cloud; lower values preserve more. 0 is neutral. Independent of the existing noise texture adjustments." },
		{ "UIMax", "1" },
		{ "UIMin", "-1" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LargeBreakupContrast_MetaData[] = {
		{ "Category", "Large Breakup" },
		{ "ClampMin", "0" },
		{ "DisplayName", "Contrast" },
		{ "DisplayPriority", "5" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Contrast of the subtractive mask around 0.5. Higher values separate solid masses from gaps more sharply. 1 is neutral. Typed values may exceed the slider range." },
		{ "UIMax", "8" },
		{ "UIMin", "0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_UnionBlendCm_MetaData[] = {
		{ "Category", "Cloud Guides" },
		{ "ClampMin", "0" },
		{ "DisplayName", "Guide Blend" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "Units", "cm" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_UnionGrowthLimitCm_MetaData[] = {
		{ "Category", "Cloud Guides" },
		{ "ClampMin", "0" },
		{ "DisplayName", "Maximum Blend Expansion" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "Units", "cm" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Quality_MetaData[] = {
		{ "Category", "Cloud Quality" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Cinematic improves volume and shadow sampling. It preserves the shape, seed and density and costs more to render." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_CloudStyle_MetaData[] = {
		{ "Category", "Cloud Appearance" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "The cloud family. Load a preset to also arrange its shape guides." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_WispStrength_MetaData[] = {
		{ "Category", "Cloud Detail" },
		{ "ClampMax", "1" },
		{ "ClampMin", "0" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Adds directional wisps while retaining the guide shape." },
		{ "UIMax", "1" },
		{ "UIMin", "0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_WispStretch_MetaData[] = {
		{ "Category", "Cloud Detail" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Stretches only the wisp pattern, independently of guide scale. Use a larger X for long cirrus strands." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_WispDirectionDegrees_MetaData[] = {
		{ "Category", "Cloud Detail" },
		{ "DisplayName", "Wisp Direction" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "UIMax", "180" },
		{ "UIMin", "-180" },
		{ "Units", "deg" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_InteriorVariation_MetaData[] = {
		{ "Category", "Cloud Detail" },
		{ "ClampMax", "1" },
		{ "ClampMin", "0" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Adds density variation inside the cloud without changing its outer guide shape." },
		{ "UIMax", "1" },
		{ "UIMin", "0" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_VerticalDensityGradient_MetaData[] = {
		{ "Category", "Cloud Detail" },
		{ "ClampMax", "1" },
		{ "ClampMin", "-1" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Changes density from the bottom to the top. Zero preserves even density." },
		{ "UIMax", "1" },
		{ "UIMin", "-1" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_VerticalReferenceHeightCm_MetaData[] = {
		{ "Category", "Cloud Detail" },
		{ "ClampMin", "1" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Height of the vertical density profile above the generator. This stays fixed when guides move." },
		{ "Units", "cm" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Preset_MetaData[] = {
		{ "Category", "Cloud Presets" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Choose a saved cloud, then press Load Preset. Location and rotation stay unchanged; new recipes restore their authored generator scale." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_bUseDefaultPresetOnFirstPlacement_MetaData[] = {
		{ "Category", "Cloud Presets" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Apply the assigned Preset once when a new actor is placed or spawned. Existing saved actors and reconstructed actors are never reset. Requires a valid Preset and no existing guides." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_PresetName_MetaData[] = {
		{ "Category", "Cloud Presets" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Name for Save Preset. A new unique asset is created in Preset Save Folder; existing presets are never overwritten." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_PresetSaveDirectory_MetaData[] = {
		{ "Category", "Cloud Presets" },
		{ "DisplayName", "Preset Save Folder" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Project Content folder for newly saved recipes, expressed as /Game/Folder. Plugin content is never overwritten. Defaults to /Game/OnlyClouds/Presets." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_bLocked_MetaData[] = {
		{ "Category", "Cloud Presets" },
		{ "DisplayName", "Locked" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Lock protects the recipe and guides. You can still move the complete generator or change rendering quality." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_WorkflowStatus_MetaData[] = {
		{ "Category", "Cloud Presets" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_CloudMaterial_MetaData[] = {
		{ "Category", "Cloud Generator" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_PreviewStatus_MetaData[] = {
		{ "Category", "Cloud Generator" },
		{ "DisplayName", "Preview Status" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_ActiveGuideCount_MetaData[] = {
		{ "Category", "Cloud Generator" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_BoundsHalfExtentCm_MetaData[] = {
		{ "Category", "Cloud Generator" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_BoundsCenterRelativeToAnchorCm_MetaData[] = {
		{ "Category", "Cloud Generator" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_ComputedExtinctionScale_MetaData[] = {
		{ "Category", "Cloud Generator" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_GuideDataTexture_MetaData[] = {
		{ "Category", "Cloud Generator" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_bDefaultPresetPlacementHandled_MetaData[] = {
		{ "Comment", "// Serialized so duplication and Blueprint reinstancing retain this decision.\n" },
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
		{ "ToolTip", "Serialized so duplication and Blueprint reinstancing retain this decision." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_LockedRecipe_MetaData[] = {
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_DynamicMaterial_MetaData[] = {
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_CurrentBaseMaterial_MetaData[] = {
		{ "ModuleRelativePath", "Public/CloudGeneratorActor.h" },
	};
#endif // WITH_METADATA

// ********** Begin Class ACloudGeneratorActor constinit property declarations *********************
	static const UECodeGen_Private::FObjectPropertyParams NewProp_SceneRoot;
	static const UECodeGen_Private::FObjectPropertyParams NewProp_CloudVolume;
	static const UECodeGen_Private::FObjectPropertyParams NewProp_Guides_Inner;
	static const UECodeGen_Private::FArrayPropertyParams NewProp_Guides;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_Density;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_Seed;
	static const UECodeGen_Private::FStructPropertyParams NewProp_CloudColor;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_SkyFill;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_BillowSizeCm;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_BillowDepthCm;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_BillowStrength;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_DetailSizeCm;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_DetailStrength;
	static const UECodeGen_Private::FBytePropertyParams NewProp_BillowStyle_Underlying;
	static const UECodeGen_Private::FEnumPropertyParams NewProp_BillowStyle;
	static const UECodeGen_Private::FSoftObjectPropertyParams NewProp_CustomShapeNoiseTexture;
	static const UECodeGen_Private::FSoftObjectPropertyParams NewProp_CustomDetailNoiseTexture;
	static const UECodeGen_Private::FBytePropertyParams NewProp_ShapeNoiseLayout_Underlying;
	static const UECodeGen_Private::FEnumPropertyParams NewProp_ShapeNoiseLayout;
	static const UECodeGen_Private::FBytePropertyParams NewProp_DetailNoiseLayout_Underlying;
	static const UECodeGen_Private::FEnumPropertyParams NewProp_DetailNoiseLayout;
	static const UECodeGen_Private::FStructPropertyParams NewProp_NoiseTiling;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_NoiseContrast;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_NoiseBrightness;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_NoiseTextureContrast;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_LevelsInputLow;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_LevelsInputMid;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_LevelsInputHigh;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_LevelsOutputLow;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_LevelsOutputHigh;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_WarpAmount;
	static void NewProp_bAnimated_SetBit(void* Obj)
	{
		((ACloudGeneratorActor*)Obj)->bAnimated = 1;
	}
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bAnimated;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_OffsetSpeedX;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_OffsetSpeedY;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_OffsetSpeedZ;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_PhaseSpeed;
	static const UECodeGen_Private::FStructPropertyParams NewProp_TextureOffsetCm;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_NoisePhase;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_LargeBreakupAmount;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_LargeBreakupScaleX;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_LargeBreakupScaleY;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_LargeBreakupScaleZ;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_LargeBreakupBrightness;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_LargeBreakupContrast;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_UnionBlendCm;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_UnionGrowthLimitCm;
	static const UECodeGen_Private::FBytePropertyParams NewProp_Quality_Underlying;
	static const UECodeGen_Private::FEnumPropertyParams NewProp_Quality;
	static const UECodeGen_Private::FBytePropertyParams NewProp_CloudStyle_Underlying;
	static const UECodeGen_Private::FEnumPropertyParams NewProp_CloudStyle;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_WispStrength;
	static const UECodeGen_Private::FStructPropertyParams NewProp_WispStretch;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_WispDirectionDegrees;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_InteriorVariation;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_VerticalDensityGradient;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_VerticalReferenceHeightCm;
	static const UECodeGen_Private::FObjectPropertyParams NewProp_Preset;
	static void NewProp_bUseDefaultPresetOnFirstPlacement_SetBit(void* Obj)
	{
		((ACloudGeneratorActor*)Obj)->bUseDefaultPresetOnFirstPlacement = 1;
	}
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bUseDefaultPresetOnFirstPlacement;
	static const UECodeGen_Private::FStrPropertyParams NewProp_PresetName;
	static const UECodeGen_Private::FStrPropertyParams NewProp_PresetSaveDirectory;
	static void NewProp_bLocked_SetBit(void* Obj)
	{
		((ACloudGeneratorActor*)Obj)->bLocked = 1;
	}
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bLocked;
	static const UECodeGen_Private::FStrPropertyParams NewProp_WorkflowStatus;
	static const UECodeGen_Private::FSoftObjectPropertyParams NewProp_CloudMaterial;
	static const UECodeGen_Private::FStrPropertyParams NewProp_PreviewStatus;
	static const UECodeGen_Private::FIntPropertyParams NewProp_ActiveGuideCount;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_BoundsHalfExtentCm;
	static const UECodeGen_Private::FStructPropertyParams NewProp_BoundsCenterRelativeToAnchorCm;
	static const UECodeGen_Private::FFloatPropertyParams NewProp_ComputedExtinctionScale;
	static const UECodeGen_Private::FObjectPropertyParams NewProp_GuideDataTexture;
	static void NewProp_bDefaultPresetPlacementHandled_SetBit(void* Obj)
	{
		((ACloudGeneratorActor*)Obj)->bDefaultPresetPlacementHandled = 1;
	}
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bDefaultPresetPlacementHandled;
	static const UECodeGen_Private::FStructPropertyParams NewProp_LockedRecipe;
	static const UECodeGen_Private::FObjectPropertyParams NewProp_DynamicMaterial;
	static const UECodeGen_Private::FObjectPropertyParams NewProp_CurrentBaseMaterial;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
// ********** End Class ACloudGeneratorActor constinit property declarations ***********************
	static constexpr UE::CodeGen::FClassNativeFunction Funcs[] = {
		{ .NameUTF8 = UTF8TEXT("AddGuide"), .Pointer = &ACloudGeneratorActor::execAddGuide },
		{ .NameUTF8 = UTF8TEXT("ApplyRecipe"), .Pointer = &ACloudGeneratorActor::execApplyRecipe },
		{ .NameUTF8 = UTF8TEXT("CaptureRecipe"), .Pointer = &ACloudGeneratorActor::execCaptureRecipe },
		{ .NameUTF8 = UTF8TEXT("GenerateVariation"), .Pointer = &ACloudGeneratorActor::execGenerateVariation },
		{ .NameUTF8 = UTF8TEXT("GetEncodedGuideData"), .Pointer = &ACloudGeneratorActor::execGetEncodedGuideData },
		{ .NameUTF8 = UTF8TEXT("LoadPreset"), .Pointer = &ACloudGeneratorActor::execLoadPreset },
		{ .NameUTF8 = UTF8TEXT("LockCloud"), .Pointer = &ACloudGeneratorActor::execLockCloud },
		{ .NameUTF8 = UTF8TEXT("RefreshCloud"), .Pointer = &ACloudGeneratorActor::execRefreshCloud },
		{ .NameUTF8 = UTF8TEXT("ResetCloudAnimation"), .Pointer = &ACloudGeneratorActor::execResetCloudAnimation },
		{ .NameUTF8 = UTF8TEXT("SavePreset"), .Pointer = &ACloudGeneratorActor::execSavePreset },
		{ .NameUTF8 = UTF8TEXT("UnlockCloud"), .Pointer = &ACloudGeneratorActor::execUnlockCloud },
	};
	static FTypeConstructFunc* DependentSingletons[];
	static constexpr FClassFunctionLinkInfo FuncInfo[] = {
		{ &Z_Construct_UFunction_ACloudGeneratorActor_AddGuide, "AddGuide" }, // 023949ae809ae2a535685408a3857cffe1cf66f2
		{ &Z_Construct_UFunction_ACloudGeneratorActor_ApplyRecipe, "ApplyRecipe" }, // 96e45626c14775cbb49a057fa6c3b5efabf233f3
		{ &Z_Construct_UFunction_ACloudGeneratorActor_CaptureRecipe, "CaptureRecipe" }, // 9131a6b50f6bd33d713d6dedc504ee0e8163de8a
		{ &Z_Construct_UFunction_ACloudGeneratorActor_GenerateVariation, "GenerateVariation" }, // 07b967bb6428b79ffc16c0dcb32d5d1576a56be2
		{ &Z_Construct_UFunction_ACloudGeneratorActor_GetEncodedGuideData, "GetEncodedGuideData" }, // b2d6b0478b690a7ae8c0a289549a3fed89a10a70
		{ &Z_Construct_UFunction_ACloudGeneratorActor_LoadPreset, "LoadPreset" }, // 3a3d49cf0fcb0a80c5622226e16e564195b982fa
		{ &Z_Construct_UFunction_ACloudGeneratorActor_LockCloud, "LockCloud" }, // ee25ad368ba00adc65e0c21abf822346836fc797
		{ &Z_Construct_UFunction_ACloudGeneratorActor_RefreshCloud, "RefreshCloud" }, // 872e2438acb6c0b5d250808e7967eeb1fab6833e
		{ &Z_Construct_UFunction_ACloudGeneratorActor_ResetCloudAnimation, "ResetCloudAnimation" }, // 6e0b9da4d1fd89f8178d8c6d74b579daa64f9e98
		{ &Z_Construct_UFunction_ACloudGeneratorActor_SavePreset, "SavePreset" }, // 0c06c43f96999a442ab1bc4a940a98c46620055f
		{ &Z_Construct_UFunction_ACloudGeneratorActor_UnlockCloud, "UnlockCloud" }, // 3c711ddc08d2a3e57c5834bd5d42b12ad84c0c6e
	};
	static_assert(UE_ARRAY_COUNT(FuncInfo) < 2048);
	static constexpr FCppClassTypeInfoStatic StaticCppClassTypeInfo = {
		TCppClassTypeTraits<ACloudGeneratorActor>::IsAbstract,
	};
	static const UECodeGen_Private::FClassParams ClassParams;
}; // struct UHT_STATICS

// ********** Begin Class ACloudGeneratorActor Property Definitions ********************************
const UECodeGen_Private::FObjectPropertyParams UHT_STATICS::NewProp_SceneRoot = { "SceneRoot", nullptr, (EPropertyFlags)0x01140000000a001d, UECodeGen_Private::EPropertyGenFlags::Object | UECodeGen_Private::EPropertyGenFlags::ObjectPtr, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, SceneRoot), Z_Construct_UClass_USceneComponent, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_SceneRoot_MetaData), NewProp_SceneRoot_MetaData) };
const UECodeGen_Private::FObjectPropertyParams UHT_STATICS::NewProp_CloudVolume = { "CloudVolume", nullptr, (EPropertyFlags)0x01140000000a001d, UECodeGen_Private::EPropertyGenFlags::Object | UECodeGen_Private::EPropertyGenFlags::ObjectPtr, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, CloudVolume), Z_Construct_UClass_UHeterogeneousVolumeComponent, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_CloudVolume_MetaData), NewProp_CloudVolume_MetaData) };
const UECodeGen_Private::FObjectPropertyParams UHT_STATICS::NewProp_Guides_Inner = { "Guides", nullptr, (EPropertyFlags)0x0104000000020000, UECodeGen_Private::EPropertyGenFlags::Object | UECodeGen_Private::EPropertyGenFlags::ObjectPtr, nullptr, nullptr, 1, 0, Z_Construct_UClass_ACloudGuideActor, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FArrayPropertyParams UHT_STATICS::NewProp_Guides = { "Guides", nullptr, (EPropertyFlags)0x0114000000020815, UECodeGen_Private::EPropertyGenFlags::Array, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, Guides), EArrayPropertyFlags::None, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Guides_MetaData), NewProp_Guides_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_Density = { "Density", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, Density), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Density_MetaData), NewProp_Density_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_Seed = { "Seed", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, Seed), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Seed_MetaData), NewProp_Seed_MetaData) };
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_CloudColor = { "CloudColor", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, CloudColor), Z_Construct_UScriptStruct_FLinearColor, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_CloudColor_MetaData), NewProp_CloudColor_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_SkyFill = { "SkyFill", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, SkyFill), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_SkyFill_MetaData), NewProp_SkyFill_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_BillowSizeCm = { "BillowSizeCm", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, BillowSizeCm), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_BillowSizeCm_MetaData), NewProp_BillowSizeCm_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_BillowDepthCm = { "BillowDepthCm", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, BillowDepthCm), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_BillowDepthCm_MetaData), NewProp_BillowDepthCm_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_BillowStrength = { "BillowStrength", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, BillowStrength), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_BillowStrength_MetaData), NewProp_BillowStrength_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_DetailSizeCm = { "DetailSizeCm", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, DetailSizeCm), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_DetailSizeCm_MetaData), NewProp_DetailSizeCm_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_DetailStrength = { "DetailStrength", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, DetailStrength), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_DetailStrength_MetaData), NewProp_DetailStrength_MetaData) };
const UECodeGen_Private::FBytePropertyParams UHT_STATICS::NewProp_BillowStyle_Underlying = { "UnderlyingType", nullptr, (EPropertyFlags)0x0000000000000000, UECodeGen_Private::EPropertyGenFlags::Byte, nullptr, nullptr, 1, 0, nullptr, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FEnumPropertyParams UHT_STATICS::NewProp_BillowStyle = { "BillowStyle", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Enum, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, BillowStyle), Z_Construct_UEnum_CloudGeneratorTools_ECloudBillowStyle, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_BillowStyle_MetaData), NewProp_BillowStyle_MetaData) }; // fca5bcce7b2c07bbbece57424fa9d1487a2c5b2d
const UECodeGen_Private::FSoftObjectPropertyParams UHT_STATICS::NewProp_CustomShapeNoiseTexture = { "CustomShapeNoiseTexture", nullptr, (EPropertyFlags)0x0014040000000005, UECodeGen_Private::EPropertyGenFlags::SoftObject, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, CustomShapeNoiseTexture), Z_Construct_UClass_UVolumeTexture, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_CustomShapeNoiseTexture_MetaData), NewProp_CustomShapeNoiseTexture_MetaData) };
const UECodeGen_Private::FSoftObjectPropertyParams UHT_STATICS::NewProp_CustomDetailNoiseTexture = { "CustomDetailNoiseTexture", nullptr, (EPropertyFlags)0x0014040000000005, UECodeGen_Private::EPropertyGenFlags::SoftObject, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, CustomDetailNoiseTexture), Z_Construct_UClass_UVolumeTexture, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_CustomDetailNoiseTexture_MetaData), NewProp_CustomDetailNoiseTexture_MetaData) };
const UECodeGen_Private::FBytePropertyParams UHT_STATICS::NewProp_ShapeNoiseLayout_Underlying = { "UnderlyingType", nullptr, (EPropertyFlags)0x0000000000000000, UECodeGen_Private::EPropertyGenFlags::Byte, nullptr, nullptr, 1, 0, nullptr, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FEnumPropertyParams UHT_STATICS::NewProp_ShapeNoiseLayout = { "ShapeNoiseLayout", nullptr, (EPropertyFlags)0x0010040000000005, UECodeGen_Private::EPropertyGenFlags::Enum, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, ShapeNoiseLayout), Z_Construct_UEnum_CloudGeneratorTools_ECloudNoiseLayout, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_ShapeNoiseLayout_MetaData), NewProp_ShapeNoiseLayout_MetaData) }; // 0d4cd965bd2fedaaa6345e6a20296a243542bc54
const UECodeGen_Private::FBytePropertyParams UHT_STATICS::NewProp_DetailNoiseLayout_Underlying = { "UnderlyingType", nullptr, (EPropertyFlags)0x0000000000000000, UECodeGen_Private::EPropertyGenFlags::Byte, nullptr, nullptr, 1, 0, nullptr, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FEnumPropertyParams UHT_STATICS::NewProp_DetailNoiseLayout = { "DetailNoiseLayout", nullptr, (EPropertyFlags)0x0010040000000005, UECodeGen_Private::EPropertyGenFlags::Enum, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, DetailNoiseLayout), Z_Construct_UEnum_CloudGeneratorTools_ECloudNoiseLayout, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_DetailNoiseLayout_MetaData), NewProp_DetailNoiseLayout_MetaData) }; // 0d4cd965bd2fedaaa6345e6a20296a243542bc54
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_NoiseTiling = { "NoiseTiling", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, NoiseTiling), Z_Construct_UScriptStruct_FVector, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_NoiseTiling_MetaData), NewProp_NoiseTiling_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_NoiseContrast = { "NoiseContrast", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, NoiseContrast), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_NoiseContrast_MetaData), NewProp_NoiseContrast_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_NoiseBrightness = { "NoiseBrightness", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, NoiseBrightness), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_NoiseBrightness_MetaData), NewProp_NoiseBrightness_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_NoiseTextureContrast = { "NoiseTextureContrast", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, NoiseTextureContrast), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_NoiseTextureContrast_MetaData), NewProp_NoiseTextureContrast_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_LevelsInputLow = { "LevelsInputLow", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, LevelsInputLow), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LevelsInputLow_MetaData), NewProp_LevelsInputLow_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_LevelsInputMid = { "LevelsInputMid", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, LevelsInputMid), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LevelsInputMid_MetaData), NewProp_LevelsInputMid_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_LevelsInputHigh = { "LevelsInputHigh", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, LevelsInputHigh), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LevelsInputHigh_MetaData), NewProp_LevelsInputHigh_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_LevelsOutputLow = { "LevelsOutputLow", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, LevelsOutputLow), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LevelsOutputLow_MetaData), NewProp_LevelsOutputLow_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_LevelsOutputHigh = { "LevelsOutputHigh", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, LevelsOutputHigh), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LevelsOutputHigh_MetaData), NewProp_LevelsOutputHigh_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_WarpAmount = { "WarpAmount", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, WarpAmount), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_WarpAmount_MetaData), NewProp_WarpAmount_MetaData) };
const UECodeGen_Private::FBoolPropertyParams UHT_STATICS::NewProp_bAnimated = { "bAnimated", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, nullptr, nullptr, 1, sizeof(bool), sizeof(ACloudGeneratorActor), &UHT_STATICS::NewProp_bAnimated_SetBit, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_bAnimated_MetaData), NewProp_bAnimated_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_OffsetSpeedX = { "OffsetSpeedX", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, OffsetSpeedX), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_OffsetSpeedX_MetaData), NewProp_OffsetSpeedX_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_OffsetSpeedY = { "OffsetSpeedY", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, OffsetSpeedY), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_OffsetSpeedY_MetaData), NewProp_OffsetSpeedY_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_OffsetSpeedZ = { "OffsetSpeedZ", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, OffsetSpeedZ), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_OffsetSpeedZ_MetaData), NewProp_OffsetSpeedZ_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_PhaseSpeed = { "PhaseSpeed", nullptr, (EPropertyFlags)0x0010000200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, PhaseSpeed), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_PhaseSpeed_MetaData), NewProp_PhaseSpeed_MetaData) };
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_TextureOffsetCm = { "TextureOffsetCm", nullptr, (EPropertyFlags)0x0010040200000005, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, TextureOffsetCm), Z_Construct_UScriptStruct_FVector, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_TextureOffsetCm_MetaData), NewProp_TextureOffsetCm_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_NoisePhase = { "NoisePhase", nullptr, (EPropertyFlags)0x0010040200000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, NoisePhase), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_NoisePhase_MetaData), NewProp_NoisePhase_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_LargeBreakupAmount = { "LargeBreakupAmount", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, LargeBreakupAmount), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LargeBreakupAmount_MetaData), NewProp_LargeBreakupAmount_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_LargeBreakupScaleX = { "LargeBreakupScaleX", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, LargeBreakupScaleX), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LargeBreakupScaleX_MetaData), NewProp_LargeBreakupScaleX_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_LargeBreakupScaleY = { "LargeBreakupScaleY", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, LargeBreakupScaleY), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LargeBreakupScaleY_MetaData), NewProp_LargeBreakupScaleY_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_LargeBreakupScaleZ = { "LargeBreakupScaleZ", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, LargeBreakupScaleZ), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LargeBreakupScaleZ_MetaData), NewProp_LargeBreakupScaleZ_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_LargeBreakupBrightness = { "LargeBreakupBrightness", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, LargeBreakupBrightness), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LargeBreakupBrightness_MetaData), NewProp_LargeBreakupBrightness_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_LargeBreakupContrast = { "LargeBreakupContrast", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, LargeBreakupContrast), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LargeBreakupContrast_MetaData), NewProp_LargeBreakupContrast_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_UnionBlendCm = { "UnionBlendCm", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, UnionBlendCm), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_UnionBlendCm_MetaData), NewProp_UnionBlendCm_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_UnionGrowthLimitCm = { "UnionGrowthLimitCm", nullptr, (EPropertyFlags)0x0010040000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, UnionGrowthLimitCm), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_UnionGrowthLimitCm_MetaData), NewProp_UnionGrowthLimitCm_MetaData) };
const UECodeGen_Private::FBytePropertyParams UHT_STATICS::NewProp_Quality_Underlying = { "UnderlyingType", nullptr, (EPropertyFlags)0x0000000000000000, UECodeGen_Private::EPropertyGenFlags::Byte, nullptr, nullptr, 1, 0, nullptr, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FEnumPropertyParams UHT_STATICS::NewProp_Quality = { "Quality", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Enum, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, Quality), Z_Construct_UEnum_CloudGeneratorTools_ECloudPreviewQuality, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Quality_MetaData), NewProp_Quality_MetaData) }; // 731be7cd69d8913698130fa31abf11b1808acf7f
const UECodeGen_Private::FBytePropertyParams UHT_STATICS::NewProp_CloudStyle_Underlying = { "UnderlyingType", nullptr, (EPropertyFlags)0x0000000000000000, UECodeGen_Private::EPropertyGenFlags::Byte, nullptr, nullptr, 1, 0, nullptr, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FEnumPropertyParams UHT_STATICS::NewProp_CloudStyle = { "CloudStyle", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Enum, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, CloudStyle), Z_Construct_UEnum_CloudGeneratorTools_ECloudStyle, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_CloudStyle_MetaData), NewProp_CloudStyle_MetaData) }; // 38df397519e8039a981a5369f52fb9e26d032611
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_WispStrength = { "WispStrength", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, WispStrength), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_WispStrength_MetaData), NewProp_WispStrength_MetaData) };
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_WispStretch = { "WispStretch", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, WispStretch), Z_Construct_UScriptStruct_FVector, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_WispStretch_MetaData), NewProp_WispStretch_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_WispDirectionDegrees = { "WispDirectionDegrees", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, WispDirectionDegrees), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_WispDirectionDegrees_MetaData), NewProp_WispDirectionDegrees_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_InteriorVariation = { "InteriorVariation", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, InteriorVariation), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_InteriorVariation_MetaData), NewProp_InteriorVariation_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_VerticalDensityGradient = { "VerticalDensityGradient", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, VerticalDensityGradient), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_VerticalDensityGradient_MetaData), NewProp_VerticalDensityGradient_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_VerticalReferenceHeightCm = { "VerticalReferenceHeightCm", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, VerticalReferenceHeightCm), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_VerticalReferenceHeightCm_MetaData), NewProp_VerticalReferenceHeightCm_MetaData) };
const UECodeGen_Private::FObjectPropertyParams UHT_STATICS::NewProp_Preset = { "Preset", nullptr, (EPropertyFlags)0x0114000000000005, UECodeGen_Private::EPropertyGenFlags::Object | UECodeGen_Private::EPropertyGenFlags::ObjectPtr, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, Preset), Z_Construct_UClass_UCloudRecipePreset, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Preset_MetaData), NewProp_Preset_MetaData) };
const UECodeGen_Private::FBoolPropertyParams UHT_STATICS::NewProp_bUseDefaultPresetOnFirstPlacement = { "bUseDefaultPresetOnFirstPlacement", nullptr, (EPropertyFlags)0x0010040000010015, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, nullptr, nullptr, 1, sizeof(bool), sizeof(ACloudGeneratorActor), &UHT_STATICS::NewProp_bUseDefaultPresetOnFirstPlacement_SetBit, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_bUseDefaultPresetOnFirstPlacement_MetaData), NewProp_bUseDefaultPresetOnFirstPlacement_MetaData) };
const UECodeGen_Private::FStrPropertyParams UHT_STATICS::NewProp_PresetName = { "PresetName", nullptr, (EPropertyFlags)0x0010000000000005, UECodeGen_Private::EPropertyGenFlags::Str, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, PresetName), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_PresetName_MetaData), NewProp_PresetName_MetaData) };
const UECodeGen_Private::FStrPropertyParams UHT_STATICS::NewProp_PresetSaveDirectory = { "PresetSaveDirectory", nullptr, (EPropertyFlags)0x0010040000000005, UECodeGen_Private::EPropertyGenFlags::Str, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, PresetSaveDirectory), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_PresetSaveDirectory_MetaData), NewProp_PresetSaveDirectory_MetaData) };
const UECodeGen_Private::FBoolPropertyParams UHT_STATICS::NewProp_bLocked = { "bLocked", nullptr, (EPropertyFlags)0x0010000000020815, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, nullptr, nullptr, 1, sizeof(bool), sizeof(ACloudGeneratorActor), &UHT_STATICS::NewProp_bLocked_SetBit, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_bLocked_MetaData), NewProp_bLocked_MetaData) };
const UECodeGen_Private::FStrPropertyParams UHT_STATICS::NewProp_WorkflowStatus = { "WorkflowStatus", nullptr, (EPropertyFlags)0x0010000000022815, UECodeGen_Private::EPropertyGenFlags::Str, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, WorkflowStatus), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_WorkflowStatus_MetaData), NewProp_WorkflowStatus_MetaData) };
const UECodeGen_Private::FSoftObjectPropertyParams UHT_STATICS::NewProp_CloudMaterial = { "CloudMaterial", nullptr, (EPropertyFlags)0x0014040000000005, UECodeGen_Private::EPropertyGenFlags::SoftObject, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, CloudMaterial), Z_Construct_UClass_UMaterialInterface, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_CloudMaterial_MetaData), NewProp_CloudMaterial_MetaData) };
const UECodeGen_Private::FStrPropertyParams UHT_STATICS::NewProp_PreviewStatus = { "PreviewStatus", nullptr, (EPropertyFlags)0x0010000000022815, UECodeGen_Private::EPropertyGenFlags::Str, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, PreviewStatus), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_PreviewStatus_MetaData), NewProp_PreviewStatus_MetaData) };
const UECodeGen_Private::FIntPropertyParams UHT_STATICS::NewProp_ActiveGuideCount = { "ActiveGuideCount", nullptr, (EPropertyFlags)0x0010040000022815, UECodeGen_Private::EPropertyGenFlags::Int, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, ActiveGuideCount), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_ActiveGuideCount_MetaData), NewProp_ActiveGuideCount_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_BoundsHalfExtentCm = { "BoundsHalfExtentCm", nullptr, (EPropertyFlags)0x0010040000022815, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, BoundsHalfExtentCm), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_BoundsHalfExtentCm_MetaData), NewProp_BoundsHalfExtentCm_MetaData) };
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_BoundsCenterRelativeToAnchorCm = { "BoundsCenterRelativeToAnchorCm", nullptr, (EPropertyFlags)0x0010040000022815, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, BoundsCenterRelativeToAnchorCm), Z_Construct_UScriptStruct_FVector, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_BoundsCenterRelativeToAnchorCm_MetaData), NewProp_BoundsCenterRelativeToAnchorCm_MetaData) };
const UECodeGen_Private::FFloatPropertyParams UHT_STATICS::NewProp_ComputedExtinctionScale = { "ComputedExtinctionScale", nullptr, (EPropertyFlags)0x0010040000022815, UECodeGen_Private::EPropertyGenFlags::Float, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, ComputedExtinctionScale), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_ComputedExtinctionScale_MetaData), NewProp_ComputedExtinctionScale_MetaData) };
const UECodeGen_Private::FObjectPropertyParams UHT_STATICS::NewProp_GuideDataTexture = { "GuideDataTexture", nullptr, (EPropertyFlags)0x0114040000222815, UECodeGen_Private::EPropertyGenFlags::Object | UECodeGen_Private::EPropertyGenFlags::ObjectPtr, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, GuideDataTexture), Z_Construct_UClass_UTexture2D, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_GuideDataTexture_MetaData), NewProp_GuideDataTexture_MetaData) };
const UECodeGen_Private::FBoolPropertyParams UHT_STATICS::NewProp_bDefaultPresetPlacementHandled = { "bDefaultPresetPlacementHandled", nullptr, (EPropertyFlags)0x0040000000000000, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, nullptr, nullptr, 1, sizeof(bool), sizeof(ACloudGeneratorActor), &UHT_STATICS::NewProp_bDefaultPresetPlacementHandled_SetBit, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_bDefaultPresetPlacementHandled_MetaData), NewProp_bDefaultPresetPlacementHandled_MetaData) };
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_LockedRecipe = { "LockedRecipe", nullptr, (EPropertyFlags)0x0040000000000000, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, LockedRecipe), Z_Construct_UScriptStruct_FCloudRecipe, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_LockedRecipe_MetaData), NewProp_LockedRecipe_MetaData) }; // 24454c819ca86f61eca43e191606be15fa6d8b92
const UECodeGen_Private::FObjectPropertyParams UHT_STATICS::NewProp_DynamicMaterial = { "DynamicMaterial", nullptr, (EPropertyFlags)0x0144000000202000, UECodeGen_Private::EPropertyGenFlags::Object | UECodeGen_Private::EPropertyGenFlags::ObjectPtr, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, DynamicMaterial), Z_Construct_UClass_UMaterialInstanceDynamic, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_DynamicMaterial_MetaData), NewProp_DynamicMaterial_MetaData) };
const UECodeGen_Private::FObjectPropertyParams UHT_STATICS::NewProp_CurrentBaseMaterial = { "CurrentBaseMaterial", nullptr, (EPropertyFlags)0x0144000000202000, UECodeGen_Private::EPropertyGenFlags::Object | UECodeGen_Private::EPropertyGenFlags::ObjectPtr, nullptr, nullptr, 1, STRUCT_OFFSET(ACloudGeneratorActor, CurrentBaseMaterial), Z_Construct_UClass_UMaterialInterface, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_CurrentBaseMaterial_MetaData), NewProp_CurrentBaseMaterial_MetaData) };
const UECodeGen_Private::FPropertyParamsBase* const UHT_STATICS::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_SceneRoot,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_CloudVolume,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Guides_Inner,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Guides,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Density,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Seed,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_CloudColor,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_SkyFill,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_BillowSizeCm,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_BillowDepthCm,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_BillowStrength,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_DetailSizeCm,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_DetailStrength,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_BillowStyle_Underlying,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_BillowStyle,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_CustomShapeNoiseTexture,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_CustomDetailNoiseTexture,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ShapeNoiseLayout_Underlying,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ShapeNoiseLayout,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_DetailNoiseLayout_Underlying,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_DetailNoiseLayout,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_NoiseTiling,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_NoiseContrast,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_NoiseBrightness,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_NoiseTextureContrast,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LevelsInputLow,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LevelsInputMid,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LevelsInputHigh,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LevelsOutputLow,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LevelsOutputHigh,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_WarpAmount,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_bAnimated,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_OffsetSpeedX,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_OffsetSpeedY,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_OffsetSpeedZ,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_PhaseSpeed,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_TextureOffsetCm,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_NoisePhase,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LargeBreakupAmount,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LargeBreakupScaleX,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LargeBreakupScaleY,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LargeBreakupScaleZ,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LargeBreakupBrightness,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LargeBreakupContrast,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_UnionBlendCm,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_UnionGrowthLimitCm,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Quality_Underlying,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Quality,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_CloudStyle_Underlying,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_CloudStyle,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_WispStrength,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_WispStretch,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_WispDirectionDegrees,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_InteriorVariation,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_VerticalDensityGradient,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_VerticalReferenceHeightCm,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Preset,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_bUseDefaultPresetOnFirstPlacement,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_PresetName,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_PresetSaveDirectory,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_bLocked,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_WorkflowStatus,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_CloudMaterial,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_PreviewStatus,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ActiveGuideCount,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_BoundsHalfExtentCm,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_BoundsCenterRelativeToAnchorCm,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ComputedExtinctionScale,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_GuideDataTexture,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_bDefaultPresetPlacementHandled,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_LockedRecipe,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_DynamicMaterial,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_CurrentBaseMaterial,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::PropPointers) < 2048);
// ********** End Class ACloudGeneratorActor Property Definitions **********************************
FTypeConstructFunc* UHT_STATICS::DependentSingletons[] = {
	(FTypeConstructFunc*)Z_Construct_UClass_AActor,
	(FTypeConstructFunc*)Z_Construct_UPackage__Script_CloudGeneratorTools,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::DependentSingletons) < 16);
const UECodeGen_Private::FClassParams UHT_STATICS::ClassParams = {
	&Z_Construct_UClass_ACloudGeneratorActor,
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
static void ACloudGeneratorActor_StaticRegisterNativesACloudGeneratorActor()
{
	UClass* Class = ACloudGeneratorActor::StaticClass();
	FNativeFunctionRegistrar::RegisterFunctions(Class, 		MakeConstArrayView(UHT_STATICS::Funcs));
}
FClassRegistrationInfo Z_Registration_Info_UClass_ACloudGeneratorActor;
UClass* Z_Construct_UClass_ACloudGeneratorActor(ETypeConstructPhase Phase)
{
	if (Phase == ETypeConstructPhase::Inner)
	{
		using TClass = ACloudGeneratorActor;
		if (!Z_Registration_Info_UClass_ACloudGeneratorActor.InnerSingleton)
		{
			GetPrivateStaticClassBody(
				TClass::StaticPackage(),
				TEXT("CloudGeneratorActor"),
				Z_Registration_Info_UClass_ACloudGeneratorActor.InnerSingleton,
				ACloudGeneratorActor_StaticRegisterNativesACloudGeneratorActor,
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
		return Z_Registration_Info_UClass_ACloudGeneratorActor.InnerSingleton;
	}
	if (!Z_Registration_Info_UClass_ACloudGeneratorActor.OuterSingleton)
	{
		UECodeGen_Private::ConstructUClass(Z_Registration_Info_UClass_ACloudGeneratorActor.OuterSingleton, UHT_STATICS::ClassParams);
	}
	return Z_Registration_Info_UClass_ACloudGeneratorActor.OuterSingleton;
}
#undef UHT_STATICS
DEFINE_VTABLE_PTR_HELPER_CTOR_NS(, ACloudGeneratorActor);
ACloudGeneratorActor::~ACloudGeneratorActor() {}
// ********** End Class ACloudGeneratorActor *******************************************************

// ********** Begin Registration *******************************************************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_CompiledInDeferFile_FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h__Script_CloudGeneratorTools_Statics
struct UHT_STATICS
{
	static constexpr FEnumRegisterCompiledInInfo EnumInfo[] = {
		{ Z_Construct_UEnum_CloudGeneratorTools_ECloudGuideShape, TEXT("ECloudGuideShape"), &ZRIE_ECloudGuideShape, CONSTRUCT_RELOAD_VERSION_INFO(FEnumReloadVersionInfo, 1836127872U) },
		{ Z_Construct_UEnum_CloudGeneratorTools_ECloudGuideOperation, TEXT("ECloudGuideOperation"), &ZRIE_ECloudGuideOperation, CONSTRUCT_RELOAD_VERSION_INFO(FEnumReloadVersionInfo, 2319841651U) },
		{ Z_Construct_UEnum_CloudGeneratorTools_ECloudPreviewQuality, TEXT("ECloudPreviewQuality"), &ZRIE_ECloudPreviewQuality, CONSTRUCT_RELOAD_VERSION_INFO(FEnumReloadVersionInfo, 1931208653U) },
		{ Z_Construct_UEnum_CloudGeneratorTools_ECloudStyle, TEXT("ECloudStyle"), &ZRIE_ECloudStyle, CONSTRUCT_RELOAD_VERSION_INFO(FEnumReloadVersionInfo, 954153333U) },
		{ Z_Construct_UEnum_CloudGeneratorTools_ECloudBillowStyle, TEXT("ECloudBillowStyle"), &ZRIE_ECloudBillowStyle, CONSTRUCT_RELOAD_VERSION_INFO(FEnumReloadVersionInfo, 4238720206U) },
		{ Z_Construct_UEnum_CloudGeneratorTools_ECloudNoiseLayout, TEXT("ECloudNoiseLayout"), &ZRIE_ECloudNoiseLayout, CONSTRUCT_RELOAD_VERSION_INFO(FEnumReloadVersionInfo, 223140197U) },
	};
	static constexpr FStructRegisterCompiledInInfo ScriptStructInfo[] = {
		{ Z_Construct_UScriptStruct_FCloudGuideRecipe, Z_Construct_UScriptStruct_FCloudGuideRecipe_Statics::NewStructOps, TEXT("CloudGuideRecipe"),&Z_Registration_Info_UScriptStruct_FCloudGuideRecipe, CONSTRUCT_RELOAD_VERSION_INFO(FStructReloadVersionInfo, sizeof(FCloudGuideRecipe), 4185885197U) },
		{ Z_Construct_UScriptStruct_FCloudRecipe, Z_Construct_UScriptStruct_FCloudRecipe_Statics::NewStructOps, TEXT("CloudRecipe"),&Z_Registration_Info_UScriptStruct_FCloudRecipe, CONSTRUCT_RELOAD_VERSION_INFO(FStructReloadVersionInfo, sizeof(FCloudRecipe), 608521345U) },
	};
	static constexpr FClassRegisterCompiledInInfo ClassInfo[] = {
		{ Z_Construct_UClass_UCloudRecipePreset, TEXT("UCloudRecipePreset"), &Z_Registration_Info_UClass_UCloudRecipePreset, CONSTRUCT_RELOAD_VERSION_INFO(FClassReloadVersionInfo, sizeof(UCloudRecipePreset), 2122148061U) },
		{ Z_Construct_UClass_UCloudGuideShapeComponent, TEXT("UCloudGuideShapeComponent"), &Z_Registration_Info_UClass_UCloudGuideShapeComponent, CONSTRUCT_RELOAD_VERSION_INFO(FClassReloadVersionInfo, sizeof(UCloudGuideShapeComponent), 3543417050U) },
		{ Z_Construct_UClass_ACloudGuideActor, TEXT("ACloudGuideActor"), &Z_Registration_Info_UClass_ACloudGuideActor, CONSTRUCT_RELOAD_VERSION_INFO(FClassReloadVersionInfo, sizeof(ACloudGuideActor), 1337792034U) },
		{ Z_Construct_UClass_ACloudGeneratorActor, TEXT("ACloudGeneratorActor"), &Z_Registration_Info_UClass_ACloudGeneratorActor, CONSTRUCT_RELOAD_VERSION_INFO(FClassReloadVersionInfo, sizeof(ACloudGeneratorActor), 2343275948U) },
	};
}; // UHT_STATICS 
static FRegisterCompiledInInfo Z_CompiledInDeferFile_FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h__Script_CloudGeneratorTools_4027da4b1e109ef60fd8efed180c9e56bbd7f30c{
	TEXT("/Script/CloudGeneratorTools"),
	UHT_STATICS::ClassInfo, UE_ARRAY_COUNT(UHT_STATICS::ClassInfo),
	UHT_STATICS::ScriptStructInfo, UE_ARRAY_COUNT(UHT_STATICS::ScriptStructInfo),
	UHT_STATICS::EnumInfo, UE_ARRAY_COUNT(UHT_STATICS::EnumInfo),
	nullptr, 0,
};
#undef UHT_STATICS
// ********** End Registration *********************************************************************
#undef UHT_STRUCT_BASE

PRAGMA_ENABLE_DEPRECATION_WARNINGS
