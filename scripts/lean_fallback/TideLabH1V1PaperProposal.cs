// TideLab-authored, synthetic H1 v1 proposal boundary. No order API.
using System;
using System.Security.Cryptography;
using System.Text;

namespace QuantConnect.Algorithm.CSharp
{
    public sealed record TideLabH1V1PaperProposal(string Policy, string ExperimentId,
        string InstrumentId, string ClientId, string SourceRevision,
        DateTime SignalClosedUtc, DateTime ObservedOpenUtc,
        int ClosedHours, TideLabH1V1Intent DecisionIntent,
        TideLabH1V1Risk Risk, bool EntriesHalted,
        string Side, decimal Quantity, decimal LimitPrice,
        decimal Equity, decimal Cash, decimal Units, decimal TargetGrossExposure);

    public static class TideLabH1V1PaperBoundary
    {
        public static TideLabH1V1PaperProposal Create(TideLabH1V1Decision decision,
            string experimentId, string instrumentId, string sourceRevision,
            DateTime observedOpenUtc, decimal limitPrice, decimal equity,
            decimal cash, decimal units)
        {
            if (string.IsNullOrWhiteSpace(experimentId) ||
                string.IsNullOrWhiteSpace(instrumentId) ||
                string.IsNullOrWhiteSpace(sourceRevision))
                throw new ArgumentException("Proposal identity is required");
            if (decision.ClosedAtUtc.Kind != DateTimeKind.Utc ||
                observedOpenUtc.Kind != DateTimeKind.Utc ||
                observedOpenUtc != decision.ClosedAtUtc ||
                decision.ClosedHours < 168 || decision.Mean is null ||
                limitPrice <= 0m || equity <= 0m || cash < 0m || units < 0m)
                throw new ArgumentException("Proposal requires a current opening mark and warmed policy");
            if (decision.Intent == TideLabH1V1Intent.Hold)
                throw new ArgumentException("Hold decisions cannot become paper intents");
            if (decision.Intent == TideLabH1V1Intent.EnterLong &&
                (decision.Risk != TideLabH1V1Risk.Clear ||
                 decision.EntriesHalted || decision.TargetGrossExposure != 0.25m ||
                 units != 0m || cash < equity * 0.25m))
                throw new ArgumentException("Entry proposal violates H1 risk or account state");
            if (decision.Intent == TideLabH1V1Intent.ExitToCash &&
                (decision.TargetGrossExposure != 0m || units <= 0m ||
                 decision.Risk == TideLabH1V1Risk.ExposureBlock ||
                 (decision.Risk == TideLabH1V1Risk.DrawdownHalt) !=
                    decision.EntriesHalted))
                throw new ArgumentException("Exit proposal requires inventory");

            var side = decision.Intent == TideLabH1V1Intent.EnterLong ? "buy" : "sell";
            var quantity = side == "buy" ?
                decimal.Floor(equity * 0.25m / limitPrice * 100000000m) / 100000000m : units;
            if (quantity <= 0m || (side == "buy" && quantity * limitPrice > cash))
                throw new ArgumentException("Proposal cannot be sized without borrowing");
            var identity = $"H1-v1|{experimentId}|{instrumentId}|{decision.ClosedAtUtc:O}|{side}";
            var hash = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(identity)));
            return new TideLabH1V1PaperProposal("H1-v1", experimentId,
                instrumentId, "H1V1-" + hash, sourceRevision,
                decision.ClosedAtUtc, observedOpenUtc, decision.ClosedHours,
                decision.Intent, decision.Risk, decision.EntriesHalted,
                side, quantity, limitPrice,
                equity, cash, units, decision.TargetGrossExposure!.Value);
        }
    }
}
