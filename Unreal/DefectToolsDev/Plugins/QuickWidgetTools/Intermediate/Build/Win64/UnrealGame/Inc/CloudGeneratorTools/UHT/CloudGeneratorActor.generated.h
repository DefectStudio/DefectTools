// Copyright Epic Games, Inc. All Rights Reserved.
/*===========================================================================
	Generated code exported from UnrealHeaderTool.
	DO NOT modify this manually! Edit the corresponding .h files instead!
===========================================================================*/

// IWYU pragma: private, include "CloudGeneratorActor.h"

#ifdef CLOUDGENERATORTOOLS_CloudGeneratorActor_generated_h
#error "CloudGeneratorActor.generated.h already included, missing '#pragma once' in CloudGeneratorActor.h"
#endif
#define CLOUDGENERATORTOOLS_CloudGeneratorActor_generated_h

#include "UObject/ObjectMacros.h"
#include "UObject/ReflectedTypeAccessors.h"
#include "Templates/IsUEnumClass.h"
#include "UObject/ScriptMacros.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS
struct FCloudRecipe;
struct FLinearColor;

// ********** Begin ScriptStruct FCloudGuideRecipe *************************************************
struct Z_Construct_UScriptStruct_FCloudGuideRecipe_Statics;
CLOUDGENERATORTOOLS_API UScriptStruct* Z_Construct_UScriptStruct_FCloudGuideRecipe(ETypeConstructPhase);

#define FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_66_GENERATED_BODY \
	friend struct ::Z_Construct_UScriptStruct_FCloudGuideRecipe_Statics; \
	UE_NODEBUG static UScriptStruct* StaticStruct() { return Z_Construct_UScriptStruct_FCloudGuideRecipe(ETypeConstructPhase::Inner); }


struct FCloudGuideRecipe;
// ********** End ScriptStruct FCloudGuideRecipe ***************************************************

// ********** Begin ScriptStruct FCloudRecipe ******************************************************
struct Z_Construct_UScriptStruct_FCloudRecipe_Statics;
CLOUDGENERATORTOOLS_API UScriptStruct* Z_Construct_UScriptStruct_FCloudRecipe(ETypeConstructPhase);

#define FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_79_GENERATED_BODY \
	friend struct ::Z_Construct_UScriptStruct_FCloudRecipe_Statics; \
	UE_NODEBUG static UScriptStruct* StaticStruct() { return Z_Construct_UScriptStruct_FCloudRecipe(ETypeConstructPhase::Inner); }


struct FCloudRecipe;
// ********** End ScriptStruct FCloudRecipe ********************************************************

// ********** Begin Class UCloudRecipePreset *******************************************************
struct Z_Construct_UClass_UCloudRecipePreset_Statics;
CLOUDGENERATORTOOLS_API UClass* Z_Construct_UClass_UCloudRecipePreset(ETypeConstructPhase);

#define FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_138_INCLASS_NO_PURE_DECLS \
private: \
	friend struct ::Z_Construct_UClass_UCloudRecipePreset_Statics; \
	friend CLOUDGENERATORTOOLS_API UClass* ::Z_Construct_UClass_UCloudRecipePreset(ETypeConstructPhase); \
public: \
	DECLARE_CLASS2(UCloudRecipePreset, UDataAsset, COMPILED_IN_FLAGS(0), CASTCLASS_None, TEXT("/Script/CloudGeneratorTools"), Z_Construct_UClass_UCloudRecipePreset) \
	DECLARE_SERIALIZER(UCloudRecipePreset)


#define FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_138_ENHANCED_CONSTRUCTORS \
	/** Standard constructor, called after all reflected properties have been initialized */ \
	NO_API UCloudRecipePreset(const FObjectInitializer& ObjectInitializer = FObjectInitializer::Get()); \
	/** Deleted move- and copy-constructors, should never be used */ \
	UCloudRecipePreset(UCloudRecipePreset&&) = delete; \
	UCloudRecipePreset(const UCloudRecipePreset&) = delete; \
	DECLARE_VTABLE_PTR_HELPER_CTOR(NO_API, UCloudRecipePreset); \
	DEFINE_VTABLE_PTR_HELPER_CTOR_CALLER(UCloudRecipePreset); \
	DEFINE_DEFAULT_OBJECT_INITIALIZER_CONSTRUCTOR_CALL(UCloudRecipePreset) \
	NO_API virtual ~UCloudRecipePreset();


