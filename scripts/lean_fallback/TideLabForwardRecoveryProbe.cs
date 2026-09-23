// TideLab-authored synthetic LEAN setup/restart probe. Copy into Lean/Tests/Engine/Setup/.
// This is deliberately a test of brokerage-report startup, not a live trading adapter.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading;
using Moq;
using NUnit.Framework;
using QuantConnect.Algorithm;
using QuantConnect.Algorithm.CSharp;
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
using QuantConnect.Orders.Fees;
using QuantConnect.Securities;
using QuantConnect.Tests.Engine.DataFeeds;

namespace QuantConnect.Tests.Engine.Setup
{
    [TestFixture]
    public class TideLabForwardRecoveryProbe
    {
        private sealed class ProbeAlgorithm : QCAlgorithm
        {
            public readonly List<OrderEvent> SeenEvents = new List<OrderEvent>();
            public Symbol SignalSymbol;
            public bool EnableSignal;
            public int DataCount;
            public int SignalCount;
            public readonly List<DateTime> DataTimesUtc = new List<DateTime>();
            private readonly TideLabSyntheticSignal _signal = new TideLabSyntheticSignal();
            public override void Initialize() { }
            public override void OnData(Slice slice)
            {
                if (!EnableSignal || !slice.Bars.TryGetValue(SignalSymbol, out var bar)) return;
                DataCount++;
                DataTimesUtc.Add(UtcTime);
                if (_signal.OnClose(bar.Close))
                {
                    SignalCount++;
                    LimitOrder(SignalSymbol, 1m, 90m);
                }
            }
            public override void OnOrderEvent(OrderEvent orderEvent)
            {
                SeenEvents.Add(orderEvent);
            }
        }

        private sealed class BrokerReport
        {
            public int Revision { get; set; }
            public int LeanOrderId { get; set; }
            public string SymbolTicker { get; set; }
            public string BrokerId { get; set; }
            public string BrokerStatus { get; set; }
            public string ExecutionId { get; set; }
            public decimal Cash { get; set; }
            public decimal Holding { get; set; }
            public decimal Quantity { get; set; }
            public decimal ExecutedQuantity { get; set; }
            public decimal LimitPrice { get; set; }
            public decimal FillPrice { get; set; }
            public decimal Fee { get; set; }
        }

        private sealed class ReconciliationRecord
        {
            public string BrokerId { get; set; }
            public string SymbolTicker { get; set; }
            public string ExecutionId { get; set; }
            public decimal Quantity { get; set; }
            public decimal FillPrice { get; set; }
            public decimal Fee { get; set; }
            public decimal CashAfter { get; set; }
            public decimal HoldingAfter { get; set; }
        }

        private static string RecordOrVerifyExecution(string reportPath, BrokerReport report)
        {
            var path = reportPath + ".reconciled.json";
            var record = new ReconciliationRecord
            {
                BrokerId = report.BrokerId,
                SymbolTicker = report.SymbolTicker,
                ExecutionId = report.ExecutionId,
                Quantity = report.Quantity,
                FillPrice = report.FillPrice,
                Fee = report.Fee,
                CashAfter = report.Cash,
                HoldingAfter = report.Holding
            };
            if (File.Exists(path))
            {
                var existing = JsonSerializer.Deserialize<ReconciliationRecord>(File.ReadAllText(path));
                Assert.That(existing.BrokerId, Is.EqualTo(record.BrokerId));
                Assert.That(existing.SymbolTicker, Is.EqualTo(record.SymbolTicker));
                Assert.That(existing.ExecutionId, Is.EqualTo(record.ExecutionId));
                Assert.That(existing.Quantity, Is.EqualTo(record.Quantity));
                Assert.That(existing.FillPrice, Is.EqualTo(record.FillPrice));
                Assert.That(existing.Fee, Is.EqualTo(record.Fee));
                Assert.That(existing.CashAfter, Is.EqualTo(record.CashAfter));
                Assert.That(existing.HoldingAfter, Is.EqualTo(record.HoldingAfter));
                return "verified_existing";
            }
            using (var file = new FileStream(path, FileMode.CreateNew, FileAccess.Write,
                FileShare.None, 4096, FileOptions.WriteThrough))
            {
                JsonSerializer.Serialize(file, record);
                file.Flush(true);
            }
            return "created";
        }

