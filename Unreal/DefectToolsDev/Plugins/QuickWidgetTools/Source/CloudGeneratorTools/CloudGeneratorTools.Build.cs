using UnrealBuildTool;

public class CloudGeneratorTools : ModuleRules
{
    public CloudGeneratorTools(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PrecompileForTargets = PrecompileTargetsType.Any;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine" });
        PrivateDependencyModuleNames.AddRange(new[] { "RenderCore", "RHI" });
        if (Target.bBuildEditor)
        {
            PrivateDependencyModuleNames.AddRange(new[] { "UnrealEd", "Slate", "SlateCore", "AssetTools", "AssetRegistry" });
        }
    }
}