#define FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_135_PROLOG
#define FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_138_GENERATED_BODY \
PRAGMA_DISABLE_DEPRECATION_WARNINGS \
public: \
	FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_138_INCLASS_NO_PURE_DECLS \
	FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_138_ENHANCED_CONSTRUCTORS \
private: \
PRAGMA_ENABLE_DEPRECATION_WARNINGS


class UCloudRecipePreset;

// ********** End Class UCloudRecipePreset *********************************************************

// ********** Begin Class UCloudGuideShapeComponent ************************************************
struct Z_Construct_UClass_UCloudGuideShapeComponent_Statics;
CLOUDGENERATORTOOLS_API UClass* Z_Construct_UClass_UCloudGuideShapeComponent(ETypeConstructPhase);

#define FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_148_INCLASS_NO_PURE_DECLS \
private: \
	friend struct ::Z_Construct_UClass_UCloudGuideShapeComponent_Statics; \
	friend CLOUDGENERATORTOOLS_API UClass* ::Z_Construct_UClass_UCloudGuideShapeComponent(ETypeConstructPhase); \
public: \
	DECLARE_CLASS2(UCloudGuideShapeComponent, UPrimitiveComponent, COMPILED_IN_FLAGS(0 | CLASS_Config), CASTCLASS_None, TEXT("/Script/CloudGeneratorTools"), Z_Construct_UClass_UCloudGuideShapeComponent) \
	DECLARE_SERIALIZER(UCloudGuideShapeComponent)


#define FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_148_ENHANCED_CONSTRUCTORS \
	/** Deleted move- and copy-constructors, should never be used */ \
	UCloudGuideShapeComponent(UCloudGuideShapeComponent&&) = delete; \
	UCloudGuideShapeComponent(const UCloudGuideShapeComponent&) = delete; \
	DECLARE_VTABLE_PTR_HELPER_CTOR(NO_API, UCloudGuideShapeComponent); \
	DEFINE_VTABLE_PTR_HELPER_CTOR_CALLER(UCloudGuideShapeComponent); \
	DEFINE_DEFAULT_CONSTRUCTOR_CALL(UCloudGuideShapeComponent) \
	NO_API virtual ~UCloudGuideShapeComponent();


#define FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_145_PROLOG
#define FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_148_GENERATED_BODY \
PRAGMA_DISABLE_DEPRECATION_WARNINGS \
public: \
	FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_148_INCLASS_NO_PURE_DECLS \
	FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_148_ENHANCED_CONSTRUCTORS \
private: \
PRAGMA_ENABLE_DEPRECATION_WARNINGS


class UCloudGuideShapeComponent;

// ********** End Class UCloudGuideShapeComponent **************************************************

// ********** Begin Class ACloudGuideActor *********************************************************
#define FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_159_RPC_WRAPPERS_NO_PURE_DECLS \
	DECLARE_FUNCTION(execNotifyGenerator);


struct Z_Construct_UClass_ACloudGuideActor_Statics;
CLOUDGENERATORTOOLS_API UClass* Z_Construct_UClass_ACloudGuideActor(ETypeConstructPhase);

#define FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_159_INCLASS_NO_PURE_DECLS \
private: \
	friend struct ::Z_Construct_UClass_ACloudGuideActor_Statics; \
	friend CLOUDGENERATORTOOLS_API UClass* ::Z_Construct_UClass_ACloudGuideActor(ETypeConstructPhase); \
public: \
	DECLARE_CLASS2(ACloudGuideActor, AActor, COMPILED_IN_FLAGS(0 | CLASS_Config), CASTCLASS_None, TEXT("/Script/CloudGeneratorTools"), Z_Construct_UClass_ACloudGuideActor) \
	DECLARE_SERIALIZER(ACloudGuideActor)


