// TideLab-authored H1 v1 research metrics. Synthetic and private runs only.
using System;
using System.Collections.Generic;
using System.Linq;

namespace QuantConnect.Algorithm.CSharp
{
    public sealed record TideLabH1AccountMetrics(decimal FinalCash,
        decimal NetReturn, decimal MaximumDrawdown, int UnderwaterHours,
        int LongestUnderwaterHours,
        decimal AverageGrossExposure, decimal Turnover, decimal Fees,
        int ClosedRoundTrips, decimal LargestRoundTripPnl,
        decimal NetWithoutLargestRoundTrip);

    public sealed record TideLabH1TrialMetrics(TideLabH1AccountMetrics Strategy,
        TideLabH1AccountMetrics Cash, TideLabH1AccountMetrics QuarterHold,
        TideLabH1AccountMetrics FullHold);

    public static class TideLabH1V1TrialAccounting
    {
        private const decimal StartingCash = 10000m;
        private const decimal UnitScale = 100000000m;

        public static TideLabH1TrialMetrics Analyze(
            IReadOnlyList<TideLabH1V1Bar> bars, DateTime scoreStartUtc,
            TideLabH1V1ReplayResult replay, TideLabH1V1Cost cost)
        {
            if (bars.Count < 170 || replay.Marks.Count != bars.Count - 169 ||
                bars[168].StartUtc != scoreStartUtc || replay.Units != 0m ||
                replay.Cash <= 0m)
                throw new ArgumentException("Trial metrics need a settled H1 partition");
            var strategyEquity = replay.Marks.Select(mark => mark.Equity)
                .Append(replay.Cash).ToArray();
            var exposure = replay.Marks.Select(mark => mark.GrossExposure).ToArray();
            var turnover = replay.Fills.Sum(fill => fill.Units * fill.FillPrice) /
                StartingCash;
            decimal? entryCost = null;
            var accountCash = StartingCash;
            var accountUnits = 0m;
            var entryUnits = 0m;
            var largest = 0m;
            var roundTrips = 0;
            foreach (var fill in replay.Fills)
            {
                if (fill.Intent == TideLabH1V1Intent.EnterLong)
                {
                    if (entryCost != null)
                        throw new ArgumentException("Overlapping H1 research entries");
                    entryCost = fill.Units * fill.FillPrice + fill.Fee;
                    entryUnits = fill.Units;
                    accountCash -= entryCost.Value;
                    accountUnits += fill.Units;
                }
                else if (fill.Intent == TideLabH1V1Intent.ExitToCash)
                {
                    if (entryCost == null || fill.Units != entryUnits)
                        throw new ArgumentException("H1 exit lacks an entry");
                    var pnl = fill.Units * fill.FillPrice - fill.Fee - entryCost.Value;
                    accountCash += fill.Units * fill.FillPrice - fill.Fee;
                    accountUnits -= fill.Units;
                    if (roundTrips == 0 || pnl > largest) largest = pnl;
                    roundTrips++;
                    entryCost = null;
                    entryUnits = 0m;
                }
                else throw new ArgumentException("A hold cannot be a fill");
                if (accountCash != fill.CashAfter ||
                    accountUnits != fill.UnitsAfter || accountCash < 0m ||
                    accountUnits < 0m)
                    throw new ArgumentException("H1 fill account does not reconcile");
            }
            if (entryCost != null || accountCash != replay.Cash ||
                    accountUnits != replay.Units || replay.TotalFees !=
                    replay.Fills.Sum(fill => fill.Fee))
                throw new ArgumentException("Unsettled H1 trade or fee mismatch");
            var strategy = Metrics(replay.Cash, strategyEquity, exposure,
                turnover, replay.TotalFees, roundTrips, largest);
            var cash = Metrics(StartingCash,
                Enumerable.Repeat(StartingCash, strategyEquity.Length).ToArray(),
                Enumerable.Repeat(0m, exposure.Length).ToArray(),
                0m, 0m, 0, 0m);
            return new TideLabH1TrialMetrics(strategy, cash,
                Benchmark(bars, cost, 0.25m), Benchmark(bars, cost, 1m));
        }

        private static TideLabH1AccountMetrics Benchmark(
            IReadOnlyList<TideLabH1V1Bar> bars, TideLabH1V1Cost cost,
            decimal allocation)
        {
            var buy = TideLabH1ConservativeExecution.Price(
                bars[168].Open, true, cost);
            var target = StartingCash * allocation;
            var affordable = StartingCash / (buy * (1m + cost.FeeRate));
            var units = decimal.Floor(Math.Min(target / buy, affordable) *
                UnitScale) / UnitScale;
            if (units <= 0m) throw new ArgumentException("Benchmark has no units");
            var buyFee = TideLabH1ConservativeExecution.Fee(units, buy, cost);
            var remainingCash = StartingCash - units * buy - buyFee;
            if (remainingCash < 0m)
                throw new ArgumentException("Benchmark would borrow");
            var marks = bars.Skip(168).Take(bars.Count - 169)
                .Select(bar => remainingCash + units * bar.Close).ToArray();
            var exposure = bars.Skip(168).Take(bars.Count - 169)
                .Select((bar, index) => units * bar.Close / marks[index]).ToArray();
            var sell = TideLabH1ConservativeExecution.Price(
                bars[^1].Open, false, cost);
            var sellFee = TideLabH1ConservativeExecution.Fee(units, sell, cost);
            var final = remainingCash + units * sell - sellFee;
            var equity = marks.Append(final).ToArray();
            return Metrics(final, equity, exposure,
                units * (buy + sell) / StartingCash, buyFee + sellFee,
                1, final - StartingCash);
        }

        private static TideLabH1AccountMetrics Metrics(decimal final,
            IReadOnlyList<decimal> equity, IReadOnlyList<decimal> exposure,
            decimal turnover, decimal fees, int roundTrips, decimal largest)
        {
            if (equity.Count != exposure.Count + 1 ||
                equity.Any(value => value <= 0m) ||
                exposure.Any(value => value < 0m || value > 1m))
                throw new ArgumentException("Invalid H1 marked account");
            var peak = StartingCash;
            var maximumDrawdown = 0m;
            var underwater = 0;
            var totalUnderwater = 0;
            var longest = 0;
            for (var index = 0; index < equity.Count; index++)
            {
                var value = equity[index];
                if (value >= peak)
                {
                    peak = value;
                    underwater = 0;
                }
                else
                {
                    // Terminal liquidation shares the final close's timestamp.
                    if (index < equity.Count - 1)
                    {
                        underwater++;
                        totalUnderwater++;
                    }
                    longest = Math.Max(longest, underwater);
                    maximumDrawdown = Math.Max(maximumDrawdown,
                        (peak - value) / peak);
                }
            }
            return new TideLabH1AccountMetrics(final,
                (final - StartingCash) / StartingCash, maximumDrawdown,
                totalUnderwater, longest,
                exposure.Count == 0 ? 0m : exposure.Average(),
                turnover, fees, roundTrips, largest,
                final - StartingCash - largest);
        }
    }
}
