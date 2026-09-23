// TideLab-authored synthetic per-execution recovery probe; no order submission path.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using NUnit.Framework;

namespace QuantConnect.Tests.Engine.Setup
{
    public sealed class TideLabExecutionLedgerProbe
    {
        private sealed class Execution
        {
            public string Id { get; set; }
            public decimal Quantity { get; set; }
            public decimal Price { get; set; }
            public decimal Fee { get; set; }
        }

        private sealed class Report
        {
            public int Revision { get; set; }
            public int LeanOrderId { get; set; }
            public string SymbolTicker { get; set; }
            public string BrokerId { get; set; }
            public string BrokerStatus { get; set; }
            public string ExecutionId { get; set; }
            public decimal Quantity { get; set; }
            public decimal ExecutedQuantity { get; set; }
            public decimal LimitPrice { get; set; }
            public decimal FillPrice { get; set; }
            public decimal Fee { get; set; }
            public decimal Cash { get; set; }
            public decimal Holding { get; set; }
            public List<Execution> Executions { get; set; }
        }

        private sealed class Ledger
        {
            public int Revision { get; set; }
            public string SymbolTicker { get; set; }
            public string BrokerId { get; set; }
            public decimal Cash { get; set; }
            public decimal Holding { get; set; }
            public List<Execution> Executions { get; set; }
        }

        private static readonly Execution First = new Execution
        {
            Id = "TL001A-EXECUTION-1", Quantity = 0.5m, Price = 90m, Fee = 0.045m
        };
        private static readonly Execution Second = new Execution
        {
            Id = "TL001A-EXECUTION-2", Quantity = 0.5m, Price = 90m, Fee = 0.045m
        };

        private static Report ReadReport(string path) =>
            JsonSerializer.Deserialize<Report>(File.ReadAllText(path));

        private static void WriteDurable(string path, object value)
        {
            using var file = new FileStream(path, FileMode.CreateNew, FileAccess.Write,
                FileShare.None, 4096, FileOptions.WriteThrough);
            JsonSerializer.Serialize(file, value);
            file.Flush(true);
        }

        private static void PublishReport(string path, Report report)
        {
            var next = path + ".next";
            WriteDurable(next, report);
            File.Move(next, path, true);
        }

        private static void ValidateExecution(Execution execution, Execution expected)
        {
            Assert.That(execution.Id, Is.EqualTo(expected.Id));
            Assert.That(execution.Quantity, Is.EqualTo(expected.Quantity));
            Assert.That(execution.Price, Is.EqualTo(expected.Price));
            Assert.That(execution.Fee, Is.EqualTo(expected.Fee));
        }

        private static void ValidateReport(Report report)
        {
            Assert.That(report, Is.Not.Null);
            Assert.That(report.SymbolTicker, Is.EqualTo("SPY"));
            Assert.That(report.BrokerId, Is.EqualTo("TL001A-BROKER-ORDER-1"));
            Assert.That(report.LeanOrderId, Is.GreaterThan(0));
            Assert.That(report.Quantity, Is.EqualTo(1m));
            Assert.That(report.LimitPrice, Is.EqualTo(90m));
            Assert.That(report.Executions, Is.Not.Null);
            Assert.That(report.Executions.Count, Is.InRange(1, 2));
            ValidateExecution(report.Executions[0], First);
            if (report.Executions.Count == 2)
                ValidateExecution(report.Executions[1], Second);
            Assert.That(report.Executions.Select(x => x.Id).Distinct().Count(),
                Is.EqualTo(report.Executions.Count));
            Assert.That(report.Holding, Is.EqualTo(report.Executions.Sum(x => x.Quantity)));
            Assert.That(report.ExecutedQuantity, Is.EqualTo(report.Holding));
            Assert.That(report.FillPrice, Is.EqualTo(90m));
            Assert.That(report.Fee, Is.EqualTo(report.Executions.Sum(x => x.Fee)));
            Assert.That(report.ExecutionId, Is.EqualTo(report.Executions.Last().Id));
            Assert.That(report.Cash, Is.EqualTo(10000m - report.Executions.Sum(
                x => x.Quantity * x.Price + x.Fee)));
            Assert.That(report.Revision, Is.EqualTo(report.Executions.Count + 1));
            Assert.That(report.BrokerStatus, Is.EqualTo(report.Executions.Count == 1 ?
                "PartiallyFilled" : "Filled"));
        }

