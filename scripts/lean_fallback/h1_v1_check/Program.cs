using QuantConnect.Algorithm.CSharp;

static void Check(bool condition, string message)
{
    if (!condition) throw new Exception(message);
}

using var input = System.Text.Json.JsonDocument.Parse(File.ReadAllText(
    Path.Combine(AppContext.BaseDirectory, "synthetic_input.json")));
var fixture = input.RootElement;
var firstClose = DateTime.Parse(fixture.GetProperty("first_close_utc").GetString()!,
    System.Globalization.CultureInfo.InvariantCulture,
    System.Globalization.DateTimeStyles.RoundtripKind);
var warmupHours = fixture.GetProperty("warmup_hours").GetInt32();
var warmupClose = decimal.Parse(fixture.GetProperty("warmup_close").GetString()!,
    System.Globalization.CultureInfo.InvariantCulture);
var closes = Enumerable.Repeat(warmupClose, warmupHours).Concat(
    fixture.GetProperty("scored_closes").EnumerateArray().Select(value =>
        decimal.Parse(value.GetString()!, System.Globalization.CultureInfo.InvariantCulture))).ToArray();
Check(firstClose.Kind == DateTimeKind.Utc && warmupHours == 168 &&
    warmupClose == 100m && closes.SequenceEqual(
        Enumerable.Repeat(100m, 168).Concat(new[] { 102m, 98m, 110m })),
    "Synthetic input definition changed unexpectedly");

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

var entry = TideLabH1V1PaperBoundary.Create(historical[168],
    "synthetic-h1-check", "synthetic:BTC-USDT", "account-rev-1",
    historical[168].ClosedAtUtc, 100m, 10000m, 10000m, 0m);
var entryAgain = TideLabH1V1PaperBoundary.Create(historical[168],
    "synthetic-h1-check", "synthetic:BTC-USDT", "account-rev-1",
    historical[168].ClosedAtUtc, 100m, 10000m, 10000m, 0m);
Check(entry == entryAgain && entry.Side == "buy" &&
    entry.Quantity == 25m && entry.TargetGrossExposure == 0.25m,
    "H1 policy did not produce a stable 25% paper proposal");
var exitProposal = TideLabH1V1PaperBoundary.Create(historical[169],
    "synthetic-h1-check", "synthetic:BTC-USDT", "account-rev-2",
    historical[169].ClosedAtUtc, 98m, 10000m, 7500m, 25m);
Check(exitProposal.Side == "sell" && exitProposal.Quantity == 25m &&
    exitProposal.ClientId != entry.ClientId,
    "H1 exit did not use full reconciled inventory");
var drawdownExit = TideLabH1V1PaperBoundary.Create(stopped[169],
    "synthetic-h1-drawdown", "synthetic:BTC-USDT", "account-rev-2",
    stopped[169].ClosedAtUtc, 98m, 8000m, 5500m, 25m);
Check(drawdownExit.Side == "sell" && drawdownExit.EntriesHalted &&
    drawdownExit.Risk == TideLabH1V1Risk.DrawdownHalt,
    "Drawdown exit must remain available while entries are halted");
var blocked = false;
try { TideLabH1V1PaperBoundary.Create(historical[168],
    "synthetic-h1-check", "synthetic:BTC-USDT", "account-rev-1",
    historical[168].ClosedAtUtc.AddHours(1), 100m, 10000m, 10000m, 0m); }
catch (ArgumentException) { blocked = true; }
Check(blocked, "A late opening snapshot must be blocked");
Console.WriteLine("H1V1_PAPER_PROPOSAL entry=25 exit=25 drawdown_exit=25 stable=yes late=blocked orders=0");
if (args.Contains("--emit-paper-proposal"))
    Console.WriteLine("H1V1_PAPER_PROPOSAL_JSON=" +
        System.Text.Json.JsonSerializer.Serialize(entry));
