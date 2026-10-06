#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "OnlyCloudsEditorLibrary.generated.h"

class AActor;

/** Result of one explicitly invoked OnlyClouds editor action. */
USTRUCT(BlueprintType)
struct ONLYCLOUDSEDITOR_API FOnlyCloudsEditorActionResult
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category="OnlyClouds")
    bool bSuccess = false;

    /** False when an existing world-cloud actor was selected without spawning another. */
    UPROPERTY(BlueprintReadOnly, Category="OnlyClouds")
    bool bCreated = false;

    UPROPERTY(BlueprintReadOnly, Category="OnlyClouds")
    FString Message;

    /** New actors, or the existing cloud controller selected by a repeated Add action. */
    UPROPERTY(BlueprintReadOnly, Category="OnlyClouds")
    TArray<TObjectPtr<AActor>> Actors;
};

/** Editor-only actions used by Quick Widget Tools and automated validation. No action runs on startup. */
UCLASS()
class ONLYCLOUDSEDITOR_API UOnlyCloudsEditorLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Copies the six saved rig actor templates into the active level in one undoable transaction. */
    UFUNCTION(BlueprintCallable, Category="OnlyClouds|Editor", meta=(DisplayName="Add Basic Light Rigg"))
    static FOnlyCloudsEditorActionResult AddBasicLightRigg();

    /** Adds the plugin world-cloud tool at the origin, unless another visible world-cloud renderer exists. */
    UFUNCTION(BlueprintCallable, Category="OnlyClouds|Editor", meta=(DisplayName="Add Layered World Clouds"))
    static FOnlyCloudsEditorActionResult AddLayeredWorldClouds();

    /** Adds the placed-cloud Blueprint at the origin with the saved Cumulus recipe and its guide actors. */
    UFUNCTION(BlueprintCallable, Category="OnlyClouds|Editor", meta=(DisplayName="Add Cloud Preset"))
    static FOnlyCloudsEditorActionResult AddCloudPreset();

    /** Shows the same notification and log message used by the original OnlyClouds menu. */
    UFUNCTION(BlueprintCallable, Category="OnlyClouds|Editor", meta=(DisplayName="Report OnlyClouds Action Result"))
    static void ReportActionResult(const FOnlyCloudsEditorActionResult& Result);

    /** Dispatches the registered internal action delegate, retained for validation and scripting. */
    UFUNCTION(BlueprintCallable, Category="OnlyClouds|Validation")
    static FOnlyCloudsEditorActionResult ExecuteRegisteredMenuAction(FName EntryName);

    /** Read-only JSON description of the internal action menu and Quick Widget Tools entry point. */
    UFUNCTION(BlueprintCallable, Category="OnlyClouds|Validation")
    static FString DescribeRegisteredMenu();

    /** Editor transaction hooks for isolated plugin validation. */
    UFUNCTION(BlueprintCallable, Category="OnlyClouds|Validation")
    static bool UndoLastEditorTransaction();

    UFUNCTION(BlueprintCallable, Category="OnlyClouds|Validation")
    static bool RedoLastEditorTransaction();
};