#define FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_159_ENHANCED_CONSTRUCTORS \
	/** Deleted move- and copy-constructors, should never be used */ \
	ACloudGuideActor(ACloudGuideActor&&) = delete; \
	ACloudGuideActor(const ACloudGuideActor&) = delete; \
	DECLARE_VTABLE_PTR_HELPER_CTOR(NO_API, ACloudGuideActor); \
	DEFINE_VTABLE_PTR_HELPER_CTOR_CALLER(ACloudGuideActor); \
	DEFINE_DEFAULT_CONSTRUCTOR_CALL(ACloudGuideActor) \
	NO_API virtual ~ACloudGuideActor();


#define FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_156_PROLOG
#define FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_159_GENERATED_BODY \
PRAGMA_DISABLE_DEPRECATION_WARNINGS \
public: \
	FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_159_RPC_WRAPPERS_NO_PURE_DECLS \
	FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_159_INCLASS_NO_PURE_DECLS \
	FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_159_ENHANCED_CONSTRUCTORS \
private: \
PRAGMA_ENABLE_DEPRECATION_WARNINGS


class ACloudGuideActor;

// ********** End Class ACloudGuideActor ***********************************************************

// ********** Begin Class ACloudGeneratorActor *****************************************************
#define FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_204_RPC_WRAPPERS_NO_PURE_DECLS \
	DECLARE_FUNCTION(execGetEncodedGuideData); \
	DECLARE_FUNCTION(execRefreshCloud); \
	DECLARE_FUNCTION(execAddGuide); \
	DECLARE_FUNCTION(execApplyRecipe); \
	DECLARE_FUNCTION(execCaptureRecipe); \
	DECLARE_FUNCTION(execUnlockCloud); \
	DECLARE_FUNCTION(execLockCloud); \
	DECLARE_FUNCTION(execLoadPreset); \
	DECLARE_FUNCTION(execSavePreset); \
	DECLARE_FUNCTION(execGenerateVariation); \
	DECLARE_FUNCTION(execResetCloudAnimation);


struct Z_Construct_UClass_ACloudGeneratorActor_Statics;
CLOUDGENERATORTOOLS_API UClass* Z_Construct_UClass_ACloudGeneratorActor(ETypeConstructPhase);

#define FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_204_INCLASS_NO_PURE_DECLS \
private: \
	friend struct ::Z_Construct_UClass_ACloudGeneratorActor_Statics; \
	friend CLOUDGENERATORTOOLS_API UClass* ::Z_Construct_UClass_ACloudGeneratorActor(ETypeConstructPhase); \
public: \
	DECLARE_CLASS2(ACloudGeneratorActor, AActor, COMPILED_IN_FLAGS(0 | CLASS_Config), CASTCLASS_None, TEXT("/Script/CloudGeneratorTools"), Z_Construct_UClass_ACloudGeneratorActor) \
	DECLARE_SERIALIZER(ACloudGeneratorActor)


#define FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_204_ENHANCED_CONSTRUCTORS \
	/** Deleted move- and copy-constructors, should never be used */ \
	ACloudGeneratorActor(ACloudGeneratorActor&&) = delete; \
	ACloudGeneratorActor(const ACloudGeneratorActor&) = delete; \
	DECLARE_VTABLE_PTR_HELPER_CTOR(NO_API, ACloudGeneratorActor); \
	DEFINE_VTABLE_PTR_HELPER_CTOR_CALLER(ACloudGeneratorActor); \
	DEFINE_DEFAULT_CONSTRUCTOR_CALL(ACloudGeneratorActor) \
	NO_API virtual ~ACloudGeneratorActor();


#define FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_201_PROLOG
#define FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_204_GENERATED_BODY \
PRAGMA_DISABLE_DEPRECATION_WARNINGS \
public: \
	FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_204_RPC_WRAPPERS_NO_PURE_DECLS \
	FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_204_INCLASS_NO_PURE_DECLS \
	FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h_204_ENHANCED_CONSTRUCTORS \
private: \
PRAGMA_ENABLE_DEPRECATION_WARNINGS


class ACloudGeneratorActor;

// ********** End Class ACloudGeneratorActor *******************************************************

