// TideLab-authored synthetic paper-order intent probe; no real broker or order.
using System;
using System.IO;
using System.Text.Json;
using NUnit.Framework;

namespace QuantConnect.Tests.Engine.Setup
{
    public sealed record TideLabPaperIntent(int Version, string ClientId,
        int SnapshotRevision, decimal Quantity, decimal LimitPrice, string Status);

    public sealed record TideLabPaperOrderReport(string ClientId, string BrokerId,
        int SnapshotRevision, decimal Quantity, decimal LimitPrice,
        decimal Cash, decimal Holding, string Status);

    public enum TideLabPaperLookup { Absent, Found, Conflict, Unknown }

    public interface ITideLabPaperOrderAuthority
    {
        TideLabPaperLookup Lookup(TideLabPaperIntent intent);
        void Submit(TideLabPaperIntent intent);
    }

    // This local file double makes absence authoritative for the synthetic paper source.
    // An external venue would need its own explicit lookup/command guarantees.
    public sealed class TideLabFilePaperOrderAuthority : ITideLabPaperOrderAuthority
    {
        private readonly string _path;
        public TideLabFilePaperOrderAuthority(string reportPath) =>
            _path = reportPath + ".paper-order.json";

        public TideLabPaperLookup Lookup(TideLabPaperIntent intent)
        {
            if (File.Exists(_path + ".unknown")) return TideLabPaperLookup.Unknown;
            if (File.Exists(_path + ".next")) return TideLabPaperLookup.Unknown;
            if (!File.Exists(_path)) return TideLabPaperLookup.Absent;
            TideLabPaperOrderReport report;
            try
            {
                report = JsonSerializer.Deserialize<TideLabPaperOrderReport>(
                    File.ReadAllText(_path));
            }
            catch { return TideLabPaperLookup.Unknown; }
            return report == Expected(intent) ? TideLabPaperLookup.Found :
                TideLabPaperLookup.Conflict;
        }

        private static TideLabPaperOrderReport Expected(TideLabPaperIntent intent) =>
            new(intent.ClientId, "TL001A-PAPER-BROKER-ORDER-3",
                intent.SnapshotRevision, intent.Quantity, intent.LimitPrice,
                9955.455m, 0.5m, "Submitted");

        public void Submit(TideLabPaperIntent intent)
        {
            if (Lookup(intent) != TideLabPaperLookup.Absent)
                throw new InvalidDataException("BLOCK_PAPER_DUPLICATE_OR_UNKNOWN");
            TideLabPaperIntentRecoveryProbe.WriteAtomic(_path, Expected(intent));
        }

        public void MakeUnknown() => File.WriteAllText(_path + ".unknown", "unknown");

        public void MakeConflict(TideLabPaperIntent intent) =>
            TideLabPaperIntentRecoveryProbe.WriteAtomic(_path,
                Expected(intent) with { LimitPrice = intent.LimitPrice + 1m });
    }

    public static class TideLabPaperIntentRecoveryProbe
    {
        private const string ClientId = "TL001A-CLIENT-ORDER-3";
        private static string IntentPath(string path) => path + ".paper-intent.json";

        public static void WriteAtomic<T>(string path, T value)
        {
            var next = path + ".next";
            if (File.Exists(next)) throw new InvalidDataException("BLOCK_STALE_PAPER_WRITE");
            using (var file = new FileStream(next, FileMode.CreateNew, FileAccess.Write,
                FileShare.None, 4096, FileOptions.WriteThrough))
            {
                JsonSerializer.Serialize(file, value);
                file.Flush(true);
            }
            File.Move(next, path, true);
        }

        private static TideLabPaperIntent ReadIntent(string path)
        {
            if (File.Exists(IntentPath(path) + ".next"))
                throw new InvalidDataException("BLOCK_STALE_PAPER_WRITE");
            var intent = JsonSerializer.Deserialize<TideLabPaperIntent>(
                File.ReadAllText(IntentPath(path)));
            if (intent == null || intent.Version != 1 || intent.ClientId != ClientId ||
                intent.SnapshotRevision != 3 || intent.Quantity != 1m ||
                intent.LimitPrice != 88m ||
                intent.Status is not ("Pending" or "Accepted"))
                throw new InvalidDataException("BLOCK_PAPER_INTENT_FIELDS");
            return intent;
        }

