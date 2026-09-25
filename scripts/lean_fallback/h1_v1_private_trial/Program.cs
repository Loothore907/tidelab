// Private H1 development/validation replay. Input and results remain under ignored data/.
using System.Buffers.Binary;
using System.Diagnostics;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using QuantConnect.Algorithm.CSharp;

static void Require(bool condition, string message)
{
    if (!condition) throw new ArgumentException(message);
}

static string Hash(byte[] bytes) => Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();

static string PrivatePath(string root, string value)
{
    var path = Path.GetFullPath(value);
    var data = Path.GetFullPath(Path.Combine(root, "data")) + Path.DirectorySeparatorChar;
    Require(path.StartsWith(data, StringComparison.Ordinal),
        "Private H1 paths must remain under ignored data/");
    return path;
}

static string Git(string root, params string[] arguments)
{
    var start = new ProcessStartInfo("git") { WorkingDirectory = root,
        RedirectStandardOutput = true, RedirectStandardError = true,
        UseShellExecute = false };
    foreach (var argument in arguments) start.ArgumentList.Add(argument);
    using var process = Process.Start(start) ?? throw new InvalidOperationException("git unavailable");
    var output = process.StandardOutput.ReadToEnd().Trim();
    process.WaitForExit();
    Require(process.ExitCode == 0, "git revision check failed");
    return output;
}

static string CostHash(string root)
{
    using var hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
    foreach (var name in new[] { "TideLabH1V1ResearchReplay.cs",
             "TideLabH1ConservativeExecution.cs", "TideLabH1V1TrialAccounting.cs" })
    {
        var bytes = File.ReadAllBytes(Path.Combine(root, "scripts", "lean_fallback", name));
        hash.AppendData(Encoding.UTF8.GetBytes(name + "\0"));
        var length = new byte[8];
        BinaryPrimitives.WriteUInt64BigEndian(length, (ulong)bytes.Length);
        hash.AppendData(length);
        hash.AppendData(bytes);
    }
    return Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant();
}

static DateTime Utc(string? value)
{
    Require(value is not null && value.EndsWith('Z'), "H1 time must have a UTC Z suffix");
    var result = DateTime.Parse(value!, CultureInfo.InvariantCulture,
        DateTimeStyles.RoundtripKind);
    Require(result.Kind == DateTimeKind.Utc, "H1 time must be UTC");
    return result;
}

static decimal Number(string? value) => decimal.Parse(value!,
    NumberStyles.Number, CultureInfo.InvariantCulture);

if (args.Length != 4)
    throw new ArgumentException("usage: H1V1PrivateTrial <input> <source-manifest> <identity> <output>");
var root = Directory.GetCurrentDirectory();
var inputPath = PrivatePath(root, args[0]);
var sourcePath = PrivatePath(root, args[1]);
var identityPath = PrivatePath(root, args[2]);
var outputPath = PrivatePath(root, args[3]);
Require(!File.Exists(outputPath), "Private H1 result already exists");
Require(Git(root, "branch", "--show-current") == "main" &&
    // WSL reading a Windows checkout otherwise reports every CRLF file as edited.
    Git(root, "-c", "core.autocrlf=true", "status", "--porcelain") == "",
    "Private H1 run needs clean integrated main");

var inputBytes = File.ReadAllBytes(inputPath);
var sourceBytes = File.ReadAllBytes(sourcePath);
using var identity = JsonDocument.Parse(File.ReadAllBytes(identityPath));
using var source = JsonDocument.Parse(sourceBytes);
using var input = JsonDocument.Parse(inputBytes);
var id = identity.RootElement;
var manifest = source.RootElement;
var fixture = input.RootElement;
Require(id.GetProperty("code").GetProperty("revision").GetString() == Git(root, "rev-parse", "HEAD") &&
    Git(root, "rev-parse", "HEAD") == Git(root, "rev-parse", "origin/main"),
    "H1 identity does not match integrated code");
Require(id.GetProperty("engine").GetProperty("source_revision").GetString() ==
    "88bce0fc6fe282378ee73c54cef1090d0d7a73ee", "H1 engine pin differs");
Require(id.GetProperty("configuration").GetProperty("sha256").GetString() == Hash(
    File.ReadAllBytes(Path.Combine(root, "docs", "experiments", "H1-V1-PREREGISTRATION.md"))),
    "Frozen H1 specification hash differs");
Require(id.GetProperty("cost").GetProperty("sha256").GetString() == CostHash(root),
    "H1 cost and accounting source hash differs");
Require(id.GetProperty("data").GetProperty("sha256").GetString() == Hash(sourceBytes) &&
    manifest.GetProperty("input_sha256").GetString() == Hash(inputBytes),
    "H1 source manifest or bar input hash differs");