        private static bool IsReconciledFill(BrokerReport report)
        {
            return report != null && report.Revision == 2 &&
                report.BrokerId == "TL001A-BROKER-ORDER-1" &&
                report.BrokerStatus == "Filled" &&
                report.ExecutionId == "TL001A-EXECUTION-1" &&
                report.Quantity == 1m && report.ExecutedQuantity == report.Quantity &&
                report.FillPrice == 90m &&
                report.Fee == 0.09m && report.Holding == report.Quantity &&
                report.Cash == 10000m - report.Quantity * report.FillPrice - report.Fee;
        }

        private static bool IsReconciledPartial(BrokerReport report)
        {
            return report != null && report.Revision == 2 &&
                report.BrokerId == "TL001A-BROKER-ORDER-1" &&
                report.BrokerStatus == "PartiallyFilled" &&
                report.ExecutionId == "TL001A-EXECUTION-1" &&
                report.Quantity == 1m && report.ExecutedQuantity == 0.5m &&
                report.LimitPrice == 90m && report.FillPrice == 90m &&
                report.Fee == 0.09m && report.Holding == report.ExecutedQuantity &&
                report.Cash == 10000m - report.ExecutedQuantity * report.FillPrice - report.Fee;
        }

        private static void ReplaceReport(string path, BrokerReport report)
        {
            var next = path + ".next";
            using (var file = new FileStream(next, FileMode.CreateNew, FileAccess.Write,
                FileShare.None, 4096, FileOptions.WriteThrough))
            {
                JsonSerializer.Serialize(file, report);
                file.Flush(true);
            }
            File.Move(next, path, true);
        }

