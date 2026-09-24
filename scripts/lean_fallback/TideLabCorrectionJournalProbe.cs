// TideLab-authored synthetic adapter journal probe; not a production broker ledger.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using NUnit.Framework;

namespace QuantConnect.Tests.Engine.Setup
{
    public sealed record TideLabJournalState(decimal Cash, decimal Holding,
        decimal FirstOrderFilled, decimal SecondOrderFilled, int EventCount,
        bool CorrectionPending);

    public static class TideLabCorrectionJournalProbe
    {
        private sealed class Entry
        {
            public int Sequence { get; set; }
            public int Revision { get; set; }
            public string Kind { get; set; }
            public string OrderId { get; set; }
            public string ExecutionId { get; set; }
            public string ReversesId { get; set; }
            public decimal Quantity { get; set; }
            public decimal Price { get; set; }
            public decimal Fee { get; set; }
        }

        private const string FirstOrder = "TL001A-BROKER-ORDER-1";
        private const string SecondOrder = "TL001A-BROKER-ORDER-2";
        private const string FirstExecution = "TL001A-EXECUTION-1";
        private const string ReplacementExecution = "TL001A-EXECUTION-1-CORRECTED";

        private static void Append(string path, Entry entry)
        {
            using var file = new FileStream(path, FileMode.Append, FileAccess.Write,
                FileShare.None, 4096, FileOptions.WriteThrough);
            JsonSerializer.Serialize(file, entry);
            file.WriteByte((byte)'\n');
            file.Flush(true);
        }

        private static IReadOnlyList<Entry> Read(string path)
        {
            var bytes = File.ReadAllBytes(path);
            if (bytes.Length == 0 || bytes[^1] != (byte)'\n')
                throw new InvalidDataException("BLOCK_TORN_JOURNAL");
            var lines = System.Text.Encoding.UTF8.GetString(bytes).Split('\n');
            var entries = lines.Take(lines.Length - 1)
                .Select(line => JsonSerializer.Deserialize<Entry>(line)).ToList();
            if (entries.Any(entry => entry == null))
                throw new InvalidDataException("BLOCK_TORN_JOURNAL");
            for (var i = 0; i < entries.Count; i++)
            {
                if (entries[i].Sequence != i + 1 || entries[i].Revision < 1 ||
                    (i > 0 && entries[i].Revision < entries[i - 1].Revision))
                    throw new InvalidDataException("BLOCK_JOURNAL_SEQUENCE");
            }
            return entries;
        }

        public static TideLabJournalState Replay(string path)
        {
            var entries = Read(path);
            var orders = new HashSet<string>();
            var active = new Dictionary<string, Entry>();
            string pending = null;
            var cash = 10000m;
            var holding = 0m;
            var firstFilled = 0m;
            var secondFilled = 0m;
            foreach (var entry in entries)
            {
                if (entry.Kind == "Order")
                {
                    if (entry.Revision != 1 || entry.Quantity != 1m ||
                        !new[] { FirstOrder, SecondOrder }.Contains(entry.OrderId) ||
                        !orders.Add(entry.OrderId))
                        throw new InvalidDataException("BLOCK_ORDER_IDENTITY");
                    continue;
                }
                if (!orders.Contains(entry.OrderId) || entry.Quantity <= 0m ||
                    entry.Price <= 0m || entry.Fee < 0m)
                    throw new InvalidDataException("BLOCK_EXECUTION_FIELDS");
                if (entry.Kind == "Reverse")
                {
                    if (pending != null || entry.OrderId != FirstOrder ||
                        entry.ReversesId != FirstExecution ||
                        !active.Remove(entry.ReversesId, out var original) ||
                        entry.Quantity != original.Quantity ||
                        entry.Price != original.Price || entry.Fee != original.Fee ||
                        entry.Revision <= original.Revision)
                        throw new InvalidDataException("BLOCK_REVERSAL");
                    cash += entry.Quantity * entry.Price + entry.Fee;
                    holding -= entry.Quantity;
                    firstFilled -= entry.Quantity;
                    pending = entry.ReversesId;
                }
                else if (entry.Kind is "Fill" or "Replacement")
                {
                    if (entry.Kind == "Fill" &&
                        (pending != null || entry.Revision != 2 ||
                            entry.ExecutionId != FirstExecution ||
                            entry.OrderId != FirstOrder))
                        throw new InvalidDataException("BLOCK_FILL_SEQUENCE");
                    if (entry.Kind == "Replacement" &&
                        (pending != FirstExecution || entry.Revision != 3 ||
                            entry.ReversesId != pending ||
                            entry.ExecutionId != ReplacementExecution ||
                            entry.OrderId != FirstOrder))
                        throw new InvalidDataException("BLOCK_REPLACEMENT");
                    if (!active.TryAdd(entry.ExecutionId, entry))
                        throw new InvalidDataException("BLOCK_DUPLICATE_EXECUTION");
                    cash -= entry.Quantity * entry.Price + entry.Fee;
                    holding += entry.Quantity;
                    if (entry.OrderId == FirstOrder) firstFilled += entry.Quantity;
                    else secondFilled += entry.Quantity;
                    if (entry.Kind == "Replacement") pending = null;
                }
                else throw new InvalidDataException("BLOCK_UNKNOWN_EVENT");
                if (firstFilled < 0m || firstFilled > 1m ||
                    secondFilled < 0m || secondFilled > 1m)
                    throw new InvalidDataException("BLOCK_ORDER_QUANTITY");
            }
            if (!orders.SetEquals(new[] { FirstOrder, SecondOrder }) ||
                holding != firstFilled + secondFilled)
                throw new InvalidDataException("BLOCK_ACCOUNT_ORDERS");
            return new TideLabJournalState(cash, holding, firstFilled,
                secondFilled, entries.Count, pending != null);
        }

