// TideLab-authored synthetic cost/fill probe for pinned LEAN. No market data or broker connection.
using System;
using System.Linq;
using NUnit.Framework;
using QuantConnect;
using QuantConnect.Data;
using QuantConnect.Data.Auxiliary;
using QuantConnect.Data.Market;
using QuantConnect.Orders;
using QuantConnect.Orders.Fees;
using QuantConnect.Orders.Fills;
using QuantConnect.Orders.Slippage;
using QuantConnect.Securities;
using QuantConnect.Securities.Equity;
using QuantConnect.Tests.Common.Data;
using QuantConnect.Tests.Common.Securities;

namespace QuantConnect.Tests.Engine.Setup
{
    public static class TideLabCostFillProbe
    {
        public static void Run()
        {
            var symbol = Symbol.Create("TL001ASYN", SecurityType.Equity, Market.USA);
            var localTime = new DateTime(2014, 6, 24, 12, 0, 0);
            var orderTime = localTime.ConvertToUtc(TimeZones.NewYork);
            var keeper = new TimeKeeper(orderTime, new[] { TimeZones.NewYork });
            var tradeConfig = new SubscriptionDataConfig(typeof(TradeBar), symbol,
                Resolution.Minute, TimeZones.NewYork, TimeZones.NewYork, true, true, false);
            var quoteConfig = new SubscriptionDataConfig(tradeConfig, typeof(QuoteBar));
            var provider = new MockSubscriptionDataConfigProvider(quoteConfig);
            provider.SubscriptionDataConfigs.Add(tradeConfig);
            var equity = new Equity(
                SecurityExchangeHoursTests.CreateUsEquitySecurityExchangeHours(),
                tradeConfig, new Cash(Currencies.USD, 0, 1m),
                SymbolProperties.GetDefault(Currencies.USD),
                ErrorCurrencyConverter.Instance,
                RegisteredSecurityDataTypesProvider.Null, Exchange.ARCA);
            equity.SetLocalTimeKeeper(keeper.GetLocalTimeKeeper(TimeZones.NewYork));
            equity.SetSlippageModel(new ConstantSlippageModel(0.001m));
            var order = new MarketOrder(symbol, 1m, orderTime);
            var quoteTime = localTime.AddMinutes(-1);
            equity.SetMarketPrice(new QuoteBar(quoteTime, symbol,
                new Bar(100m, 100m, 100m, 100m), 0.4m,
                new Bar(100.20m, 100.20m, 100.20m, 100.20m), 0.4m));
            equity.SetMarketPrice(new TradeBar(quoteTime, symbol,
                100.10m, 100.20m, 100m, 100.10m, 1m));

            var fill = new EquityFillModel().Fill(new FillModelParameters(
                equity, order, provider, Time.OneHour, null)).Single();
            var fee = new ConstantFeeModel(0.1003001m).GetOrderFee(
                new OrderFeeParameters(equity, order)).Value;

            Assert.That(fill.Status, Is.EqualTo(OrderStatus.Filled));
            Assert.That(fill.FillQuantity, Is.EqualTo(1m));
            Assert.That(fill.FillPrice, Is.EqualTo(100.3001m));
            Assert.That(fee.Amount, Is.EqualTo(0.1003001m));
            Assert.That(fee.Currency, Is.EqualTo(Currencies.USD));
            Assert.That(fill.FillQuantity, Is.GreaterThan(0.4m));
            Console.WriteLine("TL001A_LEAN_COST_FILL bid=100 ask=100.20 displayed_ask=0.4 " +
                $"order=1 slippage=0.1pct fill={fill.FillQuantity}@{fill.FillPrice} " +
                $"fee={fee.Amount} fee_model=constant decision=HOLD_OPTIMISTIC_FULL_FILL");
        }
    }
}