        private static void RunSyntheticOrderSubmission(string path, bool fillNow,
            bool forwardClock)
        {
            var symbol = Symbol.Create("TL001ASYN", SecurityType.Equity, Market.USA);
            var algorithm = new ProbeAlgorithm();
            algorithm.SignalSymbol = symbol;
            algorithm.EnableSignal = forwardClock;
            var dataManager = new DataManagerStub(algorithm, new MockDataFeed(), liveMode: true);
            algorithm.SubscriptionManager.SetDataManager(dataManager);
            var transaction = new BrokerageTransactionHandler();
            var results = new Mock<IResultHandler>();
            var realTime = new Mock<IRealTimeHandler>();
            var brokerage = new Mock<IBrokerage>();
            using var submitted = new ManualResetEventSlim();

            brokerage.Setup(x => x.IsConnected).Returns(true);
            brokerage.Setup(x => x.AccountBaseCurrency).Returns(Currencies.USD);
            brokerage.Setup(x => x.GetCashBalance()).Returns(new List<CashAmount>
            {
                new CashAmount(10000m, Currencies.USD)
            });
            brokerage.Setup(x => x.GetAccountHoldings()).Returns(new List<Holding>
            {
                new Holding { Symbol = symbol, Quantity = 0m, AveragePrice = 0m }
            });
            brokerage.Setup(x => x.GetOpenOrders()).Returns(new List<Order>());
            brokerage.Setup(x => x.PlaceOrder(It.IsAny<Order>()))
                .Callback<Order>(order =>
                {
                    order.BrokerId = new List<string> { "TL001A-BROKER-ORDER-1" };
                    var report = new BrokerReport
                    {
                        Revision = 1,
                        LeanOrderId = order.Id,
                        SymbolTicker = "TL001ASYN",
                        BrokerId = order.BrokerId[0],
                        BrokerStatus = "Submitted",
                        Cash = 10000m,
                        Holding = 0m,
                        Quantity = order.Quantity,
                        LimitPrice = 90m
                    };
                    using (var file = new FileStream(path, FileMode.CreateNew,
                        FileAccess.Write, FileShare.None, 4096, FileOptions.WriteThrough))
                    {
                        JsonSerializer.Serialize(file, report);
                        file.Flush(true);
                    }
                    submitted.Set();
                }).Returns(true);

            transaction.Initialize(algorithm, brokerage.Object, results.Object);
            using var setup = new BrokerageSetupHandler();
            var job = BrokerageSetupHandlerTests.GetJob();
            IBrokerageFactory factory;
            setup.CreateBrokerage(job, algorithm, out factory);
            factory.Dispose();
            var ok = setup.Setup(new SetupHandlerParameters(dataManager.UniverseSelection,
                algorithm, brokerage.Object, job, results.Object, transaction,
                realTime.Object, TestGlobals.DataCacheProvider, TestGlobals.MapFileProvider));
            Assert.That(ok, Is.True, string.Join(" | ", setup.Errors));
            algorithm.Securities[symbol].SetMarketPrice(new Tick { Symbol = symbol, Value = 100m });
            algorithm.SetFinishedWarmingUp();
            algorithm.Transactions.SetOrderProcessor(transaction);

            OrderTicket ticket = null;
            if (forwardClock)
            {
                var start = new DateTime(2026, 1, 5, 15, 0, 0, DateTimeKind.Utc);
                foreach (var (index, close) in new[] { 100m, 102m, 104m }.Select((value, i) => (i, value)))
                {
                    var time = start.AddHours(index);
                    var bar = new TradeBar(time, symbol, close, close, close, close,
                        1m, TimeSpan.FromHours(1));
                    var slice = new Slice(bar.EndTime, new BaseData[] { bar }, bar.EndTime);
                    algorithm.SetDateTime(bar.EndTime);
                    algorithm.SetCurrentSlice(slice);
                    algorithm.Securities[symbol].SetMarketPrice(bar);
                    algorithm.OnData(slice);
                }
                Assert.That(algorithm.DataCount, Is.EqualTo(3));
                Assert.That(algorithm.SignalCount, Is.EqualTo(1));
                Assert.That(algorithm.DataTimesUtc, Is.EqualTo(new[]
                {
                    start.AddHours(1), start.AddHours(2), start.AddHours(3)
                }));
                ticket = transaction.GetOpenOrderTickets().Single();
            }
            else
            {
                ticket = algorithm.LimitOrder(symbol, 1m, 90m);
            }
            Assert.That(submitted.Wait(TimeSpan.FromSeconds(10)), Is.True,
                "Synthetic broker did not receive the LEAN order");
            Assert.That(ticket, Is.Not.Null);
            var acknowledged = transaction.GetOpenOrders().Single();
            brokerage.Raise(x => x.OrdersStatusChanged += null, brokerage.Object,
                new List<OrderEvent>
                {
                    new OrderEvent(acknowledged, DateTime.UtcNow, OrderFee.Zero)
                    {
                        Status = OrderStatus.Submitted
                    }
                });
            Assert.That(SpinWait.SpinUntil(() => transaction.GetOpenOrders().Any(order =>
                order.Status == OrderStatus.Submitted &&
                order.BrokerId.Contains("TL001A-BROKER-ORDER-1")),
                TimeSpan.FromSeconds(10)), Is.True,
                "LEAN did not retain the broker-acknowledged pending order");
            brokerage.Verify(x => x.PlaceOrder(It.IsAny<Order>()), Times.Once);
            if (fillNow)
            {
                var report = JsonSerializer.Deserialize<BrokerReport>(File.ReadAllText(path));
                report.Revision = 2;
                report.BrokerStatus = "Filled";
                report.ExecutionId = "TL001A-EXECUTION-1";
                report.ExecutedQuantity = 1m;
                report.FillPrice = 90m;
                report.Fee = 0.09m;
                report.Cash = 9909.91m;
                report.Holding = 1m;
                ReplaceReport(path, report);
                brokerage.Raise(x => x.OrdersStatusChanged += null, brokerage.Object,
                    new List<OrderEvent>
                    {
                        new OrderEvent(acknowledged, DateTime.UtcNow,
                            new OrderFee(new CashAmount(0.09m, Currencies.USD)))
                        {
                            Status = OrderStatus.Filled,
                            FillQuantity = 1m,
                            FillPrice = 90m
                        }
                    });
                Assert.That(SpinWait.SpinUntil(() => algorithm.SeenEvents.Any(e =>
                    e.Status == OrderStatus.Filled), TimeSpan.FromSeconds(10)), Is.True);
                Assert.That(transaction.GetOpenOrders().Count, Is.Zero);
                Assert.That(algorithm.Portfolio.CashBook[Currencies.USD].Amount,
                    Is.EqualTo(9909.91m));
                Assert.That(algorithm.Portfolio[symbol].Quantity, Is.EqualTo(1m));
                Console.WriteLine("TL001A_LEAN_FORWARD phase=submit_fill order_event=Filled cash=9909.91 holding=1 new_submissions=1");
                transaction.Exit();
                dataManager.RemoveAllSubscriptions();
                return;
            }
            Console.WriteLine($"TL001A_LEAN_FORWARD phase={(forwardClock ? "submit_clock_seed" : "submit_seed")} data_count={algorithm.DataCount} signal_count={algorithm.SignalCount} broker_id=TL001A-BROKER-ORDER-1 quantity=1 new_submissions=1");
            Environment.Exit(23);
        }

