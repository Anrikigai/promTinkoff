#!/usr/bin/env python3
# pip install -i https://test.pypi.org/simple/ --extra-index-url=https://pypi.org/simple/ tinkoff-invest-openapi-client
# https://github.com/Awethon/open-api-python-client
# https://habr.com/ru/post/496722/
# https://tinkoffcreditsystems.github.io/invest-openapi/swagger-ui/

import time
import os
from math import floor
from openapi_client import openapi
from prometheus_client import Gauge
from prometheus_client import start_http_server


UPDATE_PERIOD = os.getenv('PROMTI_UPDATE', 600) # in seconds
LISTEN_PORT = os.getenv('PROMTI_PORT', 8848)

DEBUG_LEVEL = os.getenv('PROMTI_DEBUG', 0)

def LOGD(str):
    if int(DEBUG_LEVEL) > 0:
        print(str)

def init():
    global tinkoff_client

    TOKEN = os.getenv('TINVEST_TOKEN', '')
    tinkoff_client = openapi.api_client(TOKEN)

    return

def calc_in_currencies(currency, value, balance):
    if currency == "RUB":
        SumRUB = value * balance
        SumUSD = SumRUB / rateUSDRUB
        SumEUR = SumRUB / rateEURRUB
    elif currency == "USD":
        SumUSD = value * balance
        SumRUB = SumUSD * rateUSDRUB
        SumEUR = SumUSD / rateEURUSD
    elif currency == "EUR":
        SumEUR = value * balance
        SumRUB = SumEUR * rateEURRUB
        SumUSD = SumEUR * rateEURUSD
    else:
        SumRUB = 0
        SumUSD = 0
        SumEUR = 0
    return (SumRUB,SumUSD,SumEUR)

def main():
    global rateUSDRUB, rateEURRUB, rateEURUSD
    account_total = "_Total_"
    print("Starting http server")

    start_http_server(LISTEN_PORT)
    promItems = Gauge('tcs_item', 'Tinkoff portfolio items with total price', ['account','name','ticker','currency','type','balance_currency'])
    promYields = Gauge('tcs_yield', 'Tinkoff portfolio items with expected yield', ['account','name','ticker','currency','type','balance_currency'])
    promRates = Gauge('tcs_rate', 'USD/EUR rate', ['currency'])
    while True:
        tinkoff_accounts = tinkoff_client.user.user_accounts_get().payload.accounts
# [{'broker_account_id': '2046615619', 'broker_account_type': 'Tinkoff'}, {'broker_account_id': '2097503417', 'broker_account_type': 'TinkoffIis'}]
#
# Original:
# {'payload': {'accounts': [{'broker_account_id': '2046XXXXXX',
#                            'broker_account_type': 'Tinkoff'},
#                           {'broker_account_id': '2097XXXXXX',
#                            'broker_account_type': 'TinkoffIis'}]},
#  'status': 'Ok',
#  'tracking_id': 'ac81fccc34XXXXXX'}


#    promAccounts = Gauge('tcs_account', 'Tinkoff accounts', ['name'])

        rateUSDRUB = tinkoff_client.market.market_orderbook_get(depth=1,figi="BBG0013HGFT4").payload.last_price # ticker=USD000UTSTOM
        rateEURRUB = tinkoff_client.market.market_orderbook_get(depth=1,figi="BBG0013HJJ31").payload.last_price # ticker=EUR_RUB__TOM
        rateEURUSD = rateEURRUB / rateUSDRUB
        promRates.labels('USDRUB').set(rateUSDRUB)
        promRates.labels('EURRUB').set(rateEURRUB)
        promRates.labels('EURUSD').set(rateEURUSD)      

        # not good, but must be cleared - what if we've sold something and this asset was disappeared?
        # maybe we'd keep track of all assets (labels) and zero them...
        promItems._metrics.clear() 
        promYields._metrics.clear() 

        TotalSumRUB = 0
        TotalSumUSD = 0
        TotalSumEUR = 0
        TotalExpYieldRUB = 0
        TotalExpYieldUSD = 0
        TotalExpYieldEUR = 0

        # Value is in balance_currency (every asset is represented in 3 lines for RUB/USD/EUR balance)
        for account in tinkoff_accounts:
            print(f"account={account.broker_account_type}")
            pf = tinkoff_client.portfolio.portfolio_get(broker_account_id=account.broker_account_id)
