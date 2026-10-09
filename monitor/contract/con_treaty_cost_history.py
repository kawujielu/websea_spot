#!/usr/bin/env python
# -*- coding: utf-8 -*-
import time, datetime
import pandas as pd
import urllib3
import asyncio
import traceback
from loguru import logger
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.infor_contract import contract_account, SYMBOLS_CONTRACT_PAIR, acc_id_contract
from exchange.restful_api.abc_interfaces import AINTERFACES
from contract.contract_setting import get_symbols_details, getRate
from libs import sendmessage, heartbeat
from libs.database.getmysql import G_MysqlSession
from libs.get_time import ATime

a_interfaces = AINTERFACES()
acc_id_contract = [int(i) for i in acc_id_contract]

s_start_time_dt = '2023-09-25 15:00:00'
s_start_time = 1695625200


async def get_treaty_cost_history():
    contract_size = {i['symbol']: i['contract_size'] for i in get_symbols_details()}
    for i in range(1, 1000):
        start_time = s_start_time + i * 60 * 60 * 8
        end_time = start_time + 1 * 60 * 60 * 8

        start_time_dt = ATime().timestamp_to_timearray(start_time)
        end_time_dt = ATime().timestamp_to_timearray(end_time)

        print(i, start_time_dt, end_time_dt)
        await get_treaty(start_time, end_time, contract_size)

        if time.time() < start_time:
            break


async def get_treaty(start_time, end_time, contract_size):
    page_size = 100

    for j in range(1, 1000):
        res = await a_interfaces.contract_treaty_cost(page=j, page_size=page_size, max_time=end_time, min_time=start_time)
        tmp = []
        for i in res['result']['data']:
            d = {'user_id': i['user_id'], 'id': i['id'], 'symbol': i['symbol_name'], 'type': {1: "开多", 2: "开空"}[i['direction']], 'amount': i['hold_amount'], 'settle_cost': float(i['settle_cost']), 'capital_rate': i['capital_rate'],
                 'is_full': {2: "全仓", 1: "逐仓"}[i['is_full']], 'ts': i['create_time_text'], 'mark_price': i['mark_price'], 'face_value': contract_size.get(i['symbol_name'], 1), 'expect_settle_cost': float(i['expect_settle_cost']),
                 'transfer_flag': {0: "失败", 1: "成功"}[i['transfer_flag']], }
            tmp.append(d)
        print(j, len(tmp), len(res['result']['data']))

        if tmp:
            ti = list(tmp[0].keys())
            title = ','.join(ti)
            values = ','.join([str(tuple([i[j] for j in ti])) for i in tmp])

            sql = f"insert ignore into contract_treaty_cost ({title}) " \
                  f"values {values}"
            await G_MysqlSession.insert_sql(sql)

            start_time_dt = ATime().timestamp_to_timearray(start_time)
            end_time_dt = ATime().timestamp_to_timearray(end_time)

            sendmessage.send_telegram_msg(f'合约资金费用\n{start_time_dt}-{end_time_dt} {j}页 ok', ser='Alarm')
        await asyncio.sleep(2)
        if len(tmp) < page_size:
            break


async def contract_run():
    try:
        await get_treaty_cost_history()
        logger.info(f"合约资金费用 ok")
    except:
        mm = traceback.format_exc()
        sendmessage.send_telegram_msg(f'合约资金费用\n{mm}', ser='Alarm')
        logger.error(f" error:合约资金费用")


if __name__ == "__main__":
    # asyncio.run(contract_run())
    loop = asyncio.get_event_loop()
    loop.run_until_complete(contract_run())