Require(id.GetProperty("data").GetProperty("source_id").GetString() ==
    "okx.historical_archive.candlesticks.1m" &&
    id.GetProperty("data").GetProperty("kind").GetString() == "third_party" &&
    manifest.GetProperty("source_id").GetString() ==
    "okx.historical_archive.candlesticks.1m" &&
    manifest.GetProperty("instrument_id").GetString() == "okx:BTC-USDT" &&
    manifest.GetProperty("coverage_bars").GetInt32() == 28344 &&
    manifest.GetProperty("archives").GetArrayLength() == 61 &&
    manifest.GetProperty("terms_url").GetString() ==
    "https://www.okx.com/en-us/help/historicaldata-terms-and-conditions" &&
    manifest.GetProperty("us_terms_url").GetString() ==
    "https://www.okx.com/en-us/help/terms-of-service-us" &&
    manifest.GetProperty("us_terms_last_updated").GetString() == "2026-09-16" &&
    manifest.GetProperty("terms_reviewed_utc_date").GetString() ==
    DateTime.UtcNow.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture),
    "Selected OKX source or current personal-use terms review differs");
var phase = fixture.GetProperty("phase").GetString();
Require((phase == "development" || phase == "validation") &&
    manifest.GetProperty("phase").GetString() == phase &&
    id.GetProperty("trial").GetProperty("trial_id").GetString() ==
    $"h1-v1-okx-btc-usdt-{phase}", "Only registered development or validation is available");
var scoreStart = Utc(fixture.GetProperty("score_start_utc").GetString());
var scoreEnd = Utc(fixture.GetProperty("score_end_utc").GetString());
var expectedStart = phase == "development" ?
    new DateTime(2023, 7, 7, 16, 0, 0, DateTimeKind.Utc) :
    new DateTime(2025, 1, 1, 0, 0, 0, DateTimeKind.Utc);
var expectedEnd = phase == "development" ?
    new DateTime(2025, 1, 1, 0, 0, 0, DateTimeKind.Utc) :
    new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc);
Require(scoreStart == expectedStart && scoreEnd == expectedEnd,
    "H1 scored partition differs from preregistration");
var bars = fixture.GetProperty("bars").EnumerateArray().Select(item =>
    new TideLabH1V1Bar(Utc(item.GetProperty("start_utc").GetString()),
        Number(item.GetProperty("open").GetString()),
        Number(item.GetProperty("close").GetString()),
        item.GetProperty("closed").GetBoolean())).ToArray();
Require(bars.Length == 168 + (int)(scoreEnd - scoreStart).TotalHours + 1,
    "H1 scored input length differs");

static TideLabH1V1ReplayResult ReplayTwice(TideLabH1V1Bar[] bars,
    DateTime start, DateTime end, TideLabH1V1Cost cost)
{
    var first = TideLabH1V1ResearchReplay.Run(bars, start, end, cost);
    var again = TideLabH1V1ResearchReplay.Run(bars, start, end, cost);
    Require(first.Cash == again.Cash && first.Units == again.Units &&
        first.TotalFees == again.TotalFees && first.Fills.SequenceEqual(again.Fills) &&
        first.Decisions.SequenceEqual(again.Decisions) &&
        first.Marks.SequenceEqual(again.Marks), "H1 identical replay differs");
    return first;
}

var baseReplay = ReplayTwice(bars, scoreStart, scoreEnd, TideLabH1V1Cost.Base);
var stressReplay = ReplayTwice(bars, scoreStart, scoreEnd, TideLabH1V1Cost.Stress);
var baseMetrics = TideLabH1V1TrialAccounting.Analyze(bars, scoreStart,
    baseReplay, TideLabH1V1Cost.Base);
var stressMetrics = TideLabH1V1TrialAccounting.Analyze(bars, scoreStart,
    stressReplay, TideLabH1V1Cost.Stress);
var options = new JsonSerializerOptions();
options.Converters.Add(new JsonStringEnumConverter());
var result = JsonSerializer.SerializeToUtf8Bytes(new {
    schema_version = 1, phase,
    identity_sha256 = id.GetProperty("identity_sha256").GetString(),
    input_sha256 = Hash(inputBytes), score_start_utc = scoreStart,
    score_end_utc = scoreEnd, base_replay = baseReplay,
    base_metrics = baseMetrics, stress_replay = stressReplay,
    stress_metrics = stressMetrics
}, options);
Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
using (var output = new FileStream(outputPath, FileMode.CreateNew, FileAccess.Write))
    output.Write(result);
Console.WriteLine($"H1_PRIVATE_{phase!.ToUpperInvariant()} status=complete result_sha256={Hash(result)}");
