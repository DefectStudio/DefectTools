using UnrealBuildTool;

public class OnlyCloudsEditor : ModuleRules
{
    public OnlyCloudsEditor(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new [] { "Core", "CoreUObject", "Engine" });
        PrivateDependencyModuleNames.AddRange(new [] {
            "CloudGeneratorTools", "UnrealEd", "LevelEditor", "ToolMenus",
            "Slate", "SlateCore", "EditorFramework", "Json"
        });
    }
}
