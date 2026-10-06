// Copyright Epic Games, Inc. All Rights Reserved.
/*===========================================================================
	Generated code exported from UnrealHeaderTool.
	DO NOT modify this manually! Edit the corresponding .h files instead!
===========================================================================*/

#include "UObject/GeneratedCppIncludes.h"
#include "QuickWidgetToolsNiagaraLibrary.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS
static_assert(!UE_WITH_CONSTINIT_UOBJECT, "This generated code can only be compiled with !UE_WITH_CONSTINIT_UOBJECT");
void EmptyLinkFunctionForGeneratedCodeQuickWidgetToolsNiagaraLibrary() {}

// ********** Begin Cross Module References ********************************************************
ENGINE_API UClass* Z_Construct_UClass_UBlueprintFunctionLibrary(ETypeConstructPhase);
// ********** End Cross Module References **********************************************************

// ********** Begin Same Module References *********************************************************
UPackage* Z_Construct_UPackage__Script_QuickWidgetTools(ETypeConstructPhase);
QUICKWIDGETTOOLS_API UClass* Z_Construct_UClass_UQuickWidgetToolsNiagaraLibrary(ETypeConstructPhase);
QUICKWIDGETTOOLS_API UClass* Z_Construct_UClass_UQuickWidgetToolsNiagaraLibrary(ETypeConstructPhase);
// ********** End Same Module References ***********************************************************
#define UHT_STRUCT_BASE(INIT) UE::CodeGen::ConstInit::TCompiledInObjectPtr<const FStructBaseChain>(UE::Private::AsStructBaseChain(INIT))

// ********** Begin Class UQuickWidgetToolsNiagaraLibrary Function BakeSelectedNiagaraSimCacheToCurrentSequence 
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_UQuickWidgetToolsNiagaraLibrary_BakeSelectedNiagaraSimCacheToCurrentSequence_Statics
struct UHT_STATICS
{
	struct QuickWidgetToolsNiagaraLibrary_eventBakeSelectedNiagaraSimCacheToCurrentSequence_Parms
	{
		FText OutMessage;
		bool ReturnValue;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "CallInEditor", "true" },
		{ "Category", "Quick Widget Tools|Niagara" },
		{ "Comment", "/**\n\x09 * Clears and records Niagara Sim Caches for every Niagara component on the\n\x09 * single selected actor into the Level Sequence currently focused in Sequencer.\n\x09 */" },
		{ "ModuleRelativePath", "Public/QuickWidgetToolsNiagaraLibrary.h" },
		{ "ToolTip", "Clears and records Niagara Sim Caches for every Niagara component on the\nsingle selected actor into the Level Sequence currently focused in Sequencer." },
	};
#endif // WITH_METADATA

// ********** Begin Function BakeSelectedNiagaraSimCacheToCurrentSequence constinit property declarations 
	static const UECodeGen_Private::FTextPropertyParams NewProp_OutMessage;
	static void NewProp_ReturnValue_SetBit(void* Obj)
	{
		((QuickWidgetToolsNiagaraLibrary_eventBakeSelectedNiagaraSimCacheToCurrentSequence_Parms*)Obj)->ReturnValue = 1;
	}
	static const UECodeGen_Private::FBoolPropertyParams NewProp_ReturnValue;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
// ********** End Function BakeSelectedNiagaraSimCacheToCurrentSequence constinit property declarations 
	static const UECodeGen_Private::FFunctionParams FuncParams;
};

