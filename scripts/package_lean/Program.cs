// TideLab-authored synthetic adapter. Uses public LEAN APIs; no upstream patches.
using System.Globalization;
using System.Text.Json;
using QuantConnect;
using QuantConnect.Algorithm;
using QuantConnect.Brokerages;
using QuantConnect.Brokerages.Backtesting;
using QuantConnect.Configuration;
using QuantConnect.Data.Market;
using QuantConnect.Lean.Engine.DataFeeds;
using QuantConnect.Lean.Engine.Results;
using QuantConnect.Lean.Engine.TransactionHandlers;
using QuantConnect.Orders;
using QuantConnect.Orders.Fees;
using QuantConnect.Orders.Fills;
using QuantConnect.Securities;

CultureInfo.CurrentCulture = CultureInfo.InvariantCulture;
if (args.Length != 3) throw new ArgumentException("input.json output.json pinned-LEAN-Data-folder");
Config.Set("data-folder", Path.GetFullPath(args[2]));
using var document = JsonDocument.Parse(File.ReadAllBytes(args[0]));
var input = document.RootElement;
var algorithm = new PackageAlgorithm();
var result = algorithm.Replay(input);
using var output = new FileStream(args[1], FileMode.CreateNew);
JsonSerializer.Serialize(output, result, new JsonSerializerOptions { WriteIndented = true });
Console.WriteLine("TIDELAB_PACKAGE_LEAN_COMPLETED");

sealed class SyntheticFill(decimal adverse) : FillModel
{
    public override OrderEvent MarketFill(Security asset, MarketOrder order) =>
        new(order, asset.LocalTime.ConvertToUtc(asset.Exchange.TimeZone), OrderFee.Zero)
        {
            Status = OrderStatus.Filled,
            FillQuantity = order.Quantity,
            FillPrice = asset.Price * (order.Quantity > 0 ? 1 + adverse : 1 - adverse)
        };
}

sealed class SyntheticFee(decimal rate, decimal adverse) : FeeModel
{
    public override OrderFee GetOrderFee(OrderFeeParameters parameters)
    {
        var quantity = parameters.Order.Quantity;
        var price = parameters.Security.Price * (quantity > 0 ? 1 + adverse : 1 - adverse);
        return new OrderFee(new CashAmount(Math.Abs(quantity) * price * rate, "USD"));
    }
}

sealed class PackageAlgorithm : QCAlgorithm
{
    private readonly List<OrderEvent> _filled = new();
    public override void OnOrderEvent(OrderEvent orderEvent)
    {
        if (orderEvent.Status == OrderStatus.Filled) _filled.Add(orderEvent.Clone());
        else if (orderEvent.Status != OrderStatus.Submitted && orderEvent.Status != OrderStatus.New)
            throw new InvalidOperationException($"Unexpected order status: {orderEvent.Status}");
    }

    private static decimal D(JsonElement node) => decimal.Parse(node.GetString()!, CultureInfo.InvariantCulture);
    private static string S(decimal value) => value.ToString(CultureInfo.InvariantCulture);
    private static string U(DateTime value) => value.ToString("yyyy-MM-dd'T'HH:mm:ss'Z'", CultureInfo.InvariantCulture);

    private static int Warmup(JsonElement node)
    {
        var op = node.GetProperty("op").GetString();
        return op switch
        {
            "number" => 1,
            "close" => node.GetProperty("lag").GetInt32() + 1,
            "sma" => node.GetProperty("lag").GetInt32() + node.GetProperty("window").GetInt32(),
            "gt" or "lt" => Math.Max(Warmup(node.GetProperty("left")), Warmup(node.GetProperty("right"))),
            "and" or "or" => node.GetProperty("args").EnumerateArray().Max(Warmup),
            "not" => Warmup(node.GetProperty("arg")),
            _ => throw new ArgumentException("Unsupported package operator")
        };
    }

    private static decimal Number(JsonElement node, List<decimal> closes)
    {
        var op = node.GetProperty("op").GetString();
        if (op == "number") return D(node.GetProperty("value"));
        var end = closes.Count - node.GetProperty("lag").GetInt32();
        return op switch
        {
            "close" => closes[end - 1],
            "sma" => closes.Skip(end - node.GetProperty("window").GetInt32())
                .Take(node.GetProperty("window").GetInt32()).Sum() / node.GetProperty("window").GetInt32(),
            _ => throw new ArgumentException("Unsupported numeric operator")
        };
    }

    private static bool Predicate(JsonElement node, List<decimal> closes) => node.GetProperty("op").GetString() switch
    {
        "gt" => Number(node.GetProperty("left"), closes) > Number(node.GetProperty("right"), closes),
        "lt" => Number(node.GetProperty("left"), closes) < Number(node.GetProperty("right"), closes),
        "and" => node.GetProperty("args").EnumerateArray().All(arg => Predicate(arg, closes)),
        "or" => node.GetProperty("args").EnumerateArray().Any(arg => Predicate(arg, closes)),
        "not" => !Predicate(node.GetProperty("arg"), closes),
        _ => throw new ArgumentException("Unsupported predicate")
    };

    public object Replay(JsonElement input)
    {
        var rule = input.GetProperty("package").GetProperty("rule");
        var entryRule = rule.GetProperty("entry");
        var exitRule = rule.GetProperty("exit");
        var fraction = D(rule.GetProperty("target_fraction"));
        var warmup = Math.Max(Warmup(entryRule), Warmup(exitRule));
        var costs = input.GetProperty("cost");
        var initial = D(costs.GetProperty("initial_cash"));
        var feeRate = D(costs.GetProperty("fee_rate"));
        var adverse = D(costs.GetProperty("adverse_rate"));
        var unit = D(costs.GetProperty("quantity_unit"));
        var scoreStart = input.TryGetProperty("score_start", out var score) ? score.GetInt32() : 0;
        var bars = input.GetProperty("fixture").GetProperty("bars").EnumerateArray().ToArray();

