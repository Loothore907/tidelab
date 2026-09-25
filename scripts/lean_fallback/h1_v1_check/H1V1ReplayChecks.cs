using QuantConnect.Algorithm.CSharp;

internal static class H1V1ReplayChecks
{
    private static void Check(bool condition, string message)
    {
        if (!condition) throw new Exception(message);
    }

    public static void Run()
    {
        var firstStart = new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        var scoreStart = firstStart.AddHours(168);
        var scoreEnd = scoreStart.AddHours(2);
        var bars = Enumerable.Range(0, 171).Select(index => new TideLabH1V1Bar(
            firstStart.AddHours(index),
            index == 169 ? 102m : index == 170 ? 98m : 100m,
            index == 168 ? 102m : index == 169 ? 98m : 100m,
            index < 170
        )).ToArray();

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

        Console.WriteLine("H1V1_SYNTHETIC_ACCOUNTING replay=identical " +
            "next_open=pass units_8dp=pass fees=pass cash=pass " +
            "terminal=pass drawdown=pass gap=blocked unclosed=blocked orders=0");
    }
}
