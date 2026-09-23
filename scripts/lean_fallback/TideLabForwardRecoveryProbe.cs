// TideLab-authored synthetic LEAN setup/restart probe. Copy into Lean/Tests/Engine/Setup/.
// This is deliberately a test of brokerage-report startup, not a live trading adapter.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using Moq;
using NUnit.Framework;
using QuantConnect.Algorithm;
using QuantConnect.Brokerages;
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
    [TestFixture]
    public class TideLabForwardRecoveryProbe
    {
        private sealed class ProbeAlgorithm : QCAlgorithm
        {
            public override void Initialize() { }
        }

        private sealed class BrokerReport
        {
            public int Revision { get; set; }
            public string BrokerId { get; set; }
            public string BrokerStatus { get; set; }
            public string ExecutionId { get; set; }
            public decimal Cash { get; set; }
            public decimal Holding { get; set; }
            public decimal Quantity { get; set; }
            public decimal LimitPrice { get; set; }
            public decimal FillPrice { get; set; }
            public decimal Fee { get; set; }
        }

        private static bool IsReconciledFill(BrokerReport report)
        {
            return report != null && report.Revision == 2 &&
                report.BrokerId == "TL001A-BROKER-ORDER-1" &&
                report.BrokerStatus == "Filled" &&
                report.ExecutionId == "TL001A-EXECUTION-1" &&
                report.Quantity == 1m && report.FillPrice == 90m &&
                report.Fee == 0.09m && report.Holding == report.Quantity &&
                report.Cash == 10000m - report.Quantity * report.FillPrice - report.Fee;
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

        [Test]
        public void PendingOrderComesFromAuthoritativeSyntheticBrokerReport()
        {
            var path = Environment.GetEnvironmentVariable("TL001A_REPORT_PATH");
            var phase = Environment.GetEnvironmentVariable("TL001A_PHASE");
            Assert.That(path, Is.Not.Null.And.Not.Empty);

            if (phase == "seed")
            {
                // A separate synthetic brokerage owns this durable report. The LEAN process
                // exits without graceful teardown after the report becomes authoritative.
                var report = new BrokerReport
                {
                    Revision = 1,
                    BrokerId = "TL001A-BROKER-ORDER-1",
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

            if (phase == "settle" || phase == "settle_conflict")
            {
                var report = JsonSerializer.Deserialize<BrokerReport>(File.ReadAllText(path));
                Assert.That(report.Revision, Is.EqualTo(1));
                Assert.That(report.BrokerStatus, Is.EqualTo("Submitted"));
                report.Revision = 2;
                report.BrokerStatus = "Filled";
                report.ExecutionId = "TL001A-EXECUTION-1";
                report.FillPrice = 90m;
                report.Fee = 0.09m;
                report.Holding = 1m;
                report.Cash = phase == "settle" ? 9909.91m : 10000m;
                ReplaceReport(path, report);
                Console.WriteLine($"TL001A_LEAN_FORWARD phase={phase} broker_status=Filled cash={report.Cash} holding={report.Holding}");
                return;
            }

            if (phase == "restore_missing")
            {
                Assert.That(File.Exists(path), Is.False);
                Console.WriteLine("TL001A_LEAN_FORWARD phase=restore_missing decision=BLOCK reason=no_broker_report new_submissions=0");
                Environment.Exit(42);
                return;
            }

            Assert.That(phase, Is.AnyOf("seed", "restore", "restore_filled", "restore_conflict"));
            var symbol = Symbol.Create("TL001ASYN", SecurityType.Equity, Market.USA);
            var snapshot = JsonSerializer.Deserialize<BrokerReport>(File.ReadAllText(path));
            Assert.That(snapshot, Is.Not.Null);
            Assert.That(snapshot.BrokerId, Is.EqualTo("TL001A-BROKER-ORDER-1"));
            Assert.That(snapshot.Quantity, Is.EqualTo(1m));
            Assert.That(snapshot.LimitPrice, Is.EqualTo(90m));
            var pending = phase == "seed" || phase == "restore";
            if (pending)
            {
                Assert.That(snapshot.Revision, Is.EqualTo(1));
                Assert.That(snapshot.BrokerStatus, Is.EqualTo("Submitted"));
                Assert.That(snapshot.Cash, Is.EqualTo(10000m));
                Assert.That(snapshot.Holding, Is.Zero);
            }
            else if (phase == "restore_conflict")
            {
                Assert.That(IsReconciledFill(snapshot), Is.False);
                Console.WriteLine("TL001A_LEAN_FORWARD phase=restore_conflict decision=BLOCK reason=account_execution_mismatch new_submissions=0");
                Environment.Exit(42);
                return;
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
            var pendingOrder = new LimitOrder(symbol, snapshot.Quantity, snapshot.LimitPrice,
                new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc))
            {
                Status = OrderStatus.Submitted,
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
                pending ? new List<Order> { pendingOrder } : new List<Order>());

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
                Assert.That(restored.Count, Is.EqualTo(pending ? 1 : 0));
                if (pending)
                {
                    Assert.That(restored[0].Status, Is.EqualTo(OrderStatus.Submitted));
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
                Console.WriteLine($"TL001A_LEAN_FORWARD phase={phase} status={snapshot.BrokerStatus} broker_id={snapshot.BrokerId} cash={snapshot.Cash} holding={snapshot.Holding} open_orders={restored.Count} new_submissions=0");
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
