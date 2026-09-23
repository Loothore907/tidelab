// TideLab-authored historical H1 decision probe; no order is submitted.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using QuantConnect.Data;

namespace QuantConnect.Algorithm.CSharp
{
    public class TideLabH1ProbeAlgorithm : QCAlgorithm
    {
        private Symbol _symbol;
        private readonly TideLabH1Skeleton _h1 = new TideLabH1Skeleton();
        private readonly List<string> _decisions = new List<string>();
        private readonly List<string> _utcTimes = new List<string>();
        private int _count;

        public override void Initialize()
        {
            SetStartDate(2026, 1, 1);
            SetEndDate(2026, 1, 1);
            SetTimeZone(TimeZones.Utc);
            SetCash(1000);
            _symbol = AddData<TideLabH1Bar>("TIDELABH1", Resolution.Hour).Symbol;
        }

        public override void OnData(Slice slice)
        {
            if (!slice.ContainsKey(_symbol)) return;
            _count++;
            _utcTimes.Add(UtcTime.ToString("yyyy-MM-ddTHH:mm:ss", CultureInfo.InvariantCulture));
            var scenario = Environment.GetEnvironmentVariable("TL001A_H1_SCENARIO");
            var equity = scenario == "drawdown" ? 940m : 1000m;
            var decision = _h1.OnClosedHour(slice[_symbol].Value, equity, 1000m);
            if (decision.Intent != TideLabH1Intent.None)
                _decisions.Add($"{decision.ClosedHour}:{decision.Intent}:{decision.Risk}");
        }

        public override void OnEndOfAlgorithm()
        {
            var scenario = Environment.GetEnvironmentVariable("TL001A_H1_SCENARIO");
            var result = string.Join("|", _decisions);
            Log($"TL001A_H1_PARITY clock=historical scenario={scenario} bars={_count} decisions={result} utc_times={string.Join(",", _utcTimes)}");
            var expected = scenario == "drawdown" ?
                "3:EnterLong:BlockDrawdown|4:ExitToCash:Approve" :
                "3:EnterLong:Approve|4:ExitToCash:Approve";
            var expectedTimes = Enumerable.Range(6, 4).Select(hour =>
                $"2026-01-01T{hour:00}:00:00");
            if (_count != 4 || result != expected ||
                !_utcTimes.SequenceEqual(expectedTimes))
                throw new Exception("Synthetic H1 historical decisions differ");
        }
    }

    public class TideLabH1Bar : BaseData
    {
        public override DateTime EndTime
        {
            get => Time.AddHours(1);
            set => Time = value.AddHours(-1);
        }

        public override SubscriptionDataSource GetSource(
            SubscriptionDataConfig config, DateTime date, bool isLiveMode) =>
            new SubscriptionDataSource(Path.Combine(Globals.DataFolder,
                "tidelab_h1", date.ToString("yyyyMMdd", CultureInfo.InvariantCulture) +
                ".csv"), SubscriptionTransportMedium.LocalFile, FileFormat.Csv);

        public override BaseData Reader(SubscriptionDataConfig config, string line,
            DateTime date, bool isLiveMode)
        {
            var fields = line.Split(',');
            return new TideLabH1Bar
            {
                Symbol = config.Symbol,
                // LEAN interprets this custom subscription in New York time.
                // Convert the fixture's UTC bar start into that local clock first.
                Time = DateTime.ParseExact(fields[0], "yyyy-MM-dd HH:mm:ss",
                    CultureInfo.InvariantCulture).ConvertFromUtc(TimeZones.NewYork),
                Value = decimal.Parse(fields[1], CultureInfo.InvariantCulture)
            };
        }
    }
}
