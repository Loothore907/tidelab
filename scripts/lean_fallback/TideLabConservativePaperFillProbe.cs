// TideLab-authored, synthetic TL-001A fill/restart probe. No venue or market data.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using Moq;
using NUnit.Framework;
using QuantConnect;
using QuantConnect.Algorithm;
using QuantConnect.Brokerages;
using QuantConnect.Data;
using QuantConnect.Data.Auxiliary;
using QuantConnect.Data.Market;
using QuantConnect.Interfaces;
using QuantConnect.Lean.Engine.DataFeeds;
using QuantConnect.Lean.Engine.RealTime;
using QuantConnect.Lean.Engine.Results;
using QuantConnect.Lean.Engine.Setup;
using QuantConnect.Lean.Engine.TransactionHandlers;
using QuantConnect.Orders;
using QuantConnect.Orders.Fees;
using QuantConnect.Orders.Fills;
using QuantConnect.Securities;
using QuantConnect.Securities.Equity;
using QuantConnect.Tests.Common.Data;
using QuantConnect.Tests.Common.Securities;
using QuantConnect.Tests.Engine.DataFeeds;

namespace QuantConnect.Tests.Engine.Setup
{
    public sealed record TideLabQuote(DateTime TimeUtc, decimal Bid, decimal Ask,
        decimal BidSize, decimal AskSize);

    public sealed record TideLabFillRules(int Version, string Currency, decimal Tick,
        decimal Lot, decimal FeeRate, int SlippageTicks, decimal MinimumNotional,
        TimeSpan MaximumQuoteAge);

    public sealed record TideLabFillDecision(string State, decimal Quantity,
        decimal Price, decimal Fee, decimal Remaining);

    // One explicit policy is called by the historical LEAN fill seam and the
    // replaceable synthetic paper authority. It is not a venue fill forecast.
    public static class TideLabConservativeFillPolicy
    {
        public static TideLabFillDecision Decide(TideLabFillRules rules,
            TideLabQuote quote, DateTime nowUtc, decimal orderQuantity,
            decimal alreadyFilled)
        {
            if (rules.Version != 1 || rules.Currency != Currencies.USD ||
                rules.Tick <= 0 || rules.Lot <= 0 || rules.FeeRate < 0 ||
                rules.SlippageTicks < 0 || rules.MinimumNotional < 0 ||
                rules.MaximumQuoteAge <= TimeSpan.Zero ||
                orderQuantity == 0 ||
                Math.Abs(orderQuantity) % rules.Lot != 0 ||
                alreadyFilled < 0 || alreadyFilled >= Math.Abs(orderQuantity))
                return new("REJECT_RULE_OR_ORDER", 0, 0, 0, 0);

            var remaining = Math.Abs(orderQuantity) - alreadyFilled;
            if (quote == null || quote.TimeUtc.Kind != DateTimeKind.Utc ||
                nowUtc.Kind != DateTimeKind.Utc || quote.TimeUtc > nowUtc ||
                nowUtc - quote.TimeUtc > rules.MaximumQuoteAge)
                return new("HOLD_STALE_OR_UNKNOWN_QUOTE", 0, 0, 0, remaining);
            if (quote.Bid <= 0 || quote.Ask < quote.Bid ||
                quote.BidSize < 0 || quote.AskSize < 0)
                return new("REJECT_INVALID_QUOTE", 0, 0, 0, remaining);

            var buy = orderQuantity > 0;
            var displayed = buy ? quote.AskSize : quote.BidSize;
            var quantity = Math.Floor(Math.Min(remaining, displayed) / rules.Lot) * rules.Lot;
            if (quantity == 0)
                return new("HOLD_NO_DISPLAYED_LOT", 0, 0, 0, remaining);

            var rawPrice = (buy ? quote.Ask : quote.Bid) +
                (buy ? 1 : -1) * rules.SlippageTicks * rules.Tick;
            if (rawPrice <= 0) return new("REJECT_INVALID_PRICE", 0, 0, 0, remaining);
            var price = (buy ? Math.Ceiling(rawPrice / rules.Tick) :
                Math.Floor(rawPrice / rules.Tick)) * rules.Tick;
            if (quantity * price < rules.MinimumNotional)
                return new("REJECT_BELOW_MINIMUM", 0, 0, 0, remaining);
            var fee = decimal.Round(quantity * price * rules.FeeRate, 6,
                MidpointRounding.AwayFromZero);
            return new(quantity == remaining ? "FILLED" : "PARTIAL",
                buy ? quantity : -quantity, price, fee, remaining - quantity);
        }
    }

