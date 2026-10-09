#!/usr/bin/env python
# -*- coding: utf-8 -*-
import copy
import requests
import ujson
import urllib3
import pandas as pd
import time, datetime
import asyncio
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.infor_load import contract_host
from libs.requestSession import G_RequestSession
from config.infor_contract import SYMBOLS_CONTRACT_PAIR
from libs import heartbeat, sendmessage

REDUCE = 0.001
PR_MAX = 1000
PR_MIN = 10


def get_data(asks, bids, ex=None):
    asks_gear, bids_gear = {}, {}
    for i in asks:
        price = float(i[0])
        amount = float(i[1])  # / price if ex == "abc" else float(i[1])
        asks_gear[price] = asks_gear.get(price, 0) + amount
    for i in bids:
        price = float(i[0])
        amount = float(i[1])  # / price if ex == "abc" else float(i[1])
        bids_gear[price] = bids_gear.get(price, 0) + amount
    asks_gear = sorted(asks_gear.items(), key=lambda x: x[0], reverse=False)  # 升序
    bids_gear = sorted(bids_gear.items(), key=lambda x: x[0], reverse=True)  # 降序

    asks_depth_5 = sum([i[1] for i in asks_gear[:5]])
    bids_depth_5 = sum([i[1] for i in bids_gear[:5]])

    ask_bid_percent = asks_gear[0][0] / bids_gear[0][0] - 1
    return {"ask_bid_percent": ask_bid_percent, "asks_depth_5": asks_depth_5, "bids_depth_5": bids_depth_5}


async def abs_depth(symbol):
    url = f"{contract_host}/qapi-v1/market/depth?symbol={symbol}"
    result = {}
    async with G_RequestSession.request.request(method='GET',
                                                url=url,
                                                timeout=5) as r:
        result['content'] = await r.text()
        result['code'] = r.status
    if result['code'] == 200:
        res = ujson.loads(result['content'])['result']
        asks, bids = res['asks'], res['bids']

        return get_data(asks, bids, ex='abc')
    else:
        return {}


async def bitget_depth(symbol):
    host = "https://api.bitget.com"
    url = f"{host}/api/v2/mix/market/merge-depth?symbol={symbol.replace('-', '')}&productType=USDT-FUTURES"
    result = {}
    async with G_RequestSession.request.request(method='GET',
                                                url=url,
                                                timeout=5) as r:
        result['content'] = await r.text()
        result['code'] = r.status

    if result['code'] == 200:
        res = ujson.loads(result['content'])['data']
        asks, bids = res['asks'], res['bids']
        if asks and bids:
            return get_data(asks, bids)
        else:
            return {}
    else:
        return {}


async def run():
    # symbol = "BTC-USDT"

    msg_ask_bid_percent, msg_depth = "", ""
    msg_ask_bid_percent = []
    msg_depth = []
    for symbol in SYMBOLS_CONTRACT_PAIR:
        # for symbol in ['ETH-USDT']:
        res_abc = await abs_depth(symbol)
        res_bit = await bitget_depth(symbol)
        if res_abc and res_bit:
            reduce = res_bit['ask_bid_percent'] - res_abc['ask_bid_percent']
            ask_pr = res_abc['asks_depth_5'] / res_bit['asks_depth_5'] * 100
            bid_pr = res_abc['bids_depth_5'] / res_bit['bids_depth_5'] * 100
            pr_max = max(abs(ask_pr), abs(bid_pr))
            pr_min = min(abs(ask_pr), abs(bid_pr))

            if abs(reduce) > REDUCE:
                msg_ask_bid_percent.append([reduce,
                                            f"【{symbol}】\n"
                                            f"         差值:{round(reduce, 8)}\n"
                                            f"         abc:{round(res_abc['ask_bid_percent'], 8)} bit:{round(res_bit['ask_bid_percent'], 8)}\n"])
            if pr_max > PR_MAX or pr_min < PR_MIN:
                msg_depth.append([pr_max,
                                  f"【{symbol}】\n"
                                  f"         *ask*:{round(ask_pr, 2)}% *abc*:{round(res_abc['asks_depth_5'], 2)} *bit*:{round(res_bit['asks_depth_5'], 2)}\n"
                                  f"         *bid*:{round(bid_pr, 2)}% *abc*:{round(res_abc['bids_depth_5'], 2)} *bit*:{round(res_bit['bids_depth_5'], 2)}\n"])

    if msg_ask_bid_percent:
        msg_ask_bid_percent = sorted(msg_ask_bid_percent, key=lambda x: abs(x[0]))
        msg = f"*【合约】价差 abs(bitget-abc)>{REDUCE * 100}% * (30min/次)\n" + "".join([i[1] for i in msg_ask_bid_percent])
        # sendmessage.send_telegram_msg_mdv2(msg, ser='depth5_abc_bitget')
    if msg_depth:
        msg_depth = sorted(msg_depth, key=lambda x: x[0])
        msg = f"*【合约】前5挡深度深度 abc/bitget >{PR_MAX}% or <{PR_MIN}% * (30min/次)\n" + "".join([i[1] for i in msg_depth])

        # sendmessage.send_telegram_msg_mdv2(msg, ser='depth5_abc_bitget')


if __name__ == "__main__":
    asyncio.run(run())
