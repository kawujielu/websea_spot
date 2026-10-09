#!/usr/bin/env python
# -*- coding: utf-8 -*-
import time, datetime
import pandas as pd
import os, sys, asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import infor, monitor, infor_start_amount
from spot.spot_acc_amount import get_amount
from libs import heartbeat, sendmessage

import urllib3

# urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# 不提示警告
pd.set_option('mode.chained_assignment', None)


async def get_frozen_pro():
    START_AMOUNT_SPOT, START_AMOUNT_CONTRACT = await infor_start_amount.get_start_amount()
    temp = await get_amount(symbol_list=infor.SYMBOLS_LIST, spot_account_list=infor.spot_account, start_amount=START_AMOUNT_SPOT)
    temp["frozen"] = temp["frozen"].astype(float)
    temp = temp[temp["frozen"] > pow(10, -10)]
    temp['now_frozen_proportion'] = round(temp["frozen"] / temp["now_amount"] * 100, 2)
    print(temp[['account_name', 'currency', "now_frozen_proportion", 'frozen']])

    return temp


async def get_frozen():
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    data = await get_frozen_pro()
    # 冻结占比超过80%
    data_frozen = data[['account_name', 'currency', "now_frozen_proportion", 'now_amount', 'frozen']]
    message, mess_quant_web = f'{now}\n【现货】正常情况应该是没有冻结的，如果有冻结，属于异常，需要排查原因\n', ''
    if data_frozen.empty:
        print(f"{now} | A_Frozen wait 暂时没有冻结异常")

    else:
        data_frozen = data_frozen.sort_values(by=["account_name", 'now_frozen_proportion'], ascending=True)
        acc = data_frozen['account_name'].unique()

        for i in range(len(acc)):
            acc_frozen = dict(zip(data_frozen['currency'][data_frozen['account_name'] == acc[i]],
                                  data_frozen['now_frozen_proportion'][data_frozen['account_name'] == acc[i]]))

            message += f"{acc[i]}:{infor.spot_account[acc[i]]['id']}-{infor.spot_account[acc[i]]['Purpose']}\n{acc_frozen}\n"
            mess_quant_web = f"<b style='color:#FF0000'>{acc[i]}:{infor.spot_account[acc[i]]['Purpose']}</b><br>" \
                             f"{acc_frozen}<br>"
        print(message)
        sendmessage.send_telegram_msg(message, ser='spot_info')
    monitor.get_a_monitor(event_name='bb_freeze', msg=mess_quant_web)


async def spot_run():
    while True:
        try:
            await get_frozen()
            await heartbeat.i_live_well(server='冻结监控', frequency=60 * 2, index=31)
            await asyncio.sleep(60)
        except Exception as e:
            now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            sendmessage.send_telegram_msg(message=f'A_Freeze\n{e}', ser='Alarm')
            print(f'{now}| error:A_Freeze -->> {e}')
            await asyncio.sleep(10)


if __name__ == '__main__':
    asyncio.run(spot_run())
    # loop = asyncio.get_event_loop()
    # loop.run_until_complete(spot_run())