#undef CURRENT_FILE_ID
#define CURRENT_FILE_ID FID_HostProject_Plugins_QuickWidgetTools_Source_CloudGeneratorTools_Public_CloudGeneratorActor_h

// ********** Begin Enum ECloudGuideShape **********************************************************
#define FOREACH_ENUM_ECLOUDGUIDESHAPE(op) \
	op(ECloudGuideShape::Sphere) \
	op(ECloudGuideShape::Box) 

enum class ECloudGuideShape : uint8;
template<> struct TIsUEnumClass<ECloudGuideShape> { enum { Value = true }; };
template<> UE_NODEBUG CLOUDGENERATORTOOLS_NON_ATTRIBUTED_API UEnum* StaticEnum<ECloudGuideShape>();
// ********** End Enum ECloudGuideShape ************************************************************

// ********** Begin Enum ECloudGuideOperation ******************************************************
#define FOREACH_ENUM_ECLOUDGUIDEOPERATION(op) \
	op(ECloudGuideOperation::Add) \
	op(ECloudGuideOperation::Subtract) 

enum class ECloudGuideOperation : uint8;
template<> struct TIsUEnumClass<ECloudGuideOperation> { enum { Value = true }; };
template<> UE_NODEBUG CLOUDGENERATORTOOLS_NON_ATTRIBUTED_API UEnum* StaticEnum<ECloudGuideOperation>();
// ********** End Enum ECloudGuideOperation ********************************************************

// ********** Begin Enum ECloudPreviewQuality ******************************************************
#define FOREACH_ENUM_ECLOUDPREVIEWQUALITY(op) \
	op(ECloudPreviewQuality::Preview) \
	op(ECloudPreviewQuality::Cinematic) 

enum class ECloudPreviewQuality : uint8;
template<> struct TIsUEnumClass<ECloudPreviewQuality> { enum { Value = true }; };
template<> UE_NODEBUG CLOUDGENERATORTOOLS_NON_ATTRIBUTED_API UEnum* StaticEnum<ECloudPreviewQuality>();
// ********** End Enum ECloudPreviewQuality ********************************************************

// ********** Begin Enum ECloudStyle ***************************************************************
#define FOREACH_ENUM_ECLOUDSTYLE(op) \
	op(ECloudStyle::Cumulus) \
	op(ECloudStyle::Cumulonimbus) \
	op(ECloudStyle::Cirrus) 

enum class ECloudStyle : uint8;
template<> struct TIsUEnumClass<ECloudStyle> { enum { Value = true }; };
template<> UE_NODEBUG CLOUDGENERATORTOOLS_NON_ATTRIBUTED_API UEnum* StaticEnum<ECloudStyle>();
// ********** End Enum ECloudStyle *****************************************************************

// ********** Begin Enum ECloudBillowStyle *********************************************************
#define FOREACH_ENUM_ECLOUDBILLOWSTYLE(op) \
	op(ECloudBillowStyle::Classic) \
	op(ECloudBillowStyle::Cauliflower) \
	op(ECloudBillowStyle::SoftRolling) \
	op(ECloudBillowStyle::Turbulent) 

enum class ECloudBillowStyle : uint8;
template<> struct TIsUEnumClass<ECloudBillowStyle> { enum { Value = true }; };
template<> UE_NODEBUG CLOUDGENERATORTOOLS_NON_ATTRIBUTED_API UEnum* StaticEnum<ECloudBillowStyle>();
// ********** End Enum ECloudBillowStyle ***********************************************************

// ********** Begin Enum ECloudNoiseLayout *********************************************************
#define FOREACH_ENUM_ECLOUDNOISELAYOUT(op) \
	op(ECloudNoiseLayout::PackedRGB) \
	op(ECloudNoiseLayout::Grayscale) 

enum class ECloudNoiseLayout : uint8;
template<> struct TIsUEnumClass<ECloudNoiseLayout> { enum { Value = true }; };
template<> UE_NODEBUG CLOUDGENERATORTOOLS_NON_ATTRIBUTED_API UEnum* StaticEnum<ECloudNoiseLayout>();
// ********** End Enum ECloudNoiseLayout ***********************************************************

PRAGMA_ENABLE_DEPRECATION_WARNINGS
