// TideLab-authored deterministic H1 v1 research accounting. No order API.
using System;
using System.Collections.Generic;

namespace QuantConnect.Algorithm.CSharp
{
    public sealed record TideLabH1V1Bar(DateTime StartUtc, decimal Open,
        decimal Close, bool Closed);
    public sealed record TideLabH1V1Cost(decimal AdversePriceRate, decimal FeeRate)
    {
        public static TideLabH1V1Cost Base => new TideLabH1V1Cost(0.001m, 0.0025m);
        public static TideLabH1V1Cost Stress => new TideLabH1V1Cost(0.002m, 0.005m);
    }
    public sealed record TideLabH1V1Fill(DateTime SignalClosedUtc,
        DateTime FilledAtUtc, TideLabH1V1Intent Intent, decimal Units,
        decimal FillPrice, decimal Fee, decimal CashAfter, decimal UnitsAfter,
        bool Terminal);
    public sealed record TideLabH1V1Mark(DateTime ClosedAtUtc, decimal Cash,
        decimal Units, decimal Equity, decimal GrossExposure);
    public sealed record TideLabH1V1ReplayResult(decimal Cash, decimal Units,
        decimal TotalFees, IReadOnlyList<TideLabH1V1Fill> Fills,
        IReadOnlyList<TideLabH1V1Decision> Decisions,
        IReadOnlyList<TideLabH1V1Mark> Marks);

    public static class TideLabH1V1ResearchReplay
    {
        public static TideLabH1V1ReplayResult Run(IReadOnlyList<TideLabH1V1Bar> bars,
            DateTime scoreStartUtc, DateTime scoreEndUtc, TideLabH1V1Cost cost)
        {
            if (cost.AdversePriceRate < 0m || cost.AdversePriceRate >= 1m ||
                cost.FeeRate < 0m || cost.FeeRate >= 1m)
                throw new ArgumentException("Invalid research cost rates");
            if (scoreStartUtc.Kind != DateTimeKind.Utc ||
                scoreEndUtc.Kind != DateTimeKind.Utc ||
                scoreStartUtc >= scoreEndUtc ||
                scoreStartUtc.Minute != 0 || scoreStartUtc.Second != 0 ||
                scoreStartUtc.Ticks % TimeSpan.TicksPerSecond != 0 ||
                scoreEndUtc.Minute != 0 || scoreEndUtc.Second != 0 ||
                scoreEndUtc.Ticks % TimeSpan.TicksPerSecond != 0)
                throw new ArgumentException("Scored partition requires UTC hourly bounds");
            var scoredTicks = (scoreEndUtc - scoreStartUtc).Ticks;
            if (scoredTicks % TimeSpan.TicksPerHour != 0)
                throw new ArgumentException("Scored partition must contain whole hours");
            var scoredHours = checked((int)(scoredTicks / TimeSpan.TicksPerHour));
            if (scoredHours < 1 ||
                bars.Count != 168 + scoredHours + 1)
                throw new ArgumentException("Require 168 warmup, all scored bars, and one terminal open");
            var firstStart = scoreStartUtc.AddHours(-168);
            for (var i = 0; i < bars.Count; i++)
            {
                if (bars[i].StartUtc.Kind != DateTimeKind.Utc ||
                    bars[i].StartUtc != firstStart.AddHours(i) ||
                    bars[i].Open <= 0m ||
                    (i < bars.Count - 1 && (!bars[i].Closed || bars[i].Close <= 0m)))
                    throw new ArgumentException("Require closed positive, continuous UTC hours");
            }

            var policy = new TideLabH1V1Policy();
            var fills = new List<TideLabH1V1Fill>();
            var decisions = new List<TideLabH1V1Decision>();
            var marks = new List<TideLabH1V1Mark>();
            var cash = 10000m;
            var units = 0m;
            var totalFees = 0m;
            TideLabH1V1Decision? pending = null;

            for (var i = 0; i < bars.Count; i++)
            {
                var bar = bars[i];
                if (pending != null)
                {
                    if (bar.StartUtc != pending.ClosedAtUtc)
                        throw new InvalidOperationException("A signal cannot fill on its source bar");
                    Fill(pending.Intent, pending.ClosedAtUtc, bar.StartUtc,
                        bar.Open, false);
                    pending = null;
                }
                if (i == bars.Count - 1)
                {
                    if (units > 0m)
                        Fill(TideLabH1V1Intent.ExitToCash,
                            bar.StartUtc, bar.StartUtc, bar.Open, true);
                    break;
                }
                var closedAt = bar.StartUtc.AddHours(1);
                var equity = cash + units * bar.Close;
                var exposure = units == 0m ? 0m : units * bar.Close / equity;
                var decision = policy.OnClosedHour(closedAt, bar.Close,
                    units > 0m, equity, exposure);
                if (i < 168) continue; // Warmup updates the indicator only.
                marks.Add(new TideLabH1V1Mark(closedAt, cash, units, equity,
                    exposure));
                decisions.Add(decision);
                if (decision.Intent != TideLabH1V1Intent.Hold) pending = decision;
            }
            if (pending != null || units != 0m || cash <= 0m)
                throw new InvalidOperationException("Unsettled terminal research account");
            return new TideLabH1V1ReplayResult(cash, units, totalFees,
                fills.AsReadOnly(), decisions.AsReadOnly(), marks.AsReadOnly());

            void Fill(TideLabH1V1Intent intent, DateTime signalClosedUtc,
                DateTime filledAtUtc, decimal open, bool terminal)
            {
                if (intent == TideLabH1V1Intent.EnterLong)
                {
                    if (units != 0m) throw new InvalidOperationException("Entry while long");
                    var price = TideLabH1ConservativeExecution.Price(open, true, cost);
                    var target = cash * TideLabH1V1Policy.EntryTargetGrossExposure;
                    var quantity = decimal.Floor(target * 100000000m / price) /
                        100000000m;
                    if (quantity <= 0m)
                        throw new InvalidOperationException("Rounded entry has zero units");
                    var fee = TideLabH1ConservativeExecution.Fee(quantity, price, cost);
                    cash -= quantity * price + fee;
                    if (cash < 0m) throw new InvalidOperationException("Borrowing is forbidden");
                    units = quantity;
                    totalFees += fee;
                    fills.Add(new TideLabH1V1Fill(signalClosedUtc, filledAtUtc,
                        intent, quantity, price, fee, cash, units, terminal));
                }
                else if (intent == TideLabH1V1Intent.ExitToCash)
                {
                    if (units <= 0m) throw new InvalidOperationException("Exit while in cash");
                    var price = TideLabH1ConservativeExecution.Price(open, false, cost);
                    var quantity = units;
                    var fee = TideLabH1ConservativeExecution.Fee(quantity, price, cost);
                    cash += quantity * price - fee;
                    units = 0m;
                    totalFees += fee;
                    fills.Add(new TideLabH1V1Fill(signalClosedUtc, filledAtUtc,
                        intent, quantity, price, fee, cash, units, terminal));
                }
                else throw new InvalidOperationException("A hold is not a fill");
            }
        }
    }
}
