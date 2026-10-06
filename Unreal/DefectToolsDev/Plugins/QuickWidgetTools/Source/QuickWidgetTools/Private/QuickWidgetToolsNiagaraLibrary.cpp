#include "QuickWidgetToolsNiagaraLibrary.h"

#include "Subsystems/AssetEditorSubsystem.h"
#include "Editor.h"
#include "Engine/Selection.h"
#include "GameFramework/Actor.h"
#include "ILevelSequenceEditorToolkit.h"
#include "ISequencer.h"
#include "LevelSequence.h"
#include "LevelSequenceEditorBlueprintLibrary.h"
#include "MovieScene.h"
#include "NiagaraComponent.h"
#include "NiagaraSystem.h"
#include "Niagara/Sequencer/MovieSceneNiagaraCacheTrack.h"
#include "Recorder/CacheTrackRecorder.h"
#include "ScopedTransaction.h"

#define LOCTEXT_NAMESPACE "QuickWidgetToolsNiagaraLibrary"

bool UQuickWidgetToolsNiagaraLibrary::BakeSelectedNiagaraSimCacheToCurrentSequence(FText& OutMessage)
{
	OutMessage = FText::GetEmpty();

	if (!GEditor)
	{
		OutMessage = LOCTEXT("EditorUnavailable", "The Unreal Editor is not available.");
		return false;
	}

	if (UCacheTrackRecorder::GetActiveRecorder())
	{
		OutMessage = LOCTEXT("RecordingAlreadyActive", "A cache recording is already in progress.");
		return false;
	}

	USelection* SelectedActors = GEditor->GetSelectedActors();
	if (!SelectedActors || SelectedActors->Num() != 1)
	{
		OutMessage = LOCTEXT("SelectOneActor", "Select exactly one actor that contains a Niagara component.");
		return false;
	}

	AActor* SelectedActor = nullptr;
	for (FSelectionIterator It(*SelectedActors); It; ++It)
	{
		SelectedActor = Cast<AActor>(*It);
		break;
	}

	if (!SelectedActor)
	{
		OutMessage = LOCTEXT("InvalidSelectedActor", "The selected object is not a valid actor.");
		return false;
	}

	TArray<UNiagaraComponent*> NiagaraComponents;
	SelectedActor->GetComponents<UNiagaraComponent>(NiagaraComponents);
	if (NiagaraComponents.IsEmpty())
	{
		OutMessage = FText::Format(
			LOCTEXT("RequireNiagaraComponent", "'{0}' does not contain a Niagara component."),
			FText::FromString(SelectedActor->GetActorLabel()));
		return false;
	}

	for (const UNiagaraComponent* NiagaraComponent : NiagaraComponents)
	{
		if (!NiagaraComponent || !NiagaraComponent->GetAsset())
		{
			OutMessage = FText::Format(
				LOCTEXT("MissingNiagaraSystem", "Niagara component '{0}' on '{1}' has no Niagara System assigned."),
				FText::FromString(NiagaraComponent ? NiagaraComponent->GetName() : TEXT("Invalid Component")),
				FText::FromString(SelectedActor->GetActorLabel()));
			return false;
		}
	}

	ULevelSequence* RootSequence = ULevelSequenceEditorBlueprintLibrary::GetCurrentLevelSequence();
	UAssetEditorSubsystem* AssetEditorSubsystem = GEditor->GetEditorSubsystem<UAssetEditorSubsystem>();
	IAssetEditorInstance* AssetEditor = RootSequence && AssetEditorSubsystem
		? AssetEditorSubsystem->FindEditorForAsset(RootSequence, false)
		: nullptr;
	ILevelSequenceEditorToolkit* LevelSequenceEditor = AssetEditor && AssetEditor->GetEditorName() == TEXT("LevelSequenceEditor")
		? static_cast<ILevelSequenceEditorToolkit*>(AssetEditor)
		: nullptr;
	TSharedPtr<ISequencer> Sequencer = LevelSequenceEditor ? LevelSequenceEditor->GetSequencer() : nullptr;
	if (!Sequencer.IsValid())
	{
		OutMessage = LOCTEXT("NoOpenSequencer", "Open a Level Sequence in Sequencer before baking.");
		return false;
	}

	ULevelSequence* FocusedSequence = Cast<ULevelSequence>(Sequencer->GetFocusedMovieSceneSequence());
	UMovieScene* MovieScene = FocusedSequence ? FocusedSequence->GetMovieScene() : nullptr;
	if (!MovieScene)
	{
		OutMessage = LOCTEXT("NoFocusedLevelSequence", "The sequence currently focused in Sequencer is not a Level Sequence.");
		return false;
	}

	if (MovieScene->IsReadOnly())
	{
		OutMessage = FText::Format(
			LOCTEXT("SequenceReadOnly", "The focused sequence '{0}' is read-only."),
			FText::FromString(FocusedSequence->GetName()));
		return false;
	}

	const FScopedTransaction Transaction(LOCTEXT("BakeNiagaraSimCacheTransaction", "Bake Niagara Sim Cache"));
	FocusedSequence->Modify();
	MovieScene->Modify();

	const FFrameNumber StartFrame = MovieScene->GetPlaybackRange().GetLowerBoundValue();
	TArray<IMovieSceneCachedTrack*> CacheTracks;
	CacheTracks.Reserve(NiagaraComponents.Num());

	for (UNiagaraComponent* NiagaraComponent : NiagaraComponents)
	{
		const FGuid ObjectBinding = Sequencer->GetHandleToObject(NiagaraComponent, true);
		if (!ObjectBinding.IsValid())
		{
			OutMessage = FText::Format(
				LOCTEXT("UnableToBindComponent", "Unable to bind Niagara component '{0}' to the focused sequence."),
				FText::FromString(NiagaraComponent->GetName()));
			return false;
		}

		UMovieSceneNiagaraCacheTrack* CacheTrack = MovieScene->FindTrack<UMovieSceneNiagaraCacheTrack>(ObjectBinding);
		if (!CacheTrack)
		{
			CacheTrack = MovieScene->AddTrack<UMovieSceneNiagaraCacheTrack>(ObjectBinding);
		}

		if (!CacheTrack)
		{
			OutMessage = FText::Format(
				LOCTEXT("UnableToCreateCacheTrack", "Unable to create a Niagara Sim Cache track for component '{0}'."),
				FText::FromString(NiagaraComponent->GetName()));
			return false;
		}

		CacheTrack->Modify();
		CacheTrack->RemoveAllAnimationData();
		CacheTrack->SetCacheRecordingAllowed(true);
		CacheTrack->SetDisplayName(NiagaraComponents.Num() == 1
			? FText::Format(
				LOCTEXT("NiagaraCacheTrackName", "{0} Sim Cache"),
				FText::FromName(NiagaraComponent->GetAsset()->GetFName()))
			: FText::Format(
				LOCTEXT("MultiNiagaraCacheTrackName", "{0} ({1}) Sim Cache"),
				FText::FromString(NiagaraComponent->GetName()),
				FText::FromName(NiagaraComponent->GetAsset()->GetFName())));

		if (!CacheTrack->AddNewAnimation(StartFrame, NiagaraComponent))
		{
			OutMessage = FText::Format(
				LOCTEXT("UnableToCreateCacheSection", "Unable to create a Niagara Sim Cache section for component '{0}'."),
				FText::FromString(NiagaraComponent->GetName()));
			return false;
		}

		NiagaraComponent->SetSimCache(nullptr);
		NiagaraComponent->ReinitializeSystem();
		NiagaraComponent->Activate(true);
		CacheTracks.Add(CacheTrack);
	}

	Sequencer->NotifyMovieSceneDataChanged(EMovieSceneDataChangeType::MovieSceneStructureItemAdded);

	FCacheRecorderParameters RecorderParameters;
	RecorderParameters.User.bResetPlayhead = true;
	RecorderParameters.User.bStopAtPlaybackEnd = true;
	RecorderParameters.Project.bCacheTrackRecorderControlsClockTime = true;
	UCacheTrackRecorder::RecordCacheTracks(CacheTracks, Sequencer, RecorderParameters);

	if (!UCacheTrackRecorder::GetActiveRecorder())
	{
		OutMessage = LOCTEXT("UnableToStartRecording", "The Niagara Sim Cache recorder could not start. Check the Output Log for details.");
		return false;
	}

	OutMessage = FText::Format(
		LOCTEXT("RecordingStarted", "Recording {0} Niagara component(s) from '{1}' into '{2}'."),
		FText::AsNumber(NiagaraComponents.Num()),
		FText::FromString(SelectedActor->GetActorLabel()),
		FText::FromString(FocusedSequence->GetName()));
	return true;
}

#undef LOCTEXT_NAMESPACE
