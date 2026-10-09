#!/usr/bin/env python
# -*- coding: utf-8 -*-
import time, datetime, urllib3, requests
import pandas as pd
import asyncio
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from exchange.restful_api.abc_interfaces import AINTERFACES
from libs import heartbeat, sendmessage

from config import infor, infor_webhook, AINTERFACES

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# 不提示警告
pd.set_option('mode.chained_assignment', None)
symbols = ['BTC', 'ETH']

BIG_AMOUNT_PRICE = 1000000
MIN_TIME = 5
types = {0: '审核中', 1: '已通过', 2: '已撤销', 3: '排队中', 5: '打包中', 7: '确认中', 9: '已确认', 11: '失败',
         12: '已反驳'}


def get_currency_id(symbols):
    currency_id = {}
    for s in symbols:
        res = AINTERFACES().currency_list(s)['result'][0]['id']
        currency_id[s] = res
    return currency_id


async def run(currency_id):
    now_time = time.time() - 60 * MIN_TIME
    message = ""
    for symbol, id in currency_id.items():

        res = await AINTERFACES().get_deposit_list(currency_id=id, min_time=now_time)['result']['data']
        if res != []:
            for re in res:
                print(re)
                mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(re['create_time'])))
                user_id = re['user_id']
                amount = round(float(re['amount']), 2)
                status = types[re['status']] if re['status'] in types.keys() else re['status']
                total_price = int(float(re['total_price']))

                if total_price > BIG_AMOUNT_PRICE:
                    message += f"【{symbol}】ID:{user_id},amount:{amount}[{total_price}U] 状态:{status} {mtime}\n"
                    print(symbol, user_id, mtime, amount, status, total_price)

    if message != '':
        message = f"{MIN_TIME}分钟内<font color='#dd0000'>有用户大额充值</font>进来\n" \
                  f"### 确认对冲账户资金足够，如果不足，及时提醒资产备付资金\n" + message
        sendmessage.send_telegram_msg(message='大额充值' + message.replace('\n', '\n\n'),
                                      ser='EmerWarning')
    print('acc_big_deposit', 'ok')


async def spot_run():
    currency_id = get_currency_id(symbols)
    while True:
        try:
            await run(currency_id)
            await heartbeat.i_live_well(server='大额充值监控', frequency=60 * 10, index=30)
            time.sleep(60 * 2)
        except Exception as e:
            mess = f'error：acc_big_deposit-->{e}\n'
            sendmessage.send_telegram_msg(message=mess, ser='Alarm')
            time.sleep(60)


if __name__ == '__main__':
    asyncio.run(spot_run())
