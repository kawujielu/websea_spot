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


async def get_treaty_cost_history():
    contract_size = {i['symbol']: i['contract_size'] for i in get_symbols_details()}
    msg = ""
    end_time = int(time.time())
    DAY = 100
    start_time = int(end_time - 3 * 8 * 60 * 60 * DAY)
    page_size = 100

    start_time_dt = ATime().timestamp_to_timearray(start_time)

    for j in range(1, 1000):
        res = await a_interfaces.contract_treaty_cost(page=j, page_size=100, max_time=end_time, min_time=start_time)
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
        if len(tmp) < page_size:
            break


async def get_treaty_cos_all():
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    contract_size = {i['symbol']: i['contract_size'] for i in get_symbols_details()}
    end_time = int(time.time())
    start_time = int(end_time - 8 * 60 * 60)
    page_size = 100

    start_time_dt = ATime().timestamp_to_timearray(start_time)

    temp = []
    for j in range(1, 100):
        res = await a_interfaces.contract_treaty_cost(page=j, page_size=100, max_time=end_time, min_time=start_time)
        tmp = []
        for i in res['result']['data']:
            d = {'user_id': i['user_id'], 'id': i['id'], 'symbol': i['symbol_name'], 'type': {1: "开多", 2: "开空"}[i['direction']], 'amount': i['hold_amount'], 'settle_cost': float(i['settle_cost']), 'capital_rate': i['capital_rate'],
                 'is_full': {2: "全仓", 1: "逐仓"}[i['is_full']], 'ts': i['create_time_text'], 'mark_price': i['mark_price'], 'face_value': contract_size.get(i['symbol_name'], 1), 'expect_settle_cost': float(i['expect_settle_cost']),
                 'transfer_flag': {0: "失败", 1: "成功"}[i['transfer_flag']], }
            # if i['create_time_text'] < start_time_dt:
            #     break
            tmp.append(d)
        print(j, len(tmp), len(res['result']['data']))
        temp += tmp
        if len(tmp) < page_size:
            break
        await asyncio.sleep(1)

    if temp:
        ti = list(temp[0].keys())
        title = ','.join(ti)
        values = ','.join([str(tuple([i[j] for j in ti])) for i in temp])

        sql = f"insert ignore into contract_treaty_cost ({title}) " \
              f"values {values}"
        await G_MysqlSession.insert_sql(sql)
        df = pd.DataFrame(temp)
        df = df[(df['user_id'].isin(acc_id_contract)) & (df['transfer_flag'].isin(['成功', 1]))]
        if not df.empty:
            df = df.groupby(['symbol'])[['settle_cost', 'expect_settle_cost']].sum().reset_index()
            df = df.sort_values(by=["settle_cost"], ascending=True)
            settle_cost = df['settle_cost'].sum()
            expect_settle_cost = df['expect_settle_cost'].sum()
            d_dict = dict(zip(df['symbol'], df['settle_cost']))
            d_dict = {k: round(v, 2) for k, v in d_dict.items() if abs(v) > 0.01}
            msg = f"{now}\n" \
                  f"【合约资金费用】:\n" \
                  f"量化账户期望结算金额:{round(expect_settle_cost, 2)}U\n" \
                  f"量化账户实际结算金额{round(settle_cost, 2)}U\n" + (f"{d_dict}" if d_dict else "")
            sendmessage.send_telegram_msg(message=msg, ser='contract_info_user')


async def get_treaty_cost():
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    contract_size = {i['symbol']: i['contract_size'] for i in get_symbols_details()}
    end_time = int(time.time())
    start_time = int(end_time - 8 * 60 * 60)
    page_size = 100

    start_time_dt = ATime().timestamp_to_timearray(start_time)

    temp = []
    for userid in set(acc_id_contract):
        for j in range(1, 100):
            res = await a_interfaces.contract_treaty_cost(page=j, page_size=100, max_time=end_time, min_time=start_time, user_id=userid)
            tmp = []
            for i in res['result']['data']:
                d = {'user_id': i['user_id'], 'id': i['id'], 'symbol': i['symbol_name'], 'type': {1: "开多", 2: "开空"}[i['direction']], 'amount': i['hold_amount'], 'settle_cost': float(i['settle_cost']), 'capital_rate': i['capital_rate'],
                     'is_full': {2: "全仓", 1: "逐仓"}[i['is_full']], 'ts': i['create_time_text'], 'mark_price': i['mark_price'], 'face_value': contract_size.get(i['symbol_name'], 1), 'expect_settle_cost': float(i['expect_settle_cost']),
                     'transfer_flag': {0: "失败", 1: "成功"}[i['transfer_flag']], }
                if i['create_time_text'] < start_time_dt:
                    break
                tmp.append(d)
            print(j, userid, len(tmp), len(res['result']['data']))
            temp += tmp
            if len(tmp) < page_size:
                break
            await asyncio.sleep(1)

    if temp:
        ti = list(temp[0].keys())
        title = ','.join(ti)
        values = ','.join([str(tuple([i[j] for j in ti])) for i in temp])

        sql = f"insert ignore into contract_treaty_cost ({title}) " \
              f"values {values}"
        await G_MysqlSession.insert_sql(sql)
        df = pd.DataFrame(temp)
        df = df[(df['user_id'].isin(acc_id_contract)) & (df['transfer_flag'].isin(['成功', 1]))]
        if not df.empty:
            df = df.groupby(['symbol'])[['settle_cost', 'expect_settle_cost']].sum().reset_index()
            df = df.sort_values(by=["settle_cost"], ascending=True)
            settle_cost = df['settle_cost'].sum()
            expect_settle_cost = df['expect_settle_cost'].sum()
            d_dict = dict(zip(df['symbol'], df['settle_cost']))
            d_dict = {k: round(v, 2) for k, v in d_dict.items() if abs(v) > 0.01}
            msg = f"{now}\n" \
                  f"【合约资金费用】:\n" \
                  f"量化账户期望结算金额:{round(expect_settle_cost, 2)}U\n" \
                  f"量化账户实际结算金额{round(settle_cost, 2)}U\n" + (f"{d_dict}" if d_dict else "")
            sendmessage.send_telegram_msg(message=msg, ser='contract_info_user')


async def contract_run():
    try:
        await get_treaty_cos_all()
        await heartbeat.i_live_well(server='合约资金费用', frequency=60 * 60 * (16 + 1), index=35)
        print(f"合约资金费用 ok")
        logger.info(f"合约资金费用 ok")
    except:

        mm = traceback.format_exc()
        sendmessage.send_telegram_msg(f'合约资金费用\n{mm}', ser='Alarm')
        logger.error(f" error:合约资金费用")


if __name__ == "__main__":
    # asyncio.run(contract_run())
    loop = asyncio.get_event_loop()
    loop.run_until_complete(contract_run())
