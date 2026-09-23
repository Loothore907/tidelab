// TideLab-authored synthetic adapter protocol probe; not a live brokerage adapter.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace QuantConnect.Tests.Engine.Setup
{
    public sealed record TideLabBrokerExecution(string Id, decimal Quantity,
        decimal Price, decimal Fee);

    public sealed record TideLabBrokerSnapshot(int Revision, string BrokerId,
        decimal StartingCash, decimal StartingHolding, decimal OrderQuantity,
        decimal Cash, decimal Holding, IReadOnlyList<TideLabBrokerExecution> Executions);

    public sealed record TideLabEngineSnapshot(decimal Cash, decimal Holding,
        int OpenOrders, string OpenBrokerId);

    // Broker-native execution IDs stay on this side of LEAN OrderEvent conversion.
    public interface ITideLabBrokerExecutionSource
    {
        TideLabBrokerSnapshot Read();
        string Commit(TideLabBrokerExecution execution);
    }

    public interface ITideLabEngineExecutionPort
    {
        TideLabEngineSnapshot Read();
        void Deliver(TideLabBrokerExecution execution, bool finalFill);
    }

    public sealed class TideLabDelegateEnginePort : ITideLabEngineExecutionPort
    {
        private readonly Func<TideLabEngineSnapshot> _read;
        private readonly Action<TideLabBrokerExecution, bool> _deliver;

        public TideLabDelegateEnginePort(Func<TideLabEngineSnapshot> read,
            Action<TideLabBrokerExecution, bool> deliver)
        {
            _read = read;
            _deliver = deliver;
        }

        public TideLabEngineSnapshot Read() => _read();
        public void Deliver(TideLabBrokerExecution execution, bool finalFill) =>
            _deliver(execution, finalFill);
    }

    public static class TideLabExecutionDeliveryProbe
    {
        // The caller must hold submissions on every BLOCK result. This probe
        // handles one next execution at a time and never retries an order.
        public static string Reconcile(ITideLabBrokerExecutionSource source,
            ITideLabEngineExecutionPort engine, string executionId)
        {
            var broker = source.Read();
            var index = broker.Executions.ToList().FindIndex(x => x.Id == executionId);
            if (index < 0) return "BLOCK_UNREPORTED";
            if (index != broker.Executions.Count - 1) return "BLOCK_SEQUENCE";

            var execution = broker.Executions[index];
            var before = Expected(broker, index);
            var after = Expected(broker, index + 1);
            var observed = engine.Read();
            if (observed != before && observed != after)
                return "BLOCK_ENGINE_MISMATCH";

            var commit = source.Commit(execution);
            if (commit != "DELIVER_AFTER_COMMIT" && commit != "SUPPRESS_COMMITTED")
                return commit;

            if (observed == after) return "ALREADY_APPLIED";
            try
            {
                engine.Deliver(execution, after.OpenOrders == 0);
            }
            catch (IOException)
            {
                return "BLOCK_DELIVERY_INTERRUPTED";
            }

            // An acknowledgement alone cannot prove the running engine applied
            // the event. Compare the account and order state after delivery.
            if (engine.Read() != after) return "BLOCK_ENGINE_MISMATCH";
            var latest = source.Read();
            if (latest.Revision != broker.Revision || latest.BrokerId != broker.BrokerId ||
                latest.Cash != broker.Cash || latest.Holding != broker.Holding ||
                latest.Executions.Count != broker.Executions.Count ||
                latest.Executions.Last() != execution)
                return "BLOCK_REPORT_CHANGED";
            return commit == "SUPPRESS_COMMITTED" ?
                "APPLIED_FROM_COMMITTED" : "APPLIED_AFTER_COMMIT";
        }

        private static TideLabEngineSnapshot Expected(TideLabBrokerSnapshot broker,
            int executionCount)
        {
            var executions = broker.Executions.Take(executionCount);
            var holding = broker.StartingHolding + executions.Sum(x => x.Quantity);
            var cash = broker.StartingCash - executions.Sum(
                x => x.Quantity * x.Price + x.Fee);
            return new TideLabEngineSnapshot(cash, holding,
                holding < broker.OrderQuantity ? 1 : 0,
                holding < broker.OrderQuantity ? broker.BrokerId : null);
        }
    }
}
