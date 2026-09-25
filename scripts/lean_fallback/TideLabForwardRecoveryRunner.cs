// Standalone runner avoids the full LEAN test assembly's global Python initialization.
using System;
using QuantConnect.Tests;
using QuantConnect.Tests.Engine.Setup;
using QuantConnect.Tests.Engine.DataFeeds;

try
{
    TestGlobals.Initialize();
    if (Environment.GetEnvironmentVariable("TL001A_PHASE")?.StartsWith(
        "h1_report_", StringComparison.Ordinal) == true)
    {
        TideLabH1LocalReportProbe.Run(
            Environment.GetEnvironmentVariable("TL001A_REPORT_PATH"),
            Environment.GetEnvironmentVariable("TL001A_PHASE"));
    }
    else if (Environment.GetEnvironmentVariable("TL001A_PHASE") == "cost_fill")
    {
        TideLabCostFillProbe.Run();
    }
    else if (Environment.GetEnvironmentVariable("TL001A_PHASE")?.StartsWith(
        "conservative_", StringComparison.Ordinal) == true)
    {
        TideLabConservativePaperFillProbe.Run(
            Environment.GetEnvironmentVariable("TL001A_REPORT_PATH"),
            Environment.GetEnvironmentVariable("TL001A_PHASE"));
    }
    else if (Environment.GetEnvironmentVariable("TL001A_PHASE")?.StartsWith(
        "joined_", StringComparison.Ordinal) == true)
    {
        TideLabJoinedPaperWorkflowProbe.Run(
            Environment.GetEnvironmentVariable("TL001A_REPORT_PATH"),
            Environment.GetEnvironmentVariable("TL001A_PHASE"));
    }
    else if (Environment.GetEnvironmentVariable("TL001A_PHASE") is
        "managed_feed" or "managed_feed_submit_seed" or
        "managed_manager_submit_seed" or "managed_h1_baseline" or
        "managed_h1_drawdown" or "managed_h1_v1_baseline" or
        "managed_h1_v1_drawdown" or "managed_h1_v1_accounting")
    {
        new TideLabManagedFeedProbe().LiveFeedEmitsThreeSyntheticHourlyBars();
    }
    else if (Environment.GetEnvironmentVariable("TL001A_PHASE")?.StartsWith(
        "ledger_", StringComparison.Ordinal) == true)
    {
        new TideLabExecutionLedgerProbe().Run();
    }
    else if (Environment.GetEnvironmentVariable("TL001A_PHASE")?.StartsWith(
        "journal_", StringComparison.Ordinal) == true)
    {
        TideLabCorrectionJournalProbe.Run(
            Environment.GetEnvironmentVariable("TL001A_REPORT_PATH"),
            Environment.GetEnvironmentVariable("TL001A_PHASE"));
    }
    else if (Environment.GetEnvironmentVariable("TL001A_PHASE") == "snapshot_seed")
    {
        TideLabAtomicSnapshotProbe.Seed(
            Environment.GetEnvironmentVariable("TL001A_REPORT_PATH"));
    }
    else if (Environment.GetEnvironmentVariable("TL001A_PHASE")?.StartsWith(
        "paper_", StringComparison.Ordinal) == true)
    {
        TideLabPaperSubmissionBarrierProbe.Run(
            Environment.GetEnvironmentVariable("TL001A_REPORT_PATH"),
            Environment.GetEnvironmentVariable("TL001A_PHASE"));
    }
    else if (Environment.GetEnvironmentVariable("TL001A_PHASE")?.StartsWith(
        "intent_", StringComparison.Ordinal) == true)
    {
        TideLabPaperIntentRecoveryProbe.Run(
            Environment.GetEnvironmentVariable("TL001A_REPORT_PATH"),
            Environment.GetEnvironmentVariable("TL001A_PHASE"));
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
