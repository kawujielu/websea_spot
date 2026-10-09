#!/usr/bin/env python
# -*- coding: utf-8 -*-
import copy
import time, datetime
import pandas as pd
import urllib3
import asyncio
import traceback
from loguru import logger
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import monitor
from config.infor_contract import contract_account, SYMBOLS_CONTRACT_PAIR
from exchange.restful_api.abc_contract import AApi
from libs.database.getmysql import G_MysqlSession
from libs import requestSession, sendmessage, heartbeat
from contract.contract_setting import get_precision, get_symbols_details, getRate, CAPITAL_RATE_PARAM, get_capital_rate_param, sleep_time
from config import infor_contract, monitor

acc_id = infor_contract.acc_id_contract

# 不提示警告
pd.set_option('mode.chained_assignment', None)

# 监控哪些账户
acc_contract_list = list(contract_account.keys())

RISK_RATE = 500
AMOUNT_COEF = 2
POSITION_U = 10000 * 5
Type = {1: '多仓', 2: '空仓'}  # 1多仓，2空仓
fetch_timeout = 60 * 20


async def get_account_position(apikey, account):
    ao = AApi(token=apikey['token'], secret_key=apikey['sk'])
    res = await ao.position_contract()
    d = []
    if res['errno'] == 0 and res['result'] != []:
        for re in res['result']:
            temp = {}
            temp['account'] = account
            temp['symbol'] = re['symbol']
            temp['type'] = re['type']  # 1多仓，2空仓
            # temp['risk_rate'] = re['risk_rate']  # 风险率
            temp['avail_amount'] = float(re['avail_amount'])  # 可平数量(张数)
            temp['amount'] = float(re['amount'])  # 持有数量
            # temp['contract_frozen'] = float(re['contract_frozen'])  # 委托冻结(张数)
            # temp['open_price_avg'] = float(re['open_price_avg'])  # 开仓均价
            # temp['equity'] = float(re['equity'])  # 账户权益(USDT)
            # temp['avail'] = float(re['avail']) if re['avail'] else 0  # 可用(USDT)
            # temp['bood'] = float(re['bood'])  # 冻结保证金(USDT)
            temp['profit'] = float(re['profit'])  # 可用(USDT)
            d.append(temp)
            print(account, temp)

    return d


async def getpositon():
    tasks = []
    res = []
    for k, v in contract_account.items():
        apikey = v['apikey']
        tasks.append(asyncio.create_task(get_account_position(apikey, k)))
    for t in tasks:
        res += (await t)

    return res


async def get_con_fee():
    start_time = '2023-09-26 22:26:03'
    end_time = '2023-10-09 10:40:51'

    # 2023-10-09 09:37:51
    side = {'1': '开多', '2': '开空', '3': '平多', '4': '平空', }
    OrderSource = {1: '普通', 2: '爆仓', 3: '止盈', 4: '止损', 5: '反手', 6: '限价止盈止损触发', }

    # sql = f"""SELECT * from contract_mongoorders WHERE ts >"{start_time}" and ts<="{end_time}" and user_id in {tuple(acc_id)} order by _id"""
    sql = f"""SELECT * from contract_mongoorders WHERE ts >"{start_time}" and ts<="{end_time}" and user_id in {tuple(acc_id)} and symbol ='BTC-USDT' order by _id"""
    print('acc_id', acc_id)
    print('sql', sql)

    quant_symbols_position = {}

    mm, title = await G_MysqlSession.fetch_all(sql)
    for i in mm:
        i_dict = dict(zip(title, i))
        # print(i_dict)
        user_id = i_dict['user_id']
        #  # 买：开多、平空、卖：开空、平多
        # long\short
        SIDE = {"开多": "buy", "平空": "buy", "开空": "sell", "平多": "sell"}

        type = i_dict['type']  # 买：开多、卖：开空
        symbol = i_dict['symbol']
        # amount = float(i_dict['amount'])  # 张数
        price = float(i_dict['price'])
        facevalue = i_dict['facevalue']

        coef = {"buy": 1, "sell": -1}[SIDE[type]]
        amount = float(i_dict['amount']) * facevalue * coef  # 个数
        amountQuote = amount * price  # 成交额

        if not quant_symbols_position.get(symbol):
            d = {"amount": 0, 'amountQuote': 0, "openamount": 0, 'openamountQuote': 0}
            quant_symbols_position[symbol] = {"long": copy.deepcopy(d), "short": copy.deepcopy(d)}
            # quant_symbols_position[symbol] = {"long": copy.deepcopy(d)}

        dd = quant_symbols_position[symbol]

        orderType = "long" if type in ["开多", "平多"] else "short"
        # amount amountQuote
        last_amount = dd[orderType]["openamount"]
        print(f"{symbol=} {type=} {amount=} {amountQuote=} {orderType=} {last_amount=}")

        if amount * last_amount >= 0:
            dd[orderType]["openamount"] += amount
            dd[orderType]["openamountQuote"] += amountQuote
        else:
            if amount > last_amount:  # 反向,均价就是该笔订单的价格
                dd[orderType]["openamount"] += amount
                dd[orderType]["openamountQuote"] = dd[orderType]["openamount"] * price
            else:  # 同向,开仓均价不变
                openavgPrice = dd[orderType]["openamountQuote"] / dd[orderType]["openamount"]
                dd[orderType]["openamount"] += amount
                dd[orderType]["openamountQuote"] = dd[orderType]["openamount"] * openavgPrice

        dd[orderType]["amount"] += amount
        dd[orderType]["amountQuote"] += amountQuote

        dd[orderType]['openavgPrice'] = dd[orderType]["openamountQuote"] / dd[orderType]["openamount"]
        dd[orderType]['avgprice'] = dd[orderType]["amountQuote"] / dd[orderType]["amount"]
        print(dd)


async def contract_run():
    await get_con_fee()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(contract_run())