    public sealed class TideLabConservativeLeanFillModel : FillModel
    {
        private readonly TideLabFillRules _rules;
        private readonly TideLabQuote _quote;
        public TideLabConservativeLeanFillModel(TideLabFillRules rules,
            TideLabQuote quote) { _rules = rules; _quote = quote; }

        public override OrderEvent MarketFill(Security asset, MarketOrder order)
        {
            var decision = TideLabConservativeFillPolicy.Decide(_rules, _quote,
                order.Time, order.Quantity, 0);
            if (decision.State.StartsWith("REJECT", StringComparison.Ordinal))
                throw new InvalidDataException(decision.State);
            var fill = new OrderEvent(order, order.Time,
                new OrderFee(new CashAmount(decision.Fee, _rules.Currency)))
            {
                FillQuantity = decision.Quantity,
                FillPrice = decision.Price,
                Status = decision.State == "FILLED" ? OrderStatus.Filled :
                    decision.State == "PARTIAL" ? OrderStatus.PartiallyFilled :
                    OrderStatus.None,
                Message = decision.State
            };
            return fill;
        }
    }

    public sealed record TideLabConservativePaperReport(int Version, string ClientId,
        string BrokerId, string ExecutionId, string State, decimal OrderQuantity,
        decimal FilledQuantity, decimal Remaining, decimal FillPrice, decimal Fee,
        decimal Cash, decimal Holding);

    public static class TideLabConservativePaperFillProbe
    {
        private const string ClientId = "TL001A-CONSERVATIVE-CLIENT-1";
        private const string BrokerId = "TL001A-CONSERVATIVE-BROKER-1";
        private const string ExecutionId = "TL001A-CONSERVATIVE-EXEC-1";
        private static readonly DateTime Now = new(2026, 1, 1, 18, 0, 0,
            DateTimeKind.Utc);
        private static readonly TideLabFillRules Rules = new(1, Currencies.USD,
            0.01m, 0.1m, 0.001m, 1, 1m, TimeSpan.FromMinutes(2));
        private static readonly TideLabQuote Quote = new(Now.AddMinutes(-1),
            100m, 100.20m, 0.4m, 0.4m);

        private static TideLabFillDecision ExpectedDecision() =>
            TideLabConservativeFillPolicy.Decide(Rules, Quote, Now, 1m, 0);

        private static TideLabConservativePaperReport ExpectedReport()
        {
            var fill = ExpectedDecision();
            return new(1, ClientId, BrokerId, ExecutionId, fill.State, 1m,
                fill.Quantity, fill.Remaining, fill.Price, fill.Fee,
                1000m - fill.Quantity * fill.Price - fill.Fee, fill.Quantity);
        }

        private static string ReportPath(string path) => path + ".conservative.json";

        private static TideLabConservativePaperReport ReadReport(string path)
        {
            if (File.Exists(ReportPath(path) + ".next"))
                throw new InvalidDataException("BLOCK_TORN_REPORT");
            var report = JsonSerializer.Deserialize<TideLabConservativePaperReport>(
                File.ReadAllText(ReportPath(path)));
            if (report != ExpectedReport())
                throw new InvalidDataException("BLOCK_FILL_OR_ACCOUNT_MISMATCH");
            return report;
        }

