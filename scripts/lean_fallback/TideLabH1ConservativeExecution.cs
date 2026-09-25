// TideLab-authored H1 v1 synthetic execution arithmetic. No broker or data API.
using System;

namespace QuantConnect.Algorithm.CSharp
{
    public sealed record TideLabH1SyntheticLiquidity(DateTime ObservedAtUtc,
        decimal ReferenceOpen, decimal AvailableUnits);

    public sealed record TideLabH1ExecutionDecision(string State,
        decimal Quantity, decimal Price, decimal Fee, decimal Remaining);

    public static class TideLabH1ConservativeExecution
    {
        private const decimal UnitScale = 100000000m;

        public static decimal Price(decimal open, bool buy, TideLabH1V1Cost cost)
        {
            if (open <= 0m || cost.AdversePriceRate < 0m ||
                cost.AdversePriceRate >= 1m || cost.FeeRate < 0m ||
                cost.FeeRate >= 1m)
                throw new ArgumentException("Invalid H1 price or cost");
            return open * (buy ? 1m + cost.AdversePriceRate :
                                 1m - cost.AdversePriceRate);
        }

        public static decimal Fee(decimal quantity, decimal price,
            TideLabH1V1Cost cost)
        {
            if (quantity <= 0m || price <= 0m || cost.FeeRate < 0m ||
                cost.FeeRate >= 1m)
                throw new ArgumentException("Invalid H1 fee terms");
            return quantity * price * cost.FeeRate;
        }

        // An observed quote can bound a test-owned paper fill. Historical bars
        // contain no executable size, so this cannot infer a real fill from OHLCV.
        public static TideLabH1ExecutionDecision Decide(bool buy,
            decimal orderQuantity, decimal limitPrice, decimal alreadyFilled,
            TideLabH1V1Cost cost, TideLabH1SyntheticLiquidity? liquidity,
            DateTime nowUtc, TimeSpan maximumAge, decimal minimumNotional)
        {
            if (orderQuantity <= 0m || orderQuantity > decimal.MaxValue / UnitScale ||
                alreadyFilled > decimal.MaxValue / UnitScale ||
                orderQuantity * UnitScale !=
                    decimal.Floor(orderQuantity * UnitScale) ||
                limitPrice <= 0m || alreadyFilled < 0m ||
                alreadyFilled * UnitScale !=
                    decimal.Floor(alreadyFilled * UnitScale) ||
                alreadyFilled >= orderQuantity || maximumAge <= TimeSpan.Zero ||
                minimumNotional < 0m || nowUtc.Kind != DateTimeKind.Utc ||
                cost.AdversePriceRate < 0m || cost.AdversePriceRate >= 1m ||
                cost.FeeRate < 0m || cost.FeeRate >= 1m)
                return new("REJECT_TERMS", 0m, 0m, 0m, 0m);
            var remaining = orderQuantity - alreadyFilled;
            if (liquidity is null || liquidity.ObservedAtUtc.Kind != DateTimeKind.Utc ||
                liquidity.ObservedAtUtc > nowUtc ||
                nowUtc - liquidity.ObservedAtUtc > maximumAge)
                return new("HOLD_STALE_OR_UNKNOWN", 0m, 0m, 0m, remaining);
            if (liquidity.ReferenceOpen <= 0m || liquidity.AvailableUnits < 0m)
                return new("REJECT_LIQUIDITY", 0m, 0m, 0m, remaining);
            var quantity = decimal.Floor(Math.Min(remaining,
                liquidity.AvailableUnits) * UnitScale) / UnitScale;
            if (quantity == 0m)
                return new("HOLD_NO_LIQUIDITY", 0m, 0m, 0m, remaining);
            var price = Price(liquidity.ReferenceOpen, buy, cost);
            if ((buy && price > limitPrice) || (!buy && price < limitPrice))
                return new("HOLD_LIMIT", 0m, 0m, 0m, remaining);
            if (quantity * price < minimumNotional)
                return new("HOLD_BELOW_MINIMUM", 0m, 0m, 0m, remaining);
            return new(quantity == remaining ? "FILLED" : "PARTIAL", quantity,
                price, Fee(quantity, price, cost), remaining - quantity);
        }
    }
}
