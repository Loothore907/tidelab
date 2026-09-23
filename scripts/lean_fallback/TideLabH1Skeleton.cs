// TideLab-authored synthetic H1 compatibility skeleton; not a trading strategy.
using System;

namespace QuantConnect.Algorithm.CSharp
{
    public enum TideLabH1Intent { None, EnterLong, ExitToCash }
    public enum TideLabH1RiskDecision { None, Approve, BlockDrawdown, BlockExposure }

    public sealed record TideLabH1Decision(int ClosedHour, TideLabH1Intent Intent,
        TideLabH1RiskDecision Risk);

    public sealed class TideLabH1Strategy
    {
        private decimal _firstClose;
        public int ClosedHours { get; private set; }

        public TideLabH1Intent OnClosedHour(decimal close)
        {
            ClosedHours++;
            if (ClosedHours == 1) _firstClose = close;
            if (ClosedHours == 3 && close > _firstClose)
                return TideLabH1Intent.EnterLong;
            if (ClosedHours == 4 && close < _firstClose)
                return TideLabH1Intent.ExitToCash;
            return TideLabH1Intent.None;
        }
    }

    public sealed class TideLabH1RiskGate
    {
        public TideLabH1RiskDecision Evaluate(TideLabH1Intent intent,
            decimal targetGrossExposure, decimal equity, decimal peakEquity)
        {
            if (intent == TideLabH1Intent.None) return TideLabH1RiskDecision.None;
            // An exit is allowed even while new entries are paused.
            if (intent == TideLabH1Intent.ExitToCash)
                return TideLabH1RiskDecision.Approve;
            if (equity <= 0m || peakEquity <= 0m || equity < peakEquity * 0.95m)
                return TideLabH1RiskDecision.BlockDrawdown;
            if (targetGrossExposure < 0m || targetGrossExposure > 0.25m)
                return TideLabH1RiskDecision.BlockExposure;
            return TideLabH1RiskDecision.Approve;
        }
    }

    public sealed class TideLabH1Skeleton
    {
        private readonly TideLabH1Strategy _strategy = new TideLabH1Strategy();
        private readonly TideLabH1RiskGate _risk = new TideLabH1RiskGate();

        public TideLabH1Decision OnClosedHour(decimal close, decimal equity,
            decimal peakEquity)
        {
            var intent = _strategy.OnClosedHour(close);
            var risk = _risk.Evaluate(intent, 0.25m, equity, peakEquity);
            return new TideLabH1Decision(_strategy.ClosedHours, intent, risk);
        }
    }
}
