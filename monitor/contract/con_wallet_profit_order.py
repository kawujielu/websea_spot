#!/usr/bin/env python
# -*- coding: utf-8 -*-
import traceback

import time, datetime, collections
from datetime import datetime, timedelta, date
import pandas as pd
import asyncio
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import monitor, infor_load, infor_contract, infor_start_amount
from libs import heartbeat, sendmessage
from contract.contract_get_mongo_day import get_mongo_demand

from libs.database.getmysql import G_MysqlSession

symbols_contract = infor_contract.SYMBOLS_CONTRACT_PAIR + infor_contract.SYMBOLS_OFFLINE
acc_contract_id = infor_contract.acc_id_contract
from loguru import logger

sleep_timeout = 60 * 15


class con_wallet_profit():
    def __init__(self):
        self.error = []

    def get_monthstart_daystart(self):
        now = date.today()
        this_day_start = now.strftime("%Y-%m-%d %H:%M:%S")
        this_month_start = datetime(now.year, now.month, 1)
        this_month_start = str(this_month_start)
        return this_month_start, this_day_start

    def today_zero(self):
        timezone = int(time.time() - int(time.time() - time.timezone) % 86400)
        timezone_dt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timezone))

        return timezone, timezone_dt

    async def get_funding(self):
        sql = f"-- SELECT symbol,sum(settle_cost) funding from contract_treaty_cost WHERE user_id in {tuple(acc_contract_id)} GROUP BY symbol"
        sql = f"""
            SELECT symbol, SUM(settle_cost) AS funding
                FROM contract_treaty_cost
                WHERE user_id IN {tuple(acc_contract_id)}
                  AND (ts < '2025-07-10 08:00:00' OR (ts > '2025-07-16 08:00:00' AND ts < '2025-10-27 09:00:00'))
                GROUP BY symbol;
        """
        res, title = await G_MysqlSession.fetch_all(sql=sql)
        return {i[0]: i[1] for i in res}

    async def get_profitloss(self):
        sql = f"SELECT symbol,SUM(profitLoss) from contract_mongodb_day GROUP BY symbol"
        res, title = await G_MysqlSession.fetch_all(sql=sql)
        return {i[0]: i[1] for i in res}

    async def run(self):
        this_month_start, this_day_start = self.get_monthstart_daystart()
        timezone = int(time.time() - int(time.time() - time.timezone) % 86400)
        demand = {'ts': {'$gte': timezone, '$lt': 1761496200}}
        asset_position = await get_mongo_demand(demand)
        print(asset_position)




        timezone = int(time.time() - int(time.time() - time.timezone) % 86400)
        if self.error:
            sendmessage.send_telegram_msg(f'合约盈亏接口报错{self.error}', 'contract_ProfitLoss')
            sys.exit()
        if time.time() - timezone < 60 * 1.5:
            await asyncio.sleep(60 * 5 + timezone - time.time())
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        last_asset_position = await self.get_profitloss()
        demand = {'ts': {'$gte': timezone, '$lt': time.time()}}
        asset_position = await get_mongo_demand(demand)
        funding = await self.get_funding()

        temp = []
        for symbol in symbols_contract:
            tmp = collections.OrderedDict()
            tmp['time'] = now
            tmp['symbol'] = symbol
            tmp['订单盈利'] = -(last_asset_position.get(symbol, 0) + asset_position.get(symbol, 0))
            tmp['资金费用'] = funding.get(symbol, 0)
            tmp['盈利'] = tmp['订单盈利'] + tmp['资金费用']

            temp.append(tmp)
        df = pd.DataFrame(temp)
        title = ','.join([f"`{w}`" for w in df.columns])
        values = ','.join([str(tuple(i)) for i in df.values])
        sql = f"insert ignore into contract_profitloss_order ({title}) values {values}"
        await G_MysqlSession.insert_sql(sql)

        sql_profit_loss = f"select time,sum(`盈利`) as usdt from contract_profitloss_order where time > 'this_condition_start_time'  group by time order by time asc limit 1;"
        re_zone, title = await G_MysqlSession.fetch_all(sql=sql_profit_loss.replace('this_condition_start_time', this_day_start))
        re_month, title = await G_MysqlSession.fetch_all(sql=sql_profit_loss.replace('this_condition_start_time', this_month_start))

        profit_loss_all = df['盈利'].sum()

        mess = f'【合约:订单+资金费用｜量化】{now} ({int(sleep_timeout / 60)}min/次)\n' \
               f'当日盈亏:{int(profit_loss_all - re_zone[0][1])}U\n' \
               f'当月盈亏:{int(profit_loss_all - re_month[0][1])}U\n' \
               f'累计盈亏:{int(profit_loss_all)}U'
        # sendmessage.send_telegram_msg(mess, 'contract_ProfitLoss')

        return {'time': now, 'profit_loss': {'all': int(profit_loss_all), 'month': int(profit_loss_all - re_month[0][1]), 'today': int(profit_loss_all - re_zone[0][1])}}



async def contract_run():
    try:
        res = await con_wallet_profit().run()
        await heartbeat.i_live_well(server='合约盈亏监控', frequency=60 * 60 * 2, index=34)
        return res
    except Exception as e:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sendmessage.send_telegram_msg(message=f'{now} | error：con_wallet_profit {traceback.format_exc()}', ser='Alarm')
        logger.error(f'{now} | error : con_wallet_profit -->> {traceback.format_exc()}')


if __name__ == '__main__':
    pass
    # loop = asyncio.get_event_loop()
    # loop.run_until_complete(contract_run())
