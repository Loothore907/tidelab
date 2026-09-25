// TideLab-authored synthetic LEAN live data-feed probe. Copy into Lean/Tests/Engine/DataFeeds/.
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
using QuantConnect.Data.UniverseSelection;
using QuantConnect.Interfaces;
using QuantConnect.Lean.Engine;
using QuantConnect.Lean.Engine.DataFeeds;
using QuantConnect.Lean.Engine.RealTime;
using QuantConnect.Lean.Engine.Results;
using QuantConnect.Lean.Engine.Server;
using QuantConnect.Lean.Engine.TransactionHandlers;
using QuantConnect.Orders;
using QuantConnect.Orders.Fees;
using QuantConnect.Packets;
using QuantConnect.Securities;
using QuantConnect.Tests.Engine.DataFeeds.Enumerators;
using QuantConnect.Util;
using static QuantConnect.Tests.Engine.DataFeeds.Enumerators.LiveSubscriptionEnumeratorTests;

namespace QuantConnect.Tests.Engine.DataFeeds
{
    public class TideLabManagedFeedProbe
    {
        private sealed class BoundedManagedSynchronizer : ISynchronizer
        {
            private readonly ISynchronizer _inner;
            private readonly ManualTimeProvider _time;
            private readonly FeedAlgorithm _algorithm;
            private readonly DateTime _start;
            private readonly int _targetCount;

            public BoundedManagedSynchronizer(ISynchronizer inner, ManualTimeProvider time,
                FeedAlgorithm algorithm, DateTime start, int targetCount)
            {
                _inner = inner;
                _time = time;
                _algorithm = algorithm;
                _start = start;
                _targetCount = targetCount;
            }

            public IEnumerable<TimeSlice> StreamData(CancellationToken cancellationToken)
            {
                foreach (var slice in _inner.StreamData(cancellationToken))
                {
                    yield return slice;
                    if (_algorithm.Closes.Count == _targetCount) yield break;
                    // Move the invented clock only after AlgorithmManager has processed the slice.
                    var boundary = _start.AddHours(_algorithm.Closes.Count + 1)
                        .AddMinutes(1);
                    var next = _time.GetUtcNow().AddMinutes(5);
                    _time.SetCurrentTimeUtc(next < boundary ? next : boundary);
                }
            }
        }

        private sealed class FeedAlgorithm : QCAlgorithm
        {
            public Symbol ProbeSymbol;
            public readonly List<decimal> Closes = new List<decimal>();
            public readonly List<DateTime> TimesUtc = new List<DateTime>();
            public bool SubmitOrder;
            public int Signals;
            public string H1Scenario;
            public string H1V1Scenario;
            public readonly List<string> H1Decisions = new List<string>();
            private readonly TideLabSyntheticSignal _signal = new TideLabSyntheticSignal();
            private readonly TideLabH1Skeleton _h1 = new TideLabH1Skeleton();
            private readonly TideLabH1V1Policy _h1v1 = new TideLabH1V1Policy();
            private bool _h1v1IsLong;
            public void SeedH1V1Warmup(DateTime finalWarmupCloseUtc)
            {
                for (var i = 167; i >= 0; i--)
                {
                    var decision = _h1v1.OnClosedHour(finalWarmupCloseUtc.AddHours(-i),
                        100m, false, 10000m, 0m);
                    if (decision.Intent != TideLabH1V1Intent.Hold)
                        throw new InvalidOperationException("Warmup emitted a decision");
                }
            }
            public override void Initialize() { }
            public override void OnData(Slice slice)
            {
                if (!slice.Bars.TryGetValue(ProbeSymbol, out var bar)) return;
                Closes.Add(bar.Close);
                TimesUtc.Add(UtcTime);
                if (H1V1Scenario != null)
                {
                    var equity = H1V1Scenario == "drawdown" && Closes.Count >= 2 ?
                        8000m : 10000m;
                    var decision = _h1v1.OnClosedHour(UtcTime, bar.Close,
                        _h1v1IsLong, equity, _h1v1IsLong ? 0.25m : 0m);
                    if (decision.Intent != TideLabH1V1Intent.Hold)
                        H1Decisions.Add($"{decision.ClosedHours}:{decision.Intent}:{decision.Risk}");
                    _h1v1IsLong = decision.Intent switch
                    {
                        TideLabH1V1Intent.EnterLong => true,
                        TideLabH1V1Intent.ExitToCash => false,
                        _ => _h1v1IsLong
                    };
                    return;
                }
                if (H1Scenario != null)
                {
                    var equity = H1Scenario == "drawdown" ? 940m : 1000m;
                    var decision = _h1.OnClosedHour(bar.Close, equity, 1000m);
                    if (decision.Intent != TideLabH1Intent.None)
                        H1Decisions.Add($"{decision.ClosedHour}:{decision.Intent}:{decision.Risk}");
                    return;
                }
                if (_signal.OnClose(bar.Close))
                {
                    Signals++;
                    if (SubmitOrder) LimitOrder(ProbeSymbol, 1m, 90m);
                }
            }
        }

