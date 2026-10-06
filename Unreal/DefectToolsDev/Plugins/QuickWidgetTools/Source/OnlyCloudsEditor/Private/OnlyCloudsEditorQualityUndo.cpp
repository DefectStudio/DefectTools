#include "OnlyCloudsEditorQualityUndo.h"

#include "Editor.h"
#include "EditorUndoClient.h"
#include "Editor/TransBuffer.h"
#include "Engine/Engine.h"
#include "Engine/Level.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "HAL/IConsoleManager.h"
#include "UObject/ObjectKey.h"
#include "UObject/Script.h"
#include "UObject/UnrealType.h"

namespace OnlyCloudsEditor
{
    static const TCHAR* QualityNames[] = {
        TEXT("r.VolumetricRenderTarget"), TEXT("r.VolumetricRenderTarget.Mode"),
        TEXT("r.VolumetricCloud.ViewRaySampleMaxCount"), TEXT("r.VolumetricCloud.StepSizeOnZeroConservativeDensity")
    };
    static const int32 QualityValues[] = {1, 3, 10000, 1};

    FCloudQualitySnapshot CaptureCloudQuality()
    {
        FCloudQualitySnapshot Snapshot;
        for (int32 Index = 0; Index != 4; ++Index)
        {
            if (IConsoleVariable* CVar = IConsoleManager::Get().FindConsoleVariable(QualityNames[Index]))
            {
                Snapshot.Valid[Index] = true;
                Snapshot.Values[Index] = CVar->GetInt();
                Snapshot.Priorities[Index] = CVar->GetFlags() & ECVF_SetByMask;
            }
        }
        return Snapshot;
    }

    static bool SameValue(const FCloudQualitySnapshot& A, const FCloudQualitySnapshot& B, int32 Index)
    {
        return A.Valid[Index] && B.Valid[Index] && A.Values[Index] == B.Values[Index]
            && A.Priorities[Index] == B.Priorities[Index];
    }

    static bool ReadBool(AActor* Actor, const TCHAR* Name)
    {
        if (FBoolProperty* Property = FindFProperty<FBoolProperty>(Actor->GetClass(), Name))
            return Property->GetPropertyValue_InContainer(Actor);
        return false;
    }

    struct FTrackedCloudQuality
    {
        TWeakObjectPtr<AActor> Actor;
        TWeakObjectPtr<UWorld> World;
        FObjectKey ActorKey;
        FObjectKey WorldKey;
        FCloudQualitySnapshot Baseline;
        FCloudQualitySnapshot Applied;
        FCloudQualitySnapshot AfterRemoval;
        bool Owned[4] = {};
        bool WasPresent = true;
    };

    class FCloudQualityUndoClient final : public FEditorUndoClient
    {
    public:
        FCloudQualityUndoClient()
        {
            if (GEditor) GEditor->RegisterForUndo(this);
            if (GEditor)
            {
                TransactionBuffer = Cast<UTransBuffer>(GEditor->Trans.Get());
                if (TransactionBuffer.IsValid()) BeforeUndoRedoHandle = TransactionBuffer->OnBeforeRedoUndo().AddRaw(this, &FCloudQualityUndoClient::BeforeUndoRedo);
            }
            if (GEngine) ActorDeletedHandle = GEngine->OnLevelActorDeleted().AddRaw(this, &FCloudQualityUndoClient::ActorDeleted);
            WorldCleanupHandle = FWorldDelegates::OnWorldCleanup.AddRaw(this, &FCloudQualityUndoClient::WorldCleanup);
        }

        virtual ~FCloudQualityUndoClient() override
        {
            if (GEditor) GEditor->UnregisterForUndo(this);
            if (TransactionBuffer.IsValid()) TransactionBuffer->OnBeforeRedoUndo().Remove(BeforeUndoRedoHandle);
            if (GEngine) GEngine->OnLevelActorDeleted().Remove(ActorDeletedHandle);
            FWorldDelegates::OnWorldCleanup.Remove(WorldCleanupHandle);
            for (FTrackedCloudQuality& Record : Records)
            {
                AActor* Actor = Record.Actor.Get();
                if (Actor && !ReadBool(Actor, TEXT("QualityApplied"))) DropOwnership(Record);
                else Release(Record);
            }
        }

