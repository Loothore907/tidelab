// Standalone runner avoids the full LEAN test assembly's global Python initialization.
using System;
using QuantConnect.Tests;
using QuantConnect.Tests.Engine.Setup;
using QuantConnect.Tests.Engine.DataFeeds;

try
{
    TestGlobals.Initialize();
    if (Environment.GetEnvironmentVariable("TL001A_PHASE") is
        "managed_feed" or "managed_feed_submit_seed" or
        "managed_manager_submit_seed" or "managed_h1_baseline" or
        "managed_h1_drawdown")
    {
        new TideLabManagedFeedProbe().LiveFeedEmitsThreeSyntheticHourlyBars();
    }
    else if (Environment.GetEnvironmentVariable("TL001A_PHASE")?.StartsWith(
        "ledger_", StringComparison.Ordinal) == true)
    {
        new TideLabExecutionLedgerProbe().Run();
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
