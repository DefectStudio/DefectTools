#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"

#include "Blueprint/WidgetTree.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/ScrollBox.h"
#include "Components/ScrollBoxSlot.h"
#include "Components/VerticalBox.h"
#include "WidgetBlueprint.h"

namespace QuickWidgetToolsRenderFarmLayoutTests
{
constexpr TCHAR ViewerAssetPath[] =
    TEXT("/QuickWidgetTools/EditorWidgets/WBP_09_Render_Farm_Viewer.WBP_09_Render_Farm_Viewer");
constexpr TCHAR WorkerRowAssetPath[] =
    TEXT("/QuickWidgetTools/EditorWidgets/RenderFarm/WBP_RenderFarmWorkerRow.WBP_RenderFarmWorkerRow");

UHorizontalBox* FindPrimaryHorizontalBox(UWidgetBlueprint* Blueprint)
{
    if (!Blueprint || !Blueprint->WidgetTree)
    {
        return nullptr;
    }

    TArray<UWidget*> Widgets;
    Blueprint->WidgetTree->GetAllWidgets(Widgets);

    UHorizontalBox* BestBox = nullptr;
    int32 BestChildCount = 0;
    for (UWidget* Widget : Widgets)
    {
        UHorizontalBox* Candidate = Cast<UHorizontalBox>(Widget);
        if (Candidate && Candidate->GetChildrenCount() > BestChildCount)
        {
            BestBox = Candidate;
            BestChildCount = Candidate->GetChildrenCount();
        }
    }
    return BestBox;
}
} // namespace QuickWidgetToolsRenderFarmLayoutTests

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FQuickWidgetToolsRenderFarmResponsiveLayoutTest,
    "QuickWidgetTools.RenderFarm.ResponsiveLayout",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter
)

bool FQuickWidgetToolsRenderFarmResponsiveLayoutTest::RunTest(const FString& Parameters)
{
    using namespace QuickWidgetToolsRenderFarmLayoutTests;

    UWidgetBlueprint* Viewer = LoadObject<UWidgetBlueprint>(nullptr, ViewerAssetPath);
    TestNotNull(TEXT("Render Farm Viewer asset loads"), Viewer);
    if (!Viewer || !Viewer->WidgetTree)
    {
        return false;
    }

    UVerticalBox* Panel = Viewer->WidgetTree->FindWidget<UVerticalBox>(TEXT("FarmViewerList"));
    TestNotNull(TEXT("FarmViewerList is a VerticalBox"), Panel);
    if (Panel)
    {
        TestTrue(
            TEXT("FarmViewerList is inside a ScrollBox"),
            Panel->GetParent() && Panel->GetParent()->IsA<UScrollBox>()
        );
        UScrollBoxSlot* Slot = Cast<UScrollBoxSlot>(Panel->Slot);
        TestNotNull(TEXT("FarmViewerList has a ScrollBoxSlot"), Slot);
        if (Slot)
        {
            TestEqual(
                TEXT("FarmViewerList fills horizontally"),
                Slot->GetHorizontalAlignment(),
                HAlign_Fill
            );
        }

        UWidget* ListScroll = Panel->GetParent();
        UHorizontalBoxSlot* ListSlot = ListScroll
            ? Cast<UHorizontalBoxSlot>(ListScroll->Slot)
            : nullptr;
        TestNotNull(TEXT("The list ScrollBox has a HorizontalBoxSlot"), ListSlot);
        if (ListSlot)
        {
            TestEqual(
                TEXT("The list ScrollBox fills the former split-view width"),
                ListSlot->GetSize().SizeRule.GetValue(),
                ESlateSizeRule::Fill
            );
        }
    }

    TestNull(
        TEXT("The list-only viewer has no FarmViewerDetails widget"),
        Viewer->WidgetTree->FindWidget(TEXT("FarmViewerDetails"))
    );
    TestNull(
        TEXT("The list-only viewer has no FarmViewerDetailsScroll widget"),
        Viewer->WidgetTree->FindWidget(TEXT("FarmViewerDetailsScroll"))
    );

    UWidgetBlueprint* WorkerRow = LoadObject<UWidgetBlueprint>(nullptr, WorkerRowAssetPath);
    TestNotNull(TEXT("Worker Row asset loads"), WorkerRow);
    UHorizontalBox* Columns = FindPrimaryHorizontalBox(WorkerRow);
    TestNotNull(TEXT("Worker Row has a primary HorizontalBox"), Columns);
    if (!Columns)
    {
        return false;
    }

    constexpr float ExpectedWeights[] = {1.5f, 1.2f, 0.9f, 2.0f, 1.1f, 0.9f};
    TestTrue(TEXT("Worker Row has at least six columns"), Columns->GetChildrenCount() >= 6);
    for (int32 Index = 0; Index < UE_ARRAY_COUNT(ExpectedWeights) && Index < Columns->GetChildrenCount(); ++Index)
    {
        UWidget* Column = Columns->GetChildAt(Index);
        UHorizontalBoxSlot* Slot = Column ? Cast<UHorizontalBoxSlot>(Column->Slot) : nullptr;
        TestNotNull(*FString::Printf(TEXT("Worker column %d has a HorizontalBoxSlot"), Index), Slot);
        if (!Slot)
        {
            continue;
        }

        const FSlateChildSize Size = Slot->GetSize();
        TestEqual(
            *FString::Printf(TEXT("Worker column %d uses Fill sizing"), Index),
            Size.SizeRule.GetValue(),
            ESlateSizeRule::Fill
        );
        TestTrue(
            *FString::Printf(TEXT("Worker column %d has the expected Fill weight"), Index),
            FMath::IsNearlyEqual(Size.Value, ExpectedWeights[Index])
        );
    }

    return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