        void Track(AActor* Actor, const FCloudQualitySnapshot& BeforeCreation)
        {
            if (!IsValid(Actor) || !Actor->GetWorld() || Actor->GetWorld()->WorldType != EWorldType::Editor) return;
            FTrackedCloudQuality& Record = Records.AddDefaulted_GetRef();
            Record.Actor = Actor;
            Record.World = Actor->GetWorld();
            Record.ActorKey = FObjectKey(Actor);
            Record.WorldKey = FObjectKey(Actor->GetWorld());
            Record.Baseline = BeforeCreation;
            Record.Applied = CaptureCloudQuality();
            const bool HasLease = ReadBool(Actor, TEXT("QualityApplied"));
            for (int32 Index = 0; Index != 4; ++Index)
                Record.Owned[Index] = HasLease && BeforeCreation.Valid[Index] && Record.Applied.Valid[Index]
                    && Record.Applied.Values[Index] == QualityValues[Index];
        }

        virtual void PostUndo(bool Success) override { if (Success) Reconcile(); }
        virtual void PostRedo(bool Success) override { if (Success) Reconcile(); }

    private:
        TArray<FTrackedCloudQuality> Records;
        FDelegateHandle ActorDeletedHandle;
        FDelegateHandle WorldCleanupHandle;
        FDelegateHandle BeforeUndoRedoHandle;
        TWeakObjectPtr<UTransBuffer> TransactionBuffer;
        FCloudQualitySnapshot BeforeOperation;
        bool HasBeforeOperation = false;

        void BeforeUndoRedo(const FTransactionContext&)
        {
            BeforeOperation = CaptureCloudQuality();
            HasBeforeOperation = true;
            for (FTrackedCloudQuality& Record : Records)
                if (IsPresent(Record) && !ReadBool(Record.Actor.Get(), TEXT("QualityApplied")))
                    DropOwnership(Record);
        }

        static bool IsPresent(const FTrackedCloudQuality& Record)
        {
            AActor* Actor = Record.Actor.Get();
            UWorld* World = Record.World.Get();
            return Actor && World && !Actor->IsActorBeingDestroyed() && Actor->GetWorld() == World
                && Actor->GetLevel() && Actor->GetLevel()->Actors.Contains(Actor);
        }

        static void SetAtCurrentPriority(int32 Index, int32 Value)
        {
            if (IConsoleVariable* CVar = IConsoleManager::Get().FindConsoleVariable(QualityNames[Index]))
                CVar->SetWithCurrentPriority(Value);
        }

        static void DropOwnership(FTrackedCloudQuality& Record)
        {
            for (bool& Owned : Record.Owned) Owned = false;
            Record.AfterRemoval = CaptureCloudQuality();
        }

        static void Release(FTrackedCloudQuality& Record)
        {
            const FCloudQualitySnapshot Current = CaptureCloudQuality();
            for (int32 Index = 0; Index != 4; ++Index)
            {
                // An intervening user value or priority wins over this controller.
                if (Record.Owned[Index] && SameValue(Current, Record.Applied, Index))
                    SetAtCurrentPriority(Index, Record.Baseline.Values[Index]);
                Record.Owned[Index] = false;
            }
            Record.AfterRemoval = CaptureCloudQuality();
        }