        [Test]
        public void LiveFeedEmitsThreeSyntheticHourlyBars()
        {
            var start = new DateTime(2026, 1, 5, 15, 0, 0, DateTimeKind.Utc);
            var time = new ManualTimeProvider();
            time.SetCurrentTimeUtc(start);
            var algorithm = new FeedAlgorithm();
            var phase = Environment.GetEnvironmentVariable("TL001A_PHASE");
            var h1Scenario = phase == "managed_h1_drawdown" ? "drawdown" :
                phase == "managed_h1_baseline" ? "baseline" : null;
            var h1v1Scenario = phase == "managed_h1_v1_drawdown" ? "drawdown" :
                phase == "managed_h1_v1_baseline" ? "baseline" : null;
            var targetCount = h1v1Scenario != null ? 3 : h1Scenario == null ? 3 : 4;
            var managedDispatch = phase == "managed_manager_submit_seed" ||
                h1Scenario != null || h1v1Scenario != null;
            var submit = phase == "managed_feed_submit_seed" || managedDispatch;
            algorithm.SubmitOrder = submit && h1Scenario == null && h1v1Scenario == null;
            algorithm.H1Scenario = h1Scenario;
            algorithm.H1V1Scenario = h1v1Scenario;
            if (submit) algorithm.SetCash(h1Scenario == null ? 10000m : 1000m);
            algorithm.SetStartDate(2026, 1, 5);
            algorithm.SetDateTime(start);
            if (h1v1Scenario != null) algorithm.SeedH1V1Warmup(start);
            algorithm.SetBenchmark(_ => 1m);
            var symbol = Symbols.SPY;
            algorithm.ProbeSymbol = symbol;
            IEnumerable<decimal> syntheticCloses = h1v1Scenario != null ?
                new[] { 102m, 98m, 110m } :
                h1Scenario == null ?
                new[] { 100m, 102m, 104m } :
                new[] { 100m, 102m, 104m, 98m };
            using var queue = new TestDataQueueHandler
            {
                DataPerSymbol = new Dictionary<Symbol, List<BaseData>>
                {
                    [symbol] = syntheticCloses
                        .Select((close, index) => (BaseData)new TradeBar(
                            start.AddHours(index).ConvertFromUtc(TimeZones.NewYork),
                            symbol, close, close, close, close,
                            1m, TimeSpan.FromHours(1)))
                        .ToList()
                }
            };
            var feed = new TestableLiveTradingDataFeed(algorithm.Settings, queue);
            feed.TestDataQueueHandlerManager.TimeProvider = time;
            var marketHours = MarketHoursDatabase.FromDataFolder();
            var properties = SymbolPropertiesDatabase.FromDataFolder();
            var securityService = new SecurityService(algorithm.Portfolio.CashBook,
                marketHours, properties, algorithm, RegisteredSecurityDataTypesProvider.Null,
                new SecurityCacheProvider(algorithm.Portfolio), algorithm: algorithm);
            algorithm.Securities.SetSecurityService(securityService);
            var permissions = new DataPermissionManager();
            var dataManager = new DataManager(feed,
                new UniverseSelection(algorithm, securityService, permissions,
                    TestGlobals.DataProvider), algorithm, algorithm.TimeKeeper,
                marketHours, true, RegisteredSecurityDataTypesProvider.Null,
                permissions);
            algorithm.SubscriptionManager.SetDataManager(dataManager);
            algorithm.AddEquity("SPY", Resolution.Hour);
            using var synchronizer = new TestableLiveSynchronizer(time, 10);
            synchronizer.Initialize(algorithm, dataManager, new());
            feed.Initialize(algorithm, new LiveNodePacket(), new BacktestingResultHandler(),
                TestGlobals.MapFileProvider, TestGlobals.FactorFileProvider,
                TestGlobals.DataProvider, dataManager, synchronizer,
                new TestDataChannelProvider());
            algorithm.PostInitialize();
            algorithm.OnEndOfTimeStep();
            algorithm.SetLocked();
            algorithm.SetFinishedWarmingUp();
            BrokerageTransactionHandler transaction = null;
            Mock<IBrokerage> brokerage = null;
            using var submitted = new ManualResetEventSlim();
            if (submit)
            {
                var path = Environment.GetEnvironmentVariable("TL001A_REPORT_PATH");
                if (h1Scenario == null) Assert.That(path, Is.Not.Null.And.Not.Empty);
                brokerage = new Mock<IBrokerage>();
                brokerage.Setup(x => x.IsConnected).Returns(true);
                brokerage.Setup(x => x.AccountBaseCurrency).Returns(Currencies.USD);
                brokerage.Setup(x => x.PlaceOrder(It.IsAny<Order>()))
                    .Callback<Order>(order =>
                    {
                        order.BrokerId = new List<string> { "TL001A-BROKER-ORDER-1" };
                        var report = new
                        {
                            Revision = 1,
                            LeanOrderId = order.Id,
                            SymbolTicker = "SPY",
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
                transaction = new BrokerageTransactionHandler();
                transaction.Initialize(algorithm, brokerage.Object, new Mock<IResultHandler>().Object);
                algorithm.Transactions.SetOrderProcessor(transaction);
            }

            var slicesWithData = 0;
            try
            {
                using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(
                    h1v1Scenario == null ? 20 : 90));
                if (managedDispatch)
                {
                    algorithm.SetStatus(AlgorithmStatus.Running);
                    new AlgorithmManager(true).Run(new LiveNodePacket(), algorithm,
                        new BoundedManagedSynchronizer(synchronizer, time, algorithm,
                            start, targetCount),
                        transaction, new Mock<IResultHandler>().Object,
                        new Mock<IRealTimeHandler>().Object, new Mock<ILeanManager>().Object,
                        deadline, new PerformanceTrackingTool());
                    Assert.That(algorithm.RunTimeError, Is.Null);
                    slicesWithData = algorithm.Closes.Count;
                }
                else foreach (var timeSlice in synchronizer.StreamData(deadline.Token))
                {
                    algorithm.SetDateTime(timeSlice.Time);
                    if (timeSlice.Slice != null &&
                        timeSlice.Slice.Bars.TryGetValue(symbol, out _))
                    {
                        slicesWithData++;
                        algorithm.SetCurrentSlice(timeSlice.Slice);
                        algorithm.Securities[symbol].SetMarketPrice(timeSlice.Slice.Bars[symbol]);
                        // This harness dispatches the LEAN-produced slice. AlgorithmManager is not running.
                        algorithm.OnData(timeSlice.Slice);
                    }
                    if (algorithm.Closes.Count == targetCount) break;
                    // Hold at each expected bar boundary until the feed emits it.
                    // Advancing past a missing bar would conceal a gap in forward delivery.
                    var boundary = start.AddHours(algorithm.Closes.Count + 1)
                        .AddMinutes(1);
                    var next = time.GetUtcNow().AddMinutes(5);
                    time.SetCurrentTimeUtc(next < boundary ? next : boundary);
                }
                Assert.That(slicesWithData, Is.EqualTo(targetCount),
                    $"Observed closes: {string.Join(",", algorithm.Closes)}");
                Assert.That(algorithm.Closes, Is.EqualTo(syntheticCloses));
                Assert.That(algorithm.TimesUtc, Is.EqualTo(Enumerable.Range(1,
                    targetCount).Select(i => start.AddHours(i))));
                if (h1v1Scenario != null)
                {
                    var actual = string.Join("|", algorithm.H1Decisions);
                    var expected = h1v1Scenario == "drawdown" ?
                        "169:EnterLong:Clear|170:ExitToCash:DrawdownHalt" :
                        "169:EnterLong:Clear|170:ExitToCash:Clear|171:EnterLong:Clear";
                    Assert.That(actual, Is.EqualTo(expected));
                    brokerage.Verify(x => x.PlaceOrder(It.IsAny<Order>()), Times.Never);
                    Console.WriteLine($"H1V1_PARITY clock=forward drawdown={h1v1Scenario == "drawdown"} warmup=168 feed_bars={targetCount} decisions={actual} orders=0");
                    return;
                }
                if (h1Scenario != null)
                {
                    var actual = string.Join("|", algorithm.H1Decisions);
                    var expected = h1Scenario == "drawdown" ?
                        "3:EnterLong:BlockDrawdown|4:ExitToCash:Approve" :
                        "3:EnterLong:Approve|4:ExitToCash:Approve";
                    Assert.That(actual, Is.EqualTo(expected));
                    brokerage.Verify(x => x.PlaceOrder(It.IsAny<Order>()), Times.Never);
                    Console.WriteLine($"TL001A_H1_PARITY clock=forward scenario={h1Scenario} bars=4 decisions={actual}");
                    return;
                }
                Assert.That(algorithm.Signals, Is.EqualTo(1));
                if (submit)
                {
                    Assert.That(submitted.Wait(TimeSpan.FromSeconds(10)), Is.True);
                    var order = transaction.GetOpenOrders().Single();
                    brokerage.Raise(x => x.OrdersStatusChanged += null,
                        brokerage.Object, new List<OrderEvent>
                        {
                            new OrderEvent(order, DateTime.UtcNow, OrderFee.Zero)
                            {
                                Status = OrderStatus.Submitted
                            }
                        });
                    Assert.That(SpinWait.SpinUntil(() => transaction.GetOpenOrders().Any(
                        pending => pending.Status == OrderStatus.Submitted &&
                        pending.BrokerId.Contains("TL001A-BROKER-ORDER-1")),
                        TimeSpan.FromSeconds(10)), Is.True);
                    brokerage.Verify(x => x.PlaceOrder(It.IsAny<Order>()), Times.Once);
                    Console.WriteLine($"TL001A_LEAN_FEED phase={phase} slices=3 signal=1 status=Submitted new_submissions=1 manager={(managedDispatch ? "run" : "not_run")}");
                    Environment.Exit(23);
                }
                Console.WriteLine("TL001A_LEAN_FEED phase=managed_feed slices=3 closes=100,102,104 callback=3 signal=1 manager=not_run");
            }
            finally
            {
                feed.Exit();
                dataManager.RemoveAllSubscriptions();
                transaction?.Exit();
            }
        }
    }
}
