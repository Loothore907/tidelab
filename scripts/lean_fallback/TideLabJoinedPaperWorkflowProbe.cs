// TideLab-authored synthetic TL-001A paper authority/LEAN join. No external broker.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading;
using Moq;
using NUnit.Framework;
using QuantConnect;
using QuantConnect.Algorithm;
using QuantConnect.Brokerages;
using QuantConnect.Data;
using QuantConnect.Data.Market;
using QuantConnect.Interfaces;
using QuantConnect.Lean.Engine.DataFeeds;
using QuantConnect.Lean.Engine.RealTime;
using QuantConnect.Lean.Engine.Results;
using QuantConnect.Lean.Engine.Setup;
using QuantConnect.Lean.Engine.TransactionHandlers;
using QuantConnect.Orders;
using QuantConnect.Securities;
using QuantConnect.Tests.Engine.DataFeeds;

namespace QuantConnect.Tests.Engine.Setup
{
    public sealed record TideLabJoinedIntent(int Version, string ClientId,
        string BrokerId, decimal Quantity, decimal LimitPrice);

    // Matches the durable mock IBrokerage report from the existing LEAN submit path.
    public sealed record TideLabJoinedBrokerReport(int Revision, int LeanOrderId,
        string SymbolTicker, string BrokerId, string BrokerStatus,
        string ExecutionId, decimal Cash, decimal Holding, decimal Quantity,
        decimal ExecutedQuantity, decimal LimitPrice, decimal FillPrice,
        decimal Fee);

    public sealed record TideLabJoinedLedger(int Version, int ReportRevision,
        string ExecutionId, decimal Quantity, decimal Price, decimal Fee,
        decimal Cash, decimal Holding, string CorrectionOf);

    public sealed record TideLabJoinedNextReport(int Version, string ClientId,
        string BrokerId, int LeanOrderId, decimal Quantity, decimal LimitPrice,
        string Status);

    public static class TideLabJoinedPaperWorkflowProbe
    {
        private const string FirstClientId = "TL001A-JOINED-CLIENT-1";
        private const string FirstBrokerId = "TL001A-BROKER-ORDER-1";
        private const string FirstExecutionId = "TL001A-JOINED-EXEC-1";
        private const string NextClientId = "TL001A-JOINED-CLIENT-2";
        private const string NextBrokerId = "TL001A-JOINED-BROKER-2";
        private static readonly DateTime Now = new(2026, 1, 5, 18, 0, 0,
            DateTimeKind.Utc);
        private static readonly TideLabFillRules Rules = new(1, Currencies.USD,
            0.01m, 0.1m, 0.001m, 1, 1m, TimeSpan.FromMinutes(2));
        private static readonly TideLabQuote Quote = new(Now.AddMinutes(-1),
            89.80m, 89.90m, 0.4m, 0.4m);

        private static string InitialIntentPath(string path) =>
            path + ".joined-intent.json";
        private static string LedgerPath(string path) =>
            path + ".joined-ledger.json";
        private static string NextIntentPath(string path) =>
            path + ".joined-next-intent.json";
        private static string NextReportPath(string path) =>
            path + ".joined-next-report.json";

        private static T Read<T>(string path) where T : class
        {
            if (File.Exists(path + ".next"))
                throw new InvalidDataException("BLOCK_TORN_WRITE");
            return JsonSerializer.Deserialize<T>(File.ReadAllText(path)) ??
                throw new InvalidDataException("BLOCK_EMPTY_RECORD");
        }

        private static void Write<T>(string path, T value) =>
            TideLabPaperIntentRecoveryProbe.WriteAtomic(path, value);

        private static TideLabJoinedIntent FirstIntent(string path)
        {
            var intent = Read<TideLabJoinedIntent>(InitialIntentPath(path));
            if (intent != new TideLabJoinedIntent(1, FirstClientId,
                FirstBrokerId, 1m, 90m))
                throw new InvalidDataException("BLOCK_INITIAL_INTENT");
            return intent;
        }

        public static void ValidateInitialIntent(string path, Order order)
        {
            var intent = FirstIntent(path);
            if (order is not LimitOrder limit || order.Quantity != intent.Quantity ||
                limit.LimitPrice != intent.LimitPrice)
                throw new InvalidDataException("BLOCK_UNBOUND_INITIAL_SUBMISSION");
        }