// ********** Begin Function BakeSelectedNiagaraSimCacheToCurrentSequence Property Definitions *****
const UECodeGen_Private::FTextPropertyParams UHT_STATICS::NewProp_OutMessage = { "OutMessage", nullptr, (EPropertyFlags)0x0010000000000180, UECodeGen_Private::EPropertyGenFlags::Text, nullptr, nullptr, 1, STRUCT_OFFSET(QuickWidgetToolsNiagaraLibrary_eventBakeSelectedNiagaraSimCacheToCurrentSequence_Parms, OutMessage), METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FBoolPropertyParams UHT_STATICS::NewProp_ReturnValue = { "ReturnValue", nullptr, (EPropertyFlags)0x0010000000000580, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, nullptr, nullptr, 1, sizeof(bool), sizeof(QuickWidgetToolsNiagaraLibrary_eventBakeSelectedNiagaraSimCacheToCurrentSequence_Parms), &UHT_STATICS::NewProp_ReturnValue_SetBit, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FPropertyParamsBase* const UHT_STATICS::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_OutMessage,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ReturnValue,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::PropPointers) < 2048);
// ********** End Function BakeSelectedNiagaraSimCacheToCurrentSequence Property Definitions *******
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_UQuickWidgetToolsNiagaraLibrary, nullptr, "BakeSelectedNiagaraSimCacheToCurrentSequence", UHT_STATICS::PropPointers, UE_ARRAY_COUNT(UHT_STATICS::PropPointers), DataSizeOf<UHT_STATICS::QuickWidgetToolsNiagaraLibrary_eventBakeSelectedNiagaraSimCacheToCurrentSequence_Parms>(), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04422401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
static_assert(sizeof(UHT_STATICS::QuickWidgetToolsNiagaraLibrary_eventBakeSelectedNiagaraSimCacheToCurrentSequence_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_UQuickWidgetToolsNiagaraLibrary_BakeSelectedNiagaraSimCacheToCurrentSequence(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(UQuickWidgetToolsNiagaraLibrary::execBakeSelectedNiagaraSimCacheToCurrentSequence)
{
	P_GET_PROPERTY_REF(FTextProperty,Z_Param_Out_OutMessage);
	P_FINISH;
	P_NATIVE_BEGIN;
	*(bool*)Z_Param__Result=UQuickWidgetToolsNiagaraLibrary::BakeSelectedNiagaraSimCacheToCurrentSequence(Z_Param_Out_OutMessage);
	P_NATIVE_END;
}
// ********** End Class UQuickWidgetToolsNiagaraLibrary Function BakeSelectedNiagaraSimCacheToCurrentSequence 

// ********** Begin Class UQuickWidgetToolsNiagaraLibrary ******************************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UClass_UQuickWidgetToolsNiagaraLibrary_Statics
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "Comment", "/** Editor-only helpers used by the Quick Widget Tools Niagara UI. */" },
		{ "IncludePath", "QuickWidgetToolsNiagaraLibrary.h" },
		{ "ModuleRelativePath", "Public/QuickWidgetToolsNiagaraLibrary.h" },
		{ "ToolTip", "Editor-only helpers used by the Quick Widget Tools Niagara UI." },
	};
#endif // WITH_METADATA

// ********** Begin Class UQuickWidgetToolsNiagaraLibrary constinit property declarations **********
// ********** End Class UQuickWidgetToolsNiagaraLibrary constinit property declarations ************
	static constexpr UE::CodeGen::FClassNativeFunction Funcs[] = {
		{ .NameUTF8 = UTF8TEXT("BakeSelectedNiagaraSimCacheToCurrentSequence"), .Pointer = &UQuickWidgetToolsNiagaraLibrary::execBakeSelectedNiagaraSimCacheToCurrentSequence },
	};
	static FTypeConstructFunc* DependentSingletons[];
	static constexpr FClassFunctionLinkInfo FuncInfo[] = {
		{ &Z_Construct_UFunction_UQuickWidgetToolsNiagaraLibrary_BakeSelectedNiagaraSimCacheToCurrentSequence, "BakeSelectedNiagaraSimCacheToCurrentSequence" }, // 439aae95b36c8bf1fbb6b1d040ede97d0d934a10
	};
	static_assert(UE_ARRAY_COUNT(FuncInfo) < 2048);
	static constexpr FCppClassTypeInfoStatic StaticCppClassTypeInfo = {
		TCppClassTypeTraits<UQuickWidgetToolsNiagaraLibrary>::IsAbstract,
	};
	static const UECodeGen_Private::FClassParams ClassParams;
}; // struct UHT_STATICS
FTypeConstructFunc* UHT_STATICS::DependentSingletons[] = {
	(FTypeConstructFunc*)Z_Construct_UClass_UBlueprintFunctionLibrary,
	(FTypeConstructFunc*)Z_Construct_UPackage__Script_QuickWidgetTools,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::DependentSingletons) < 16);
