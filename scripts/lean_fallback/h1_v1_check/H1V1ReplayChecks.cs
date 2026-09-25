using QuantConnect.Algorithm.CSharp;

internal static class H1V1ReplayChecks
{
    private static void Check(bool condition, string message)
    {
        if (!condition) throw new Exception(message);
    }

    public static void Run()
    {
        using var input = System.Text.Json.JsonDocument.Parse(File.ReadAllText(
            Path.Combine(AppContext.BaseDirectory, "synthetic_input.json")));
        var fixture = input.RootElement;
        var firstClose = DateTime.Parse(
            fixture.GetProperty("first_close_utc").GetString()!,
            System.Globalization.CultureInfo.InvariantCulture,
            System.Globalization.DateTimeStyles.RoundtripKind);
        var warmupHours = fixture.GetProperty("warmup_hours").GetInt32();
        var warmupClose = decimal.Parse(
            fixture.GetProperty("warmup_close").GetString()!,
            System.Globalization.CultureInfo.InvariantCulture);
        var closes = Enumerable.Repeat(warmupClose, warmupHours).Concat(
            fixture.GetProperty("scored_closes").EnumerateArray().Select(value =>
                decimal.Parse(value.GetString()!,
                    System.Globalization.CultureInfo.InvariantCulture))).ToArray();
        Check(firstClose.Kind == DateTimeKind.Utc && warmupHours == 168 &&
            warmupClose == 100m && closes.SequenceEqual(
                Enumerable.Repeat(100m, 168).Concat(new[] { 102m, 98m, 110m })),
            "Synthetic historical input definition changed unexpectedly");
        var firstStart = firstClose.AddHours(-1);
        var scoreStart = firstStart.AddHours(warmupHours);
        var scoreEnd = firstStart.AddHours(closes.Length - 1);
        var bars = Enumerable.Range(0, closes.Length).Select(index =>
            new TideLabH1V1Bar(firstStart.AddHours(index),
                index == 0 ? warmupClose : closes[index - 1], closes[index],
                index < closes.Length - 1)).ToArray();

        var result = TideLabH1V1ResearchReplay.Run(bars, scoreStart,
            scoreEnd, TideLabH1V1Cost.Base);
        var again = TideLabH1V1ResearchReplay.Run(bars, scoreStart,
            scoreEnd, TideLabH1V1Cost.Base);
        Check(result.Cash == again.Cash && result.Units == again.Units &&
            result.TotalFees == again.TotalFees &&
            result.Fills.SequenceEqual(again.Fills) &&
            result.Marks.SequenceEqual(again.Marks) &&
            result.Decisions.SequenceEqual(again.Decisions),
            "Identical replay changed decisions or balances");

        var quantity = decimal.Floor(2500m * 100000000m / (102m * 1.001m)) /
            100000000m;
        var buyPrice = 102m * 1.001m;
        var sellPrice = 98m * 0.999m;
        var buyFee = quantity * buyPrice * 0.0025m;
        var sellFee = quantity * sellPrice * 0.0025m;
        var expectedCash = 10000m - quantity * buyPrice - buyFee +
            quantity * sellPrice - sellFee;
        Check(result.Fills.Count == 2 && result.Decisions.Count == 2 &&
            result.Marks.Count == 2 && result.Units == 0m &&
            result.Cash == expectedCash &&
            result.TotalFees == buyFee + sellFee,
            "Cash, inventory, fees, or event counts differ");
        Check(result.Fills[0].Units == quantity &&
            result.Fills[0].FilledAtUtc == bars[169].StartUtc &&
            result.Fills[0].SignalClosedUtc == bars[168].StartUtc.AddHours(1) &&
            result.Fills[1].FilledAtUtc == bars[170].StartUtc &&
            result.Fills[1].SignalClosedUtc == bars[169].StartUtc.AddHours(1) &&
            result.Fills.All(fill => fill.FilledAtUtc >
                fill.SignalClosedUtc.AddHours(-1)),
            "A fill used its signal bar or wrong following open");
        Check(result.Marks[1].Cash == result.Fills[0].CashAfter &&
            result.Marks[1].Units == quantity &&
            result.Marks[1].Equity == result.Marks[1].Cash + quantity * 98m &&
            result.Fills.All(fill => fill.CashAfter >= 0m),
            "Marked account or no-borrowing invariant differs");

        var stress = TideLabH1V1ResearchReplay.Run(bars, scoreStart,
            scoreEnd, TideLabH1V1Cost.Stress);
        Check(stress.Cash < result.Cash && stress.TotalFees > result.TotalFees,
            "Declared stress costs did not worsen the synthetic result");

        var terminal = (TideLabH1V1Bar[])bars.Clone();
        terminal[169] = terminal[169] with { Close = 103m };
        terminal[170] = terminal[170] with { Open = 103m };
        var forced = TideLabH1V1ResearchReplay.Run(terminal, scoreStart,
            scoreEnd, TideLabH1V1Cost.Base);
        Check(forced.Fills.Count == 2 && forced.Fills[1].Terminal &&
            forced.Fills[1].Intent == TideLabH1V1Intent.ExitToCash &&
            forced.Units == 0m, "Final open did not liquidate the position");

        // The frozen rule still proposes an entry on the final scored close.
        // The next open must both execute it and liquidate it with both costs.
        var lastEntry = (TideLabH1V1Bar[])bars.Clone();
        lastEntry[168] = lastEntry[168] with { Close = 100m };
        lastEntry[169] = lastEntry[169] with { Close = 102m };
        lastEntry[170] = lastEntry[170] with { Open = 102m };
        var terminalRoundTrip = TideLabH1V1ResearchReplay.Run(lastEntry,
            scoreStart, scoreEnd, TideLabH1V1Cost.Base);
        Check(terminalRoundTrip.Fills.Count == 2 &&
            terminalRoundTrip.Fills[0].FilledAtUtc == scoreEnd &&
            terminalRoundTrip.Fills[1].FilledAtUtc == scoreEnd &&
            terminalRoundTrip.Fills[1].Terminal &&
            terminalRoundTrip.Cash < 10000m,
            "Last-close entry did not pay both terminal costs");

        var drawdown = (TideLabH1V1Bar[])bars.Clone();
        drawdown[169] = drawdown[169] with { Close = 1m };
        drawdown[170] = drawdown[170] with { Open = 1m };
        var stopped = TideLabH1V1ResearchReplay.Run(drawdown, scoreStart,
            scoreEnd, TideLabH1V1Cost.Base);
        Check(stopped.Decisions[1].Risk == TideLabH1V1Risk.DrawdownHalt &&
            stopped.Decisions[1].Intent == TideLabH1V1Intent.ExitToCash &&
            stopped.Units == 0m, "Marked drawdown did not exit");

        var gap = (TideLabH1V1Bar[])bars.Clone();
        gap[100] = gap[100] with { StartUtc = gap[100].StartUtc.AddHours(1) };
        var rejected = false;
        try { TideLabH1V1ResearchReplay.Run(gap, scoreStart,
            scoreEnd, TideLabH1V1Cost.Base); }
        catch (ArgumentException) { rejected = true; }
        Check(rejected, "Replay accepted a missing hour");

        var unclosed = (TideLabH1V1Bar[])bars.Clone();
        unclosed[169] = unclosed[169] with { Closed = false };
        rejected = false;
        try { TideLabH1V1ResearchReplay.Run(unclosed, scoreStart,
            scoreEnd, TideLabH1V1Cost.Base); }
        catch (ArgumentException) { rejected = true; }
        Check(rejected, "Replay accepted an unclosed scored bar");

        var opening = bars[169].StartUtc;
        var buyLiquidity = new TideLabH1SyntheticLiquidity(opening, 99.8m, 10m);
        var partial = TideLabH1ConservativeExecution.Decide(true, 25m, 100m,
            0m, TideLabH1V1Cost.Base, buyLiquidity, opening,
            TimeSpan.FromMinutes(2), 1m);
        Check(partial == new TideLabH1ExecutionDecision("PARTIAL", 10m,
            99.8998m, 2.497495m, 15m),
            "Conservative H1 partial fill or declared cost changed");
        Check(TideLabH1ConservativeExecution.Decide(true, 25m, 100m, 0m,
            TideLabH1V1Cost.Base, buyLiquidity with
                { ObservedAtUtc = opening.AddMinutes(-3) }, opening,
            TimeSpan.FromMinutes(2), 1m).State == "HOLD_STALE_OR_UNKNOWN",
            "Stale H1 liquidity must hold");
        Check(TideLabH1ConservativeExecution.Decide(true, 25m, 100m, 0m,
            TideLabH1V1Cost.Base, buyLiquidity with { AvailableUnits = 0m },
            opening, TimeSpan.FromMinutes(2), 1m).State == "HOLD_NO_LIQUIDITY",
            "Unobserved H1 size must not fill");
        Check(TideLabH1ConservativeExecution.Decide(true, 25m, 99m, 0m,
            TideLabH1V1Cost.Base, buyLiquidity, opening,
            TimeSpan.FromMinutes(2), 1m).State == "HOLD_LIMIT",
            "Buy execution may not exceed the limit");
        Check(TideLabH1ConservativeExecution.Decide(true, 25.000000001m, 100m,
            0m, TideLabH1V1Cost.Base, buyLiquidity, opening,
            TimeSpan.FromMinutes(2), 1m).State == "REJECT_TERMS",
            "H1 execution must enforce eight-decimal units");
        var sellLiquidity = new TideLabH1SyntheticLiquidity(
            bars[170].StartUtc, 98.2m, 10m);
        var sell = TideLabH1ConservativeExecution.Decide(false, 10m, 98m,
            0m, TideLabH1V1Cost.Base, sellLiquidity,
            bars[170].StartUtc, TimeSpan.FromMinutes(2), 1m);
        Check(sell == new TideLabH1ExecutionDecision("FILLED", 10m,
            98.1018m, 2.452545m, 0m),
            "Conservative H1 sell fill or declared cost changed");

        var trial = TideLabH1V1TrialAccounting.Analyze(bars, scoreStart,
            result, TideLabH1V1Cost.Base);
        var stressedTrial = TideLabH1V1TrialAccounting.Analyze(bars,
            scoreStart, stress, TideLabH1V1Cost.Stress);
        Check(trial.Strategy.FinalCash == result.Cash &&
            trial.Strategy.Fees == result.TotalFees &&
            trial.Strategy.ClosedRoundTrips == 1 &&
            trial.Strategy.LargestRoundTripPnl == result.Cash - 10000m &&
            trial.Strategy.NetWithoutLargestRoundTrip == 0m &&
            trial.Cash.FinalCash == 10000m && trial.Cash.MaximumDrawdown == 0m &&
            trial.QuarterHold.FinalCash > trial.Strategy.FinalCash &&
            trial.QuarterHold.FinalCash < trial.Cash.FinalCash &&
            trial.FullHold.FinalCash < trial.QuarterHold.FinalCash &&
            trial.FullHold.FinalCash > 0m &&
            trial.Strategy.MaximumDrawdown > 0m &&
            trial.Strategy.LongestUnderwaterHours > 0 &&
            trial.Strategy.UnderwaterHours >=
                trial.Strategy.LongestUnderwaterHours &&
            stressedTrial.Strategy.FinalCash < trial.Strategy.FinalCash &&
            stressedTrial.QuarterHold.FinalCash < trial.QuarterHold.FinalCash,
            "Registered H1 metrics or cost stress changed");
        rejected = false;
        try { TideLabH1V1TrialAccounting.Analyze(bars, scoreStart,
            result with { Cash = result.Cash + 1m }, TideLabH1V1Cost.Base); }
        catch (ArgumentException) { rejected = true; }
        Check(rejected, "Trial metrics accepted an unreconciled final account");
        Console.WriteLine("H1V1_SYNTHETIC_TRIAL accounting=pass " +
            $"round_trips={trial.Strategy.ClosedRoundTrips} " +
            $"cash={trial.Strategy.FinalCash} " +
            $"quarter={trial.QuarterHold.FinalCash} " +
            $"full={trial.FullHold.FinalCash} " +
            $"stress={stressedTrial.Strategy.FinalCash}");

        Console.WriteLine("H1V1_SYNTHETIC_ACCOUNTING replay=identical " +
            "next_open=pass units_8dp=pass fees=pass cash=pass " +
            "terminal=pass drawdown=pass gap=blocked unclosed=blocked orders=0");
    }
}
