// Copyright Epic Games, Inc. All Rights Reserved.
/*===========================================================================
	Generated code exported from UnrealHeaderTool.
	DO NOT modify this manually! Edit the corresponding .h files instead!
===========================================================================*/

#include "UObject/GeneratedCppIncludes.h"
#include "QuickWidgetToolsFXWidget.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS
static_assert(!UE_WITH_CONSTINIT_UOBJECT, "This generated code can only be compiled with !UE_WITH_CONSTINIT_UOBJECT");
void EmptyLinkFunctionForGeneratedCodeQuickWidgetToolsFXWidget() {}

// ********** Begin Cross Module References ********************************************************
BLUTILITY_API UClass* Z_Construct_UClass_UEditorUtilityWidget(ETypeConstructPhase);
// ********** End Cross Module References **********************************************************

// ********** Begin Same Module References *********************************************************
UPackage* Z_Construct_UPackage__Script_QuickWidgetTools(ETypeConstructPhase);
QUICKWIDGETTOOLS_API UClass* Z_Construct_UClass_UQuickWidgetToolsFXWidget(ETypeConstructPhase);
QUICKWIDGETTOOLS_API UClass* Z_Construct_UClass_UQuickWidgetToolsFXWidget(ETypeConstructPhase);
// ********** End Same Module References ***********************************************************
#define UHT_STRUCT_BASE(INIT) UE::CodeGen::ConstInit::TCompiledInObjectPtr<const FStructBaseChain>(UE::Private::AsStructBaseChain(INIT))

// ********** Begin Class UQuickWidgetToolsFXWidget ************************************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UClass_UQuickWidgetToolsFXWidget_Statics
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "Comment", "/** One-click FX utilities exposed through the Quick Widget Tools menu. */" },
		{ "IncludePath", "QuickWidgetToolsFXWidget.h" },
		{ "ModuleRelativePath", "Public/QuickWidgetToolsFXWidget.h" },
		{ "ToolTip", "One-click FX utilities exposed through the Quick Widget Tools menu." },
	};
#endif // WITH_METADATA

// ********** Begin Class UQuickWidgetToolsFXWidget constinit property declarations ****************
// ********** End Class UQuickWidgetToolsFXWidget constinit property declarations ******************
	static FTypeConstructFunc* DependentSingletons[];
	static constexpr FCppClassTypeInfoStatic StaticCppClassTypeInfo = {
		TCppClassTypeTraits<UQuickWidgetToolsFXWidget>::IsAbstract,
	};
	static const UECodeGen_Private::FClassParams ClassParams;
}; // struct UHT_STATICS
FTypeConstructFunc* UHT_STATICS::DependentSingletons[] = {
	(FTypeConstructFunc*)Z_Construct_UClass_UEditorUtilityWidget,
	(FTypeConstructFunc*)Z_Construct_UPackage__Script_QuickWidgetTools,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::DependentSingletons) < 16);
const UECodeGen_Private::FClassParams UHT_STATICS::ClassParams = {
	&Z_Construct_UClass_UQuickWidgetToolsFXWidget,
	"Editor",
	&StaticCppClassTypeInfo,
	DependentSingletons,
	nullptr,
	nullptr,
	nullptr,
	UE_ARRAY_COUNT(DependentSingletons),
	0,
	0,
	0,
	0x00B010A4u,
	METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)
};
FClassRegistrationInfo Z_Registration_Info_UClass_UQuickWidgetToolsFXWidget;
UClass* Z_Construct_UClass_UQuickWidgetToolsFXWidget(ETypeConstructPhase Phase)
{
	if (Phase == ETypeConstructPhase::Inner)
	{
		using TClass = UQuickWidgetToolsFXWidget;
		if (!Z_Registration_Info_UClass_UQuickWidgetToolsFXWidget.InnerSingleton)
		{
			GetPrivateStaticClassBody(
				TClass::StaticPackage(),
				TEXT("QuickWidgetToolsFXWidget"),
				Z_Registration_Info_UClass_UQuickWidgetToolsFXWidget.InnerSingleton,
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
		return Z_Registration_Info_UClass_UQuickWidgetToolsFXWidget.InnerSingleton;
	}
	if (!Z_Registration_Info_UClass_UQuickWidgetToolsFXWidget.OuterSingleton)
	{
		UECodeGen_Private::ConstructUClass(Z_Registration_Info_UClass_UQuickWidgetToolsFXWidget.OuterSingleton, UHT_STATICS::ClassParams);
	}
	return Z_Registration_Info_UClass_UQuickWidgetToolsFXWidget.OuterSingleton;
}
#undef UHT_STATICS
UQuickWidgetToolsFXWidget::UQuickWidgetToolsFXWidget(const FObjectInitializer& ObjectInitializer) : Super(ObjectInitializer) {}
DEFINE_VTABLE_PTR_HELPER_CTOR_NS(, UQuickWidgetToolsFXWidget);
UQuickWidgetToolsFXWidget::~UQuickWidgetToolsFXWidget() {}
// ********** End Class UQuickWidgetToolsFXWidget **************************************************

// ********** Begin Registration *******************************************************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_CompiledInDeferFile_FID_HostProject_Plugins_QuickWidgetTools_Source_QuickWidgetTools_Public_QuickWidgetToolsFXWidget_h__Script_QuickWidgetTools_Statics
struct UHT_STATICS
{
	static constexpr FClassRegisterCompiledInInfo ClassInfo[] = {
		{ Z_Construct_UClass_UQuickWidgetToolsFXWidget, TEXT("UQuickWidgetToolsFXWidget"), &Z_Registration_Info_UClass_UQuickWidgetToolsFXWidget, CONSTRUCT_RELOAD_VERSION_INFO(FClassReloadVersionInfo, sizeof(UQuickWidgetToolsFXWidget), 3613860958U) },
	};
}; // UHT_STATICS 
static FRegisterCompiledInInfo Z_CompiledInDeferFile_FID_HostProject_Plugins_QuickWidgetTools_Source_QuickWidgetTools_Public_QuickWidgetToolsFXWidget_h__Script_QuickWidgetTools_c81d8615cc919c5e084baccb92bc940831a895cd{
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
