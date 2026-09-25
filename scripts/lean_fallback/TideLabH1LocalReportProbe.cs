// TideLab-authored synthetic H1/LEAN report probe. Copy into Lean/Tests/Engine/Setup/.
// The local report and account are controlled fixtures, never external broker state.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading;
using Moq;
using NUnit.Framework;
using QuantConnect.Algorithm;
using QuantConnect.Algorithm.CSharp;
using QuantConnect.Brokerages;
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
    public static class TideLabH1LocalReportProbe
    {
        private sealed class ProbeAlgorithm : QCAlgorithm
        {
            public override void Initialize() { }
        }

        private sealed record Execution(string ExecutionId, decimal Quantity,
            decimal Price, decimal Fee);

        private sealed record Report(int Version, string ClientId, string InstrumentId,
            string SourceRevision, int LeanOrderId, string BrokerId, int Revision,
            string BrokerStatus, decimal Quantity, decimal LimitPrice,
            List<Execution> Executions, decimal Cash, decimal Holding);

        private static T Read<T>(string path) =>
            JsonSerializer.Deserialize<T>(File.ReadAllText(path)) ??
            throw new InvalidDataException("H1 report or proposal is empty");

        private static void Write(string path, Report report, bool replace = false)
        {
            var target = replace ? path + ".next" : path;
            using (var file = new FileStream(target, FileMode.CreateNew,
                FileAccess.Write, FileShare.None, 4096, FileOptions.WriteThrough))
            {
                JsonSerializer.Serialize(file, report);
                file.Flush(true);
            }
            if (replace) File.Move(target, path, true);
        }

        private static void Bridge(string action)
        {
            var script = Environment.GetEnvironmentVariable("TL_H1_BRIDGE_SCRIPT") ??
                throw new InvalidDataException("Missing H1 bridge script");
            var database = Environment.GetEnvironmentVariable("TL_H1_BRIDGE_DATABASE") ??
                throw new InvalidDataException("Missing H1 bridge database");
            var proposal = Environment.GetEnvironmentVariable("TL_H1_PROPOSAL_PATH") ??
                throw new InvalidDataException("Missing H1 proposal path");
            var report = Environment.GetEnvironmentVariable("TL001A_REPORT_PATH") ??
                throw new InvalidDataException("Missing H1 report path");
            var start = new ProcessStartInfo(
                Environment.GetEnvironmentVariable("TL_H1_BRIDGE_PYTHON") ?? "python3")
            {
                UseShellExecute = false,
                RedirectStandardError = true
            };
            foreach (var argument in new[] { script, action, database, proposal, report })
                start.ArgumentList.Add(argument);
            using var process = Process.Start(start) ??
                throw new InvalidDataException("H1 bridge process did not start");
            var error = process.StandardError.ReadToEnd();
            process.WaitForExit();
            if (process.ExitCode != 0)
                throw new InvalidDataException("BLOCK_H1_" + action + ": " + error);
        }

        private static void CheckIdentity(TideLabH1V1PaperProposal proposal,
            Report report)
        {
            if (report.Version != 1 || report.ClientId != proposal.ClientId ||
                report.InstrumentId != proposal.InstrumentId ||
                report.SourceRevision != proposal.SourceRevision ||
                report.Quantity != (proposal.Side == "buy" ?
                    proposal.Quantity : -proposal.Quantity) ||
                report.LimitPrice != proposal.LimitPrice ||
                report.LeanOrderId <= 0 || string.IsNullOrEmpty(report.BrokerId))
                throw new InvalidDataException("H1 report identity changed");
        }

        private static void Setup(string path, TideLabH1V1PaperProposal proposal,
            Report report, bool submit, Action? duringOpenOrders = null)
        {
            var symbol = Symbol.Create("TLH1SYN", SecurityType.Equity, Market.USA);
            var algorithm = new ProbeAlgorithm();
            var dataManager = new DataManagerStub(algorithm, new MockDataFeed(),
                liveMode: true);
            algorithm.SubscriptionManager.SetDataManager(dataManager);
            var transaction = new BrokerageTransactionHandler();
            var results = new Mock<IResultHandler>();
            var realTime = new Mock<IRealTimeHandler>();
            var brokerage = new Mock<IBrokerage>();
            using var submitted = new ManualResetEventSlim();
            var cash = report?.Cash ?? proposal.Cash;
            var holding = report?.Holding ?? proposal.Units;
            brokerage.Setup(x => x.IsConnected).Returns(true);
            brokerage.Setup(x => x.AccountBaseCurrency).Returns(Currencies.USD);
            brokerage.Setup(x => x.GetCashBalance()).Returns(new List<CashAmount>
                { new(cash, Currencies.USD) });
            brokerage.Setup(x => x.GetAccountHoldings()).Returns(new List<Holding>
                { new() { Symbol = symbol, Quantity = holding,
                    AveragePrice = proposal.LimitPrice, MarketPrice = proposal.LimitPrice } });
            var open = new List<Order>();
            if (report?.BrokerStatus == "PartiallyFilled" ||
                report?.BrokerStatus == "Submitted")
                open.Add(new LimitOrder(symbol, report.Quantity, report.LimitPrice,
                    proposal.ObservedOpenUtc)
                {
                    Id = report.LeanOrderId,
                    Status = report.BrokerStatus == "Submitted" ?
                        OrderStatus.Submitted : OrderStatus.PartiallyFilled,
                    BrokerId = new List<string> { report.BrokerId }
                });
            var openedOrders = false;
            brokerage.Setup(x => x.GetOpenOrders()).Returns(() =>
            {
                if (!openedOrders && duringOpenOrders != null)
                {
                    openedOrders = true;
                    duringOpenOrders();
                }
                return open;
            });
            if (submit)
                brokerage.Setup(x => x.PlaceOrder(It.IsAny<Order>()))
                    .Callback<Order>(order =>
                    {
                        if (order is not LimitOrder limit ||
                            order.Quantity != (proposal.Side == "buy" ?
                                proposal.Quantity : -proposal.Quantity) ||
                            limit.LimitPrice != proposal.LimitPrice ||
                            order.Symbol != symbol)
                            throw new InvalidDataException("H1 LEAN order terms changed");
                        Bridge("claim"); // SQLite unknown state precedes broker write.
                        order.BrokerId = new List<string>
                            { "H1-BROKER-" + proposal.ClientId[5..21] };
                        Write(path, new Report(1, proposal.ClientId,
                            proposal.InstrumentId, proposal.SourceRevision, order.Id,
                            order.BrokerId[0], 1, "Submitted", order.Quantity,
                            limit.LimitPrice, new List<Execution>(), proposal.Cash,
                            proposal.Units));
                        submitted.Set();
                    }).Returns(true);
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
                    TestGlobals.DataCacheProvider, TestGlobals.MapFileProvider));
                Assert.That(ok, Is.True, string.Join(" | ", setup.Errors));
                Assert.That(algorithm.Portfolio.CashBook[Currencies.USD].Amount,
                    Is.EqualTo(cash));
                Assert.That(algorithm.Portfolio[symbol].Quantity,
                    Is.EqualTo(holding));
                Assert.That(transaction.GetOpenOrders().Count, Is.EqualTo(open.Count));
                if (submit)
                {
                    algorithm.Securities[symbol].SetMarketPrice(new Tick
                        { Symbol = symbol, Value = proposal.LimitPrice });
                    algorithm.SetFinishedWarmingUp();
                    algorithm.Transactions.SetOrderProcessor(transaction);
                    var ticket = algorithm.LimitOrder(symbol,
                        proposal.Side == "buy" ? proposal.Quantity : -proposal.Quantity,
                        proposal.LimitPrice);
                    Assert.That(ticket, Is.Not.Null);
                    Assert.That(ticket.Status, Is.Not.EqualTo(OrderStatus.Invalid),
                        ticket.GetMostRecentOrderResponse()?.ToString());
                    Assert.That(submitted.Wait(TimeSpan.FromSeconds(10)), Is.True,
                        "LEAN did not route the H1 order");
                    brokerage.Verify(x => x.PlaceOrder(It.IsAny<Order>()), Times.Once);
                }
                else brokerage.Verify(x => x.PlaceOrder(It.IsAny<Order>()), Times.Never);
            }
            finally
            {
                transaction.Exit();
                dataManager.RemoveAllSubscriptions();
            }
        }

        public static void Run(string path, string phase)
        {
            if (string.IsNullOrWhiteSpace(path))
                throw new ArgumentNullException(nameof(path));
            var proposal = Read<TideLabH1V1PaperProposal>(
                Environment.GetEnvironmentVariable("TL_H1_PROPOSAL_PATH") ??
                throw new InvalidDataException("Missing H1 proposal path"));
            if (proposal.Policy != "H1-v1" ||
                proposal.Side is not ("buy" or "sell") ||
                proposal.Quantity <= 0m ||
                (proposal.Side == "buy" && proposal.Units != 0m) ||
                (proposal.Side == "sell" && proposal.Units != proposal.Quantity) ||
                proposal.ObservedOpenUtc.Kind != DateTimeKind.Utc)
                throw new InvalidDataException("Invalid H1 synthetic order proposal");
            if (phase == "h1_report_seed")
            {
                if (File.Exists(path)) throw new InvalidDataException("H1 report exists");
                Setup(path, proposal, null, submit: true);
                var seeded = Read<Report>(path);
                CheckIdentity(proposal, seeded);
                Console.WriteLine($"H1V1_LEAN_REPORT phase=seed client={proposal.ClientId} " +
                    $"lean_id={seeded.LeanOrderId} quantity={seeded.Quantity} " +
                    "revision=1 new_submissions=1");
                return;
            }
            if (File.Exists(path + ".next"))
            {
                Console.WriteLine("H1V1_LEAN_REPORT gate=torn_candidate_holds " +
                    "new_submissions=0");
                throw new InvalidDataException("BLOCK_H1_TORN_REPORT");
            }
            var reportBytes = File.ReadAllBytes(path);
            var report = JsonSerializer.Deserialize<Report>(reportBytes) ??
                throw new InvalidDataException("H1 report is empty");
            CheckIdentity(proposal, report);
            if (phase == "h1_report_snapshot")
            {
                if (report.BrokerStatus is not ("Filled" or "Canceled"))
                    throw new InvalidDataException("H1 snapshot needs terminal order");
                var reference = Environment.GetEnvironmentVariable("TL_H1_REPORT_REFERENCE") ??
                    throw new InvalidDataException("Missing H1 report reference");
                var snapshotPath = Environment.GetEnvironmentVariable("TL_H1_SNAPSHOT_PATH") ??
                    throw new InvalidDataException("Missing H1 snapshot path");
                var token = $"H1-MOCK-{report.BrokerId}-{report.Revision}";
                using (var file = new FileStream(snapshotPath, FileMode.CreateNew,
                    FileAccess.Write, FileShare.None, 4096, FileOptions.WriteThrough))
                {
                    JsonSerializer.Serialize(file, new
                    {
                        Version = 1, Source = "synthetic-local-broker",
                        ObservedAtUtc = proposal.ObservedOpenUtc.AddHours(1),
                        ConsistencyToken = token, AccountRevision = token,
                        OrdersRevision = token, ExecutionsRevision = token,
                        ClientId = report.ClientId, BrokerId = report.BrokerId,
                        OrderStatus = report.BrokerStatus,
                        ReportRevision = report.Revision, ReportReference = reference,
                        Cash = report.Cash, Holding = report.Holding,
                        OpenBrokerIds = Array.Empty<string>(),
                        OrderFinality = "terminal_at_cursor"
                    });
                    file.Flush(true);
                }
                Console.WriteLine("H1V1_LEAN_REPORT phase=snapshot " +
                    "source=synthetic-local-broker new_submissions=0");
                return;
            }
            if (phase == "h1_report_cost_missed")
            {
                if (report.Revision != 1 || report.BrokerStatus != "Submitted")
                    throw new InvalidDataException("H1 missed fill requires submitted report");
                var now = proposal.ObservedOpenUtc;
                var stale = TideLabH1ConservativeExecution.Decide(true,
                    proposal.Quantity, proposal.LimitPrice, 0m,
                    TideLabH1V1Cost.Base,
                    new TideLabH1SyntheticLiquidity(now.AddMinutes(-3), 99.8m, 10m),
                    now, TimeSpan.FromMinutes(2), 1m);
                var empty = TideLabH1ConservativeExecution.Decide(true,
                    proposal.Quantity, proposal.LimitPrice, 0m,
                    TideLabH1V1Cost.Base,
                    new TideLabH1SyntheticLiquidity(now, 99.8m, 0m),
                    now, TimeSpan.FromMinutes(2), 1m);
                var limit = TideLabH1ConservativeExecution.Decide(true,
                    proposal.Quantity, proposal.LimitPrice, 0m,
                    TideLabH1V1Cost.Base,
                    new TideLabH1SyntheticLiquidity(now, 100m, 10m),
                    now, TimeSpan.FromMinutes(2), 1m);
                Assert.That(stale.State, Is.EqualTo("HOLD_STALE_OR_UNKNOWN"));
                Assert.That(empty.State, Is.EqualTo("HOLD_NO_LIQUIDITY"));
                Assert.That(limit.State, Is.EqualTo("HOLD_LIMIT"));
                Assert.That(JsonSerializer.Serialize(Read<Report>(path)),
                    Is.EqualTo(JsonSerializer.Serialize(report)));
                Console.WriteLine("H1V1_LEAN_REPORT phase=cost_missed " +
                    "stale=HOLD empty=HOLD limit=HOLD revision=1 new_submissions=0");
                return;
            }
            if (phase == "h1_report_cost_partial")
            {
                if (proposal.Side != "buy" || report.Revision != 1 ||
                    report.BrokerStatus != "Submitted")
                    throw new InvalidDataException("H1 cost partial requires entry report");
                var now = proposal.ObservedOpenUtc;
                var fill = TideLabH1ConservativeExecution.Decide(true,
                    proposal.Quantity, proposal.LimitPrice, 0m,
                    TideLabH1V1Cost.Base,
                    new TideLabH1SyntheticLiquidity(now, 99.8m, 10m),
                    now, TimeSpan.FromMinutes(2), 1m);
                Assert.That(fill.State, Is.EqualTo("PARTIAL"));
                report = report with
                {
                    Revision = 2, BrokerStatus = "PartiallyFilled",
                    Executions = new List<Execution> {
                        new("H1-COST-ENTRY-" + proposal.ClientId[5..21],
                            fill.Quantity, fill.Price, fill.Fee) },
                    Cash = proposal.Cash - fill.Quantity * fill.Price - fill.Fee,
                    Holding = proposal.Units + fill.Quantity
                };
                Write(path, report, replace: true);
                Console.WriteLine($"H1V1_LEAN_REPORT phase=cost_partial revision=2 " +
                    $"quantity={fill.Quantity} price={fill.Price} fee={fill.Fee} " +
                    $"remaining={fill.Remaining} cash={report.Cash} " +
                    $"holding={report.Holding} new_submissions=0");
                return;
            }
            if (phase == "h1_report_cost_sell_fill")
            {
                if (proposal.Side != "sell" || report.Revision != 1 ||
                    report.BrokerStatus != "Submitted")
                    throw new InvalidDataException("H1 cost sell requires exit report");
                var now = proposal.ObservedOpenUtc;
                var fill = TideLabH1ConservativeExecution.Decide(false,
                    proposal.Quantity, proposal.LimitPrice, 0m,
                    TideLabH1V1Cost.Base,
                    new TideLabH1SyntheticLiquidity(now, 98.2m, 10m),
                    now, TimeSpan.FromMinutes(2), 1m);
                Assert.That(fill.State, Is.EqualTo("FILLED"));
                report = report with
                {
                    Revision = 2, BrokerStatus = "Filled",
                    Executions = new List<Execution> {
                        new("H1-COST-EXIT-" + proposal.ClientId[5..21],
                            fill.Quantity, fill.Price, fill.Fee) },
                    Cash = proposal.Cash + fill.Quantity * fill.Price - fill.Fee,
                    Holding = proposal.Units - fill.Quantity
                };
                Write(path, report, replace: true);
                Console.WriteLine($"H1V1_LEAN_REPORT phase=cost_sell_fill revision=2 " +
                    $"quantity={fill.Quantity} price={fill.Price} fee={fill.Fee} " +
                    $"cash={report.Cash} holding={report.Holding} new_submissions=0");
                return;
            }
            if (phase == "h1_report_partial")
            {
                if (report.Revision != 1 || report.BrokerStatus != "Submitted")
                    throw new InvalidDataException("H1 partial requires submitted report");
                var fill = new Execution("H1-EXEC-" + proposal.ClientId[5..21],
                    report.Quantity * 0.4m, 99m, 0.1m);
                report = report with
                {
                    Revision = 2, BrokerStatus = "PartiallyFilled",
                    Executions = new List<Execution> { fill },
                    Cash = proposal.Cash - fill.Quantity * fill.Price - fill.Fee,
                    Holding = proposal.Units + fill.Quantity
                };
                Write(path, report, replace: true);
                Console.WriteLine($"H1V1_LEAN_REPORT phase=partial revision=2 " +
                    $"quantity={fill.Quantity} cash={report.Cash} " +
                    $"holding={report.Holding} new_submissions=0");
                return;
            }
            if (phase == "h1_report_cancel")
            {
                if (report.Revision != 2 || report.BrokerStatus != "PartiallyFilled")
                    throw new InvalidDataException("H1 cancel requires partial report");
                report = report with { Revision = 3, BrokerStatus = "Canceled" };
                Write(path, report, replace: true);
                Console.WriteLine($"H1V1_LEAN_REPORT phase=cancel revision=3 " +
                    $"holding={report.Holding} new_submissions=0");
                return;
            }
            if (phase == "h1_report_correct")
            {
                if (report.Revision != 2 || report.BrokerStatus != "PartiallyFilled")
                    throw new InvalidDataException("H1 correction requires partial report");
                var corrected = report.Executions.Single() with { Price = 98m };
                report = report with
                {
                    Revision = 3,
                    Executions = new List<Execution> { corrected },
                    Cash = proposal.Cash - corrected.Quantity * corrected.Price - corrected.Fee
                };
                Write(path, report, replace: true);
                Console.WriteLine("H1V1_LEAN_REPORT phase=correct revision=3 " +
                    "journal=must_hold new_submissions=0");
                return;
            }
            if (phase is "h1_report_restore" or "h1_report_restore_race")
            {
                Bridge("reconcile"); // Failed journal check stops before LEAN setup.
                if (File.Exists(path + ".next") ||
                    !reportBytes.SequenceEqual(File.ReadAllBytes(path)))
                    throw new InvalidDataException("BLOCK_H1_REVISION_RACE");
                Action? race = null;
                if (phase == "h1_report_restore_race")
                {
                    if (report.Revision != 2 ||
                        report.BrokerStatus != "PartiallyFilled")
                        throw new InvalidDataException("H1 restore race needs partial report");
                    race = () =>
                    {
                        var original = report.Executions.Single();
                        var corrected = original with { Price = original.Price - 1m };
                        Write(path, report with
                        {
                            Revision = 3,
                            Executions = new List<Execution> { corrected },
                            Cash = proposal.Cash - corrected.Quantity *
                                corrected.Price - corrected.Fee
                        }, replace: true);
                    };
                }
                Setup(path, proposal, report, submit: false, race);
                if (File.Exists(path + ".next") ||
                    !reportBytes.SequenceEqual(File.ReadAllBytes(path)))
                {
                    Console.WriteLine("H1V1_LEAN_REPORT phase=restore_race " +
                        "decision=BLOCK_REVISION_RACE new_submissions=0");
                    throw new InvalidDataException("BLOCK_H1_REVISION_RACE");
                }
                if (race != null)
                    throw new InvalidDataException("H1 restore race was not observed");
                Console.WriteLine($"H1V1_LEAN_REPORT phase=restore revision={report.Revision} " +
                    $"cash={report.Cash} holding={report.Holding} " +
                    "new_submissions=0");
                return;
            }
            throw new InvalidDataException("Unknown H1 local report phase");
        }
    }
}
