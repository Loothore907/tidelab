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
        private readonly TideLabH1V1Policy _v1 = new TideLabH1V1Policy();
        private readonly List<string> _decisions = new List<string>();
        private readonly List<string> _utcTimes = new List<string>();
        private readonly List<TideLabH1V1Bar> _v1Bars = new List<TideLabH1V1Bar>();
        private int _count;
        private bool _v1IsLong;

        public override void Initialize()
        {
            SetStartDate(2026, 1, 1);
            SetEndDate(2026, 1,
                Environment.GetEnvironmentVariable("TL_H1_V1_PROBE") == "1" ? 8 : 1);
            SetTimeZone(TimeZones.Utc);
            SetCash(Environment.GetEnvironmentVariable("TL_H1_V1_PROBE") == "1" ?
                10000 : 1000);
            _symbol = AddData<TideLabH1Bar>("TIDELABH1", Resolution.Hour).Symbol;
        }

        public override void OnData(Slice slice)
        {
            if (!slice.ContainsKey(_symbol)) return;
            _count++;
            _utcTimes.Add(UtcTime.ToString("yyyy-MM-ddTHH:mm:ss", CultureInfo.InvariantCulture));
            if (Environment.GetEnvironmentVariable("TL_H1_V1_ACCOUNTING") == "1")
            {
                var bar = (TideLabH1Bar)slice[_symbol];
                _v1Bars.Add(new TideLabH1V1Bar(UtcTime.AddHours(-1),
                    bar.Open, bar.Value, true));
                return;
            }
            if (Environment.GetEnvironmentVariable("TL_H1_V1_PROBE") == "1")
            {
                var v1Equity = Environment.GetEnvironmentVariable("TL_H1_V1_DRAWDOWN") == "1" &&
                    _count >= 170 ? 8000m : 10000m;
                var v1Decision = _v1.OnClosedHour(UtcTime, slice[_symbol].Value,
                    _v1IsLong, v1Equity, _v1IsLong ? 0.25m : 0m);
                if (v1Decision.Intent != TideLabH1V1Intent.Hold)
                    _decisions.Add($"{v1Decision.ClosedHours}:{v1Decision.Intent}:{v1Decision.Risk}");
                _v1IsLong = v1Decision.Intent switch
                {
                    TideLabH1V1Intent.EnterLong => true,
                    TideLabH1V1Intent.ExitToCash => false,
                    _ => _v1IsLong
                };
                return;
            }
            var scenario = Environment.GetEnvironmentVariable("TL001A_H1_SCENARIO");
            var equity = scenario == "drawdown" ? 940m : 1000m;
            var decision = _h1.OnClosedHour(slice[_symbol].Value, equity, 1000m);
            if (decision.Intent != TideLabH1Intent.None)
                _decisions.Add($"{decision.ClosedHour}:{decision.Intent}:{decision.Risk}");
        }

        public override void OnEndOfAlgorithm()
        {
            if (Environment.GetEnvironmentVariable("TL_H1_V1_ACCOUNTING") == "1")
            {
                var scoreStart = new DateTime(2026, 1, 8, 5, 0, 0, DateTimeKind.Utc);
                var scoreEnd = scoreStart.AddHours(2);
                var baseline = TideLabH1V1ResearchReplay.Run(_v1Bars,
                    scoreStart, scoreEnd, TideLabH1V1Cost.Base);
                var stress = TideLabH1V1ResearchReplay.Run(_v1Bars,
                    scoreStart, scoreEnd, TideLabH1V1Cost.Stress);
                if (_count != 171 || baseline.Fills.Count != 2 ||
                    baseline.Decisions.Count != 2 || baseline.Units != 0m ||
                    stress.Fills.Count != 2 || stress.Units != 0m ||
                    stress.Cash >= baseline.Cash)
                    throw new Exception("H1 v1 historical accounting differs");
                Log($"H1V1_ACCOUNTING clock=historical bars={_count} cash={baseline.Cash.ToString(CultureInfo.InvariantCulture)} fees={baseline.TotalFees.ToString(CultureInfo.InvariantCulture)} stress_cash={stress.Cash.ToString(CultureInfo.InvariantCulture)} fills=2 orders=0");
                return;
            }
            if (Environment.GetEnvironmentVariable("TL_H1_V1_PROBE") == "1")
            {
                var drawdown = Environment.GetEnvironmentVariable("TL_H1_V1_DRAWDOWN") == "1";
                var actual = string.Join("|", _decisions);
                var v1Expected = drawdown ?
                    "169:EnterLong:Clear|170:ExitToCash:DrawdownHalt" :
                    "169:EnterLong:Clear|170:ExitToCash:Clear|171:EnterLong:Clear";
                Log($"H1V1_OBSERVED bars={_count} decisions={actual} first={_utcTimes.FirstOrDefault()} last={_utcTimes.LastOrDefault()}");
                if (_count != 171 || actual != v1Expected ||
                    _utcTimes[0] != "2026-01-01T06:00:00" ||
                    _utcTimes[^1] != "2026-01-08T08:00:00")
                    throw new Exception("H1 v1 historical decisions or UTC boundaries differ");
                Log($"H1V1_PARITY clock=historical drawdown={drawdown} bars={_count} decisions={actual} orders=0");
                return;
            }
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
        public decimal Open { get; set; }
        public override DateTime EndTime
        {
            get => Time.AddHours(1);
            set => Time = value.AddHours(-1);
        }

        public override SubscriptionDataSource GetSource(
            SubscriptionDataConfig config, DateTime date, bool isLiveMode) =>
            new SubscriptionDataSource(Path.Combine(Globals.DataFolder,
                Environment.GetEnvironmentVariable("TL_H1_V1_PROBE") == "1" ?
                    "tidelab_h1_v1" : "tidelab_h1",
                date.ToString("yyyyMMdd", CultureInfo.InvariantCulture) +
                ".csv"), SubscriptionTransportMedium.LocalFile, FileFormat.Csv);

        public override BaseData Reader(SubscriptionDataConfig config, string line,
            DateTime date, bool isLiveMode)
        {
            var fields = line.Split(',');
            var close = decimal.Parse(fields[1], CultureInfo.InvariantCulture);
            return new TideLabH1Bar
            {
                Symbol = config.Symbol,
                // LEAN interprets this custom subscription in New York time.
                // Convert the fixture's UTC bar start into that local clock first.
                Time = DateTime.ParseExact(fields[0], "yyyy-MM-dd HH:mm:ss",
                    CultureInfo.InvariantCulture).ConvertFromUtc(TimeZones.NewYork),
                Value = close,
                Open = fields.Length > 2 ?
                    decimal.Parse(fields[2], CultureInfo.InvariantCulture) : close
            };
        }
    }
}