        [Test]
        public void PendingOrderComesFromAuthoritativeSyntheticBrokerReport()
        {
            var path = Environment.GetEnvironmentVariable("TL001A_REPORT_PATH");
            var phase = Environment.GetEnvironmentVariable("TL001A_PHASE");
            Assert.That(path, Is.Not.Null.And.Not.Empty);

            if (phase == "submit_seed" || phase == "submit_fill" ||
                phase == "submit_clock_seed")
            {
                RunSyntheticOrderSubmission(path, phase == "submit_fill",
                    phase == "submit_clock_seed");
                return;
            }

            if (phase == "seed")
            {
                // A separate synthetic brokerage owns this durable report. The LEAN process
                // exits without graceful teardown after the report becomes authoritative.
                var report = new BrokerReport
                {
                    Revision = 1,
                    BrokerId = "TL001A-BROKER-ORDER-1",
                    SymbolTicker = "TL001ASYN",
                    BrokerStatus = "Submitted",
                    Cash = 10000m,
                    Holding = 0m,
                    Quantity = 1m,
                    LimitPrice = 90m
                };
                using (var file = new FileStream(path, FileMode.CreateNew, FileAccess.Write,
                    FileShare.None, 4096, FileOptions.WriteThrough))
                {
                    JsonSerializer.Serialize(file, report);
                    file.Flush(true);
                }
            }

            if (phase == "settle" || phase == "settle_conflict" ||
                phase == "settle_quantity_conflict" ||
                phase == "settle_partial" || phase == "settle_partial_conflict")
            {
                var report = JsonSerializer.Deserialize<BrokerReport>(File.ReadAllText(path));
                Assert.That(report.Revision, Is.EqualTo(1));
                Assert.That(report.BrokerStatus, Is.EqualTo("Submitted"));
                report.Revision = 2;
                var partial = phase.StartsWith("settle_partial", StringComparison.Ordinal);
                report.BrokerStatus = partial ? "PartiallyFilled" : "Filled";
                report.ExecutionId = "TL001A-EXECUTION-1";
                report.ExecutedQuantity = partial ? 0.5m : 1m;
                if (phase == "settle_quantity_conflict") report.ExecutedQuantity = 0.5m;
                report.FillPrice = 90m;
                report.Fee = 0.09m;
                report.Holding = phase == "settle_quantity_conflict" ? 1m :
                    report.ExecutedQuantity;
                report.Cash = phase == "settle" ? 9909.91m :
                    phase == "settle_partial" ? 9954.91m :
                    phase == "settle_quantity_conflict" ? 9909.91m : 10000m;
                ReplaceReport(path, report);
                Console.WriteLine($"TL001A_LEAN_FORWARD phase={phase} broker_status={report.BrokerStatus} cash={report.Cash} holding={report.Holding}");
                return;
            }

            if (phase == "tear_record")
            {
                Assert.That(IsReconciledFill(JsonSerializer.Deserialize<BrokerReport>(
                    File.ReadAllText(path))), Is.True);
                using (var file = new FileStream(path + ".reconciled.json",
                    FileMode.CreateNew, FileAccess.Write, FileShare.None, 4096,
                    FileOptions.WriteThrough))
                {
                    var bytes = System.Text.Encoding.UTF8.GetBytes("{\"ExecutionId\":");
                    file.Write(bytes, 0, bytes.Length);
                    file.Flush(true);
                }
                Console.WriteLine("TL001A_LEAN_FORWARD phase=tear_record record=truncated");
                return;
            }

            if (phase == "restore_missing")
            {
                Assert.That(File.Exists(path), Is.False);
                Console.WriteLine("TL001A_LEAN_FORWARD phase=restore_missing decision=BLOCK reason=no_broker_report new_submissions=0");
                Environment.Exit(42);
                return;
            }

            Assert.That(phase, Is.AnyOf("seed", "restore", "restore_filled",
                "restore_late_event", "restore_conflict", "restore_quantity_conflict",
                "restore_partial", "restore_ledger_partial", "restore_ledger_full",
                "restore_ledger_partial_late_events", "restore_ledger_full_late_events",
                "restore_ledger_partial_screened", "restore_ledger_partial_screened_crash",
                "restore_ledger_full_lag",
                "restore_partial_conflict", "restore_torn_record"));
            var snapshot = JsonSerializer.Deserialize<BrokerReport>(File.ReadAllText(path));
            Assert.That(snapshot, Is.Not.Null);
            Assert.That(snapshot.SymbolTicker, Is.AnyOf("TL001ASYN", "SPY"));
            var symbol = Symbol.Create(snapshot.SymbolTicker, SecurityType.Equity, Market.USA);
            Assert.That(snapshot.BrokerId, Is.EqualTo("TL001A-BROKER-ORDER-1"));
            Assert.That(snapshot.Quantity, Is.EqualTo(1m));
            Assert.That(snapshot.LimitPrice, Is.EqualTo(90m));
            var pending = phase == "seed" || phase == "restore";
            var ledgerPartial = phase == "restore_ledger_partial" ||
                phase == "restore_ledger_partial_late_events" ||
                phase == "restore_ledger_partial_screened" ||
                phase == "restore_ledger_partial_screened_crash";
            var ledgerFull = phase == "restore_ledger_full" ||
                phase == "restore_ledger_full_late_events";
            if (phase == "restore_ledger_full_lag")
            {
                Assert.That(snapshot.BrokerStatus, Is.EqualTo("Filled"));
                Assert.That(TideLabExecutionLedgerProbe.IsReadyForFreshSetup(path, 2), Is.False);
                Console.WriteLine("TL001A_LEAN_FORWARD phase=restore_ledger_full_lag decision=BLOCK reason=ledger_behind_broker new_submissions=0");
                Environment.Exit(42);
                return;
            }
            if (ledgerPartial || ledgerFull)
            {
                Assert.That(TideLabExecutionLedgerProbe.IsReadyForFreshSetup(path,
                    ledgerPartial ? 1 : 2), Is.True,
                    "Do not start LEAN until every broker execution is committed");
            }
            else if (pending)
            {
                Assert.That(snapshot.Revision, Is.EqualTo(1));
                Assert.That(snapshot.BrokerStatus, Is.EqualTo("Submitted"));
                Assert.That(snapshot.Cash, Is.EqualTo(10000m));
                Assert.That(snapshot.Holding, Is.Zero);
            }
            else if (phase == "restore_conflict" ||
                phase == "restore_quantity_conflict" ||
                phase == "restore_partial_conflict")
            {
                Assert.That(phase != "restore_partial_conflict" ? IsReconciledFill(snapshot) :
                    IsReconciledPartial(snapshot), Is.False);
                Console.WriteLine($"TL001A_LEAN_FORWARD phase={phase} decision=BLOCK reason=account_execution_mismatch new_submissions=0");
                Environment.Exit(42);
                return;
            }
            else if (phase == "restore_partial")
            {
                Assert.That(IsReconciledPartial(snapshot), Is.True,
                    "A partial execution requires an exact execution and account reconciliation");
            }
            else
            {
                Assert.That(IsReconciledFill(snapshot), Is.True,
                    "A changed outcome requires an exact execution and account reconciliation");
            }

            var algorithm = new ProbeAlgorithm();
            var dataManager = new DataManagerStub(algorithm, new MockDataFeed(), liveMode: true);
            algorithm.SubscriptionManager.SetDataManager(dataManager);
            var transaction = new BrokerageTransactionHandler();
            var results = new Mock<IResultHandler>();
            var realTime = new Mock<IRealTimeHandler>();
            var brokerage = new Mock<IBrokerage>();
            var partialOrder = phase == "restore_partial" || ledgerPartial;
            var hasOpenOrder = pending || partialOrder;
            var pendingOrder = new LimitOrder(symbol, snapshot.Quantity, snapshot.LimitPrice,
                new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc))
            {
                Status = partialOrder ? OrderStatus.PartiallyFilled : OrderStatus.Submitted,
                BrokerId = new List<string> { snapshot.BrokerId }
            };
            brokerage.Setup(x => x.IsConnected).Returns(true);
            brokerage.Setup(x => x.AccountBaseCurrency).Returns(Currencies.USD);
            brokerage.Setup(x => x.GetCashBalance()).Returns(new List<CashAmount>
            {
                new CashAmount(snapshot.Cash, Currencies.USD)
            });
            brokerage.Setup(x => x.GetAccountHoldings()).Returns(new List<Holding>
            {
                new Holding { Symbol = symbol, Quantity = snapshot.Holding,
                    AveragePrice = pending ? 0m : snapshot.FillPrice,
                    MarketPrice = pending ? 0m : snapshot.FillPrice }
            });
            brokerage.Setup(x => x.GetOpenOrders()).Returns(
                hasOpenOrder ? new List<Order> { pendingOrder } : new List<Order>());

