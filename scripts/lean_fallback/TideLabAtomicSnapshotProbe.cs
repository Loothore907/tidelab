// TideLab-authored synthetic broker snapshot probe; no real brokerage adapter.
using System;
using System.IO;
using System.Text.Json;
using NUnit.Framework;

namespace QuantConnect.Tests.Engine.Setup
{
    public sealed record TideLabAtomicBrokerSnapshot(int Revision, decimal Cash,
        decimal Holding, decimal FirstFilled, decimal SecondFilled,
        string FirstBrokerId, string SecondBrokerId, int JournalEvents);

    public static class TideLabAtomicSnapshotProbe
    {
        public static string SnapshotPath(string reportPath) =>
            reportPath + ".broker-snapshot.json";

        public static TideLabAtomicBrokerSnapshot Read(string reportPath)
        {
            var snapshot = JsonSerializer.Deserialize<TideLabAtomicBrokerSnapshot>(
                File.ReadAllText(SnapshotPath(reportPath)));
            if (snapshot == null || snapshot.Revision is not (2 or 3) ||
                snapshot.FirstBrokerId != "TL001A-BROKER-ORDER-1" ||
                snapshot.SecondBrokerId != "TL001A-BROKER-ORDER-2" ||
                snapshot.Holding != snapshot.FirstFilled + snapshot.SecondFilled ||
                snapshot.FirstFilled != 0.5m || snapshot.SecondFilled != 0m ||
                snapshot.JournalEvents != (snapshot.Revision == 2 ? 3 : 5) ||
                snapshot.Cash != (snapshot.Revision == 2 ? 9954.955m : 9955.455m))
                throw new InvalidDataException("BLOCK_BROKER_SNAPSHOT");
            return snapshot;
        }

        private static void Publish(string reportPath,
            TideLabAtomicBrokerSnapshot snapshot)
        {
            var path = SnapshotPath(reportPath);
            var next = path + ".next";
            if (File.Exists(next)) throw new InvalidDataException("BLOCK_STALE_SNAPSHOT_CANDIDATE");
            using (var file = new FileStream(next, FileMode.CreateNew, FileAccess.Write,
                FileShare.None, 4096, FileOptions.WriteThrough))
            {
                JsonSerializer.Serialize(file, snapshot);
                file.Flush(true);
            }
            File.Move(next, path, true);
            Assert.That(Read(reportPath), Is.EqualTo(snapshot));
        }

        public static void Seed(string reportPath)
        {
            Assert.That(File.Exists(SnapshotPath(reportPath)), Is.False);
            Publish(reportPath, new TideLabAtomicBrokerSnapshot(2, 9954.955m,
                0.5m, 0.5m, 0m, "TL001A-BROKER-ORDER-1",
                "TL001A-BROKER-ORDER-2", 3));
            Console.WriteLine("TL001A_LEAN_SNAPSHOT phase=seed revision=2 orders=2 journal_events=3");
        }

        public static void Correct(string reportPath)
        {
            Assert.That(Read(reportPath).Revision, Is.EqualTo(2));
            var journal = TideLabCorrectionJournalProbe.Replay(
                reportPath + ".correction-journal.jsonl");
            Assert.That(journal, Is.EqualTo(new TideLabJournalState(
                9955.455m, 0.5m, 0.5m, 0m, 5, false)));
            Publish(reportPath, new TideLabAtomicBrokerSnapshot(3, journal.Cash,
                journal.Holding, journal.FirstOrderFilled,
                journal.SecondOrderFilled, "TL001A-BROKER-ORDER-1",
                "TL001A-BROKER-ORDER-2", journal.EventCount));
            Console.WriteLine("TL001A_LEAN_SNAPSHOT phase=correct revision=3 orders=2 journal_events=5");
        }
    }
}
