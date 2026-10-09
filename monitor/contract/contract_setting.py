import asyncio, requests, datetime
import copy

import numpy as np
import os, sys

import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs.database.getredis import get_redis_contract
from config.infor_load import contract_host, public_host
from config.infor_contract import SYMBOLS_CONTRACT_OUT, SYMBOLS_CONTRACT_PAIR

CAPITAL_RATE_PARAM = {s: 8 for s in SYMBOLS_CONTRACT_PAIR}


async def getRate(SYMBOLS_CONTRACT_PAIR):
    ret = {}
    tasks = [[asyncio.create_task(get_redis_contract.hgetall(i)), i] for i in SYMBOLS_CONTRACT_PAIR]
    for i, symbol in tasks:
        price = await i
        if price:
            price = [float(v) for k, v in price.items() if 'price' in str(k)]
            ret[symbol] = np.mean(price)
            # ret[symbol] = float(list(price.values())[0])
    ret['USDT-USDT'] = 1
    return ret


# 自动获取交易对
def get_symbols():
    res = requests.get(contract_host + '/qapi-v1/symbol/precision', timeout=15, verify=False)
    symbols = []
    if res.status_code == 200:
        res = res.json()
        if res["errno"] == 0:
            symbols = [x for x in res["result"] if x.split('-')[0] not in SYMBOLS_CONTRACT_OUT]
    return symbols


def get_trade(symbols, size=1):
    trade = {}
    for s in symbols:
        res = requests.get(contract_host + '/qapi-v1/market/trade', params={'symbol': s, 'size': size}, timeout=15, verify=False)
        if res.status_code == 200:
            res = res.json()
            if res["errno"] == 0 and res["result"]['data']:
                trade[s] = res["result"]['data'][0]['price']
    return trade


def get_precision():
    res = requests.get(contract_host + '/qapi-v1/symbol/precision', timeout=15, verify=False)
    if res.status_code == 200:
        res = res.json()
        if res["errno"] == 0:
            return {k: v for k, v in res["result"].items() if k not in SYMBOLS_CONTRACT_OUT}
    return []


def get_symbols_details():
    res = requests.get(contract_host + '/qapi-v1/symbol/symbols', timeout=15, verify=False)
    if res.status_code == 200:
        res = res.json()
        if res["errno"] == 0:
            return res["result"]
    return []


async def capitalrateparam(symbol=None):
    host = public_host + '/openApi/contract/capitalRateParam'
    host = f"{host}?symbol={symbol}" if symbol else host
    res = requests.get(host, timeout=15, verify=False)
    if res.status_code == 200:
        res = res.json()
        if res["errno"] == 0:
            return res["result"]
    return []


async def get_capital_rate_param():
    global CAPITAL_RATE_PARAM
    while True:
        try:
            res = await capitalrateparam()
            CAPITAL_RATE_PARAM = {i['name']: i['cycle'] if i['cycle'] else 8 for i in res}
        except:
            pass
        finally:
            await asyncio.sleep(60 * 60)


async def sleep_time(PARAM, fetch_timeout):
    now_time = datetime.datetime.now()
    HOUR = now_time.hour
    MINUTE = now_time.minute
    sleep_timeout = fetch_timeout
    cycle = {k: (HOUR + 1) % v for k, v in PARAM.items() if (HOUR + 1) % v == 0}
    d_sleep = 5
    if cycle:
        if MINUTE >= fetch_timeout / 60 and MINUTE < 30:
            sleep_timeout = (30 - MINUTE) * 60
        elif MINUTE >= 30 and MINUTE < 50:
            if MINUTE % d_sleep == 0:
                sleep_timeout = 60 * d_sleep
            else:
                sleep_timeout = (d_sleep - MINUTE % d_sleep) * 60
        elif MINUTE >= 50:
            sleep_timeout = 60 * 1
    else:
        if MINUTE % fetch_timeout == 0:
            sleep_timeout = fetch_timeout
        else:
            sleep_timeout = fetch_timeout - MINUTE * 60 % fetch_timeout

    return max(sleep_timeout, 60 * 1)


if __name__ == '__main__':
    d = asyncio.run(capitalrateparam())
    print(d)