            try
            {
                transaction.Initialize(algorithm, brokerage.Object, results.Object);
                using var setup = new BrokerageSetupHandler();
                var job = BrokerageSetupHandlerTests.GetJob();
                IBrokerageFactory factory;
                setup.CreateBrokerage(job, algorithm, out factory);
                factory.Dispose();
                var ok = setup.Setup(new SetupHandlerParameters(dataManager.UniverseSelection,
                    algorithm, brokerage.Object, job, results.Object, transaction,
                    realTime.Object, TestGlobals.DataCacheProvider, TestGlobals.MapFileProvider));
                Assert.That(ok, Is.True, string.Join(" | ", setup.Errors));

                var restored = transaction.GetOpenOrders();
                Assert.That(restored.Count, Is.EqualTo(hasOpenOrder ? 1 : 0));
                if (hasOpenOrder)
                {
                    Assert.That(restored[0].Status, Is.EqualTo(partialOrder ?
                        OrderStatus.PartiallyFilled : OrderStatus.Submitted));
                    Assert.That(restored[0].BrokerId, Does.Contain(snapshot.BrokerId));
                }
                else
                {
                    // Setup asks for open orders only. The closed execution is recovered
                    // from the broker report, not from LEAN's fresh transaction handler.
                    Assert.That(transaction.Orders.Count, Is.Zero);
                }
                Assert.That(algorithm.Portfolio.CashBook[Currencies.USD].Amount,
                    Is.EqualTo(snapshot.Cash));
                Assert.That(algorithm.Portfolio[symbol].Quantity, Is.EqualTo(snapshot.Holding));
                brokerage.Verify(x => x.GetOpenOrders(), Times.Once);
                brokerage.Verify(x => x.GetCashBalance(), Times.Once);
                brokerage.Verify(x => x.GetAccountHoldings(), Times.Once);
                brokerage.Verify(x => x.PlaceOrder(It.IsAny<Order>()), Times.Never);
                if (phase == "restore_ledger_partial_screened" ||
                    phase == "restore_ledger_partial_screened_crash")
                {
                    const string first = "TL001A-EXECUTION-1";
                    const string second = "TL001A-EXECUTION-2";
                    Assert.That(TideLabExecutionLedgerProbe.ScreenBrokerExecution(path,
                        first, 0.5m, 90m, 0.045m), Is.EqualTo("SUPPRESS_COMMITTED"));
                    Assert.That(TideLabExecutionLedgerProbe.ScreenBrokerExecution(path,
                        second, 0.5m, 90m, 0.045m), Is.EqualTo("BLOCK_UNREPORTED"));
                    Assert.That(TideLabExecutionLedgerProbe.ScreenBrokerExecution(path,
                        first, 0.5m, 90m, 0.09m), Is.EqualTo("BLOCK_MISMATCH"));
                    Assert.That(algorithm.SeenEvents, Is.Empty);
                    TideLabExecutionLedgerProbe.AdvanceReportToFull(path);
                    Assert.That(TideLabExecutionLedgerProbe.ScreenBrokerExecution(path,
                        second, 0.5m, 90m, 0.045m), Is.EqualTo("DELIVER_AFTER_COMMIT"));
                    if (phase == "restore_ledger_partial_screened_crash")
                    {
                        Console.WriteLine("TL001A_LEAN_FORWARD phase=restore_ledger_partial_screened_crash first=suppressed unreported=blocked second=committed delivery=not_started new_submissions=0");
                        Environment.Exit(23);
                    }
                    var lateOrder = new LimitOrder(symbol, snapshot.Quantity,
                        snapshot.LimitPrice, DateTime.UtcNow)
                    {
                        Id = snapshot.LeanOrderId,
                        BrokerId = new List<string> { snapshot.BrokerId }
                    };
                    brokerage.Raise(x => x.OrdersStatusChanged += null,
                        brokerage.Object, new List<OrderEvent>
                        {
                            new OrderEvent(lateOrder, DateTime.UtcNow,
                                new OrderFee(new CashAmount(0.045m, Currencies.USD)))
                            {
                                Status = OrderStatus.Filled,
                                FillQuantity = 0.5m,
                                FillPrice = 90m
                            }
                        });
                    Assert.That(algorithm.SeenEvents.Count, Is.EqualTo(1));
                    Assert.That(algorithm.Portfolio.CashBook[Currencies.USD].Amount,
                        Is.EqualTo(9909.91m));
                    Assert.That(algorithm.Portfolio[symbol].Quantity, Is.EqualTo(1m));
                    Assert.That(transaction.GetOpenOrders(), Is.Empty);
                    Assert.That(TideLabExecutionLedgerProbe.ScreenBrokerExecution(path,
                        second, 0.5m, 90m, 0.045m), Is.EqualTo("SUPPRESS_COMMITTED"));
                    brokerage.Verify(x => x.PlaceOrder(It.IsAny<Order>()), Times.Never);
                    Console.WriteLine("TL001A_LEAN_FORWARD phase=restore_ledger_partial_screened first=suppressed unreported=blocked second=delivered_after_commit callbacks=1 cash=9909.91 holding=1 open_orders=0 new_submissions=0");
                    return;
                }
                if (phase == "restore_ledger_partial_late_events" ||
                    phase == "restore_ledger_full_late_events")
                {
                    var ledgerBefore = File.ReadAllBytes(path + ".ledger.json");
                    var lateOrder = new LimitOrder(symbol, snapshot.Quantity,
                        snapshot.LimitPrice, DateTime.UtcNow)
                    {
                        Id = snapshot.LeanOrderId,
                        BrokerId = new List<string> { snapshot.BrokerId }
                    };
                    var statuses = ledgerPartial ?
                        new[] { OrderStatus.PartiallyFilled, OrderStatus.PartiallyFilled } :
                        new[] { OrderStatus.PartiallyFilled, OrderStatus.Filled };
                    foreach (var status in statuses)
                    {
                        brokerage.Raise(x => x.OrdersStatusChanged += null,
                            brokerage.Object, new List<OrderEvent>
                            {
                                new OrderEvent(lateOrder, DateTime.UtcNow,
                                    new OrderFee(new CashAmount(0.045m, Currencies.USD)))
                                {
                                    Status = status,
                                    FillQuantity = 0.5m,
                                    FillPrice = 90m
                                }
                            });
                    }
                    if (ledgerPartial)
                    {
                        Assert.That(algorithm.SeenEvents.Count, Is.EqualTo(2));
                        Assert.That(File.ReadAllBytes(path + ".ledger.json")
                            .SequenceEqual(ledgerBefore), Is.True);
                        var cashAfter = algorithm.Portfolio.CashBook[Currencies.USD].Amount;
                        var holdingAfter = algorithm.Portfolio[symbol].Quantity;
                        var openAfter = transaction.GetOpenOrders().Count;
                        Assert.That(cashAfter, Is.EqualTo(9864.865m));
                        Assert.That(holdingAfter, Is.EqualTo(1.5m));
                        Assert.That(openAfter, Is.EqualTo(1));
                        brokerage.Verify(x => x.PlaceOrder(It.IsAny<Order>()), Times.Never);
                        Console.WriteLine($"TL001A_LEAN_FORWARD phase={phase} delivery=applied_duplicate events=2 cash={cashAfter} holding={holdingAfter} open_orders={openAfter} ledger=unchanged decision=BLOCK reason=duplicate_partial_event new_submissions=0");
                        Environment.Exit(42);
                    }
                    Assert.That(algorithm.SeenEvents, Is.Empty);
                    Assert.That(algorithm.Portfolio.CashBook[Currencies.USD].Amount,
                        Is.EqualTo(snapshot.Cash));
                    Assert.That(algorithm.Portfolio[symbol].Quantity,
                        Is.EqualTo(snapshot.Holding));
                    Assert.That(transaction.GetOpenOrders().Count,
                        Is.EqualTo(ledgerPartial ? 1 : 0));
                    Assert.That(File.ReadAllBytes(path + ".ledger.json")
                        .SequenceEqual(ledgerBefore), Is.True);
                    brokerage.Verify(x => x.PlaceOrder(It.IsAny<Order>()), Times.Never);
                    Console.WriteLine($"TL001A_LEAN_FORWARD phase={phase} delivery=rejected_unknown_order events=2 cash={snapshot.Cash} holding={snapshot.Holding} open_orders={(ledgerPartial ? 1 : 0)} ledger=unchanged new_submissions=0");
                    return;
                }
                if (partialOrder)
                {
                    Console.WriteLine($"TL001A_LEAN_FORWARD phase={phase} status=PartiallyFilled cash={snapshot.Cash} holding={snapshot.Holding} open_orders=1 decision=HOLD_NEW_ORDERS new_submissions=0");
                    return;
                }
                string recordState;
                try
                {
                    recordState = pending ? "none" : ledgerFull ? "ledger_verified" :
                        RecordOrVerifyExecution(path, snapshot);
                }
                catch (JsonException) when (phase == "restore_torn_record")
                {
                    Console.WriteLine("TL001A_LEAN_FORWARD phase=restore_torn_record decision=BLOCK reason=truncated_reconciliation_record new_submissions=0");
                    Environment.Exit(42);
                    return;
                }
                if (phase == "restore_late_event")
                {
                    Assert.That(snapshot.LeanOrderId, Is.GreaterThan(0));
                    var lateOrder = new LimitOrder(symbol, snapshot.Quantity,
                        snapshot.LimitPrice, DateTime.UtcNow)
                    {
                        Id = snapshot.LeanOrderId,
                        BrokerId = new List<string> { snapshot.BrokerId }
                    };
                    brokerage.Raise(x => x.OrdersStatusChanged += null, brokerage.Object,
                        new List<OrderEvent>
                        {
                            new OrderEvent(lateOrder, DateTime.UtcNow,
                                new OrderFee(new CashAmount(snapshot.Fee, Currencies.USD)))
                            {
                                Status = OrderStatus.Filled,
                                FillQuantity = snapshot.Quantity,
                                FillPrice = snapshot.FillPrice
                            }
                        });
                    Assert.That(algorithm.SeenEvents, Is.Empty);
                    Assert.That(algorithm.Portfolio.CashBook[Currencies.USD].Amount,
                        Is.EqualTo(snapshot.Cash));
                    Assert.That(algorithm.Portfolio[symbol].Quantity,
                        Is.EqualTo(snapshot.Holding));
                    brokerage.Verify(x => x.PlaceOrder(It.IsAny<Order>()), Times.Never);
                    Console.WriteLine($"TL001A_LEAN_FORWARD phase=restore_late_event delivery=rejected_unknown_order record={recordState} cash={snapshot.Cash} holding={snapshot.Holding} new_submissions=0");
                    return;
                }
                Console.WriteLine($"TL001A_LEAN_FORWARD phase={phase} status={snapshot.BrokerStatus} symbol={snapshot.SymbolTicker} broker_id={snapshot.BrokerId} cash={snapshot.Cash} holding={snapshot.Holding} open_orders={restored.Count} record={recordState} new_submissions=0");
                if (phase == "seed")
                {
                    // Terminate with the LEAN transaction handler still holding the order.
                    Environment.Exit(23);
                }
            }
            finally
            {
                transaction.Exit();
                dataManager.RemoveAllSubscriptions();
            }
        }
    }
}
