#!/usr/bin/env python
# -*- coding: utf-8 -*-
import time, datetime, requests, asyncio
import pandas as pd
import os, sys, asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import infor, monitor, infor_load
from libs import heartbeat, sendmessage
from spot.spot_setting import get_symbols, get_precision

import urllib3

A_DEPTH = 21

symbols = infor.SYMBOLS_PAIR
symbols_out = infor.SYMBOLS_OUT
host = infor_load.spot_host
sleep_timeout = 60 * 2
RATIO = 1


def get_depth_quant(precision):
    result = []
    url = host + '/openApi/market/gears_depth'
    for symbol, price_precision in precision.items():
        res = requests.get(url, params={'symbol': symbol}, timeout=15, verify=False)
        if res.status_code == 200:
            res = res.json()
            if res['errno'] == 0 and res['result']['asks'] and res['result']['bids']:
                temp = {}
                temp['symbol'] = symbol
                asks, bids = res['result']['asks'], res['result']['bids']

                temp['asks'] = int((asks[-1]['gear']))
                temp['bids'] = int(bids[-1]['gear'])
                temp['ask1'] = float((asks[0]['price']))
                temp['bid1'] = float(bids[0]['price'])

                temp['price'] = price_precision
                temp['price_precision'] = 10 ** (-price_precision) * RATIO
                result.append(temp)

    df = pd.DataFrame(result)
    df['price_reduce'] = df['ask1'] - df['bid1']
    return df


async def get_depth_price(precision, staging):
    df = get_depth_quant(precision)
    df1 = df[((df['bids'] < A_DEPTH) & (df['asks'] < A_DEPTH)) & (~df['symbol'].isin(symbols_out))]
    df2 = df[(df['price_reduce'] <= df['price_precision']) & (~df['symbol'].isin(['BTC-USDT', 'ETH-USDT']))]
    mess_quant_web = ''
    mess1, mess2 = '', ''
    price_reduce_symbol = {}

    for i in range(len(df1)):
        symbol = df1['symbol'].iloc[i]
        curr = symbol.split('-')[0]
        side = '[项目方]' if curr in infor.SYMBOLS_LIST_PROJECT else ''
        bids = df1['bids'].iloc[i]
        asks = df1['asks'].iloc[i]
        mess1 += f"【{symbol}】：asks:{asks} bids:{bids}{side}\n"
        mess_quant_web += f"<b style='color:#FF0000'>【{symbol}】</b> asks:{asks} bids:{bids}{side}<br>"
    for i in range(len(df2)):
        symbol = df2['symbol'].iloc[i]
        curr = symbol.split('-')[0]
        side = '[项目方]' if curr in infor.SYMBOLS_LIST_PROJECT else ''
        bid1 = df2['bid1'].iloc[i]
        ask1 = df2['ask1'].iloc[i]
        price = df2['price'].iloc[i]
        price_reduce = round(df2['price_reduce'].iloc[i], price)
        price_precision = df2['price_precision'].iloc[i]
        d = round(price_reduce / price_precision, 2)
        mess2 += f"【{symbol}】:ask1:{ask1} bid1:{bid1} 价差:{price_reduce} {side}\n"
        price_reduce_symbol[symbol] = f"【{symbol}】:ask1:{ask1} bid1:{bid1} 价差:{price_reduce} {side}"

    message = ''
    # if mess1:
    #     mess1 += f'【现货】合并深度不足{A_DEPTH}档,请相关同事注意 ({int(sleep_timeout / 60)}min/次)\n' + mess1
    # if mess2:
    #     message = f'【现货】买卖1价差低于{RATIO}个价格价格精度,请相关同事注意 ({int(sleep_timeout / 60)}min/次)\n' + mess2
    # if mess2:
    # print(message)
    #     sendmessage.send_telegram_msg(message=message, ser='depth')
    # monitor.get_a_monitor(event_name='bb_depth', msg=mess_quant_web)
    # print(f'{now} | spot a_depth wait 1min')

    staging.append(price_reduce_symbol)
    return mess1, staging


async def get_staging(now, precision, staging):
    mess1, staging = await get_depth_price(precision, staging)
    if len(staging) >= 3:
        staging = staging[-3:]
        message = ""
        mess_quant_web = ""

        staging_symbols = staging[0].keys() & staging[1].keys() & staging[2].keys()
        if mess1:
            message += f'【现货】合并深度不足{A_DEPTH}档,请相关同事注意 ({int(sleep_timeout / 60)}min/次)\n' + mess1 + '\n'
        if staging_symbols:
            message += f'【现货】买卖1价差低于{RATIO}个价格价格精度,连续三次超过设置参数,请相关同事注意 ({int(sleep_timeout / 60)}min/次)\n' + '\n'.join([staging[-1][s] for s in staging_symbols])
        if message:
            sendmessage.send_telegram_msg(message=message, ser='depth')
            monitor.get_a_monitor(event_name='bb_depth', msg=mess_quant_web)
    return staging


async def spot_run():
    symbols = get_symbols()
    precision = {k: int(v['price']) for k, v in get_precision().items() if k in symbols}
    staging = []
    while True:
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            staging = await get_staging(now, precision, staging)
            await heartbeat.i_live_well(server='现货合并挡深度监控', frequency=60 * 11, index=31)
        except Exception as e:
            sendmessage.send_telegram_msg(message=f'a_depth error : {e}', ser='Alarm')
            now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f'{now} | error:a_depth -->> {e}')
        finally:
            await asyncio.sleep(sleep_timeout)


async def test():
    precision = {k: int(v['price']) for k, v in get_precision().items()}
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    staging = []
    for i in range(4):
        print(i + 1, len(staging), staging)
        staging = await get_staging(now, precision, staging)


if __name__ == '__main__':
    asyncio.run(spot_run())
