// Standalone runner avoids the full LEAN test assembly's global Python initialization.
using System;
using QuantConnect.Tests;
using QuantConnect.Tests.Engine.Setup;

try
{
    TestGlobals.Initialize();
    new TideLabForwardRecoveryProbe()
        .PendingOrderComesFromAuthoritativeSyntheticBrokerReport();
    return 0;
}
catch (Exception error)
{
    Console.Error.WriteLine(error);
    return 1;
}
