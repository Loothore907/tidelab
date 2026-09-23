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
            public string BrokerId { get; set; }
            public decimal Cash { get; set; }
            public decimal Holding { get; set; }
            public decimal Quantity { get; set; }
            public decimal LimitPrice { get; set; }
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
                    BrokerId = "TL001A-BROKER-ORDER-1",
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

            Assert.That(phase, Is.AnyOf("seed", "restore"));
            var symbol = Symbol.Create("TL001ASYN", SecurityType.Equity, Market.USA);
            var snapshot = JsonSerializer.Deserialize<BrokerReport>(File.ReadAllText(path));
            Assert.That(snapshot, Is.Not.Null);
            Assert.That(snapshot.BrokerId, Is.EqualTo("TL001A-BROKER-ORDER-1"));
            Assert.That(snapshot.Cash, Is.EqualTo(10000m));
            Assert.That(snapshot.Holding, Is.Zero);
            Assert.That(snapshot.Quantity, Is.EqualTo(1m));
            Assert.That(snapshot.LimitPrice, Is.EqualTo(90m));

            var algorithm = new ProbeAlgorithm();
            var dataManager = new DataManagerStub(algorithm, new MockDataFeed(), liveMode: true);
            algorithm.SubscriptionManager.SetDataManager(dataManager);
            var transaction = new BrokerageTransactionHandler();
            var results = new Mock<IResultHandler>();
            var realTime = new Mock<IRealTimeHandler>();
            var brokerage = new Mock<IBrokerage>();
            var pending = new LimitOrder(symbol, snapshot.Quantity, snapshot.LimitPrice,
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
                new Holding { Symbol = symbol, Quantity = snapshot.Holding, AveragePrice = 0m }
            });
            brokerage.Setup(x => x.GetOpenOrders()).Returns(new List<Order> { pending });

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
                Assert.That(restored.Count, Is.EqualTo(1));
                Assert.That(restored[0].Status, Is.EqualTo(OrderStatus.Submitted));
                Assert.That(restored[0].BrokerId, Does.Contain(snapshot.BrokerId));
                Assert.That(algorithm.Portfolio.CashBook[Currencies.USD].Amount,
                    Is.EqualTo(snapshot.Cash));
                Assert.That(algorithm.Portfolio[symbol].Quantity, Is.EqualTo(snapshot.Holding));
                brokerage.Verify(x => x.GetOpenOrders(), Times.Once);
                brokerage.Verify(x => x.GetCashBalance(), Times.Once);
                brokerage.Verify(x => x.GetAccountHoldings(), Times.Once);
                brokerage.Verify(x => x.PlaceOrder(It.IsAny<Order>()), Times.Never);
                Console.WriteLine($"TL001A_LEAN_FORWARD phase={phase} status=pending broker_id={snapshot.BrokerId} cash={snapshot.Cash} holding={snapshot.Holding} new_submissions=0");
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
