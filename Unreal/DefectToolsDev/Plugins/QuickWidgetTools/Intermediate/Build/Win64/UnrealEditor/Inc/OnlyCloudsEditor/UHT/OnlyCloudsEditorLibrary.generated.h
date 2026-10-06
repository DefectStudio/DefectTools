// Copyright Epic Games, Inc. All Rights Reserved.
/*===========================================================================
	Generated code exported from UnrealHeaderTool.
	DO NOT modify this manually! Edit the corresponding .h files instead!
===========================================================================*/

// IWYU pragma: private, include "OnlyCloudsEditorLibrary.h"

#ifdef ONLYCLOUDSEDITOR_OnlyCloudsEditorLibrary_generated_h
#error "OnlyCloudsEditorLibrary.generated.h already included, missing '#pragma once' in OnlyCloudsEditorLibrary.h"
#endif
#define ONLYCLOUDSEDITOR_OnlyCloudsEditorLibrary_generated_h

#include "UObject/ObjectMacros.h"
#include "UObject/ReflectedTypeAccessors.h"
#include "UObject/ScriptMacros.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS
struct FOnlyCloudsEditorActionResult;

// ********** Begin ScriptStruct FOnlyCloudsEditorActionResult *************************************
struct Z_Construct_UScriptStruct_FOnlyCloudsEditorActionResult_Statics;
ONLYCLOUDSEDITOR_API UScriptStruct* Z_Construct_UScriptStruct_FOnlyCloudsEditorActionResult(ETypeConstructPhase);

#define FID_HostProject_Plugins_QuickWidgetTools_Source_OnlyCloudsEditor_Public_OnlyCloudsEditorLibrary_h_13_GENERATED_BODY \
	friend struct ::Z_Construct_UScriptStruct_FOnlyCloudsEditorActionResult_Statics; \
	UE_NODEBUG static UScriptStruct* StaticStruct() { return Z_Construct_UScriptStruct_FOnlyCloudsEditorActionResult(ETypeConstructPhase::Inner); }


struct FOnlyCloudsEditorActionResult;
// ********** End ScriptStruct FOnlyCloudsEditorActionResult ***************************************

// ********** Begin Class UOnlyCloudsEditorLibrary *************************************************
#define FID_HostProject_Plugins_QuickWidgetTools_Source_OnlyCloudsEditor_Public_OnlyCloudsEditorLibrary_h_34_RPC_WRAPPERS_NO_PURE_DECLS \
	DECLARE_FUNCTION(execRedoLastEditorTransaction); \
	DECLARE_FUNCTION(execUndoLastEditorTransaction); \
	DECLARE_FUNCTION(execDescribeRegisteredMenu); \
	DECLARE_FUNCTION(execExecuteRegisteredMenuAction); \
	DECLARE_FUNCTION(execReportActionResult); \
	DECLARE_FUNCTION(execAddCloudPreset); \
	DECLARE_FUNCTION(execAddLayeredWorldClouds); \
	DECLARE_FUNCTION(execAddBasicLightRigg);


struct Z_Construct_UClass_UOnlyCloudsEditorLibrary_Statics;
ONLYCLOUDSEDITOR_API UClass* Z_Construct_UClass_UOnlyCloudsEditorLibrary(ETypeConstructPhase);

#define FID_HostProject_Plugins_QuickWidgetTools_Source_OnlyCloudsEditor_Public_OnlyCloudsEditorLibrary_h_34_INCLASS_NO_PURE_DECLS \
private: \
	friend struct ::Z_Construct_UClass_UOnlyCloudsEditorLibrary_Statics; \
	friend ONLYCLOUDSEDITOR_API UClass* ::Z_Construct_UClass_UOnlyCloudsEditorLibrary(ETypeConstructPhase); \
public: \
	DECLARE_CLASS2(UOnlyCloudsEditorLibrary, UBlueprintFunctionLibrary, COMPILED_IN_FLAGS(0), CASTCLASS_None, TEXT("/Script/OnlyCloudsEditor"), Z_Construct_UClass_UOnlyCloudsEditorLibrary) \
	DECLARE_SERIALIZER(UOnlyCloudsEditorLibrary)


#define FID_HostProject_Plugins_QuickWidgetTools_Source_OnlyCloudsEditor_Public_OnlyCloudsEditorLibrary_h_34_ENHANCED_CONSTRUCTORS \
	/** Standard constructor, called after all reflected properties have been initialized */ \
	NO_API UOnlyCloudsEditorLibrary(const FObjectInitializer& ObjectInitializer = FObjectInitializer::Get()); \
	/** Deleted move- and copy-constructors, should never be used */ \
	UOnlyCloudsEditorLibrary(UOnlyCloudsEditorLibrary&&) = delete; \
	UOnlyCloudsEditorLibrary(const UOnlyCloudsEditorLibrary&) = delete; \
	DECLARE_VTABLE_PTR_HELPER_CTOR(NO_API, UOnlyCloudsEditorLibrary); \
	DEFINE_VTABLE_PTR_HELPER_CTOR_CALLER(UOnlyCloudsEditorLibrary); \
	DEFINE_DEFAULT_OBJECT_INITIALIZER_CONSTRUCTOR_CALL(UOnlyCloudsEditorLibrary) \
	NO_API virtual ~UOnlyCloudsEditorLibrary();


#define FID_HostProject_Plugins_QuickWidgetTools_Source_OnlyCloudsEditor_Public_OnlyCloudsEditorLibrary_h_31_PROLOG
#define FID_HostProject_Plugins_QuickWidgetTools_Source_OnlyCloudsEditor_Public_OnlyCloudsEditorLibrary_h_34_GENERATED_BODY \
PRAGMA_DISABLE_DEPRECATION_WARNINGS \
public: \
	FID_HostProject_Plugins_QuickWidgetTools_Source_OnlyCloudsEditor_Public_OnlyCloudsEditorLibrary_h_34_RPC_WRAPPERS_NO_PURE_DECLS \
	FID_HostProject_Plugins_QuickWidgetTools_Source_OnlyCloudsEditor_Public_OnlyCloudsEditorLibrary_h_34_INCLASS_NO_PURE_DECLS \
	FID_HostProject_Plugins_QuickWidgetTools_Source_OnlyCloudsEditor_Public_OnlyCloudsEditorLibrary_h_34_ENHANCED_CONSTRUCTORS \
private: \
PRAGMA_ENABLE_DEPRECATION_WARNINGS


class UOnlyCloudsEditorLibrary;

// ********** End Class UOnlyCloudsEditorLibrary ***************************************************

#undef CURRENT_FILE_ID
#define CURRENT_FILE_ID FID_HostProject_Plugins_QuickWidgetTools_Source_OnlyCloudsEditor_Public_OnlyCloudsEditorLibrary_h

PRAGMA_ENABLE_DEPRECATION_WARNINGS
