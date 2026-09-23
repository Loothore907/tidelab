// TideLab-authored synthetic LEAN live data-feed probe. Copy into Lean/Tests/Engine/DataFeeds/.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using NUnit.Framework;
using QuantConnect.Algorithm;
using QuantConnect.Data;
using QuantConnect.Data.Market;
using QuantConnect.Data.UniverseSelection;
using QuantConnect.Interfaces;
using QuantConnect.Lean.Engine.DataFeeds;
using QuantConnect.Lean.Engine.Results;
using QuantConnect.Packets;
using QuantConnect.Securities;
using QuantConnect.Tests.Engine.DataFeeds.Enumerators;
using QuantConnect.Util;
using static QuantConnect.Tests.Engine.DataFeeds.Enumerators.LiveSubscriptionEnumeratorTests;

namespace QuantConnect.Tests.Engine.DataFeeds
{
    public class TideLabManagedFeedProbe
    {
        private sealed class FeedAlgorithm : QCAlgorithm
        {
            public Symbol ProbeSymbol;
            public readonly List<decimal> Closes = new List<decimal>();
            public readonly List<DateTime> TimesUtc = new List<DateTime>();
            public override void Initialize() { }
            public override void OnData(Slice slice)
            {
                if (!slice.Bars.TryGetValue(ProbeSymbol, out var bar)) return;
                Closes.Add(bar.Close);
                TimesUtc.Add(UtcTime);
            }
        }

        [Test]
        public void LiveFeedEmitsThreeSyntheticHourlyBars()
        {
            var start = new DateTime(2026, 1, 5, 15, 0, 0, DateTimeKind.Utc);
            var time = new ManualTimeProvider();
            time.SetCurrentTimeUtc(start);
            var algorithm = new FeedAlgorithm();
            algorithm.SetStartDate(2026, 1, 5);
            algorithm.SetDateTime(start);
            algorithm.SetBenchmark(_ => 1m);
            var symbol = Symbols.SPY;
            algorithm.ProbeSymbol = symbol;
            using var queue = new TestDataQueueHandler
            {
                DataPerSymbol = new Dictionary<Symbol, List<BaseData>>
                {
                    [symbol] = new[] { 100m, 102m, 104m }
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

            var slicesWithData = 0;
            try
            {
                using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(20));
                foreach (var timeSlice in synchronizer.StreamData(deadline.Token))
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
                    if (algorithm.Closes.Count == 3) break;
                    // Hold at each expected bar boundary until the feed emits it.
                    // Advancing past a missing bar would conceal a gap in forward delivery.
                    var boundary = start.AddHours(algorithm.Closes.Count + 1)
                        .AddMinutes(1);
                    var next = time.GetUtcNow().AddMinutes(5);
                    time.SetCurrentTimeUtc(next < boundary ? next : boundary);
                }
                Assert.That(slicesWithData, Is.EqualTo(3),
                    $"Observed closes: {string.Join(",", algorithm.Closes)}");
                Assert.That(algorithm.Closes, Is.EqualTo(new[] { 100m, 102m, 104m }));
                Assert.That(algorithm.TimesUtc, Is.EqualTo(new[]
                {
                    start.AddHours(1), start.AddHours(2), start.AddHours(3)
                }));
                Console.WriteLine("TL001A_LEAN_FEED phase=managed_feed slices=3 closes=100,102,104 callback=3 manager=not_run");
            }
            finally
            {
                feed.Exit();
                dataManager.RemoveAllSubscriptions();
            }
        }
    }
}
