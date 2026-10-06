# Building Quick Widget Tools for distribution

The shared plugin includes the `QuickWidgetTools` and `OnlyCloudsEditor` editor
modules, plus the `CloudGeneratorTools` runtime module used by placed clouds and
world-cloud actors. Keeping these module names preserves their native class
identities. Cloud content lives under `/QuickWidgetTools/OnlyClouds`.

Use the installed UE 5.8 Windows build and its supported Visual Studio C++
toolchain on the developer/build machine. Artist workstations using the same
engine build can load the distributed editor DLLs without compiling this plugin.
Another engine build or operating system needs separately built and tested
binaries. Shader compilation is separate and can still occur.

## Build

From PowerShell, run this script from the plugin checkout:

```powershell
.\Scripts\Build-QuickWidgetTools.ps1 -ValidateOnly
.\Scripts\Build-QuickWidgetTools.ps1
```

If Unreal is installed elsewhere, pass the installation directory containing
`Engine`:

```powershell
.\Scripts\Build-QuickWidgetTools.ps1 -EngineRoot 'D:\Unreal Engine\5.8\UE_5.8'
```

The default output root is `I:\AICache\quickwidgettools-build`. A different
`-OutputRoot` must also be a dedicated subfolder of `I:\AICache`. Each run uses a
new directory and leaves previous results intact. The script stages a source copy
there, so build output cannot replace files in the working plugin.
It never installs its result over a running editor's DLLs.

The script runs the same three UnrealBuildTool targets used by Unreal's
`BuildPlugin`: editor Development and runtime Development/Shipping for Win64.
It assembles the portable package from the exact build-manifest products,
generated headers, source, content, resources, and configuration. The companion
`Config/FilterPlugin.ini` also includes documentation, scripts, and configuration
when packaging through UAT separately.

All configurable temporary, cache, and log locations are redirected into the run
directory. A process-local .NET startup hook creates a scratch trace using Unreal's
public UBA trace API. Direct UBT invocation supplies a session ID that preserves
this trace, avoiding Unreal's default Windows-profile trace location. No engine
files are modified. UE 5.8 always uses the UBA executor for local builds;
`-NoUBA` disables its detouring, and remote executors are also disabled.

A scratch XML configuration cache uses engine defaults without regenerating
user-profile configuration. Consequently the build does not inherit workstation
`BuildConfiguration.xml` overrides. The engine still manages its own short-lived
process marker under `Engine/Intermediate/UbtRuns`; that internal marker has no
path override in UE 5.8 and is removed by UBT on exit.

Each successful run creates:

- `Package/QuickWidgetTools`: the complete portable plugin.
- `build-report.json`: engine version, BuildId, output paths, and outcome.
- `version-files.txt`: exact compiled/generated product paths to review for Git.
- `build-products.json`: those products' sizes and SHA-256 hashes.
- `Logs`: per-target compiler output, contained UBA traces, and the three XML build manifests.

`-ValidateOnly` checks source prerequisites, engine compatibility baseline, the
three required modules, cloud content, and missing Git LFS downloads. It does not
compile or claim that the source builds successfully.

## Publish together

After a successful build and testing in an isolated project, close the affected
editor before installing rebuilt DLLs into its working plugin. Review and copy
the exact files listed in `version-files.txt` from the generated package into the
same relative paths in this repository. Distribute matching source, descriptor,
configuration, and content in the same commit as the compiled products.

The build products include:

- `Binaries/Win64/UnrealEditor-QuickWidgetTools.dll`
- `Binaries/Win64/UnrealEditor-CloudGeneratorTools.dll`
- `Binaries/Win64/UnrealEditor-OnlyCloudsEditor.dll`
- `Binaries/Win64/UnrealEditor.modules`
- UAT's generated headers and editor import libraries under `Intermediate/Build`.
- `CloudGeneratorTools.precompiled` and **all objects it references**, under each
  of `Intermediate/Build/Win64/x64/UnrealGame/Development/CloudGeneratorTools` and
  `Intermediate/Build/Win64/x64/UnrealGame/Shipping/CloudGeneratorTools`.

The runtime objects and manifests are deliberate distribution products. Do not
apply the usual blanket removal of `Intermediate` to a packaged plugin: deleting
these products prevents downstream game builds from consuming its precompiled
runtime module. They do not remove the normal toolchain/linking requirements of
packaging an Unreal project. Keep routine build caches, project `Saved`, and
other temporary output ignored; include only the packaged paths from the report.
PDBs may be retained with the private build package for debugging; they are not
needed for artist editor use. Use Git LFS for large binary build products as well
as Unreal assets, and confirm the repository ignore rules permit the intentional
distribution products before syncing.

Sync the plugin repository first. Each consuming project then updates and syncs
its submodule commit reference. Do not install the old standalone `OnlyClouds` or
`CloudGeneratorTools` plugin alongside this combined plugin: the duplicate native
module names would conflict.

## Validate before publishing

Open a clean project with the packaged plugin using the target engine build.
Confirm it opens without asking to compile, the FX widget compiles, and all three
cloud buttons operate and undo correctly. Confirm the package dependency graph
does not require the CloudGenerator development project's `/Game` assets. Check
the template rig, saved presets, cloud materials, world layers, and placed-cloud
guides in a real rendering viewport. A successful C++ build alone does not verify
material appearance or Movie Render Queue output.
