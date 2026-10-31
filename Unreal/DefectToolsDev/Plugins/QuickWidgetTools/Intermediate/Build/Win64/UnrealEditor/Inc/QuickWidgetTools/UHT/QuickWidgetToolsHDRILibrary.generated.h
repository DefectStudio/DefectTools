// Copyright Epic Games, Inc. All Rights Reserved.
/*===========================================================================
	Generated code exported from UnrealHeaderTool.
	DO NOT modify this manually! Edit the corresponding .h files instead!
===========================================================================*/

// IWYU pragma: private, include "QuickWidgetToolsHDRILibrary.h"

#ifdef QUICKWIDGETTOOLS_QuickWidgetToolsHDRILibrary_generated_h
#error "QuickWidgetToolsHDRILibrary.generated.h already included, missing '#pragma once' in QuickWidgetToolsHDRILibrary.h"
#endif
#define QUICKWIDGETTOOLS_QuickWidgetToolsHDRILibrary_generated_h

#include "UObject/ObjectMacros.h"
#include "UObject/ReflectedTypeAccessors.h"
#include "UObject/ScriptMacros.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS
class UTextureCube;
class UTextureRenderTargetCube;

// ********** Begin Class UQuickWidgetToolsHDRILibrary *********************************************
#define FID_HostProject_Plugins_QuickWidgetTools_Source_QuickWidgetTools_Public_QuickWidgetToolsHDRILibrary_h_14_RPC_WRAPPERS_NO_PURE_DECLS \
	DECLARE_FUNCTION(execGetHDRCubeSourceSliceCount); \
	DECLARE_FUNCTION(execGetHDRCubeSourceSize); \
	DECLARE_FUNCTION(execReleaseHDRCubeRenderTarget); \
	DECLARE_FUNCTION(execCreateHDRTextureCube); \
	DECLARE_FUNCTION(execFlushHDRICaptureRendering); \
	DECLARE_FUNCTION(execCreateHDRCubeRenderTarget);


struct Z_Construct_UClass_UQuickWidgetToolsHDRILibrary_Statics;
QUICKWIDGETTOOLS_API UClass* Z_Construct_UClass_UQuickWidgetToolsHDRILibrary(ETypeConstructPhase);

#define FID_HostProject_Plugins_QuickWidgetTools_Source_QuickWidgetTools_Public_QuickWidgetToolsHDRILibrary_h_14_INCLASS_NO_PURE_DECLS \
private: \
	friend struct ::Z_Construct_UClass_UQuickWidgetToolsHDRILibrary_Statics; \
	friend QUICKWIDGETTOOLS_API UClass* ::Z_Construct_UClass_UQuickWidgetToolsHDRILibrary(ETypeConstructPhase); \
public: \
	DECLARE_CLASS2(UQuickWidgetToolsHDRILibrary, UBlueprintFunctionLibrary, COMPILED_IN_FLAGS(0), CASTCLASS_None, TEXT("/Script/QuickWidgetTools"), Z_Construct_UClass_UQuickWidgetToolsHDRILibrary) \
	DECLARE_SERIALIZER(UQuickWidgetToolsHDRILibrary)


#define FID_HostProject_Plugins_QuickWidgetTools_Source_QuickWidgetTools_Public_QuickWidgetToolsHDRILibrary_h_14_ENHANCED_CONSTRUCTORS \
	/** Standard constructor, called after all reflected properties have been initialized */ \
	NO_API UQuickWidgetToolsHDRILibrary(const FObjectInitializer& ObjectInitializer = FObjectInitializer::Get()); \
	/** Deleted move- and copy-constructors, should never be used */ \
	UQuickWidgetToolsHDRILibrary(UQuickWidgetToolsHDRILibrary&&) = delete; \
	UQuickWidgetToolsHDRILibrary(const UQuickWidgetToolsHDRILibrary&) = delete; \
	DECLARE_VTABLE_PTR_HELPER_CTOR(NO_API, UQuickWidgetToolsHDRILibrary); \
	DEFINE_VTABLE_PTR_HELPER_CTOR_CALLER(UQuickWidgetToolsHDRILibrary); \
	DEFINE_DEFAULT_OBJECT_INITIALIZER_CONSTRUCTOR_CALL(UQuickWidgetToolsHDRILibrary) \
	NO_API virtual ~UQuickWidgetToolsHDRILibrary();


#define FID_HostProject_Plugins_QuickWidgetTools_Source_QuickWidgetTools_Public_QuickWidgetToolsHDRILibrary_h_11_PROLOG
#define FID_HostProject_Plugins_QuickWidgetTools_Source_QuickWidgetTools_Public_QuickWidgetToolsHDRILibrary_h_14_GENERATED_BODY \
PRAGMA_DISABLE_DEPRECATION_WARNINGS \
public: \
	FID_HostProject_Plugins_QuickWidgetTools_Source_QuickWidgetTools_Public_QuickWidgetToolsHDRILibrary_h_14_RPC_WRAPPERS_NO_PURE_DECLS \
	FID_HostProject_Plugins_QuickWidgetTools_Source_QuickWidgetTools_Public_QuickWidgetToolsHDRILibrary_h_14_INCLASS_NO_PURE_DECLS \
	FID_HostProject_Plugins_QuickWidgetTools_Source_QuickWidgetTools_Public_QuickWidgetToolsHDRILibrary_h_14_ENHANCED_CONSTRUCTORS \
private: \
PRAGMA_ENABLE_DEPRECATION_WARNINGS


class UQuickWidgetToolsHDRILibrary;

// ********** End Class UQuickWidgetToolsHDRILibrary ***********************************************

#undef CURRENT_FILE_ID
#define CURRENT_FILE_ID FID_HostProject_Plugins_QuickWidgetTools_Source_QuickWidgetTools_Public_QuickWidgetToolsHDRILibrary_h

PRAGMA_ENABLE_DEPRECATION_WARNINGS
