// Copyright Epic Games, Inc. All Rights Reserved.
/*===========================================================================
	Generated code exported from UnrealHeaderTool.
	DO NOT modify this manually! Edit the corresponding .h files instead!
===========================================================================*/

#include "UObject/GeneratedCppIncludes.h"
#include "OnlyCloudsEditorLibrary.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS
static_assert(!UE_WITH_CONSTINIT_UOBJECT, "This generated code can only be compiled with !UE_WITH_CONSTINIT_UOBJECT");
void EmptyLinkFunctionForGeneratedCodeOnlyCloudsEditorLibrary() {}

// ********** Begin Cross Module References ********************************************************
ENGINE_API UClass* Z_Construct_UClass_UBlueprintFunctionLibrary(ETypeConstructPhase);
ENGINE_API UClass* Z_Construct_UClass_AActor(ETypeConstructPhase);
// ********** End Cross Module References **********************************************************

// ********** Begin Same Module References *********************************************************
UPackage* Z_Construct_UPackage__Script_OnlyCloudsEditor(ETypeConstructPhase);
ONLYCLOUDSEDITOR_API UScriptStruct* Z_Construct_UScriptStruct_FOnlyCloudsEditorActionResult(ETypeConstructPhase);
ONLYCLOUDSEDITOR_API UClass* Z_Construct_UClass_UOnlyCloudsEditorLibrary(ETypeConstructPhase);
ONLYCLOUDSEDITOR_API UClass* Z_Construct_UClass_UOnlyCloudsEditorLibrary(ETypeConstructPhase);
// ********** End Same Module References ***********************************************************
#define UHT_STRUCT_BASE(INIT) UE::CodeGen::ConstInit::TCompiledInObjectPtr<const FStructBaseChain>(UE::Private::AsStructBaseChain(INIT))

