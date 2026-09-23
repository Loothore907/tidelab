// TideLab-authored synthetic LEAN compatibility probe; no market data or orders.
using System;
using System.Globalization;
using System.IO;
using QuantConnect.Data;

namespace QuantConnect.Algorithm.CSharp
{
    public class TideLabSyntheticProbeAlgorithm : QCAlgorithm
    {
        private Symbol _symbol;
        private int _count;
        private decimal _sum;

        public override void Initialize()
        {
            SetStartDate(2026, 1, 1);
            SetEndDate(2026, 1, 3);
            SetTimeZone(TimeZones.Utc);
            SetCash(10000);
            _symbol = AddData<TideLabSyntheticBar>("TIDELAB", Resolution.Hour).Symbol;
        }

        public override void OnData(Slice slice)
        {
            if (!slice.ContainsKey(_symbol)) return;
            _count++;
            _sum += slice[_symbol].Value;
        }

        public override void OnEndOfAlgorithm()
        {
            Log($"TL001A_LEAN_SYNTHETIC count={_count} sum={_sum}");
            if (_count != 3 || _sum != 306m) throw new Exception("Synthetic fixture mismatch");
        }
    }

    public class TideLabSyntheticBar : BaseData
    {
        public override DateTime EndTime
        {
            get => Time.AddHours(1);
            set => Time = value.AddHours(-1);
        }

        public override SubscriptionDataSource GetSource(
            SubscriptionDataConfig config, DateTime date, bool isLiveMode)
        {
            var path = Path.Combine(
                Globals.DataFolder,
                "tidelab",
                date.ToString("yyyyMMdd", CultureInfo.InvariantCulture) + ".csv");
            return new SubscriptionDataSource(
                path, SubscriptionTransportMedium.LocalFile, FileFormat.Csv);
        }

        public override BaseData Reader(
            SubscriptionDataConfig config, string line, DateTime date, bool isLiveMode)
        {
            var fields = line.Split(',');
            return new TideLabSyntheticBar
            {
                Symbol = config.Symbol,
                Time = DateTime.ParseExact(
                    fields[0], "yyyy-MM-dd HH:mm:ss", CultureInfo.InvariantCulture),
                Value = decimal.Parse(fields[1], CultureInfo.InvariantCulture),
            };
        }
    }
}
