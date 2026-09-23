// TideLab-authored, deterministic synthetic signal used by historical and forward probes.
namespace QuantConnect.Algorithm.CSharp
{
    public sealed class TideLabSyntheticSignal
    {
        private decimal _firstClose;
        public int Count { get; private set; }

        public bool OnClose(decimal close)
        {
            Count++;
            if (Count == 1) _firstClose = close;
            return Count == 3 && close > _firstClose;
        }
    }
}