// ********** Begin ScriptStruct FOnlyCloudsEditorActionResult *************************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UScriptStruct_FOnlyCloudsEditorActionResult_Statics
struct UHT_STATICS
{
	static inline consteval int32 GetStructSize() { return DataSizeOf<FOnlyCloudsEditorActionResult>(); }
	static inline consteval int16 GetStructAlignment() { return alignof(FOnlyCloudsEditorActionResult); }
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "BlueprintType", "true" },
		{ "Comment", "/** Result of one explicitly invoked OnlyClouds editor action. */" },
		{ "ModuleRelativePath", "Public/OnlyCloudsEditorLibrary.h" },
		{ "ToolTip", "Result of one explicitly invoked OnlyClouds editor action." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_bSuccess_MetaData[] = {
		{ "Category", "OnlyClouds" },
		{ "ModuleRelativePath", "Public/OnlyCloudsEditorLibrary.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_bCreated_MetaData[] = {
		{ "Category", "OnlyClouds" },
		{ "Comment", "/** False when an existing world-cloud actor was selected without spawning another. */" },
		{ "ModuleRelativePath", "Public/OnlyCloudsEditorLibrary.h" },
		{ "ToolTip", "False when an existing world-cloud actor was selected without spawning another." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Message_MetaData[] = {
		{ "Category", "OnlyClouds" },
		{ "ModuleRelativePath", "Public/OnlyCloudsEditorLibrary.h" },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Actors_MetaData[] = {
		{ "Category", "OnlyClouds" },
		{ "Comment", "/** New actors, or the existing cloud controller selected by a repeated Add action. */" },
		{ "ModuleRelativePath", "Public/OnlyCloudsEditorLibrary.h" },
		{ "ToolTip", "New actors, or the existing cloud controller selected by a repeated Add action." },
	};
#endif // WITH_METADATA

// ********** Begin ScriptStruct FOnlyCloudsEditorActionResult constinit property declarations *****
	static void NewProp_bSuccess_SetBit(void* Obj)
	{
		((FOnlyCloudsEditorActionResult*)Obj)->bSuccess = 1;
	}
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bSuccess;
	static void NewProp_bCreated_SetBit(void* Obj)
	{
		((FOnlyCloudsEditorActionResult*)Obj)->bCreated = 1;
	}
	static const UECodeGen_Private::FBoolPropertyParams NewProp_bCreated;
	static const UECodeGen_Private::FStrPropertyParams NewProp_Message;
	static const UECodeGen_Private::FObjectPropertyParams NewProp_Actors_Inner;
	static const UECodeGen_Private::FArrayPropertyParams NewProp_Actors;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
// ********** End ScriptStruct FOnlyCloudsEditorActionResult constinit property declarations *******
	static void* NewStructOps()
	{
		return (UScriptStruct::ICppStructOps*)new UScriptStruct::TCppStructOps<FOnlyCloudsEditorActionResult>();
	}
	static const UECodeGen_Private::FStructParams StructParams;
}; // struct UHT_STATICS

// ********** Begin ScriptStruct FOnlyCloudsEditorActionResult Property Definitions ****************
const UECodeGen_Private::FBoolPropertyParams UHT_STATICS::NewProp_bSuccess = { "bSuccess", nullptr, (EPropertyFlags)0x0010000000000014, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, nullptr, nullptr, 1, sizeof(bool), sizeof(FOnlyCloudsEditorActionResult), &UHT_STATICS::NewProp_bSuccess_SetBit, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_bSuccess_MetaData), NewProp_bSuccess_MetaData) };
const UECodeGen_Private::FBoolPropertyParams UHT_STATICS::NewProp_bCreated = { "bCreated", nullptr, (EPropertyFlags)0x0010000000000014, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, nullptr, nullptr, 1, sizeof(bool), sizeof(FOnlyCloudsEditorActionResult), &UHT_STATICS::NewProp_bCreated_SetBit, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_bCreated_MetaData), NewProp_bCreated_MetaData) };
const UECodeGen_Private::FStrPropertyParams UHT_STATICS::NewProp_Message = { "Message", nullptr, (EPropertyFlags)0x0010000000000014, UECodeGen_Private::EPropertyGenFlags::Str, nullptr, nullptr, 1, STRUCT_OFFSET(FOnlyCloudsEditorActionResult, Message), METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Message_MetaData), NewProp_Message_MetaData) };
const UECodeGen_Private::FObjectPropertyParams UHT_STATICS::NewProp_Actors_Inner = { "Actors", nullptr, (EPropertyFlags)0x0104000000000000, UECodeGen_Private::EPropertyGenFlags::Object | UECodeGen_Private::EPropertyGenFlags::ObjectPtr, nullptr, nullptr, 1, 0, Z_Construct_UClass_AActor, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FArrayPropertyParams UHT_STATICS::NewProp_Actors = { "Actors", nullptr, (EPropertyFlags)0x0114000000000014, UECodeGen_Private::EPropertyGenFlags::Array, nullptr, nullptr, 1, STRUCT_OFFSET(FOnlyCloudsEditorActionResult, Actors), EArrayPropertyFlags::None, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Actors_MetaData), NewProp_Actors_MetaData) };
const UECodeGen_Private::FPropertyParamsBase* const UHT_STATICS::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_bSuccess,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_bCreated,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Message,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Actors_Inner,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Actors,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::PropPointers) < 2048);
// ********** End ScriptStruct FOnlyCloudsEditorActionResult Property Definitions ******************
const UECodeGen_Private::FStructParams UHT_STATICS::StructParams = {
	(FTypeConstructFunc*)Z_Construct_UPackage__Script_OnlyCloudsEditor,
	nullptr,
	&NewStructOps,
	"OnlyCloudsEditorActionResult",
	UHT_STATICS::PropPointers,
	UE_ARRAY_COUNT(UHT_STATICS::PropPointers),
	DataSizeOf<FOnlyCloudsEditorActionResult>(),
	alignof(FOnlyCloudsEditorActionResult),
	RF_Public|RF_Transient|RF_MarkAsNative,
	EStructFlags(0x00000201),
	METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)
};
static FStructRegistrationInfo Z_Registration_Info_UScriptStruct_FOnlyCloudsEditorActionResult;
UScriptStruct* Z_Construct_UScriptStruct_FOnlyCloudsEditorActionResult(ETypeConstructPhase Phase)
{
	if (Phase == ETypeConstructPhase::Outer)
	{
		if (!Z_Registration_Info_UScriptStruct_FOnlyCloudsEditorActionResult.OuterSingleton)
		{
			Z_Registration_Info_UScriptStruct_FOnlyCloudsEditorActionResult.OuterSingleton = GetStaticStruct(Z_Construct_UScriptStruct_FOnlyCloudsEditorActionResult, (UObject*)Z_Construct_UPackage__Script_OnlyCloudsEditor(ETypeConstructPhase::Outer), TEXT("OnlyCloudsEditorActionResult"));
		}
		return Z_Registration_Info_UScriptStruct_FOnlyCloudsEditorActionResult.OuterSingleton;
	}
	if (!Z_Registration_Info_UScriptStruct_FOnlyCloudsEditorActionResult.InnerSingleton)
	{
		UECodeGen_Private::ConstructUScriptStruct(Z_Registration_Info_UScriptStruct_FOnlyCloudsEditorActionResult.InnerSingleton, UHT_STATICS::StructParams);
	}
	return CastChecked<UScriptStruct>(Z_Registration_Info_UScriptStruct_FOnlyCloudsEditorActionResult.InnerSingleton);
}
#undef UHT_STATICS
// ********** End ScriptStruct FOnlyCloudsEditorActionResult ***************************************

// ********** Begin Class UOnlyCloudsEditorLibrary Function AddBasicLightRigg **********************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_UOnlyCloudsEditorLibrary_AddBasicLightRigg_Statics
struct UHT_STATICS
{
	struct OnlyCloudsEditorLibrary_eventAddBasicLightRigg_Parms
	{
		FOnlyCloudsEditorActionResult ReturnValue;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "Category", "OnlyClouds|Editor" },
		{ "Comment", "/** Copies the six saved rig actor templates into the active level in one undoable transaction. */" },
		{ "DisplayName", "Add Basic Light Rigg" },
		{ "ModuleRelativePath", "Public/OnlyCloudsEditorLibrary.h" },
		{ "ToolTip", "Copies the six saved rig actor templates into the active level in one undoable transaction." },
	};
#endif // WITH_METADATA

// ********** Begin Function AddBasicLightRigg constinit property declarations *********************
	static const UECodeGen_Private::FStructPropertyParams NewProp_ReturnValue;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
// ********** End Function AddBasicLightRigg constinit property declarations ***********************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};

