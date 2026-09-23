// Standalone runner avoids the full LEAN test assembly's global Python initialization.
using System;
using QuantConnect.Tests;
using QuantConnect.Tests.Engine.Setup;
using QuantConnect.Tests.Engine.DataFeeds;

try
{
    TestGlobals.Initialize();
    if (Environment.GetEnvironmentVariable("TL001A_PHASE") == "managed_feed")
    {
        new TideLabManagedFeedProbe().LiveFeedEmitsThreeSyntheticHourlyBars();
    }
    else
    {
        new TideLabForwardRecoveryProbe()
            .PendingOrderComesFromAuthoritativeSyntheticBrokerReport();
    }
    return 0;
}
catch (Exception error)
{
    Console.Error.WriteLine(error);
    return 1;
}
