// Copyright Epic Games, Inc. All Rights Reserved.
/*===========================================================================
	Generated code exported from UnrealHeaderTool.
	DO NOT modify this manually! Edit the corresponding .h files instead!
===========================================================================*/

// IWYU pragma: private, include "UltraDynamicSkyOnlyClouds.h"

#ifdef CLOUDGENERATORTOOLS_UltraDynamicSkyOnlyClouds_generated_h
#error "UltraDynamicSkyOnlyClouds.generated.h already included, missing '#pragma once' in UltraDynamicSkyOnlyClouds.h"
#endif
#define CLOUDGENERATORTOOLS_UltraDynamicSkyOnlyClouds_generated_h

#include "UObject/ObjectMacros.h"
#include "UObject/ReflectedTypeAccessors.h"
#include "UObject/ScriptMacros.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS

// ********** Begin ScriptStruct FUDSOnlyCloudLayer ************************************************
struct Z_Construct_UScriptStruct_FUDSOnlyCloudLayer_Statics;
CLOUDGENERATORTOOLS_API UScriptStruct* Z_Construct_UScriptStruct_FUDSOnlyCloudLayer(ETypeConstructPhase);

#define FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_UltraDynamicSkyOnlyClouds_h_19_GENERATED_BODY \
	friend struct ::Z_Construct_UScriptStruct_FUDSOnlyCloudLayer_Statics; \
	UE_NODEBUG static UScriptStruct* StaticStruct() { return Z_Construct_UScriptStruct_FUDSOnlyCloudLayer(ETypeConstructPhase::Inner); }


struct FUDSOnlyCloudLayer;
// ********** End ScriptStruct FUDSOnlyCloudLayer **************************************************

// ********** Begin Class AUltraDynamicSkyOnlyClouds ***********************************************
#define FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_UltraDynamicSkyOnlyClouds_h_61_RPC_WRAPPERS_NO_PURE_DECLS \
	DECLARE_FUNCTION(execAddCloudLayer); \
	DECLARE_FUNCTION(execResetAnimationTime); \
	DECLARE_FUNCTION(execRestorePreviousCloudQuality); \
	DECLARE_FUNCTION(execApplyCinematicCloudQuality); \
	DECLARE_FUNCTION(execRefreshClouds);


struct Z_Construct_UClass_AUltraDynamicSkyOnlyClouds_Statics;
CLOUDGENERATORTOOLS_API UClass* Z_Construct_UClass_AUltraDynamicSkyOnlyClouds(ETypeConstructPhase);

#define FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_UltraDynamicSkyOnlyClouds_h_61_INCLASS_NO_PURE_DECLS \
private: \
	friend struct ::Z_Construct_UClass_AUltraDynamicSkyOnlyClouds_Statics; \
	friend CLOUDGENERATORTOOLS_API UClass* ::Z_Construct_UClass_AUltraDynamicSkyOnlyClouds(ETypeConstructPhase); \
public: \
	DECLARE_CLASS2(AUltraDynamicSkyOnlyClouds, AActor, COMPILED_IN_FLAGS(0 | CLASS_Config), CASTCLASS_None, TEXT("/Script/CloudGeneratorTools"), Z_Construct_UClass_AUltraDynamicSkyOnlyClouds) \
	DECLARE_SERIALIZER(AUltraDynamicSkyOnlyClouds)


#define FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_UltraDynamicSkyOnlyClouds_h_61_ENHANCED_CONSTRUCTORS \
	/** Deleted move- and copy-constructors, should never be used */ \
	AUltraDynamicSkyOnlyClouds(AUltraDynamicSkyOnlyClouds&&) = delete; \
	AUltraDynamicSkyOnlyClouds(const AUltraDynamicSkyOnlyClouds&) = delete; \
	DECLARE_VTABLE_PTR_HELPER_CTOR(NO_API, AUltraDynamicSkyOnlyClouds); \
	DEFINE_VTABLE_PTR_HELPER_CTOR_CALLER(AUltraDynamicSkyOnlyClouds); \
	DEFINE_DEFAULT_CONSTRUCTOR_CALL(AUltraDynamicSkyOnlyClouds) \
	NO_API virtual ~AUltraDynamicSkyOnlyClouds();


#define FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_UltraDynamicSkyOnlyClouds_h_58_PROLOG
#define FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_UltraDynamicSkyOnlyClouds_h_61_GENERATED_BODY \
PRAGMA_DISABLE_DEPRECATION_WARNINGS \
public: \
	FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_UltraDynamicSkyOnlyClouds_h_61_RPC_WRAPPERS_NO_PURE_DECLS \
	FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_UltraDynamicSkyOnlyClouds_h_61_INCLASS_NO_PURE_DECLS \
	FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_UltraDynamicSkyOnlyClouds_h_61_ENHANCED_CONSTRUCTORS \
private: \
PRAGMA_ENABLE_DEPRECATION_WARNINGS


class AUltraDynamicSkyOnlyClouds;

// ********** End Class AUltraDynamicSkyOnlyClouds *************************************************

#undef CURRENT_FILE_ID
#define CURRENT_FILE_ID FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_UltraDynamicSkyOnlyClouds_h

PRAGMA_ENABLE_DEPRECATION_WARNINGS
