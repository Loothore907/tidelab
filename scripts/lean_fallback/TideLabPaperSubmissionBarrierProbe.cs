// TideLab-authored synthetic forward-paper source probe; not a production broker.
using System;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using Moq;
using NUnit.Framework;
using QuantConnect.Brokerages;
using QuantConnect.Interfaces;
using QuantConnect.Orders;

namespace QuantConnect.Tests.Engine.Setup
{
    public interface ITideLabForwardPaperSource
    {
        TideLabAtomicBrokerSnapshot ReadSnapshot();
        void ApplyCorrection();
        string SubmitIfCurrent(int expectedRevision, Func<bool> submit);
    }

    // All paper correction writers and order submissions must enter this source.
    // The durable journal/snapshot are checked on every read and before submission.
    public sealed class TideLabSerializedPaperSource : ITideLabForwardPaperSource
    {
        private readonly object _gate = new();
        private readonly string _reportPath;
        private bool _submissionUnknown;

        public TideLabSerializedPaperSource(string reportPath) => _reportPath = reportPath;

        private TideLabAtomicBrokerSnapshot ReadValidated()
        {
            var snapshot = TideLabAtomicSnapshotProbe.Read(_reportPath);
            var journal = TideLabCorrectionJournalProbe.Replay(
                _reportPath + ".correction-journal.jsonl");
            if (journal.CorrectionPending || journal.EventCount != snapshot.JournalEvents ||
                journal.Cash != snapshot.Cash || journal.Holding != snapshot.Holding ||
                journal.FirstOrderFilled != snapshot.FirstFilled ||
                journal.SecondOrderFilled != snapshot.SecondFilled)
                throw new InvalidDataException("BLOCK_PAPER_SOURCE_MISMATCH");
            return snapshot;
        }

        public TideLabAtomicBrokerSnapshot ReadSnapshot()
        {
            lock (_gate) return ReadValidated();
        }

        public void ApplyCorrection()
        {
            lock (_gate)
            {
                if (ReadValidated().Revision != 2)
                    throw new InvalidDataException("BLOCK_PAPER_CORRECTION_REVISION");
                TideLabCorrectionJournalProbe.Run(_reportPath, "journal_reverse");
                TideLabCorrectionJournalProbe.Run(_reportPath, "journal_replace");
                TideLabAtomicSnapshotProbe.Correct(_reportPath);
                Assert.That(ReadValidated().Revision, Is.EqualTo(3));
            }
        }

        public string SubmitIfCurrent(int expectedRevision, Func<bool> submit)
        {
            lock (_gate)
            {
                if (_submissionUnknown) return "BLOCK_SUBMISSION_UNKNOWN";
                if (ReadValidated().Revision != expectedRevision)
                    return "BLOCK_STALE_REVISION";
                try
                {
                    if (!submit())
                    {
                        _submissionUnknown = true;
                        return "BLOCK_SUBMISSION_UNKNOWN";
                    }
                    return "SUBMITTED_PAPER";
                }
                catch
                {
                    _submissionUnknown = true;
                    return "BLOCK_SUBMISSION_UNKNOWN";
                }
            }
        }
    }

    public static class TideLabPaperSubmissionBarrierProbe
    {
        private static (Mock<IBrokerage> Broker, Order Order) NewSubmission()
        {
            var broker = new Mock<IBrokerage>();
            broker.Setup(x => x.PlaceOrder(It.IsAny<Order>())).Returns(true);
            var order = new LimitOrder(
                Symbol.Create("TL001ASYN", SecurityType.Equity, Market.USA),
                1m, 88m, new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc));
            return (broker, order);
        }

        public static void Run(string path, string phase)
        {
            ITideLabForwardPaperSource source = new TideLabSerializedPaperSource(path);
            var (broker, order) = NewSubmission();
            if (phase == "paper_torn")
            {
                Assert.That(() => source.ReadSnapshot(), Throws.TypeOf<InvalidDataException>()
                    .With.Message.Contains("BLOCK_PAPER_SOURCE_MISMATCH"));
                broker.Verify(x => x.PlaceOrder(It.IsAny<Order>()), Times.Never);
                Console.WriteLine("TL001A_LEAN_PAPER phase=torn decision=BLOCK_PAPER_SOURCE_MISMATCH " +
                    "new_submissions=0");
                return;
            }
            var before = source.ReadSnapshot();
            if (phase == "paper_stale")
            {
                Assert.That(before.Revision, Is.EqualTo(2));
                source.ApplyCorrection();
                var result = source.SubmitIfCurrent(before.Revision,
                    () => broker.Object.PlaceOrder(order));
                Assert.That(result, Is.EqualTo("BLOCK_STALE_REVISION"));
                broker.Verify(x => x.PlaceOrder(It.IsAny<Order>()), Times.Never);
                Console.WriteLine("TL001A_LEAN_PAPER phase=stale decision=BLOCK_STALE_REVISION " +
                    "snapshot=2 current=3 new_submissions=0");
            }
            else if (phase == "paper_stable")
            {
                Assert.That(before.Revision, Is.EqualTo(3));
                var result = source.SubmitIfCurrent(before.Revision,
                    () => broker.Object.PlaceOrder(order));
                Assert.That(result, Is.EqualTo("SUBMITTED_PAPER"));
                broker.Verify(x => x.PlaceOrder(order), Times.Once);
                Console.WriteLine("TL001A_LEAN_PAPER phase=stable decision=SUBMITTED_PAPER " +
                    "snapshot=3 current=3 new_submissions=1");
            }
            else if (phase == "paper_concurrent")
            {
                Assert.That(before.Revision, Is.EqualTo(2));
                using var insideSubmit = new ManualResetEventSlim();
                using var releaseSubmit = new ManualResetEventSlim();
                using var correctionStarted = new ManualResetEventSlim();
                var submission = Task.Run(() => source.SubmitIfCurrent(before.Revision,
                    () =>
                    {
                        insideSubmit.Set();
                        if (!releaseSubmit.Wait(TimeSpan.FromSeconds(10)))
                            throw new TimeoutException("paper submission release");
                        return broker.Object.PlaceOrder(order);
                    }));
                Assert.That(insideSubmit.Wait(TimeSpan.FromSeconds(10)), Is.True);
                var correction = Task.Run(() =>
                {
                    correctionStarted.Set();
                    source.ApplyCorrection();
                });
                try
                {
                    Assert.That(correctionStarted.Wait(TimeSpan.FromSeconds(10)), Is.True);
                    Assert.That(correction.Wait(TimeSpan.FromMilliseconds(100)), Is.False,
                        "Correction must wait until paper submission exits the source gate");
                    Assert.That(TideLabAtomicSnapshotProbe.Read(path).Revision, Is.EqualTo(2));
                }
                finally { releaseSubmit.Set(); }
                Assert.That(submission.Result, Is.EqualTo("SUBMITTED_PAPER"));
                Assert.That(correction.Wait(TimeSpan.FromSeconds(10)), Is.True);
                Assert.That(source.ReadSnapshot().Revision, Is.EqualTo(3));
                broker.Verify(x => x.PlaceOrder(order), Times.Once);
                Console.WriteLine("TL001A_LEAN_PAPER phase=concurrent decision=SERIALIZED " +
                    "submit_revision=2 correction_revision=3 new_submissions=1");
            }
            else throw new ArgumentException(phase);
        }
    }
}