        private static TideLabJoinedBrokerReport Report(string path)
        {
            FirstIntent(path);
            var report = Read<TideLabJoinedBrokerReport>(path);
            if (report.LeanOrderId <= 0 || report.SymbolTicker != "TL001ASYN" ||
                report.BrokerId != FirstBrokerId || report.Quantity != 1m ||
                report.LimitPrice != 90m || report.Revision is < 1 or > 4)
                throw new InvalidDataException("BLOCK_REPORT_IDENTITY");
            if (report.Revision == 1)
            {
                if (report.BrokerStatus != "Submitted" ||
                    report.ExecutedQuantity != 0 || report.Cash != 10000m ||
                    report.Holding != 0)
                    throw new InvalidDataException("BLOCK_PENDING_ACCOUNT");
                return report;
            }
            var price = report.Revision == 2 ? 89.91m : 89.92m;
            var fee = report.Revision == 2 ? 0.035964m : 0.035968m;
            if (report.BrokerStatus != (report.Revision == 4 ? "Canceled" :
                "PartiallyFilled") || report.ExecutionId != FirstExecutionId ||
                report.ExecutedQuantity != 0.4m || report.FillPrice != price ||
                report.Fee != fee || report.Holding != 0.4m ||
                report.Cash != 10000m - 0.4m * price - fee)
                throw new InvalidDataException("BLOCK_EXECUTION_ACCOUNT_MISMATCH");
            return report;
        }

        private static TideLabJoinedLedger ExpectedLedger(
            TideLabJoinedBrokerReport report) =>
            new(1, report.Revision == 4 ? 3 : report.Revision,
                FirstExecutionId, report.ExecutedQuantity, report.FillPrice,
                report.Fee, report.Cash, report.Holding,
                report.Revision >= 3 ? FirstExecutionId : null);

        private static string LedgerDecision(string path,
            TideLabJoinedBrokerReport report)
        {
            if (!File.Exists(LedgerPath(path))) return "BLOCK_LEDGER_ABSENT";
            try
            {
                return Read<TideLabJoinedLedger>(LedgerPath(path)) ==
                    ExpectedLedger(report) ? "MATCH" : "BLOCK_LEDGER_BEHIND";
            }
            catch (IOException) { return "BLOCK_LEDGER_UNKNOWN"; }
            catch (JsonException) { return "BLOCK_LEDGER_UNKNOWN"; }
        }

        private static string NextReady(string path, int expectedRevision)
        {
            var report = Report(path);
            if (report.Revision != expectedRevision)
                return "BLOCK_STALE_REVISION";
            if (LedgerDecision(path, report) != "MATCH")
                return "BLOCK_LEDGER_BEHIND";
            if (report.BrokerStatus != "Canceled" ||
                report.ExecutedQuantity != 0.4m)
                return "BLOCK_FIRST_ORDER_OPEN";
            if (File.Exists(NextReportPath(path)) ||
                File.Exists(NextReportPath(path) + ".next"))
                return "BLOCK_NEXT_ALREADY_SUBMITTED_OR_UNKNOWN";
            var next = Read<TideLabJoinedIntent>(NextIntentPath(path));
            if (next != new TideLabJoinedIntent(1, NextClientId,
                NextBrokerId, 1m, 80m))
                return "BLOCK_NEXT_INTENT";
            return "READY";
        }

        private sealed class ProbeAlgorithm : QCAlgorithm
        {
            public override void Initialize() { }
        }