        private static Ledger ReadAndValidateLedger(string path, Report report)
        {
            if (!File.Exists(path)) return null;
            var ledger = JsonSerializer.Deserialize<Ledger>(File.ReadAllText(path));
            Assert.That(ledger, Is.Not.Null);
            Assert.That(ledger.SymbolTicker, Is.EqualTo(report.SymbolTicker));
            Assert.That(ledger.BrokerId, Is.EqualTo(report.BrokerId));
            Assert.That(ledger.Executions, Is.Not.Null);
            Assert.That(ledger.Executions.Count, Is.InRange(1, report.Executions.Count));
            for (var i = 0; i < ledger.Executions.Count; i++)
                ValidateExecution(ledger.Executions[i], report.Executions[i]);
            Assert.That(ledger.Revision, Is.EqualTo(ledger.Executions.Count + 1));
            Assert.That(ledger.Holding, Is.EqualTo(ledger.Executions.Sum(x => x.Quantity)));
            Assert.That(ledger.Cash, Is.EqualTo(10000m - ledger.Executions.Sum(
                x => x.Quantity * x.Price + x.Fee)));
            return ledger;
        }

        private static Ledger FromReport(Report report) => new Ledger
        {
            Revision = report.Revision,
            SymbolTicker = report.SymbolTicker,
            BrokerId = report.BrokerId,
            Cash = report.Cash,
            Holding = report.Holding,
            Executions = report.Executions
        };

        public static bool IsReadyForFreshSetup(string reportPath, int expectedExecutions)
        {
            var report = ReadReport(reportPath);
            ValidateReport(report);
            Assert.That(report.Executions.Count, Is.EqualTo(expectedExecutions));
            var ledger = ReadAndValidateLedger(reportPath + ".ledger.json", report);
            return ledger != null && ledger.Executions.Count == expectedExecutions;
        }

        // Test adapter seam: the broker's stable execution ID is checked before
        // constructing a LEAN OrderEvent, which has no broker execution ID here.
        public static string ScreenBrokerExecution(string reportPath, string executionId,
            decimal quantity, decimal price, decimal fee)
        {
            var report = ReadReport(reportPath);
            ValidateReport(report);
            var ledgerPath = reportPath + ".ledger.json";
            var ledger = ReadAndValidateLedger(ledgerPath, report);
            Assert.That(ledger, Is.Not.Null);
            var execution = report.Executions.SingleOrDefault(x => x.Id == executionId);
            if (execution == null) return "BLOCK_UNREPORTED";
            if (execution.Quantity != quantity || execution.Price != price ||
                execution.Fee != fee) return "BLOCK_MISMATCH";
            if (ledger.Executions.Any(x => x.Id == executionId)) return "SUPPRESS_COMMITTED";
            if (ledger.Executions.Count + 1 != report.Executions.Count ||
                report.Executions.Last().Id != executionId) return "BLOCK_SEQUENCE";
            var next = ledgerPath + ".next";
            Assert.That(File.Exists(next), Is.False);
            WriteDurable(next, FromReport(report));
            File.Move(next, ledgerPath, true);
            Assert.That(IsReadyForFreshSetup(reportPath, report.Executions.Count), Is.True);
            return "DELIVER_AFTER_COMMIT";
        }

