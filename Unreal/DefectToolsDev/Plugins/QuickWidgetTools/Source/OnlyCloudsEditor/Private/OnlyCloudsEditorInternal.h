#pragma once

#include "CoreMinimal.h"
#include "OnlyCloudsEditorLibrary.h"

namespace OnlyCloudsEditor
{
    inline const FName ToolbarName(TEXT("LevelEditor.LevelEditorToolBar.User"));
    inline const FName SectionName(TEXT("OnlyClouds"));
    inline const FName ToolbarEntryName(TEXT("OnlyClouds_Menu"));
    inline const FName MenuName(TEXT("OnlyClouds.Tools"));
    inline const FName OwnerName(TEXT("OnlyCloudsEditor"));

    bool CanUseEditorWorld();
    void RunRegisteredAction(FName ActionName);
    FOnlyCloudsEditorActionResult TakeLastActionResult();
    void ResetLastActionResult();
}