        private static void CheckLeanSetup(string path,
            TideLabJoinedBrokerReport report, bool nextSubmitted = false,
            bool submitNext = false)
        {
            if (LedgerDecision(path, report) != "MATCH")
                throw new InvalidDataException("BLOCK_LEDGER_BEFORE_LEAN_SETUP");
            var symbol = Symbol.Create("TL001ASYN", SecurityType.Equity, Market.USA);
            var algorithm = new ProbeAlgorithm();
            var dataManager = new DataManagerStub(algorithm, new MockDataFeed(),
                liveMode: true);
            algorithm.SubscriptionManager.SetDataManager(dataManager);
            var transaction = new BrokerageTransactionHandler();
            var results = new Mock<IResultHandler>();
            var realTime = new Mock<IRealTimeHandler>();
            var brokerage = new Mock<IBrokerage>();
            using var placed = new ManualResetEventSlim();
            brokerage.Setup(x => x.IsConnected).Returns(true);
            brokerage.Setup(x => x.AccountBaseCurrency).Returns(Currencies.USD);
            brokerage.Setup(x => x.GetCashBalance()).Returns(new List<CashAmount>
                { new(report.Cash, Currencies.USD) });
            brokerage.Setup(x => x.GetAccountHoldings()).Returns(new List<Holding>
                { new() { Symbol = symbol, Quantity = report.Holding,
                    AveragePrice = report.FillPrice,
                    MarketPrice = report.FillPrice } });
            var open = new List<Order>();
            if (report.BrokerStatus == "PartiallyFilled")
                open.Add(new LimitOrder(symbol, 1m, 90m, Now)
                {
                    Id = report.LeanOrderId,
                    Status = OrderStatus.PartiallyFilled,
                    BrokerId = new List<string> { report.BrokerId }
                });
            if (nextSubmitted)
            {
                var next = Read<TideLabJoinedNextReport>(NextReportPath(path));
                Assert.That(next, Is.EqualTo(new TideLabJoinedNextReport(1,
                    NextClientId, NextBrokerId, next.LeanOrderId, 1m, 80m,
                    "Submitted")));
                open.Add(new LimitOrder(symbol, 1m, 80m, Now)
                {
                    Id = next.LeanOrderId,
                    Status = OrderStatus.Submitted,
                    BrokerId = new List<string> { NextBrokerId }
                });
            }
            brokerage.Setup(x => x.GetOpenOrders()).Returns(open);
            if (submitNext)
            {
                Assert.That(NextReady(path, report.Revision), Is.EqualTo("READY"));
                brokerage.Setup(x => x.PlaceOrder(It.IsAny<Order>()))
                    .Callback<Order>(order =>
                    {
                        if (NextReady(path, report.Revision) != "READY" ||
                            order is not LimitOrder limit ||
                            order.Quantity != 1m || limit.LimitPrice != 80m)
                            throw new InvalidDataException("BLOCK_NEXT_SUBMISSION");
                        order.BrokerId = new List<string> { NextBrokerId };
                        Write(NextReportPath(path), new TideLabJoinedNextReport(
                            1, NextClientId, NextBrokerId, order.Id, 1m, 80m,
                            "Submitted"));
                        placed.Set();
                    }).Returns(true);
            }

            try
            {
                transaction.Initialize(algorithm, brokerage.Object, results.Object);
                using var setup = new BrokerageSetupHandler();
                var job = BrokerageSetupHandlerTests.GetJob();
                IBrokerageFactory factory;
                setup.CreateBrokerage(job, algorithm, out factory);
                factory.Dispose();
                var ok = setup.Setup(new SetupHandlerParameters(
                    dataManager.UniverseSelection, algorithm, brokerage.Object,
                    job, results.Object, transaction, realTime.Object,
                    TestGlobals.DataCacheProvider,
                    TestGlobals.MapFileProvider));
                Assert.That(ok, Is.True, string.Join(" | ", setup.Errors));
                Assert.That(algorithm.Portfolio.CashBook[Currencies.USD].Amount,
                    Is.EqualTo(report.Cash));
                Assert.That(algorithm.Portfolio[symbol].Quantity,
                    Is.EqualTo(report.Holding));
                Assert.That(transaction.GetOpenOrders().Count,
                    Is.EqualTo(open.Count));
                Assert.That(transaction.GetOpenOrders().SelectMany(x => x.BrokerId),
                    Is.EquivalentTo(open.SelectMany(x => x.BrokerId)));
                if (submitNext)
                {
                    algorithm.Securities[symbol].SetMarketPrice(new Tick
                        { Symbol = symbol, Value = 100m });
                    algorithm.SetFinishedWarmingUp();
                    algorithm.Transactions.SetOrderProcessor(transaction);
                    var ticket = algorithm.LimitOrder(symbol, 1m, 80m);
                    Assert.That(ticket, Is.Not.Null);
                    Assert.That(placed.Wait(TimeSpan.FromSeconds(10)), Is.True,
                        "LEAN did not route the next order to the paper source");
                    brokerage.Verify(x => x.PlaceOrder(It.IsAny<Order>()),
                        Times.Once);
                }
                else brokerage.Verify(x => x.PlaceOrder(It.IsAny<Order>()),
                    Times.Never);
            }
            finally
            {
                transaction.Exit();
                dataManager.RemoveAllSubscriptions();
            }
        }