        public static void Run(string path, string phase)
        {
            var journal = path + ".correction-journal.jsonl";
            if (phase == "journal_seed")
            {
                Assert.That(File.Exists(journal), Is.False);
                Append(journal, new Entry { Sequence = 1, Revision = 1,
                    Kind = "Order", OrderId = FirstOrder, Quantity = 1m });
                Append(journal, new Entry { Sequence = 2, Revision = 1,
                    Kind = "Order", OrderId = SecondOrder, Quantity = 1m });
                Append(journal, new Entry { Sequence = 3, Revision = 2,
                    Kind = "Fill", OrderId = FirstOrder,
                    ExecutionId = FirstExecution, Quantity = 0.5m,
                    Price = 90m, Fee = 0.045m });
                Assert.That(Replay(journal), Is.EqualTo(new TideLabJournalState(
                    9954.955m, 0.5m, 0.5m, 0m, 3, false)));
                Console.WriteLine("TL001A_LEAN_JOURNAL phase=seed orders=2 events=3 cash=9954.955 holding=0.5");
            }
            else if (phase == "journal_reverse")
            {
                Assert.That(Replay(journal).EventCount, Is.EqualTo(3));
                Append(journal, new Entry { Sequence = 4, Revision = 3,
                    Kind = "Reverse", OrderId = FirstOrder,
                    ReversesId = FirstExecution, Quantity = 0.5m,
                    Price = 90m, Fee = 0.045m });
                Assert.That(Replay(journal), Is.EqualTo(new TideLabJournalState(
                    10000m, 0m, 0m, 0m, 4, true)));
                Console.WriteLine("TL001A_LEAN_JOURNAL phase=reverse decision=HOLD_CORRECTION_PENDING events=4");
            }
            else if (phase == "journal_replace")
            {
                Assert.That(Replay(journal).CorrectionPending, Is.True);
                Append(journal, new Entry { Sequence = 5, Revision = 3,
                    Kind = "Replacement", OrderId = FirstOrder,
                    ExecutionId = ReplacementExecution, ReversesId = FirstExecution,
                    Quantity = 0.5m, Price = 89m, Fee = 0.045m });
                Assert.That(Replay(journal), Is.EqualTo(new TideLabJournalState(
                    9955.455m, 0.5m, 0.5m, 0m, 5, false)));
                Console.WriteLine("TL001A_LEAN_JOURNAL phase=replace orders=2 events=5 cash=9955.455 holding=0.5");
            }
            else if (phase == "journal_verify")
            {
                Assert.That(Replay(journal), Is.EqualTo(new TideLabJournalState(
                    9955.455m, 0.5m, 0.5m, 0m, 5, false)));
                Console.WriteLine("TL001A_LEAN_JOURNAL phase=verify orders=2 events=5 duplicate=none");
            }
            else throw new ArgumentException(phase);
        }
    }
}