        public static void AdvanceReportToFull(string path)
        {
            var report = ReadReport(path);
            ValidateReport(report);
            Assert.That(report.Revision, Is.EqualTo(2));
            report.Revision = 3;
            report.BrokerStatus = "Filled";
            report.Executions.Add(Second);
            report.ExecutionId = Second.Id;
            report.ExecutedQuantity = 1m;
            report.Fee += Second.Fee;
            report.Holding = 1m;
            report.Cash = 9909.91m;
            ValidateReport(report);
            PublishReport(path, report);
        }

        public void Run()
        {
            var path = Environment.GetEnvironmentVariable("TL001A_REPORT_PATH");
            var phase = Environment.GetEnvironmentVariable("TL001A_PHASE");
            Assert.That(path, Is.Not.Null.And.Not.Empty);
            var ledgerPath = path + ".ledger.json";
            var next = ledgerPath + ".next";
            var report = ReadReport(path);

            if (phase == "ledger_partial_report")
            {
                Assert.That(report.Revision, Is.EqualTo(1));
                Assert.That(report.BrokerStatus, Is.EqualTo("Submitted"));
                report.Revision = 2;
                report.BrokerStatus = "PartiallyFilled";
                report.Executions = new List<Execution> { First };
                report.ExecutionId = First.Id;
                report.ExecutedQuantity = First.Quantity;
                report.FillPrice = First.Price;
                report.Fee = First.Fee;
                report.Holding = 0.5m;
                report.Cash = 9954.955m;
                ValidateReport(report);
                PublishReport(path, report);
                Console.WriteLine("TL001A_LEAN_LEDGER phase=partial_report revision=2 executions=1 cash=9954.955 holding=0.5");
                return;
            }

            if (phase == "ledger_full_report")
            {
                AdvanceReportToFull(path);
                Console.WriteLine("TL001A_LEAN_LEDGER phase=full_report revision=3 executions=2 cash=9909.91 holding=1");
                return;
            }

            ValidateReport(report);
            var existing = ReadAndValidateLedger(ledgerPath, report);
            if (phase == "ledger_crash_before_write")
            {
                Assert.That(report.Revision, Is.EqualTo(3));
                Assert.That(existing.Executions.Count, Is.EqualTo(1));
                Console.WriteLine("TL001A_LEAN_LEDGER phase=crash_before_write broker_executions=2 ledger_executions=1");
                Environment.Exit(23);
            }
            if (phase == "ledger_crash_after_flush")
            {
                Assert.That(report.Revision, Is.EqualTo(3));
                Assert.That(existing.Executions.Count, Is.EqualTo(1));
                WriteDurable(next, FromReport(report));
                Console.WriteLine("TL001A_LEAN_LEDGER phase=crash_after_flush broker_executions=2 ledger_executions=1 candidate_flushed=true");
                Environment.Exit(23);
            }
            Assert.That(phase, Is.EqualTo("ledger_reconcile"));
            if (existing != null && existing.Executions.Count == report.Executions.Count)
            {
                Assert.That(File.Exists(next), Is.False);
                Console.WriteLine($"TL001A_LEAN_LEDGER phase=reconcile state=verified_existing executions={existing.Executions.Count} cash={existing.Cash} holding={existing.Holding}");
                return;
            }
            var state = "created_from_report";
            if (File.Exists(next))
            {
                var candidate = ReadAndValidateLedger(next, report);
                Assert.That(candidate.Executions.Count, Is.EqualTo(report.Executions.Count));
                state = "recovered_flushed_candidate";
            }
            else
            {
                WriteDurable(next, FromReport(report));
            }
            File.Move(next, ledgerPath, true);
            var committed = ReadAndValidateLedger(ledgerPath, report);
            Assert.That(committed.Executions.Count, Is.EqualTo(report.Executions.Count));
            Console.WriteLine($"TL001A_LEAN_LEDGER phase=reconcile state={state} executions={committed.Executions.Count} cash={committed.Cash} holding={committed.Holding}");
        }
    }
}
