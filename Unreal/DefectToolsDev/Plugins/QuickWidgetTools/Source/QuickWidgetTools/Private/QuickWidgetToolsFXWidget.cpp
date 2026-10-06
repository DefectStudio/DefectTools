#include "QuickWidgetToolsFXWidget.h"

#include "Framework/Notifications/NotificationManager.h"
#include "QuickWidgetToolsNiagaraLibrary.h"
#include "Styling/AppStyle.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Notifications/SNotificationList.h"
#include "Widgets/Text/STextBlock.h"

#define LOCTEXT_NAMESPACE "QuickWidgetToolsFXWidget"

TSharedRef<SWidget> UQuickWidgetToolsFXWidget::RebuildWidget()
{
	return SNew(SBox)
		.MinDesiredWidth(380.0f)
		.Padding(16.0f)
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 0.0f, 0.0f, 6.0f)
			[
				SNew(STextBlock)
				.Text(LOCTEXT("Title", "Niagara Sim Cache"))
				.Font(FAppStyle::GetFontStyle(TEXT("HeadingExtraSmall")))
			]
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 0.0f, 0.0f, 12.0f)
			[
				SNew(STextBlock)
				.Text(LOCTEXT(
					"Instructions",
					"Select one actor with one Niagara component, then open the target Level Sequence in Sequencer."))
				.AutoWrapText(true)
			]
			+ SVerticalBox::Slot()
			.AutoHeight()
			[
				SNew(SButton)
				.Text(LOCTEXT("BakeButton", "Bake Selected Niagara Sim Cache"))
				.ToolTipText(LOCTEXT(
					"BakeButtonTooltip",
					"Clear any existing Sim Cache track data and record a new cache into the sequence currently focused in Sequencer."))
				.OnClicked_UObject(this, &UQuickWidgetToolsFXWidget::HandleBakeNiagaraCacheClicked)
			]
		];
}

FReply UQuickWidgetToolsFXWidget::HandleBakeNiagaraCacheClicked()
{
	FText Message;
	const bool bStarted = UQuickWidgetToolsNiagaraLibrary::BakeSelectedNiagaraSimCacheToCurrentSequence(Message);

	FNotificationInfo Notification(Message);
	Notification.ExpireDuration = 5.0f;
	Notification.bUseLargeFont = false;
	TSharedPtr<SNotificationItem> Item = FSlateNotificationManager::Get().AddNotification(Notification);
	if (Item.IsValid())
	{
		Item->SetCompletionState(bStarted ? SNotificationItem::CS_Success : SNotificationItem::CS_Fail);
	}

	return FReply::Handled();
}

#undef LOCTEXT_NAMESPACE