        public static void Run(string path, string phase)
        {
            if (string.IsNullOrWhiteSpace(path)) throw new ArgumentNullException(nameof(path));
            if (phase == "joined_intent_seed")
            {
                Assert.That(File.Exists(InitialIntentPath(path)), Is.False);
                Write(InitialIntentPath(path), new TideLabJoinedIntent(1,
                    FirstClientId, FirstBrokerId, 1m, 90m));
                FirstIntent(path);
                Console.WriteLine("TL001A_LEAN_JOINED phase=intent_seed " +
                    "client=stable status=durable new_submissions=0");
                return;
            }
            var report = Report(path);
            if (phase == "joined_partial_crash")
            {
                Assert.That(report.Revision, Is.EqualTo(1));
                var missed = TideLabConservativeFillPolicy.Decide(Rules,
                    Quote with { AskSize = 0m }, Now, 1m, 0);
                var rejected = TideLabConservativeFillPolicy.Decide(Rules,
                    Quote, Now, 1.05m, 0);
                Assert.That(missed.State, Is.EqualTo("HOLD_NO_DISPLAYED_LOT"));
                Assert.That(rejected.State, Is.EqualTo("REJECT_RULE_OR_ORDER"));
                Assert.That(Report(path), Is.EqualTo(report));
                var fill = TideLabConservativeFillPolicy.Decide(Rules,
                    Quote, Now, report.Quantity, 0);
                Assert.That(fill, Is.EqualTo(new TideLabFillDecision(
                    "PARTIAL", 0.4m, 89.91m, 0.035964m, 0.6m)));
                Write(path, report with
                {
                    Revision = 2,
                    BrokerStatus = "PartiallyFilled",
                    ExecutionId = FirstExecutionId,
                    ExecutedQuantity = fill.Quantity,
                    FillPrice = fill.Price,
                    Fee = fill.Fee,
                    Cash = 10000m - fill.Quantity * fill.Price - fill.Fee,
                    Holding = fill.Quantity
                });
                Assert.That(Report(path).Cash, Is.EqualTo(9964.000036m));
                Assert.That(File.Exists(LedgerPath(path)), Is.False);
                Console.WriteLine("TL001A_LEAN_JOINED phase=partial_crash " +
                    "fill=0.4@89.91 fee=0.035964 remaining=0.6 " +
                    "missed=HOLD rejected=REJECT ledger=absent new_submissions=0");
                Environment.Exit(74);
            }
            if (phase == "joined_reconcile_partial")
            {
                Assert.That(report.Revision, Is.EqualTo(2));
                Assert.That(LedgerDecision(path, report),
                    Is.EqualTo("BLOCK_LEDGER_ABSENT"));
                Write(LedgerPath(path), ExpectedLedger(report));
                Assert.That(LedgerDecision(path, report), Is.EqualTo("MATCH"));
                CheckLeanSetup(path, report);
                Console.WriteLine("TL001A_LEAN_JOINED phase=reconcile_partial " +
                    "ledger=one_execution cash=9964.000036 holding=0.4 " +
                    "open_orders=1 next=BLOCK_FIRST_ORDER_OPEN new_submissions=0");
                return;
            }
            if (phase == "joined_reconcile_repeat")
            {
                Assert.That(report.Revision, Is.EqualTo(2));
                Assert.That(LedgerDecision(path, report), Is.EqualTo("MATCH"));
                CheckLeanSetup(path, report);
                Console.WriteLine("TL001A_LEAN_JOINED phase=reconcile_repeat " +
                    "execution=verified_once open_orders=1 new_submissions=0");
                return;
            }
            if (phase == "joined_correct_hold")
            {
                Assert.That(report.Revision, Is.EqualTo(2));
                Write(path, report with
                {
                    Revision = 3,
                    FillPrice = 89.92m,
                    Fee = 0.035968m,
                    Cash = 9963.996032m
                });
                report = Report(path);
                Assert.That(LedgerDecision(path, report),
                    Is.EqualTo("BLOCK_LEDGER_BEHIND"));
                Assert.That(NextReady(path, 2), Is.EqualTo("BLOCK_STALE_REVISION"));
                Assert.That(NextReady(path, 3), Is.EqualTo("BLOCK_LEDGER_BEHIND"));
                Console.WriteLine("TL001A_LEAN_JOINED phase=correct_hold " +
                    "report=3 ledger=2 next=BLOCK_STALE_REVISION " +
                    "or_BLOCK_LEDGER_BEHIND " +
                    "new_submissions=0");
                return;
            }
            if (phase == "joined_reconcile_correction")
            {
                Assert.That(report.Revision, Is.EqualTo(3));
                var old = Read<TideLabJoinedLedger>(LedgerPath(path));
                Assert.That(old.ReportRevision, Is.EqualTo(2));
                Assert.That(old.ExecutionId, Is.EqualTo(FirstExecutionId));
                Write(LedgerPath(path), ExpectedLedger(report));
                Assert.That(LedgerDecision(path, report), Is.EqualTo("MATCH"));
                CheckLeanSetup(path, report);
                Console.WriteLine("TL001A_LEAN_JOINED phase=reconcile_correction " +
                    "execution=corrected cash=9963.996032 holding=0.4 " +
                    "open_orders=1 new_submissions=0");
                return;
            }
            if (phase == "joined_cancel_remaining")
            {
                Assert.That(report.Revision, Is.EqualTo(3));
                Assert.That(LedgerDecision(path, report), Is.EqualTo("MATCH"));
                Write(path, report with
                    { Revision = 4, BrokerStatus = "Canceled" });
                report = Report(path);
                Assert.That(LedgerDecision(path, report), Is.EqualTo("MATCH"));
                CheckLeanSetup(path, report);
                Console.WriteLine("TL001A_LEAN_JOINED phase=cancel_remaining " +
                    "report=4 first_order=closed cash=9963.996032 " +
                    "holding=0.4 open_orders=0 new_submissions=0");
                return;
            }
            if (phase == "joined_next_submit")
            {
                Assert.That(report.Revision, Is.EqualTo(4));
                Write(NextIntentPath(path), new TideLabJoinedIntent(1,
                    NextClientId, NextBrokerId, 1m, 80m));
                Assert.That(NextReady(path, 4), Is.EqualTo("READY"));
                CheckLeanSetup(path, report, submitNext: true);
                var next = Read<TideLabJoinedNextReport>(NextReportPath(path));
                Assert.That(next.ClientId, Is.EqualTo(NextClientId));
                Assert.That(next.BrokerId, Is.EqualTo(NextBrokerId));
                Assert.That(next.LeanOrderId, Is.GreaterThan(0));
                Console.WriteLine("TL001A_LEAN_JOINED phase=next_submit " +
                    "decision=SUBMITTED_AFTER_RECONCILIATION " +
                    "new_submissions=1");
                return;
            }
            if (phase == "joined_next_repeat")
            {
                Assert.That(report.Revision, Is.EqualTo(4));
                Assert.That(NextReady(path, 4),
                    Is.EqualTo("BLOCK_NEXT_ALREADY_SUBMITTED_OR_UNKNOWN"));
                CheckLeanSetup(path, report, nextSubmitted: true);
                Console.WriteLine("TL001A_LEAN_JOINED phase=next_repeat " +
                    "decision=ADOPT_EXISTING_NEXT_ORDER open_orders=1 " +
                    "new_submissions=0");
                return;
            }
            if (phase == "joined_bad_account")
            {
                Assert.That(report.Revision, Is.EqualTo(4));
                Write(path, report with { Cash = report.Cash + 1m });
                Assert.That(() => Report(path),
                    Throws.TypeOf<InvalidDataException>().With.Message.Contains(
                        "BLOCK_EXECUTION_ACCOUNT_MISMATCH"));
                Console.WriteLine("TL001A_LEAN_JOINED phase=bad_account " +
                    "decision=BLOCK_EXECUTION_ACCOUNT_MISMATCH " +
                    "new_submissions=0");
                return;
            }
            throw new ArgumentException(phase);
        }
    }
}