# {'average_position_price': {'currency': 'USD', 'value': 34.83}, # Invested
#  'average_position_price_no_nkd': None,
#  'balance': 10.0,
#  'blocked': None,
#  'expected_yield': {'currency': 'USD', 'value': 119.2}, # add yield to get the current position
#  'figi': 'BBG000BR2B91',
#  'instrument_type': 'Stock',
#  'isin': 'US7170811035',
#  'lots': 10,
#  'name': 'Pfizer',
#  'ticker': 'PFE'}
            for position in pf.payload.positions:
                (SumRUB,SumUSD,SumEUR) = calc_in_currencies(position.average_position_price.currency, position.average_position_price.value, position.balance)
                (YieldRUB,YieldUSD,YieldEUR) = calc_in_currencies(position.expected_yield.currency, position.expected_yield.value, 1)
                TotalSumRUB += SumRUB
                TotalSumUSD += SumUSD
                TotalSumEUR += SumEUR
                TotalExpYieldRUB += YieldRUB
                TotalExpYieldUSD += YieldUSD
                TotalExpYieldEUR += YieldEUR

                # for better portfolio diversification visibility
                if position.ticker == "USD000UTSTOM":
                    position.average_position_price.currency = "USD"
                elif position.ticker == "EUR_RUB__TOM":
                    position.average_position_price.currency = "EUR"

                LOGD(f"account={account.broker_account_type}, name={position.name}, ticker={position.ticker}, \
currency={position.average_position_price.currency}, type={position.instrument_type}, \
balance={position.balance}, lots={position.lots}, value={position.average_position_price.value} \
Sum: {SumRUB:.0f} {SumUSD:.0f} {SumEUR:.0f} Yield: {YieldRUB:.0f} {YieldUSD:.0f} {YieldEUR:.0f}")

                promItems.labels(account=account.broker_account_type,name=position.name,ticker=position.ticker, 
                    currency=position.average_position_price.currency,type=position.instrument_type,balance_currency="RUB").set(SumRUB)
                promItems.labels(account=account.broker_account_type,name=position.name,ticker=position.ticker, 
                    currency=position.average_position_price.currency,type=position.instrument_type,balance_currency="USD").set(SumUSD)
                promItems.labels(account=account.broker_account_type,name=position.name,ticker=position.ticker, 
                    currency=position.average_position_price.currency,type=position.instrument_type,balance_currency="EUR").set(SumEUR)

                promYields.labels(account=account.broker_account_type,name=position.name,ticker=position.ticker, 
                    currency=position.average_position_price.currency,type=position.instrument_type,balance_currency="RUB").set(YieldRUB)
                promYields.labels(account=account.broker_account_type,name=position.name,ticker=position.ticker, 
                    currency=position.average_position_price.currency,type=position.instrument_type,balance_currency="USD").set(YieldUSD)
                promYields.labels(account=account.broker_account_type,name=position.name,ticker=position.ticker, 
                    currency=position.average_position_price.currency,type=position.instrument_type,balance_currency="EUR").set(YieldEUR)

            pf = tinkoff_client.portfolio.portfolio_currencies_get(broker_account_id=account.broker_account_id)
            for position in pf.payload.currencies:
                if position.currency == "RUB":
                    (SumRUB,SumUSD,SumEUR) = calc_in_currencies(position.currency, 1, position.balance)
                    TotalSumRUB += SumRUB
                    TotalSumUSD += SumUSD
                    TotalSumEUR += SumEUR
                    position_name = "Рубль"
                    position_ticker = "RUBRUB"
                    instrument_type = "Currency"
                    rate_value = 1
                    position_currency = "RUB"
                    LOGD(f"account={account.broker_account_type}, name={position_name}, ticker={position_ticker}, \
currency={position.currency}, type={instrument_type}, \
balance={position.balance}, lots={floor(position.balance / 1000)}, value={rate_value} \
Sum: {SumRUB:.0f} {SumUSD:.0f} {SumEUR:.0f} Yield: {YieldRUB:.0f} {YieldUSD:.0f} {YieldEUR:.0f}")

                    promItems.labels(account=account.broker_account_type,name=position_name,ticker=position_ticker, 
                        currency=position_currency,type=instrument_type,balance_currency="RUB").set(SumRUB)
                    promItems.labels(account=account.broker_account_type,name=position_name,ticker=position_ticker, 
                        currency=position_currency,type=instrument_type,balance_currency="USD").set(SumUSD)
                    promItems.labels(account=account.broker_account_type,name=position_name,ticker=position_ticker, 
                        currency=position_currency,type=instrument_type,balance_currency="EUR").set(SumEUR)

                    promYields.labels(account=account.broker_account_type,name=position_name,ticker=position_ticker, 
                        currency=position_currency,type=instrument_type,balance_currency="RUB").set(0)
                    promYields.labels(account=account.broker_account_type,name=position_name,ticker=position_ticker, 
                        currency=position_currency,type=instrument_type,balance_currency="USD").set(0)
                    promYields.labels(account=account.broker_account_type,name=position_name,ticker=position_ticker, 
                        currency=position_currency,type=instrument_type,balance_currency="EUR").set(0)

        LOGD(f"Total: {TotalSumRUB:.0f} {TotalSumUSD:.0f} {TotalSumEUR:.0f} yield: {TotalExpYieldRUB:.0f} {TotalExpYieldUSD:.0f} {TotalExpYieldEUR:.0f}\n")
        # TotalSum = invested; TotalSum + TotalExpYield = Current position
        promItems.labels(account=account_total,name=account_total,ticker=account_total, 
            currency="Multi",type=account_total,balance_currency="RUB").set(TotalSumRUB)
        promItems.labels(account=account_total,name=account_total,ticker=account_total, 
            currency="Multi",type=account_total,balance_currency="USD").set(TotalSumUSD)
        promItems.labels(account=account_total,name=account_total,ticker=account_total, 
            currency="Multi",type=account_total,balance_currency="EUR").set(TotalSumEUR)
        promYields.labels(account=account_total,name=account_total,ticker=account_total, 
            currency="Multi",type=account_total,balance_currency="RUB").set(TotalExpYieldRUB)
        promYields.labels(account=account_total,name=account_total,ticker=account_total, 
            currency="Multi",type=account_total,balance_currency="USD").set(TotalExpYieldUSD)
        promYields.labels(account=account_total,name=account_total,ticker=account_total, 
            currency="Multi",type=account_total,balance_currency="EUR").set(TotalExpYieldEUR)


    #    promGauge[0].set(4.2)   # Set to a given value
        time.sleep(UPDATE_PERIOD)
    return

if __name__ == "__main__":
    init()
    main()
    print("Exiting")
    exit(0)