using UnrealBuildTool;

public class WitnessBridge : ModuleRules
{
    public WitnessBridge(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine" });
        PrivateDependencyModuleNames.AddRange(new[] { "Json", "JsonUtilities", "ApplicationCore", "Slate" });
    }
}
