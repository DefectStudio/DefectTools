#pragma once

#include "CoreMinimal.h"

class AActor;

namespace OnlyCloudsEditor
{
    struct FCloudQualitySnapshot
    {
        int32 Values[4] = {};
        uint32 Priorities[4] = {};
        bool Valid[4] = {};
    };

    FCloudQualitySnapshot CaptureCloudQuality();
    void StartCloudQualityUndoTracking();
    void StopCloudQualityUndoTracking();
    void TrackCreatedWorldCloud(AActor* Actor, const FCloudQualitySnapshot& BeforeCreation);
}
