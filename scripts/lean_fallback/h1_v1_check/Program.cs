using QuantConnect.Algorithm.CSharp;

static void Check(bool condition, string message)
{
    if (!condition) throw new Exception(message);
}

var firstClose = new DateTime(2026, 1, 1, 1, 0, 0, DateTimeKind.Utc);
var closes = Enumerable.Repeat(100m, 168).Concat(new[] { 102m, 98m, 110m }).ToArray();

List<TideLabH1V1Decision> Replay(bool forward, bool drawdown = false)
{
    var policy = new TideLabH1V1Policy();
    var decisions = new List<TideLabH1V1Decision>();
    var longPosition = false;
    var pending = TideLabH1V1Intent.Hold;
    var proposedAt = -1;
    var filledAt = new List<(int Proposed, int Filled)>();
    var clock = firstClose;
    for (var i = 0; i < closes.Length; i++)
    {
        // The previous close's proposal changes position at this bar's open.
        // No proposal can fill against the bar that produced it.
        if (pending != TideLabH1V1Intent.Hold)
        {
            Check(i > proposedAt, "Same-bar fill attempted");
            longPosition = pending == TideLabH1V1Intent.EnterLong;
            filledAt.Add((proposedAt, i));
            pending = TideLabH1V1Intent.Hold;
        }
        var closedAt = forward ? clock : firstClose.AddHours(i);
        var equity = drawdown && i >= 169 ? 8000m : 10000m;
        var decision = policy.OnClosedHour(closedAt, closes[i], longPosition,
            equity, longPosition ? 0.25m : 0m);
        decisions.Add(decision);
        pending = decision.Intent;
        if (pending != TideLabH1V1Intent.Hold) proposedAt = i;
        clock = clock.AddHours(1);
    }
    Check(filledAt.All(pair => pair.Filled == pair.Proposed + 1),
        "A proposal filled outside the following open");
    return decisions;
}

var historical = Replay(false);
var forward = Replay(true);
Check(historical.SequenceEqual(forward), "Historical and forward decisions differ");
Check(historical.Take(167).All(d => d.Mean is null &&
    d.Intent == TideLabH1V1Intent.Hold), "Warmup emitted a signal");
Check(historical[167].Mean == 100m &&
    historical[167].Intent == TideLabH1V1Intent.Hold, "Equality must hold cash");
Check(historical[168].Intent == TideLabH1V1Intent.EnterLong &&
    historical[168].TargetGrossExposure == 0.25m &&
    historical[168].ClosedAtUtc == firstClose.AddHours(168),
    "Strictly above mean must enter only after hour close");
Check(historical[169].Intent == TideLabH1V1Intent.ExitToCash,
    "At or below mean must exit when long");
Check(historical[169].TargetGrossExposure == 0m,
    "An exit must target cash");

var equalitySignal = new TideLabH1V1Signal();
for (var i = 0; i < 167; i++)
    equalitySignal.OnClosedHour(firstClose.AddHours(i), 100m, false);
Check(equalitySignal.OnClosedHour(firstClose.AddHours(167), 100m, true).Intent ==
    TideLabH1V1Intent.ExitToCash, "Equality must exit when long");
var longHoldSignal = new TideLabH1V1Signal();
for (var i = 0; i < 168; i++)
    longHoldSignal.OnClosedHour(firstClose.AddHours(i), 100m, false);
Check(longHoldSignal.OnClosedHour(firstClose.AddHours(168), 102m, true).Intent ==
    TideLabH1V1Intent.Hold, "A rising long position must not rebalance");

var stopped = Replay(true, drawdown: true);
Check(stopped[169].Intent == TideLabH1V1Intent.ExitToCash &&
    stopped[169].Risk == TideLabH1V1Risk.DrawdownHalt,
    "Drawdown must force an exit at the threshold");
Check(stopped[170].Intent == TideLabH1V1Intent.Hold &&
    stopped[170].EntriesHalted, "Later entry must remain halted");

var reset = new TideLabH1V1Policy();
Check(reset.OnClosedHour(firstClose, 100m, false, 10000m, 0m)
    .EntriesHalted == false, "New partition must reset risk state");

var independentRisk = new TideLabH1V1RiskGate();
var oversized = TideLabH1V1Intent.EnterLong;
Check(independentRisk.Evaluate(10000m, false, 0m, 0.26m, ref oversized) ==
    TideLabH1V1Risk.ExposureBlock && oversized == TideLabH1V1Intent.Hold,
    "Risk must reject an oversized independent entry proposal");

foreach (var badHour in new[] { firstClose, firstClose.AddHours(2) })
{
    var policy = new TideLabH1V1Policy();
    policy.OnClosedHour(firstClose, 100m, false, 10000m, 0m);
    var failed = false;
    try { policy.OnClosedHour(badHour, 100m, false, 10000m, 0m); }
    catch (InvalidOperationException) { failed = true; }
    Check(failed, "Duplicate and missing hours must fail closed");
}

Console.WriteLine("H1V1_SYNTHETIC_DECISIONS bars=171 warmup=168 parity=pass " +
    "strict_threshold=pass next_open=pass drawdown=pass exposure=pass " +
    "reset=pass continuity=pass orders=0");

H1V1ReplayChecks.Run();
