// Copyright Epic Games, Inc. All Rights Reserved.
/*===========================================================================
	Generated code exported from UnrealHeaderTool.
	DO NOT modify this manually! Edit the corresponding .h files instead!
===========================================================================*/

#include "UObject/GeneratedCppIncludes.h"
PRAGMA_DISABLE_DEPRECATION_WARNINGS
void EmptyLinkFunctionForGeneratedCodeOnlyCloudsEditor_init() {}
static_assert(!UE_WITH_CONSTINIT_UOBJECT, "This generated code can only be compiled with !UE_WITH_CONSTINIT_OBJECT");
	static FPackageRegistrationInfo Z_Registration_Info_UPackage__Script_OnlyCloudsEditor;
	FORCENOINLINE UPackage* Z_Construct_UPackage__Script_OnlyCloudsEditor(ETypeConstructPhase)
	{
		if (!Z_Registration_Info_UPackage__Script_OnlyCloudsEditor.OuterSingleton)
		{
		static const UECodeGen_Private::FPackageParams PackageParams = {
			"/Script/OnlyCloudsEditor",
			nullptr,
			0,
			PKG_CompiledIn | 0x00000040,
			0x4B454826,
			0xA112E0DC,
			METADATA_PARAMS(0, nullptr)
		};
		UECodeGen_Private::ConstructUPackage(Z_Registration_Info_UPackage__Script_OnlyCloudsEditor.OuterSingleton, PackageParams);
	}
	return Z_Registration_Info_UPackage__Script_OnlyCloudsEditor.OuterSingleton;
}
static FRegisterCompiledInInfo Z_CompiledInDeferPackage_UPackage__Script_OnlyCloudsEditor(Z_Construct_UPackage__Script_OnlyCloudsEditor, TEXT("/Script/OnlyCloudsEditor"), Z_Registration_Info_UPackage__Script_OnlyCloudsEditor, CONSTRUCT_RELOAD_VERSION_INFO(FPackageReloadVersionInfo, 0x4B454826, 0xA112E0DC));
PRAGMA_ENABLE_DEPRECATION_WARNINGS