// ********** Begin Function AddBasicLightRigg Property Definitions ********************************
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_ReturnValue = { "ReturnValue", nullptr, (EPropertyFlags)0x0010000000000580, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, STRUCT_OFFSET(OnlyCloudsEditorLibrary_eventAddBasicLightRigg_Parms, ReturnValue), Z_Construct_UScriptStruct_FOnlyCloudsEditorActionResult, METADATA_PARAMS(0, nullptr) }; // 191130fa04dd24e65269442c820aded00b0f9f17
const UECodeGen_Private::FPropertyParamsBase* const UHT_STATICS::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ReturnValue,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::PropPointers) < 2048);
// ********** End Function AddBasicLightRigg Property Definitions **********************************
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_UOnlyCloudsEditorLibrary, nullptr, "AddBasicLightRigg", UHT_STATICS::PropPointers, UE_ARRAY_COUNT(UHT_STATICS::PropPointers), DataSizeOf<UHT_STATICS::OnlyCloudsEditorLibrary_eventAddBasicLightRigg_Parms>(), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04022401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
static_assert(sizeof(UHT_STATICS::OnlyCloudsEditorLibrary_eventAddBasicLightRigg_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_UOnlyCloudsEditorLibrary_AddBasicLightRigg(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(UOnlyCloudsEditorLibrary::execAddBasicLightRigg)
{
	P_FINISH;
	P_NATIVE_BEGIN;
	*(FOnlyCloudsEditorActionResult*)Z_Param__Result=UOnlyCloudsEditorLibrary::AddBasicLightRigg();
	P_NATIVE_END;
}
// ********** End Class UOnlyCloudsEditorLibrary Function AddBasicLightRigg ************************

// ********** Begin Class UOnlyCloudsEditorLibrary Function AddCloudPreset *************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_UOnlyCloudsEditorLibrary_AddCloudPreset_Statics
struct UHT_STATICS
{
	struct OnlyCloudsEditorLibrary_eventAddCloudPreset_Parms
	{
		FOnlyCloudsEditorActionResult ReturnValue;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "Category", "OnlyClouds|Editor" },
		{ "Comment", "/** Adds the placed-cloud Blueprint at the origin with the saved Cumulus recipe and its guide actors. */" },
		{ "DisplayName", "Add Cloud Preset" },
		{ "ModuleRelativePath", "Public/OnlyCloudsEditorLibrary.h" },
		{ "ToolTip", "Adds the placed-cloud Blueprint at the origin with the saved Cumulus recipe and its guide actors." },
	};
#endif // WITH_METADATA

// ********** Begin Function AddCloudPreset constinit property declarations ************************
	static const UECodeGen_Private::FStructPropertyParams NewProp_ReturnValue;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
// ********** End Function AddCloudPreset constinit property declarations **************************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};

// ********** Begin Function AddCloudPreset Property Definitions ***********************************
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_ReturnValue = { "ReturnValue", nullptr, (EPropertyFlags)0x0010000000000580, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, STRUCT_OFFSET(OnlyCloudsEditorLibrary_eventAddCloudPreset_Parms, ReturnValue), Z_Construct_UScriptStruct_FOnlyCloudsEditorActionResult, METADATA_PARAMS(0, nullptr) }; // 191130fa04dd24e65269442c820aded00b0f9f17
const UECodeGen_Private::FPropertyParamsBase* const UHT_STATICS::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ReturnValue,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::PropPointers) < 2048);
// ********** End Function AddCloudPreset Property Definitions *************************************
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_UOnlyCloudsEditorLibrary, nullptr, "AddCloudPreset", UHT_STATICS::PropPointers, UE_ARRAY_COUNT(UHT_STATICS::PropPointers), DataSizeOf<UHT_STATICS::OnlyCloudsEditorLibrary_eventAddCloudPreset_Parms>(), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04022401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
static_assert(sizeof(UHT_STATICS::OnlyCloudsEditorLibrary_eventAddCloudPreset_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_UOnlyCloudsEditorLibrary_AddCloudPreset(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(UOnlyCloudsEditorLibrary::execAddCloudPreset)
{
	P_FINISH;
	P_NATIVE_BEGIN;
	*(FOnlyCloudsEditorActionResult*)Z_Param__Result=UOnlyCloudsEditorLibrary::AddCloudPreset();
	P_NATIVE_END;
}
// ********** End Class UOnlyCloudsEditorLibrary Function AddCloudPreset ***************************

// ********** Begin Class UOnlyCloudsEditorLibrary Function AddLayeredWorldClouds ******************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_UOnlyCloudsEditorLibrary_AddLayeredWorldClouds_Statics
struct UHT_STATICS
{
	struct OnlyCloudsEditorLibrary_eventAddLayeredWorldClouds_Parms
	{
		FOnlyCloudsEditorActionResult ReturnValue;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "Category", "OnlyClouds|Editor" },
		{ "Comment", "/** Adds the plugin world-cloud tool at the origin, unless another visible world-cloud renderer exists. */" },
		{ "DisplayName", "Add Layered World Clouds" },
		{ "ModuleRelativePath", "Public/OnlyCloudsEditorLibrary.h" },
		{ "ToolTip", "Adds the plugin world-cloud tool at the origin, unless another visible world-cloud renderer exists." },
	};
#endif // WITH_METADATA

// ********** Begin Function AddLayeredWorldClouds constinit property declarations *****************
	static const UECodeGen_Private::FStructPropertyParams NewProp_ReturnValue;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
// ********** End Function AddLayeredWorldClouds constinit property declarations *******************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};

// ********** Begin Function AddLayeredWorldClouds Property Definitions ****************************
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_ReturnValue = { "ReturnValue", nullptr, (EPropertyFlags)0x0010000000000580, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, STRUCT_OFFSET(OnlyCloudsEditorLibrary_eventAddLayeredWorldClouds_Parms, ReturnValue), Z_Construct_UScriptStruct_FOnlyCloudsEditorActionResult, METADATA_PARAMS(0, nullptr) }; // 191130fa04dd24e65269442c820aded00b0f9f17
const UECodeGen_Private::FPropertyParamsBase* const UHT_STATICS::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ReturnValue,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::PropPointers) < 2048);
// ********** End Function AddLayeredWorldClouds Property Definitions ******************************
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_UOnlyCloudsEditorLibrary, nullptr, "AddLayeredWorldClouds", UHT_STATICS::PropPointers, UE_ARRAY_COUNT(UHT_STATICS::PropPointers), DataSizeOf<UHT_STATICS::OnlyCloudsEditorLibrary_eventAddLayeredWorldClouds_Parms>(), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04022401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
static_assert(sizeof(UHT_STATICS::OnlyCloudsEditorLibrary_eventAddLayeredWorldClouds_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_UOnlyCloudsEditorLibrary_AddLayeredWorldClouds(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(UOnlyCloudsEditorLibrary::execAddLayeredWorldClouds)
{
	P_FINISH;
	P_NATIVE_BEGIN;
	*(FOnlyCloudsEditorActionResult*)Z_Param__Result=UOnlyCloudsEditorLibrary::AddLayeredWorldClouds();
	P_NATIVE_END;
}
// ********** End Class UOnlyCloudsEditorLibrary Function AddLayeredWorldClouds ********************

// ********** Begin Class UOnlyCloudsEditorLibrary Function DescribeRegisteredMenu *****************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_UOnlyCloudsEditorLibrary_DescribeRegisteredMenu_Statics
struct UHT_STATICS
{
	struct OnlyCloudsEditorLibrary_eventDescribeRegisteredMenu_Parms
	{
		FString ReturnValue;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "Category", "OnlyClouds|Validation" },
		{ "Comment", "/** Read-only JSON description of the internal action menu and Quick Widget Tools entry point. */" },
		{ "ModuleRelativePath", "Public/OnlyCloudsEditorLibrary.h" },
		{ "ToolTip", "Read-only JSON description of the internal action menu and Quick Widget Tools entry point." },
	};
#endif // WITH_METADATA

// ********** Begin Function DescribeRegisteredMenu constinit property declarations ****************
	static const UECodeGen_Private::FStrPropertyParams NewProp_ReturnValue;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
// ********** End Function DescribeRegisteredMenu constinit property declarations ******************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};

// ********** Begin Function DescribeRegisteredMenu Property Definitions ***************************
const UECodeGen_Private::FStrPropertyParams UHT_STATICS::NewProp_ReturnValue = { "ReturnValue", nullptr, (EPropertyFlags)0x0010000000000580, UECodeGen_Private::EPropertyGenFlags::Str, nullptr, nullptr, 1, STRUCT_OFFSET(OnlyCloudsEditorLibrary_eventDescribeRegisteredMenu_Parms, ReturnValue), METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FPropertyParamsBase* const UHT_STATICS::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ReturnValue,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::PropPointers) < 2048);
// ********** End Function DescribeRegisteredMenu Property Definitions *****************************
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_UOnlyCloudsEditorLibrary, nullptr, "DescribeRegisteredMenu", UHT_STATICS::PropPointers, UE_ARRAY_COUNT(UHT_STATICS::PropPointers), DataSizeOf<UHT_STATICS::OnlyCloudsEditorLibrary_eventDescribeRegisteredMenu_Parms>(), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04022401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
static_assert(sizeof(UHT_STATICS::OnlyCloudsEditorLibrary_eventDescribeRegisteredMenu_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_UOnlyCloudsEditorLibrary_DescribeRegisteredMenu(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(UOnlyCloudsEditorLibrary::execDescribeRegisteredMenu)
{
	P_FINISH;
	P_NATIVE_BEGIN;
	*(FString*)Z_Param__Result=UOnlyCloudsEditorLibrary::DescribeRegisteredMenu();
	P_NATIVE_END;
}
// ********** End Class UOnlyCloudsEditorLibrary Function DescribeRegisteredMenu *******************

// ********** Begin Class UOnlyCloudsEditorLibrary Function ExecuteRegisteredMenuAction ************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_UOnlyCloudsEditorLibrary_ExecuteRegisteredMenuAction_Statics
struct UHT_STATICS
{
	struct OnlyCloudsEditorLibrary_eventExecuteRegisteredMenuAction_Parms
	{
		FName EntryName;
		FOnlyCloudsEditorActionResult ReturnValue;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "Category", "OnlyClouds|Validation" },
		{ "Comment", "/** Dispatches the registered internal action delegate, retained for validation and scripting. */" },
		{ "ModuleRelativePath", "Public/OnlyCloudsEditorLibrary.h" },
		{ "ToolTip", "Dispatches the registered internal action delegate, retained for validation and scripting." },
	};
#endif // WITH_METADATA

// ********** Begin Function ExecuteRegisteredMenuAction constinit property declarations ***********
	static const UECodeGen_Private::FNamePropertyParams NewProp_EntryName;
	static const UECodeGen_Private::FStructPropertyParams NewProp_ReturnValue;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
// ********** End Function ExecuteRegisteredMenuAction constinit property declarations *************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};

// ********** Begin Function ExecuteRegisteredMenuAction Property Definitions **********************
const UECodeGen_Private::FNamePropertyParams UHT_STATICS::NewProp_EntryName = { "EntryName", nullptr, (EPropertyFlags)0x0010000000000080, UECodeGen_Private::EPropertyGenFlags::Name, nullptr, nullptr, 1, STRUCT_OFFSET(OnlyCloudsEditorLibrary_eventExecuteRegisteredMenuAction_Parms, EntryName), METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_ReturnValue = { "ReturnValue", nullptr, (EPropertyFlags)0x0010000000000580, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, STRUCT_OFFSET(OnlyCloudsEditorLibrary_eventExecuteRegisteredMenuAction_Parms, ReturnValue), Z_Construct_UScriptStruct_FOnlyCloudsEditorActionResult, METADATA_PARAMS(0, nullptr) }; // 191130fa04dd24e65269442c820aded00b0f9f17
const UECodeGen_Private::FPropertyParamsBase* const UHT_STATICS::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_EntryName,
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ReturnValue,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::PropPointers) < 2048);
// ********** End Function ExecuteRegisteredMenuAction Property Definitions ************************
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_UOnlyCloudsEditorLibrary, nullptr, "ExecuteRegisteredMenuAction", UHT_STATICS::PropPointers, UE_ARRAY_COUNT(UHT_STATICS::PropPointers), DataSizeOf<UHT_STATICS::OnlyCloudsEditorLibrary_eventExecuteRegisteredMenuAction_Parms>(), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04022401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
static_assert(sizeof(UHT_STATICS::OnlyCloudsEditorLibrary_eventExecuteRegisteredMenuAction_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_UOnlyCloudsEditorLibrary_ExecuteRegisteredMenuAction(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(UOnlyCloudsEditorLibrary::execExecuteRegisteredMenuAction)
{
	P_GET_PROPERTY(FNameProperty,Z_Param_EntryName);
	P_FINISH;
	P_NATIVE_BEGIN;
	*(FOnlyCloudsEditorActionResult*)Z_Param__Result=UOnlyCloudsEditorLibrary::ExecuteRegisteredMenuAction(Z_Param_EntryName);
	P_NATIVE_END;
}
// ********** End Class UOnlyCloudsEditorLibrary Function ExecuteRegisteredMenuAction **************

// ********** Begin Class UOnlyCloudsEditorLibrary Function RedoLastEditorTransaction **************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_UOnlyCloudsEditorLibrary_RedoLastEditorTransaction_Statics
struct UHT_STATICS
{
	struct OnlyCloudsEditorLibrary_eventRedoLastEditorTransaction_Parms
	{
		bool ReturnValue;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "Category", "OnlyClouds|Validation" },
		{ "ModuleRelativePath", "Public/OnlyCloudsEditorLibrary.h" },
	};
#endif // WITH_METADATA

// ********** Begin Function RedoLastEditorTransaction constinit property declarations *************
	static void NewProp_ReturnValue_SetBit(void* Obj)
	{
		((OnlyCloudsEditorLibrary_eventRedoLastEditorTransaction_Parms*)Obj)->ReturnValue = 1;
	}
	static const UECodeGen_Private::FBoolPropertyParams NewProp_ReturnValue;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
// ********** End Function RedoLastEditorTransaction constinit property declarations ***************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};

// ********** Begin Function RedoLastEditorTransaction Property Definitions ************************
const UECodeGen_Private::FBoolPropertyParams UHT_STATICS::NewProp_ReturnValue = { "ReturnValue", nullptr, (EPropertyFlags)0x0010000000000580, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, nullptr, nullptr, 1, sizeof(bool), sizeof(OnlyCloudsEditorLibrary_eventRedoLastEditorTransaction_Parms), &UHT_STATICS::NewProp_ReturnValue_SetBit, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FPropertyParamsBase* const UHT_STATICS::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ReturnValue,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::PropPointers) < 2048);
// ********** End Function RedoLastEditorTransaction Property Definitions **************************
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_UOnlyCloudsEditorLibrary, nullptr, "RedoLastEditorTransaction", UHT_STATICS::PropPointers, UE_ARRAY_COUNT(UHT_STATICS::PropPointers), DataSizeOf<UHT_STATICS::OnlyCloudsEditorLibrary_eventRedoLastEditorTransaction_Parms>(), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04022401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
static_assert(sizeof(UHT_STATICS::OnlyCloudsEditorLibrary_eventRedoLastEditorTransaction_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_UOnlyCloudsEditorLibrary_RedoLastEditorTransaction(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(UOnlyCloudsEditorLibrary::execRedoLastEditorTransaction)
{
	P_FINISH;
	P_NATIVE_BEGIN;
	*(bool*)Z_Param__Result=UOnlyCloudsEditorLibrary::RedoLastEditorTransaction();
	P_NATIVE_END;
}
// ********** End Class UOnlyCloudsEditorLibrary Function RedoLastEditorTransaction ****************

// ********** Begin Class UOnlyCloudsEditorLibrary Function ReportActionResult *********************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_UOnlyCloudsEditorLibrary_ReportActionResult_Statics
struct UHT_STATICS
{
	struct OnlyCloudsEditorLibrary_eventReportActionResult_Parms
	{
		FOnlyCloudsEditorActionResult Result;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "Category", "OnlyClouds|Editor" },
		{ "Comment", "/** Shows the same notification and log message used by the original OnlyClouds menu. */" },
		{ "DisplayName", "Report OnlyClouds Action Result" },
		{ "ModuleRelativePath", "Public/OnlyCloudsEditorLibrary.h" },
		{ "ToolTip", "Shows the same notification and log message used by the original OnlyClouds menu." },
	};
	static constexpr UECodeGen_Private::FMetaDataPairParam NewProp_Result_MetaData[] = {
		{ "NativeConst", "" },
	};
#endif // WITH_METADATA

// ********** Begin Function ReportActionResult constinit property declarations ********************
	static const UECodeGen_Private::FStructPropertyParams NewProp_Result;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
// ********** End Function ReportActionResult constinit property declarations **********************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};

// ********** Begin Function ReportActionResult Property Definitions *******************************
const UECodeGen_Private::FStructPropertyParams UHT_STATICS::NewProp_Result = { "Result", nullptr, (EPropertyFlags)0x0010000008000182, UECodeGen_Private::EPropertyGenFlags::Struct, nullptr, nullptr, 1, STRUCT_OFFSET(OnlyCloudsEditorLibrary_eventReportActionResult_Parms, Result), Z_Construct_UScriptStruct_FOnlyCloudsEditorActionResult, METADATA_PARAMS(UE_ARRAY_COUNT(NewProp_Result_MetaData), NewProp_Result_MetaData) }; // 191130fa04dd24e65269442c820aded00b0f9f17
const UECodeGen_Private::FPropertyParamsBase* const UHT_STATICS::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_Result,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::PropPointers) < 2048);
// ********** End Function ReportActionResult Property Definitions *********************************
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_UOnlyCloudsEditorLibrary, nullptr, "ReportActionResult", UHT_STATICS::PropPointers, UE_ARRAY_COUNT(UHT_STATICS::PropPointers), DataSizeOf<UHT_STATICS::OnlyCloudsEditorLibrary_eventReportActionResult_Parms>(), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04422401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
static_assert(sizeof(UHT_STATICS::OnlyCloudsEditorLibrary_eventReportActionResult_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_UOnlyCloudsEditorLibrary_ReportActionResult(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(UOnlyCloudsEditorLibrary::execReportActionResult)
{
	P_GET_STRUCT_REF(FOnlyCloudsEditorActionResult,Z_Param_Out_Result);
	P_FINISH;
	P_NATIVE_BEGIN;
	UOnlyCloudsEditorLibrary::ReportActionResult(Z_Param_Out_Result);
	P_NATIVE_END;
}
// ********** End Class UOnlyCloudsEditorLibrary Function ReportActionResult ***********************

// ********** Begin Class UOnlyCloudsEditorLibrary Function UndoLastEditorTransaction **************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UFunction_UOnlyCloudsEditorLibrary_UndoLastEditorTransaction_Statics
struct UHT_STATICS
{
	struct OnlyCloudsEditorLibrary_eventUndoLastEditorTransaction_Parms
	{
		bool ReturnValue;
	};
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "Category", "OnlyClouds|Validation" },
		{ "Comment", "/** Editor transaction hooks for isolated plugin validation. */" },
		{ "ModuleRelativePath", "Public/OnlyCloudsEditorLibrary.h" },
		{ "ToolTip", "Editor transaction hooks for isolated plugin validation." },
	};
#endif // WITH_METADATA

// ********** Begin Function UndoLastEditorTransaction constinit property declarations *************
	static void NewProp_ReturnValue_SetBit(void* Obj)
	{
		((OnlyCloudsEditorLibrary_eventUndoLastEditorTransaction_Parms*)Obj)->ReturnValue = 1;
	}
	static const UECodeGen_Private::FBoolPropertyParams NewProp_ReturnValue;
	static const UECodeGen_Private::FPropertyParamsBase* const PropPointers[];
// ********** End Function UndoLastEditorTransaction constinit property declarations ***************
	static const UECodeGen_Private::FFunctionParams FuncParams;
};

// ********** Begin Function UndoLastEditorTransaction Property Definitions ************************
const UECodeGen_Private::FBoolPropertyParams UHT_STATICS::NewProp_ReturnValue = { "ReturnValue", nullptr, (EPropertyFlags)0x0010000000000580, UECodeGen_Private::EPropertyGenFlags::Bool | UECodeGen_Private::EPropertyGenFlags::NativeBool, nullptr, nullptr, 1, sizeof(bool), sizeof(OnlyCloudsEditorLibrary_eventUndoLastEditorTransaction_Parms), &UHT_STATICS::NewProp_ReturnValue_SetBit, METADATA_PARAMS(0, nullptr) };
const UECodeGen_Private::FPropertyParamsBase* const UHT_STATICS::PropPointers[] = {
	(const UECodeGen_Private::FPropertyParamsBase*)&UHT_STATICS::NewProp_ReturnValue,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::PropPointers) < 2048);
// ********** End Function UndoLastEditorTransaction Property Definitions **************************
const UECodeGen_Private::FFunctionParams UHT_STATICS::FuncParams = { { (FTypeConstructFunc*)Z_Construct_UClass_UOnlyCloudsEditorLibrary, nullptr, "UndoLastEditorTransaction", UHT_STATICS::PropPointers, UE_ARRAY_COUNT(UHT_STATICS::PropPointers), DataSizeOf<UHT_STATICS::OnlyCloudsEditorLibrary_eventUndoLastEditorTransaction_Parms>(), RF_Public|RF_Transient|RF_MarkAsNative, (EFunctionFlags)0x04022401, 0, 0, METADATA_PARAMS(UE_ARRAY_COUNT(UHT_STATICS::Type_MetaData), UHT_STATICS::Type_MetaData)},  };
static_assert(sizeof(UHT_STATICS::OnlyCloudsEditorLibrary_eventUndoLastEditorTransaction_Parms) < MAX_uint16);
UFunction* Z_Construct_UFunction_UOnlyCloudsEditorLibrary_UndoLastEditorTransaction(ETypeConstructPhase Phase)
{
	static UFunction* ReturnFunction = nullptr;
	if (!ReturnFunction)
	{
		UECodeGen_Private::ConstructUFunction(&ReturnFunction, UHT_STATICS::FuncParams);
	}
	return ReturnFunction;
}
#undef UHT_STATICS
DEFINE_FUNCTION(UOnlyCloudsEditorLibrary::execUndoLastEditorTransaction)
{
	P_FINISH;
	P_NATIVE_BEGIN;
	*(bool*)Z_Param__Result=UOnlyCloudsEditorLibrary::UndoLastEditorTransaction();
	P_NATIVE_END;
}
// ********** End Class UOnlyCloudsEditorLibrary Function UndoLastEditorTransaction ****************

// ********** Begin Class UOnlyCloudsEditorLibrary *************************************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_Construct_UClass_UOnlyCloudsEditorLibrary_Statics
struct UHT_STATICS
{
#if WITH_METADATA
	static constexpr UECodeGen_Private::FMetaDataPairParam Type_MetaData[] = {
		{ "Comment", "/** Editor-only actions used by Quick Widget Tools and automated validation. No action runs on startup. */" },
		{ "IncludePath", "OnlyCloudsEditorLibrary.h" },
		{ "ModuleRelativePath", "Public/OnlyCloudsEditorLibrary.h" },
		{ "ToolTip", "Editor-only actions used by Quick Widget Tools and automated validation. No action runs on startup." },
	};
#endif // WITH_METADATA

// ********** Begin Class UOnlyCloudsEditorLibrary constinit property declarations *****************
// ********** End Class UOnlyCloudsEditorLibrary constinit property declarations *******************
	static constexpr UE::CodeGen::FClassNativeFunction Funcs[] = {
		{ .NameUTF8 = UTF8TEXT("AddBasicLightRigg"), .Pointer = &UOnlyCloudsEditorLibrary::execAddBasicLightRigg },
		{ .NameUTF8 = UTF8TEXT("AddCloudPreset"), .Pointer = &UOnlyCloudsEditorLibrary::execAddCloudPreset },
		{ .NameUTF8 = UTF8TEXT("AddLayeredWorldClouds"), .Pointer = &UOnlyCloudsEditorLibrary::execAddLayeredWorldClouds },
		{ .NameUTF8 = UTF8TEXT("DescribeRegisteredMenu"), .Pointer = &UOnlyCloudsEditorLibrary::execDescribeRegisteredMenu },
		{ .NameUTF8 = UTF8TEXT("ExecuteRegisteredMenuAction"), .Pointer = &UOnlyCloudsEditorLibrary::execExecuteRegisteredMenuAction },
		{ .NameUTF8 = UTF8TEXT("RedoLastEditorTransaction"), .Pointer = &UOnlyCloudsEditorLibrary::execRedoLastEditorTransaction },
		{ .NameUTF8 = UTF8TEXT("ReportActionResult"), .Pointer = &UOnlyCloudsEditorLibrary::execReportActionResult },
		{ .NameUTF8 = UTF8TEXT("UndoLastEditorTransaction"), .Pointer = &UOnlyCloudsEditorLibrary::execUndoLastEditorTransaction },
	};
	static FTypeConstructFunc* DependentSingletons[];
	static constexpr FClassFunctionLinkInfo FuncInfo[] = {
		{ &Z_Construct_UFunction_UOnlyCloudsEditorLibrary_AddBasicLightRigg, "AddBasicLightRigg" }, // 9851459fd6a89c706a513b1dc112d029b1121ec9
		{ &Z_Construct_UFunction_UOnlyCloudsEditorLibrary_AddCloudPreset, "AddCloudPreset" }, // b4d81e93c464d5ae412cef17d0c43c748514de1c
		{ &Z_Construct_UFunction_UOnlyCloudsEditorLibrary_AddLayeredWorldClouds, "AddLayeredWorldClouds" }, // 825ab7f16635539ec08d1ae0c8738af7629bc4a3
		{ &Z_Construct_UFunction_UOnlyCloudsEditorLibrary_DescribeRegisteredMenu, "DescribeRegisteredMenu" }, // 71dea94648e8fed34e38be48101e980911f1476f
		{ &Z_Construct_UFunction_UOnlyCloudsEditorLibrary_ExecuteRegisteredMenuAction, "ExecuteRegisteredMenuAction" }, // d1b2f32239f3bd9cc31b74d7d6a5aa7b12e59060
		{ &Z_Construct_UFunction_UOnlyCloudsEditorLibrary_RedoLastEditorTransaction, "RedoLastEditorTransaction" }, // 8c22c641dfa76159f364d5a242621250cb679753
		{ &Z_Construct_UFunction_UOnlyCloudsEditorLibrary_ReportActionResult, "ReportActionResult" }, // 29747b418201a55a19425f0fc4cdd72ff0aec0fb
		{ &Z_Construct_UFunction_UOnlyCloudsEditorLibrary_UndoLastEditorTransaction, "UndoLastEditorTransaction" }, // 39ae0458f7ed803af49bd2aed84f3e4e735a6fa2
	};
	static_assert(UE_ARRAY_COUNT(FuncInfo) < 2048);
	static constexpr FCppClassTypeInfoStatic StaticCppClassTypeInfo = {
		TCppClassTypeTraits<UOnlyCloudsEditorLibrary>::IsAbstract,
	};
	static const UECodeGen_Private::FClassParams ClassParams;
}; // struct UHT_STATICS
FTypeConstructFunc* UHT_STATICS::DependentSingletons[] = {
	(FTypeConstructFunc*)Z_Construct_UClass_UBlueprintFunctionLibrary,
	(FTypeConstructFunc*)Z_Construct_UPackage__Script_OnlyCloudsEditor,
};
static_assert(UE_ARRAY_COUNT(UHT_STATICS::DependentSingletons) < 16);
const UECodeGen_Private::FClassParams UHT_STATICS::ClassParams = {
	&Z_Construct_UClass_UOnlyCloudsEditorLibrary,
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
static void UOnlyCloudsEditorLibrary_StaticRegisterNativesUOnlyCloudsEditorLibrary()
{
	UClass* Class = UOnlyCloudsEditorLibrary::StaticClass();
	FNativeFunctionRegistrar::RegisterFunctions(Class, 		MakeConstArrayView(UHT_STATICS::Funcs));
}
FClassRegistrationInfo Z_Registration_Info_UClass_UOnlyCloudsEditorLibrary;
UClass* Z_Construct_UClass_UOnlyCloudsEditorLibrary(ETypeConstructPhase Phase)
{
	if (Phase == ETypeConstructPhase::Inner)
	{
		using TClass = UOnlyCloudsEditorLibrary;
		if (!Z_Registration_Info_UClass_UOnlyCloudsEditorLibrary.InnerSingleton)
		{
			GetPrivateStaticClassBody(
				TClass::StaticPackage(),
				TEXT("OnlyCloudsEditorLibrary"),
				Z_Registration_Info_UClass_UOnlyCloudsEditorLibrary.InnerSingleton,
				UOnlyCloudsEditorLibrary_StaticRegisterNativesUOnlyCloudsEditorLibrary,
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
		return Z_Registration_Info_UClass_UOnlyCloudsEditorLibrary.InnerSingleton;
	}
	if (!Z_Registration_Info_UClass_UOnlyCloudsEditorLibrary.OuterSingleton)
	{
		UECodeGen_Private::ConstructUClass(Z_Registration_Info_UClass_UOnlyCloudsEditorLibrary.OuterSingleton, UHT_STATICS::ClassParams);
	}
	return Z_Registration_Info_UClass_UOnlyCloudsEditorLibrary.OuterSingleton;
}
#undef UHT_STATICS
UOnlyCloudsEditorLibrary::UOnlyCloudsEditorLibrary(const FObjectInitializer& ObjectInitializer) : Super(ObjectInitializer) {}
DEFINE_VTABLE_PTR_HELPER_CTOR_NS(, UOnlyCloudsEditorLibrary);
UOnlyCloudsEditorLibrary::~UOnlyCloudsEditorLibrary() {}
// ********** End Class UOnlyCloudsEditorLibrary ***************************************************

// ********** Begin Registration *******************************************************************
#ifdef UHT_STATICS
#error UHT_STATICS already defined
#endif
#define UHT_STATICS Z_CompiledInDeferFile_FID_HostProject_Plugins_QuickWidgetTools_Source_OnlyCloudsEditor_Public_OnlyCloudsEditorLibrary_h__Script_OnlyCloudsEditor_Statics
struct UHT_STATICS
{
	static constexpr FStructRegisterCompiledInInfo ScriptStructInfo[] = {
		{ Z_Construct_UScriptStruct_FOnlyCloudsEditorActionResult, Z_Construct_UScriptStruct_FOnlyCloudsEditorActionResult_Statics::NewStructOps, TEXT("OnlyCloudsEditorActionResult"),&Z_Registration_Info_UScriptStruct_FOnlyCloudsEditorActionResult, CONSTRUCT_RELOAD_VERSION_INFO(FStructReloadVersionInfo, sizeof(FOnlyCloudsEditorActionResult), 420557050U) },
	};
	static constexpr FClassRegisterCompiledInInfo ClassInfo[] = {
		{ Z_Construct_UClass_UOnlyCloudsEditorLibrary, TEXT("UOnlyCloudsEditorLibrary"), &Z_Registration_Info_UClass_UOnlyCloudsEditorLibrary, CONSTRUCT_RELOAD_VERSION_INFO(FClassReloadVersionInfo, sizeof(UOnlyCloudsEditorLibrary), 1027779360U) },
	};
}; // UHT_STATICS 
static FRegisterCompiledInInfo Z_CompiledInDeferFile_FID_HostProject_Plugins_QuickWidgetTools_Source_OnlyCloudsEditor_Public_OnlyCloudsEditorLibrary_h__Script_OnlyCloudsEditor_a0ccb0cff0c5d5134532158e412f2fb5a41d12bc{
	TEXT("/Script/OnlyCloudsEditor"),
	UHT_STATICS::ClassInfo, UE_ARRAY_COUNT(UHT_STATICS::ClassInfo),
	UHT_STATICS::ScriptStructInfo, UE_ARRAY_COUNT(UHT_STATICS::ScriptStructInfo),
	nullptr, 0,
	nullptr, 0,
};
#undef UHT_STATICS
// ********** End Registration *********************************************************************
#undef UHT_STRUCT_BASE

PRAGMA_ENABLE_DEPRECATION_WARNINGS
