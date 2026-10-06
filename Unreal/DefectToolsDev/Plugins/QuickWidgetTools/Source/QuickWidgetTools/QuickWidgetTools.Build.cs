using UnrealBuildTool;

public class QuickWidgetTools : ModuleRules
{
    public QuickWidgetTools(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(
            new string[]
            {
                "Core",
                "CoreUObject",
                "Engine"
            }
        );

        PrivateDependencyModuleNames.AddRange(
            new string[]
            {
                "Slate",
                "SlateCore",
                "ToolMenus",
                "AssetRegistry",
                "Blutility",
                "UMG",
                "UMGEditor",
                "UnrealEd",
                "RenderCore",
                "RHI",
                "LevelSequence",
                "LevelSequenceEditor",
                "MovieScene",
                "Sequencer",
                "Niagara",
                "NiagaraSimCaching",
                "CacheTrackRecorder"
            }
        );
    }
}