        SetTimeZone(TimeZones.Utc);
        SetAccountCurrency("USD");
        SetCash(initial);
        SetBrokerageModel(BrokerageName.Default, AccountType.Cash);
        Settings.FreePortfolioValuePercentage = 0m;
        // Only static engine metadata is read. This invented instrument has explicit rules.
        const string ticker = "TLUSD";
        MarketHoursDatabase.SetEntryAlwaysOpen(Market.Coinbase, ticker, SecurityType.Crypto, TimeZones.Utc);
        SymbolPropertiesDatabase.SetEntry(Market.Coinbase, ticker, SecurityType.Crypto,
            new SymbolProperties("TideLab synthetic", "USD", 1m, unit, unit, ticker));
        var service = new SecurityService(Portfolio.CashBook, MarketHoursDatabase,
            SymbolPropertiesDatabase, this, RegisteredSecurityDataTypesProvider.Null,
            new SecurityCacheProvider(Portfolio), algorithm: this);
        var permissions = new DataPermissionManager();
        using var provider = new DefaultDataProvider();
        var selection = new UniverseSelection(this, service, permissions, provider);
        // Throw on any request to subscribe/fetch: the harness owns all invented events.
        var manager = new DataManager(new NullDataFeed(), selection, this,
            new TimeKeeper(DateTime.UtcNow, TimeZones.Utc), MarketHoursDatabase, false,
            RegisteredSecurityDataTypesProvider.Null, permissions);
        Securities.SetSecurityService(service);
        SubscriptionManager.SetDataManager(manager);
        var security = AddCrypto(ticker, Resolution.Tick, Market.Coinbase);
        security.SetFillModel(new SyntheticFill(adverse));
        security.SetFeeModel(new SyntheticFee(feeRate, adverse));
        SetFinishedWarmingUp();

        using var brokerage = new BacktestingBrokerage(this);
        var transactions = new BacktestingTransactionHandler();
        transactions.Initialize(this, brokerage, new BacktestingResultHandler());
        Transactions.SetOrderProcessor(transactions);
        var traces = new List<object>();
        var closes = new List<decimal>();
        string? pending = null;
        decimal budget = 0;
        try
        {
            for (var index = 0; index < bars.Length; index++)
            {
                var bar = bars[index];
                var start = DateTime.Parse(bar.GetProperty("start_utc").GetString()!,
                    CultureInfo.InvariantCulture, DateTimeStyles.AdjustToUniversal | DateTimeStyles.AssumeUniversal);
                var opening = D(bar.GetProperty("open"));
                var close = D(bar.GetProperty("close"));
                SetDateTime(start);
                security.SetMarketPrice(new Tick(start, security.Symbol, opening, opening));
                Portfolio.CashBook["TL"].CurrencyConversion.ConversionRate = opening;
                object? fillTrace = null;
                if (pending != null)
                {
                    var quantity = pending == "sell" ? -security.Holdings.Quantity :
                        decimal.Floor(Math.Min(budget, Portfolio.CashBook["USD"].Amount) /
                            (opening * (1 + adverse) * (1 + feeRate)) / unit) * unit;
                    if (quantity == 0) throw new InvalidOperationException("Target below executable unit");
                    var before = _filled.Count;
                    var ticket = MarketOrder(security.Symbol, quantity, asynchronous: true);
                    transactions.ProcessSynchronousEvents();
                    if (ticket.Status != OrderStatus.Filled || _filled.Count != before + 1)
                        throw new InvalidOperationException($"LEAN did not fill exactly once: {ticket.Status}; {ticket.GetMostRecentOrderResponse()}");
                    var fill = _filled[^1];
                    fillTrace = new { index, utc = U(fill.UtcTime), side = pending,
                        quantity = S(Math.Abs(fill.FillQuantity)), price = S(fill.FillPrice),
                        fee = S(fill.OrderFee.Value.Amount) };
                    pending = null;
                }
                SetDateTime(start.AddHours(1));
                security.SetMarketPrice(new Tick(start.AddHours(1), security.Symbol, close, close));
                Portfolio.CashBook["TL"].CurrencyConversion.ConversionRate = close;
                closes.Add(close);
                bool? entry = null, exit = null;
                var action = "hold";
                if (index >= scoreStart && closes.Count >= warmup && index != bars.Length - 1)
                {
                    entry = Predicate(entryRule, closes);
                    exit = Predicate(exitRule, closes);
                    if (security.Holdings.Quantity > 0 && exit.Value) pending = "sell";
                    else if (security.Holdings.Quantity == 0 && entry.Value)
                    {
                        pending = "buy";
                        budget = Portfolio.CashBook["USD"].Amount * fraction;
                    }
                    action = pending ?? "hold";
                }
                if (Portfolio.CashBook["USD"].Amount < 0 || security.Holdings.Quantity < 0)
                    throw new InvalidOperationException("Negative cash or holdings");
                if (index >= scoreStart) traces.Add(new { index, close_utc = U(UtcTime), entry, exit, action, fill = fillTrace,
                    cash = S(Portfolio.CashBook["USD"].Amount), units = S(security.Holdings.Quantity),
                    equity = S(Portfolio.TotalPortfolioValue) });
            }
            if (Transactions.GetOpenOrders().Count != 0 || ErrorMessages.Count != 0)
                throw new InvalidOperationException("LEAN retained open orders or reported errors: " + string.Join("; ", ErrorMessages));
            return new { trace = traces, order_count = Transactions.OrdersCount, fill_count = _filled.Count };
        }
        finally { transactions.Exit(); }
    }
}
