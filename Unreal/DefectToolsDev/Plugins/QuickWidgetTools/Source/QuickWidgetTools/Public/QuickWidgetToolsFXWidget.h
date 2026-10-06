#pragma once

#include "CoreMinimal.h"
#include "EditorUtilityWidget.h"
#include "QuickWidgetToolsFXWidget.generated.h"

/** One-click FX utilities exposed through the Quick Widget Tools menu. */
UCLASS()
class QUICKWIDGETTOOLS_API UQuickWidgetToolsFXWidget : public UEditorUtilityWidget
{
	GENERATED_BODY()

protected:
	virtual TSharedRef<SWidget> RebuildWidget() override;

private:
	FReply HandleBakeNiagaraCacheClicked();
};