        private static void Accept(string path, TideLabPaperIntent intent) =>
            WriteAtomic(IntentPath(path), intent with { Status = "Accepted" });

        private static string Recover(string path,
            ITideLabForwardPaperSource source, ITideLabPaperOrderAuthority authority,
            out int newSubmissions)
        {
            newSubmissions = 0;
            var intent = ReadIntent(path);
            if (source.ReadSnapshot().Revision != intent.SnapshotRevision)
                return "BLOCK_STALE_INTENT";
            var lookup = authority.Lookup(intent);
            if (lookup == TideLabPaperLookup.Unknown) return "BLOCK_UNKNOWN_REPORT";
            if (lookup == TideLabPaperLookup.Conflict) return "BLOCK_CONFLICTING_REPORT";
            if (lookup == TideLabPaperLookup.Found)
            {
                Accept(path, intent);
                return "RECOVERED_EXISTING";
            }
            if (intent.Status == "Accepted") return "BLOCK_MISSING_ACCEPTED_ORDER";
            // Only the local single-writer paper double can declare absence final.
            var result = source.SubmitIfCurrent(intent.SnapshotRevision, () =>
            {
                authority.Submit(intent);
                return true;
            });
            if (result != "SUBMITTED_PAPER") return result;
            newSubmissions = 1;
            Accept(path, intent);
            return "RECOVERED_ABSENT";
        }

        public static void Run(string path, string phase)
        {
            ITideLabForwardPaperSource source = new TideLabSerializedPaperSource(path);
            var authority = new TideLabFilePaperOrderAuthority(path);
            Assert.That(source.ReadSnapshot().Revision, Is.EqualTo(3));
            if (phase is "intent_crash_before_dispatch" or "intent_crash_after_commit")
            {
                Assert.That(File.Exists(IntentPath(path)), Is.False);
                var intent = new TideLabPaperIntent(1, ClientId, 3, 1m, 88m, "Pending");
                var result = source.SubmitIfCurrent(3, () =>
                {
                    WriteAtomic(IntentPath(path), intent);
                    Assert.That(ReadIntent(path), Is.EqualTo(intent));
                    if (phase == "intent_crash_before_dispatch")
                    {
                        Console.WriteLine("TL001A_LEAN_INTENT phase=before_dispatch " +
                            "intent=durable broker=absent new_submissions=0");
                        Environment.Exit(71);
                    }
                    authority.Submit(intent);
                    Assert.That(authority.Lookup(intent), Is.EqualTo(TideLabPaperLookup.Found));
                    Console.WriteLine("TL001A_LEAN_INTENT phase=after_commit " +
                        "intent=pending broker=submitted ack=lost new_submissions=1");
                    Environment.Exit(72);
                    return true;
                });
                throw new InvalidOperationException("Expected forced exit, got " + result);
            }
            if (phase == "intent_mark_unknown")
            {
                authority.MakeUnknown();
                Console.WriteLine("TL001A_LEAN_INTENT phase=mark_unknown report=unknown");
                return;
            }
            if (phase == "intent_mark_conflict")
            {
                authority.MakeConflict(ReadIntent(path));
                Console.WriteLine("TL001A_LEAN_INTENT phase=mark_conflict report=conflicting");
                return;
            }
            var decision = Recover(path, source, authority, out var submitted);
            var expected = phase switch
            {
                "intent_recover_absent" => "RECOVERED_ABSENT",
                "intent_recover_existing" or "intent_recover_repeat" => "RECOVERED_EXISTING",
                "intent_recover_unknown" => "BLOCK_UNKNOWN_REPORT",
                "intent_recover_conflict" => "BLOCK_CONFLICTING_REPORT",
                _ => throw new ArgumentException(phase)
            };
            Assert.That(decision, Is.EqualTo(expected));
            Assert.That(submitted, Is.EqualTo(phase == "intent_recover_absent" ? 1 : 0));
            if (decision.StartsWith("RECOVERED", StringComparison.Ordinal))
            {
                Assert.That(ReadIntent(path).Status, Is.EqualTo("Accepted"));
                Assert.That(authority.Lookup(ReadIntent(path)),
                    Is.EqualTo(TideLabPaperLookup.Found));
            }
            else Assert.That(ReadIntent(path).Status, Is.EqualTo("Pending"));
            Console.WriteLine($"TL001A_LEAN_INTENT phase={phase} decision={decision} " +
                $"new_submissions={submitted}");
        }
    }
}