const UECodeGen_Private::FClassParams UHT_STATICS::ClassParams = {
	&Z_Construct_UClass_UQuickWidgetToolsNiagaraLibrary,
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
static void UQuickWidgetToolsNiagaraLibrary_StaticRegisterNativesUQuickWidgetToolsNiagaraLibrary()
{
	UClass* Class = UQuickWidgetToolsNiagaraLibrary::StaticClass();
	FNativeFunctionRegistrar::RegisterFunctions(Class, 		MakeConstArrayView(UHT_STATICS::Funcs));
}
FClassRegistrationInfo Z_Registration_Info_UClass_UQuickWidgetToolsNiagaraLibrary;
UClass* Z_Construct_UClass_UQuickWidgetToolsNiagaraLibrary(ETypeConstructPhase Phase)
{
	if (Phase == ETypeConstructPhase::Inner)
	{
		using TClass = UQuickWidgetToolsNiagaraLibrary;
		if (!Z_Registration_Info_UClass_UQuickWidgetToolsNiagaraLibrary.InnerSingleton)
		{
			GetPrivateStaticClassBody(
				TClass::StaticPackage(),
				TEXT("QuickWidgetToolsNiagaraLibrary"),
				Z_Registration_Info_UClass_UQuickWidgetToolsNiagaraLibrary.InnerSingleton,
				UQuickWidgetToolsNiagaraLibrary_StaticRegisterNativesUQuickWidgetToolsNiagaraLibrary,
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
		return Z_Registration_Info_UClass_UQuickWidgetToolsNiagaraLibrary.InnerSingleton;
	}
	if (!Z_Registration_Info_UClass_UQuickWidgetToolsNiagaraLibrary.OuterSingleton)
	{
		UECodeGen_Private::ConstructUClass(Z_Registration_Info_UClass_UQuickWidgetToolsNiagaraLibrary.OuterSingleton, UHT_STATICS::ClassParams);
	}
	return Z_Registration_Info_UClass_UQuickWidgetToolsNiagaraLibrary.OuterSingleton;
}
#undef UHT_STATICS
UQuickWidgetToolsNiagaraLibrary::UQuickWidgetToolsNiagaraLibrary(const FObjectInitializer& ObjectInitializer) : Super(ObjectInitializer) {}
DEFINE_VTABLE_PTR_HELPER_CTOR_NS(, UQuickWidgetToolsNiagaraLibrary);
UQuickWidgetToolsNiagaraLibrary::~UQuickWidgetToolsNiagaraLibrary() {}
// ********** End Class UQuickWidgetToolsNiagaraLibrary ********************************************

// ********** Begin Registration *******************************************************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_CompiledInDeferFile_FID_HostProject_Plugins_QuickWidgetTools_Source_QuickWidgetTools_Public_QuickWidgetToolsNiagaraLibrary_h__Script_QuickWidgetTools_Statics
struct UHT_STATICS
{
	static constexpr FClassRegisterCompiledInInfo ClassInfo[] = {
		{ Z_Construct_UClass_UQuickWidgetToolsNiagaraLibrary, TEXT("UQuickWidgetToolsNiagaraLibrary"), &Z_Registration_Info_UClass_UQuickWidgetToolsNiagaraLibrary, CONSTRUCT_RELOAD_VERSION_INFO(FClassReloadVersionInfo, sizeof(UQuickWidgetToolsNiagaraLibrary), 503898253U) },
	};
}; // UHT_STATICS 
static FRegisterCompiledInInfo Z_CompiledInDeferFile_FID_HostProject_Plugins_QuickWidgetTools_Source_QuickWidgetTools_Public_QuickWidgetToolsNiagaraLibrary_h__Script_QuickWidgetTools_bd151c7940bfd1a4a162a08199df972bbf45738d{
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