        public static OrderEvent HistoricalFill(TideLabFillRules rules,
            TideLabQuote quote, DateTime nowUtc, decimal quantity)
        {
            var symbol = Symbol.Create("TL001ASYN", SecurityType.Equity, Market.USA);
            var order = new MarketOrder(symbol, quantity, nowUtc);
            var localTime = nowUtc.ConvertFromUtc(TimeZones.NewYork);
            var keeper = new TimeKeeper(nowUtc, new[] { TimeZones.NewYork });
            var tradeConfig = new SubscriptionDataConfig(typeof(TradeBar), symbol,
                Resolution.Minute, TimeZones.NewYork, TimeZones.NewYork, true,
                true, false);
            var quoteConfig = new SubscriptionDataConfig(tradeConfig,
                typeof(QuoteBar));
            var provider = new MockSubscriptionDataConfigProvider(quoteConfig);
            provider.SubscriptionDataConfigs.Add(tradeConfig);
            var equity = new Equity(
                SecurityExchangeHoursTests.CreateUsEquitySecurityExchangeHours(),
                tradeConfig, new Cash(Currencies.USD, 0, 1m),
                SymbolProperties.GetDefault(Currencies.USD),
                ErrorCurrencyConverter.Instance,
                RegisteredSecurityDataTypesProvider.Null, Exchange.ARCA);
            equity.SetLocalTimeKeeper(keeper.GetLocalTimeKeeper(TimeZones.NewYork));
            equity.SetMarketPrice(new QuoteBar(localTime.AddMinutes(-1), symbol,
                new Bar(quote.Bid, quote.Bid, quote.Bid, quote.Bid), quote.BidSize,
                new Bar(quote.Ask, quote.Ask, quote.Ask, quote.Ask), quote.AskSize));
            return new TideLabConservativeLeanFillModel(rules, quote)
                .Fill(new FillModelParameters(equity, order, provider,
                    Time.OneHour, null)).Single();
        }

        private static void CheckPolicyAndHistoricalSeam()
        {
            var expected = ExpectedDecision();
            Assert.That(expected, Is.EqualTo(new TideLabFillDecision(
                "PARTIAL", 0.4m, 100.21m, 0.040084m, 0.6m)));
            var leanFill = HistoricalFill(Rules, Quote, Now, 1m);
            Assert.That(leanFill.Status, Is.EqualTo(OrderStatus.PartiallyFilled));
            Assert.That(leanFill.FillQuantity, Is.EqualTo(expected.Quantity));
            Assert.That(leanFill.FillPrice, Is.EqualTo(expected.Price));
            Assert.That(leanFill.OrderFee.Value.Amount, Is.EqualTo(expected.Fee));
            Assert.That(leanFill.OrderFee.Value.Currency, Is.EqualTo(Currencies.USD));
            Assert.That(TideLabConservativeFillPolicy.Decide(Rules,
                Quote with { TimeUtc = Now.AddMinutes(-3) }, Now, 1m, 0).State,
                Is.EqualTo("HOLD_STALE_OR_UNKNOWN_QUOTE"));
            Assert.That(TideLabConservativeFillPolicy.Decide(Rules,
                Quote with { AskSize = 0.05m }, Now, 1m, 0).State,
                Is.EqualTo("HOLD_NO_DISPLAYED_LOT"));
            Assert.That(TideLabConservativeFillPolicy.Decide(Rules,
                Quote, Now, 1.05m, 0).State,
                Is.EqualTo("REJECT_RULE_OR_ORDER"));
            Assert.That(TideLabConservativeFillPolicy.Decide(Rules,
                Quote, Now, -1m, 0), Is.EqualTo(new TideLabFillDecision(
                "PARTIAL", -0.4m, 99.99m, 0.039996m, 0.6m)));
        }

        private sealed class ProbeAlgorithm : QCAlgorithm
        {
            public override void Initialize() { }
        }

