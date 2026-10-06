#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "QuickWidgetToolsNiagaraLibrary.generated.h"

/** Editor-only helpers used by the Quick Widget Tools Niagara UI. */
UCLASS()
class QUICKWIDGETTOOLS_API UQuickWidgetToolsNiagaraLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Clears and records Niagara Sim Caches for every Niagara component on the
	 * single selected actor into the Level Sequence currently focused in Sequencer.
	 */
	UFUNCTION(BlueprintCallable, CallInEditor, Category = "Quick Widget Tools|Niagara")
	static bool BakeSelectedNiagaraSimCacheToCurrentSequence(FText& OutMessage);
};
