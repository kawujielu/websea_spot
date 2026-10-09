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

from config.infor_contract import contract_account, SYMBOLS_CONTRACT_PAIR
from exchange.restful_api.abc_interfaces import AINTERFACES
from contract.contract_setting import get_symbols_details, getRate
from libs import sendmessage, heartbeat

a_interfaces = AINTERFACES()
sleep_timeout = 60 * 10


async def get_positon():
    msg = ""
    res = await a_interfaces.contract_position(symbol=None)
    res = res.get('result', {}).get('data', {})
    if res:
        rate = await getRate(SYMBOLS_CONTRACT_PAIR)
        for k, v in res.items():
            net_direction_total = v.get('net_direction_total')
            net_direction_total_amount = float(v.get('many_direction_total_amount')) + float(v.get('empty_direction_total_amount'))
            side = '多仓' if net_direction_total_amount > 0 else '空仓'
            net_direction_total_amount_u = net_direction_total_amount * float(rate.get(k, 0))
            msg += f"【{k}】:{side} {int(net_direction_total)}张 {int(net_direction_total_amount_u)}U\n"
        message = f"【合约】用户净持仓 ({int(sleep_timeout / 60)}min/次)\n{msg}"
        sendmessage.send_telegram_msg(message, ser='contract_info_user')


async def contract_run():
    while True:
        try:
            await get_positon()
            await heartbeat.i_live_well(server='合约用户净持仓', frequency=60 * 30, index=33)
            logger.info(f" contract_risk_rate wait 2min")
            await asyncio.sleep(sleep_timeout)
        except:

            mm = traceback.format_exc()
            sendmessage.send_telegram_msg(f'con_position 用户净持仓监控\n{mm}', ser='Alarm')
            logger.error(f" error:用户净持仓")
            await asyncio.sleep(sleep_timeout / 2)


if __name__ == "__main__":
    asyncio.run(get_positon())
