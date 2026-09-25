// TideLab-authored H1 v1 decision policy. It does not submit or fill orders.
using System;
using System.Collections.Generic;

namespace QuantConnect.Algorithm.CSharp
{
    public enum TideLabH1V1Intent { Hold, EnterLong, ExitToCash }
    public enum TideLabH1V1Risk { Clear, DrawdownHalt, ExposureBlock }

    public sealed record TideLabH1V1Decision(DateTime ClosedAtUtc, int ClosedHours,
        decimal? Mean, TideLabH1V1Intent Intent, TideLabH1V1Risk Risk,
        bool EntriesHalted, decimal? TargetGrossExposure);

    // The signal consumes closed bars only. Position state is supplied by the
    // execution/ledger boundary, never inferred from an unfilled proposal.
    public sealed class TideLabH1V1Signal
    {
        private readonly Queue<decimal> _closes = new Queue<decimal>();
        private decimal _sum;
        private DateTime? _lastCloseUtc;
        public int ClosedHours { get; private set; }

        public (decimal? Mean, TideLabH1V1Intent Intent) OnClosedHour(
            DateTime closedAtUtc, decimal close, bool isLong)
        {
            if (closedAtUtc.Kind != DateTimeKind.Utc ||
                closedAtUtc.Minute != 0 || closedAtUtc.Second != 0 ||
                closedAtUtc.Ticks % TimeSpan.TicksPerSecond != 0 || close <= 0m)
                throw new ArgumentException("Expected a positive, closed UTC hourly bar");
            if (_lastCloseUtc.HasValue &&
                closedAtUtc != _lastCloseUtc.Value.AddHours(1))
                throw new InvalidOperationException("Duplicate or missing closed hour");
            _lastCloseUtc = closedAtUtc;
            _closes.Enqueue(close);
            _sum += close;
            if (_closes.Count > 168) _sum -= _closes.Dequeue();
            ClosedHours++;
            if (_closes.Count < 168) return (null, TideLabH1V1Intent.Hold);
            var mean = _sum / 168m;
            var intent = isLong ?
                (close <= mean ? TideLabH1V1Intent.ExitToCash : TideLabH1V1Intent.Hold) :
                (close > mean ? TideLabH1V1Intent.EnterLong : TideLabH1V1Intent.Hold);
            return (mean, intent);
        }
    }

    // A new policy instance is required for each scored partition. Warmup is
    // supplied as closed bars with constant starting equity and a cash position.
    public sealed class TideLabH1V1RiskGate
    {
        private decimal _peakEquity;
        public bool EntriesHalted { get; private set; }

        public TideLabH1V1Risk Evaluate(decimal equity, bool isLong,
            decimal grossExposure, decimal proposedGrossExposure,
            ref TideLabH1V1Intent intent)
        {
            if (equity <= 0m || grossExposure < 0m ||
                proposedGrossExposure < 0m)
                throw new ArgumentException("Invalid account mark or exposure");
            if (equity > _peakEquity) _peakEquity = equity;
            if (equity <= _peakEquity * 0.80m) EntriesHalted = true;
            if (EntriesHalted)
            {
                intent = isLong ? TideLabH1V1Intent.ExitToCash : TideLabH1V1Intent.Hold;
                return TideLabH1V1Risk.DrawdownHalt;
            }
            if (intent == TideLabH1V1Intent.EnterLong &&
                (isLong || grossExposure != 0m || proposedGrossExposure == 0m ||
                    proposedGrossExposure > TideLabH1V1Policy.EntryTargetGrossExposure))
            {
                intent = TideLabH1V1Intent.Hold;
                return TideLabH1V1Risk.ExposureBlock;
            }
            return TideLabH1V1Risk.Clear;
        }
    }

    public sealed class TideLabH1V1Policy
    {
        public const decimal EntryTargetGrossExposure = 0.25m;
        private readonly TideLabH1V1Signal _signal = new TideLabH1V1Signal();
        private readonly TideLabH1V1RiskGate _risk = new TideLabH1V1RiskGate();

        public TideLabH1V1Decision OnClosedHour(DateTime closedAtUtc,
            decimal close, bool isLong, decimal equity, decimal grossExposure)
        {
            if (equity <= 0m || grossExposure < 0m)
                throw new ArgumentException("Invalid account mark or exposure");
            var (mean, intent) = _signal.OnClosedHour(closedAtUtc, close, isLong);
            var risk = _risk.Evaluate(equity, isLong, grossExposure,
                intent == TideLabH1V1Intent.EnterLong ? EntryTargetGrossExposure : 0m,
                ref intent);
            decimal? target = intent switch
            {
                TideLabH1V1Intent.EnterLong => EntryTargetGrossExposure,
                TideLabH1V1Intent.ExitToCash => 0m,
                _ => null
            };
            return new TideLabH1V1Decision(closedAtUtc, _signal.ClosedHours,
                mean, intent, risk, _risk.EntriesHalted, target);
        }
    }
}