        private static void CheckLeanRestart(TideLabConservativePaperReport report)
        {
            var symbol = Symbol.Create("TL001ASYN", SecurityType.Equity, Market.USA);
            var algorithm = new ProbeAlgorithm();
            var dataManager = new DataManagerStub(algorithm, new MockDataFeed(),
                liveMode: true);
            algorithm.SubscriptionManager.SetDataManager(dataManager);
            var transaction = new BrokerageTransactionHandler();
            var results = new Mock<IResultHandler>();
            var realTime = new Mock<IRealTimeHandler>();
            var brokerage = new Mock<IBrokerage>();
            brokerage.Setup(x => x.IsConnected).Returns(true);
            brokerage.Setup(x => x.AccountBaseCurrency).Returns(Currencies.USD);
            brokerage.Setup(x => x.GetCashBalance()).Returns(new List<CashAmount>
                { new(report.Cash, Currencies.USD) });
            brokerage.Setup(x => x.GetAccountHoldings()).Returns(new List<Holding>
                { new() { Symbol = symbol, Quantity = report.Holding,
                    AveragePrice = report.FillPrice, MarketPrice = report.FillPrice } });
            brokerage.Setup(x => x.GetOpenOrders()).Returns(new List<Order>
                { new MarketOrder(symbol, report.OrderQuantity, Now)
                    { Status = OrderStatus.PartiallyFilled,
                        BrokerId = new List<string> { report.BrokerId } } });

            transaction.Initialize(algorithm, brokerage.Object, results.Object);
            using var setup = new BrokerageSetupHandler();
            var job = BrokerageSetupHandlerTests.GetJob();
            IBrokerageFactory factory;
            setup.CreateBrokerage(job, algorithm, out factory);
            factory.Dispose();
            var ok = setup.Setup(new SetupHandlerParameters(
                dataManager.UniverseSelection, algorithm, brokerage.Object, job,
                results.Object, transaction, realTime.Object,
                TestGlobals.DataCacheProvider, TestGlobals.MapFileProvider));
            Assert.That(ok, Is.True, string.Join(" | ", setup.Errors));
            var restored = transaction.GetOpenOrders().Single();
            Assert.That(restored.Status, Is.EqualTo(OrderStatus.PartiallyFilled));
            Assert.That(restored.BrokerId, Does.Contain(report.BrokerId));
            Assert.That(algorithm.Portfolio.CashBook[Currencies.USD].Amount,
                Is.EqualTo(report.Cash));
            Assert.That(algorithm.Portfolio[symbol].Quantity,
                Is.EqualTo(report.Holding));
            brokerage.Verify(x => x.PlaceOrder(It.IsAny<Order>()), Times.Never);
            transaction.Exit();
        }

        public static void Run(string path, string phase)
        {
            CheckPolicyAndHistoricalSeam();
            if (phase == "conservative_historical")
            {
                Console.WriteLine("TL001A_LEAN_CONSERVATIVE phase=historical " +
                    "fill=0.4@100.21 fee=0.040084 remaining=0.6 " +
                    "stale=HOLD no_lot=HOLD bad_order=REJECT");
                return;
            }
            if (phase == "conservative_forward_seed")
            {
                Assert.That(File.Exists(ReportPath(path)), Is.False);
                TideLabPaperIntentRecoveryProbe.WriteAtomic(ReportPath(path),
                    ExpectedReport());
                Assert.That(ReadReport(path), Is.EqualTo(ExpectedReport()));
                Console.WriteLine("TL001A_LEAN_CONSERVATIVE phase=forward_seed " +
                    "execution=committed fill=0.4@100.21 remaining=0.6 " +
                    "cash=959.875916 holding=0.4 new_submissions=0");
                Environment.Exit(73);
            }
            if (phase is "conservative_forward_restore" or
                "conservative_forward_repeat")
            {
                var report = ReadReport(path);
                Assert.That(report.Cash, Is.EqualTo(959.875916m));
                Assert.That(report.Holding, Is.EqualTo(0.4m));
                Assert.That(report.Remaining, Is.EqualTo(0.6m));
                CheckLeanRestart(report);
                Console.WriteLine($"TL001A_LEAN_CONSERVATIVE phase={phase} " +
                    "decision=HOLD_REMAINING_OPEN cash=959.875916 holding=0.4 " +
                    "open_orders=1 new_submissions=0");
                return;
            }
            if (phase == "conservative_forward_mismatch")
            {
                var report = ReadReport(path);
                TideLabPaperIntentRecoveryProbe.WriteAtomic(ReportPath(path),
                    report with { Cash = report.Cash + 1m });
                Assert.That(() => ReadReport(path),
                    Throws.TypeOf<InvalidDataException>().With.Message.Contains(
                        "BLOCK_FILL_OR_ACCOUNT_MISMATCH"));
                Console.WriteLine("TL001A_LEAN_CONSERVATIVE phase=mismatch " +
                    "decision=BLOCK_FILL_OR_ACCOUNT_MISMATCH new_submissions=0");
                return;
            }
            throw new ArgumentException(phase);
        }
    }
}