        static void Reapply(FTrackedCloudQuality& Record, const FCloudQualitySnapshot& Before)
        {
            AActor* Actor = Record.Actor.Get();
            if (!Actor) return;
            const bool WantsQuality = ReadBool(Actor, TEXT("bApplyCloudRendererQuality")) && ReadBool(Actor, TEXT("bCinematicOffline"));
            // Undo can resurrect the transient cache without resurrecting console
            // state. Force this actor's real refresh to acquire a fresh baseline.
            if (FBoolProperty* Cache = FindFProperty<FBoolProperty>(Actor->GetClass(), TEXT("QualityApplied")))
                Cache->SetPropertyValue_InContainer(Actor, false);
            if (UFunction* Refresh = Actor->FindFunction(TEXT("RefreshClouds")))
            {
                FEditorScriptExecutionGuard ScriptGuard;
                Actor->ProcessEvent(Refresh, nullptr);
            }
            FCloudQualitySnapshot After = CaptureCloudQuality();
            const bool HasLease = WantsQuality && ReadBool(Actor, TEXT("QualityApplied"));
            for (int32 Index = 0; Index != 4; ++Index)
            {
                const bool UnchangedSinceRemoval = SameValue(Before, Record.AfterRemoval, Index);
                const bool AppliedExpected = After.Valid[Index] && After.Values[Index] == QualityValues[Index];
                // Changes made between Undo and Redo also win. The normal case
                // reacquires quality and stores the current values as its baseline.
                if (HasLease && !UnchangedSinceRemoval && AppliedExpected && Before.Valid[Index])
                    SetAtCurrentPriority(Index, Before.Values[Index]);
                Record.Owned[Index] = HasLease && UnchangedSinceRemoval && AppliedExpected;
                // Actor reconstruction can run before PostRedo and set quality
                // already. Preserve the true pre-transaction baseline in the
                // Blueprint's own release cache as well as the editor tracker.
                if (HasLease && Before.Valid[Index])
                    if (FIntProperty* Previous = FindFProperty<FIntProperty>(Actor->GetClass(), *FString::Printf(TEXT("PreviousQuality%d"), Index)))
                        Previous->SetPropertyValue_InContainer(Actor, Before.Values[Index]);
            }
            Record.Baseline = Before;
            Record.Applied = CaptureCloudQuality();
        }

        void Reconcile()
        {
            for (FTrackedCloudQuality& Record : Records)
            {
                const bool Present = IsPresent(Record);
                if (Record.WasPresent && !Present) Release(Record);
                else if (!Record.WasPresent && Present) Reapply(Record, HasBeforeOperation ? BeforeOperation : CaptureCloudQuality());
                Record.WasPresent = Present;
            }
            // Retain absent actors while their world is alive: Redo needs the
            // same record. Weak references never keep a closed map alive.
            Records.RemoveAll([](const FTrackedCloudQuality& Record) { return !Record.World.IsValid(); });
            HasBeforeOperation = false;
        }

        void ActorDeleted(AActor* Actor)
        {
            if (!Actor) return;
            for (FTrackedCloudQuality& Record : Records)
            {
                if (Record.ActorKey == FObjectKey(Actor) && Record.WasPresent)
                {
                    // Normal deletion already called Blueprint ReceiveDestroyed.
                    // During undo, the pre-transaction ownership snapshot wins;
                    // the actor's transient flags may already have been rewound.
                    if (!GIsTransacting && !ReadBool(Actor, TEXT("QualityApplied"))) DropOwnership(Record);
                    else Release(Record);
                    Record.WasPresent = false;
                }
            }
        }

        void WorldCleanup(UWorld* World, bool, bool)
        {
            if (!World) return;
            const FObjectKey Key(World);
            for (FTrackedCloudQuality& Record : Records)
                if (Record.WorldKey == Key)
                {
                    AActor* Actor = Record.Actor.Get();
                    if (Actor && !ReadBool(Actor, TEXT("QualityApplied"))) DropOwnership(Record);
                    else Release(Record);
                }
            Records.RemoveAll([Key](const FTrackedCloudQuality& Record) { return Record.WorldKey == Key; });
        }
    };

    static TUniquePtr<FCloudQualityUndoClient> QualityUndoClient;

    void StartCloudQualityUndoTracking()
    {
        if (!QualityUndoClient && GEditor) QualityUndoClient = MakeUnique<FCloudQualityUndoClient>();
    }

    void StopCloudQualityUndoTracking() { QualityUndoClient.Reset(); }

    void TrackCreatedWorldCloud(AActor* Actor, const FCloudQualitySnapshot& BeforeCreation)
    {
        if (QualityUndoClient) QualityUndoClient->Track(Actor, BeforeCreation);
    }
}
