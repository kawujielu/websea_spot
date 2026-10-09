#!/usr/bin/env python
# -*- coding: utf-8 -*-
import traceback

import time, datetime, urllib3, json, requests, ccxt, collections
from datetime import datetime, timedelta, date
import pandas as pd
import asyncio
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import monitor, infor, infor_load, infor_contract, infor_start_amount
from libs import heartbeat, sendmessage
from exchange.restful_api.abc_interfaces import AINTERFACES
from spot.spot_acc_amount import get_amount as spotamount
from contract.con_amount import Amount as contractAmount
from libs.database.getmysql import G_MysqlSession
from contract.con_wallet_profit_order import contract_run as contract_run_order
from loguru import logger


symbols = list(set(infor.SYMBOLS_LIST + infor_contract.SYMBOLS_QUOTE))
symbols_contract = infor_contract.SYMBOLS_CONTRACT_PAIR + infor_contract.SYMBOLS_OFFLINE
# 查询合约钱包账户
acc_contract_list = infor_contract.contract_account
SYMBOLS_SPOT_LIST = infor.SYMBOLS_LIST
SYMBOLS_CONTRACT_PAIR = infor_contract.SYMBOLS_CONTRACT_PAIR
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

    async def get_spot_wallet(self, START_AMOUNT_SPOT):
        df_quant = await spotamount(symbol_list=SYMBOLS_SPOT_LIST, spot_account_list=acc_contract_list, start_amount=START_AMOUNT_SPOT)
        df_quant = df_quant[~(df_quant['now_amount'].isin([0]) & df_quant['start_amount'].isin([0]))]

        df_quant = df_quant.groupby(['currency'])['now_amount', 'start_amount'].sum().reset_index()
        df_quant.rename(columns={'currency': 'symbol'}, inplace=True)
        return df_quant

    async def get_contract_wallet(self, START_AMOUNT_CONTRACT):
        df_quant = await contractAmount(symbol_list=symbols_contract, accountList=acc_contract_list, start_amount=START_AMOUNT_CONTRACT)
        df_quant = df_quant[~(df_quant['now_amount'].isin([0]) & df_quant['start_amount'].isin([0]))]
        df_quant = df_quant.groupby(['symbol'])[['now_amount', 'start_amount']].sum().reset_index()
        return df_quant

    async def contract_special_acc(self):
        # 持仓、手续费中间账户：-12
        # 盈亏中间账户：-13[-13的资金+所有用户的已实现盈亏之和+所有用户的未实现盈亏之和+穿仓金额=0]
        # 资金费用结算中间账户：-14
        # 资金费用（非量化）：-25
        # 资金费用（量化）：-26
        # acc = {'穿仓-全仓': '-31', '穿仓-逐仓': '-33', '持仓、手续费中间账户': '-12', '盈亏中间账户': '-13'}
        acc = {'穿仓-全仓': '-31', '穿仓-逐仓': '-33', '盈亏中间账户': '-13'}
        temp = {}
        a_interfaces = AINTERFACES()
        for k, user_id in acc.items():
            for w, v in {5: "逐仓", 6: "全仓"}.items():
                logger.error(f"{w=} {user_id=} -- contract_treatybalance")
                res = await a_interfaces.contract_treatybalance(user_id=user_id, wallet=w)
                logger.error(f"{w=} {user_id=} -- contract_treatybalance {res=}")
                if 'code' not in res.keys():
                    if res.get('errno') == 0 and res.get('result', {}).get('data', []):
                        mm = {i['symbol']: sum([float(j.get('balance', 0)) for j in i['status_list'] if j['status_text'] == '可用']) for i in res['result']['data']}
                    else:
                        mm = {}
                else:
                    self.error.append(f'{user_id}|{v}')
                    mm = {}
                temp[f'{user_id}|{v}'] = {k: v for k, v in mm.items() if v}

        return temp

    async def wallet_profit(self):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        this_month_start, this_day_start = self.get_monthstart_daystart()
        START_AMOUNT_SPOT, START_AMOUNT_CONTRACT = await infor_start_amount.get_start_amount()
        # df_spot = await self.get_spot_wallet(START_AMOUNT_SPOT)
        df_spot = pd.DataFrame()
        df_contract = await self.get_contract_wallet(START_AMOUNT_CONTRACT) # 这个是做市账户每个交易对的余额
        df = pd.concat([df_contract, df_spot])
        special = await self.contract_special_acc()
        if self.error:
            sendmessage.send_telegram_msg(f'合约盈亏接口报错{self.error}', 'contract_ProfitLoss')
            sys.exit()
        temp = []
        for i in range(len(df)):
            symbol = df['symbol'].iloc[i]
            if symbol in symbols_contract:
                tmp = collections.OrderedDict()
                now_amount = df['now_amount'].iloc[i]
                start_amount = df['start_amount'].iloc[i]
                tmp['time'] = now
                tmp['symbol'] = symbol
                tmp['now_amount'] = now_amount
                tmp['start_amount'] = start_amount
                tmp['差值|wallet'] = now_amount - start_amount
                special_amount = 0
                for k, v in special.items():    # 这是什么数据？穿仓+盈亏中间账户的可用金额
                    tmp[k] = v.get(symbol, 0)
                    special_amount += v.get(symbol, 0)
                tmp['差值'] = tmp['差值|wallet'] + special_amount
                # print(f"now_amount: {now_amount} start_amount: {start_amount} special_amount:{special_amount} 77777777777777777777")
                # print(tmp['差值'])
                temp.append(tmp)
        df = pd.DataFrame(temp)
        title = ','.join([f"`{w}`" for w in df.columns])
        values = ','.join([str(tuple(i)) for i in df.values])
        sql = f"insert ignore into contract_profitloss ({title}) values {values}"
        # await G_MysqlSession.insert_sql(sql)
        
        # df['base'], df['quote'] = df['symbol'].str.split('-', -1).str
        # df['quote'][df['quote'].isnull()] = df['base'][df['quote'].isnull()]
        # date = df.groupby(['quote'])['差值'].sum().reset_index()
        # profit_loss = dict(zip(date['quote'], date['差值']))
        # return profit_loss
        print(f"日期:{this_day_start}")
        sql_profit_loss = f"select time,sum(`差值`) as usdt from contract_profitloss where time < 'this_condition_start_time'  group by time order by time desc limit 1;"
        re_zone, title = await G_MysqlSession.fetch_all(sql=sql_profit_loss.replace('this_condition_start_time', this_day_start))
        re_month, title = await G_MysqlSession.fetch_all(sql=sql_profit_loss.replace('this_condition_start_time', this_month_start))
        profit_loss_all = df['差值'].sum()

        # # 结算的盈亏
        # settle, settle_title = await G_MysqlSession.fetch_all(sql="select time,coin,amount from exchange_transfer_profit where type='contract'")
        # settle_today = sum([i[2] for i in settle if str(i[0]) > this_day_start])
        # settle_month = sum([i[2] for i in settle if str(i[0]) > this_month_start])
        # settle_all = sum([i[2] for i in settle])
        settle_today = settle['today']
        settle_month = settle['month']
        settle_all = settle['all']
        
        # profit_loss_all是穿仓+盈亏中间账户的可用金额,
        mess = f'【合约】{now} ({int(sleep_timeout / 60)}min/次)\n' \
               f'当日盈亏:{int(profit_loss_all - re_zone[0][1] + settle_today)}U\n' \
               f'当月盈亏:{int(profit_loss_all - re_month[0][1] + settle_month)}U\n' \
               f'累计盈亏:{int(profit_loss_all)}U ({int(profit_loss_all + settle_all)}U)'
        # sendmessage.send_telegram_msg(mess, 'contract_ProfitLoss')
        # sendmessage.send_telegram_msg(mess, 'spot_contract_profitLoss')

        return {'time': now, 'profit_loss': {'all': int(profit_loss_all),
                                             'month': int(profit_loss_all - re_month[0][1] + settle_month),
                                             'today': int(profit_loss_all - re_zone[0][1] + settle_today),
                                             'settle_all': int(settle_all),
                                             }}

    async def get_settle(self):
        # 结算的盈亏
        this_month_start, this_day_start = self.get_monthstart_daystart()
        settle, settle_title = await G_MysqlSession.fetch_all(sql="select time,coin,amount from exchange_transfer_profit where type='contract'")
        settle_today = sum([i[2] for i in settle if str(i[0]) > this_day_start])
        settle_month = sum([i[2] for i in settle if str(i[0]) > this_month_start])
        settle_all = sum([i[2] for i in settle])
        return {'all': settle_all, 'month': settle_month, 'today': settle_today}

    # def run_web(self):
    #     # 监控盈亏发送的数据
    #     # sql = 'select time , round(sum(差值)) from wallet_profit_loss  group by time order by time desc limit 50 ;'
    #     # results, title = get_data.read_mysql_Con(rds_db='contract_monitor', sql=sql)
    #     # results = sorted(results, key=lambda x: x[0])
    #     # time_now = results[-1][0]
    #     # uset_now = results[-1][1]
    #     # profit_loss_today = uset_now - uset_zero
    #     #
    #     # results.append([profit_loss_today, uset_now])
    #     # mess_quant_web = json.dumps(results)
    #     # # print(mess_quant_web)
    #     # monitor.get_a_monitor(event_name='hy_hedge_chart', msg=mess_quant_web)
    #     ids = infor_contract.acc_id_contract
    #     time_last_day = setting_quant.timestamp_to_timearray(int(time.time() - 19 * 60 * 60))
    #     sql = f"select DATE_FORMAT( ts ,'%Y-%m-%d %H') time,sum(ProfitLoss)*(-1) ProfitLoss  from con_orders where ts >'{time_last_day}' and User_id not in {tuple(ids)}  group by  DATE_FORMAT(ts ,'%Y-%m-%d %H');"
    #     results, title = get_data.read_mysql_Con(rds_db='contract_monitor', sql=sql)
    #     results = list(results)[1:]
    #     results.append(['Abc量化订单盈亏', '｜每小时盈亏'])
    #     mess_quant_web = json.dumps(results)
    #     monitor.get_a_monitor(event_name='hy_hedge_chart', msg=mess_quant_web)

    async def contract_run(self):
        try:
            res = await self.wallet_profit()
            await heartbeat.i_live_well(server='合约盈亏监控', frequency=60 * 60 * 2, index=34)
            return res
        except Exception as e:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            sendmessage.send_telegram_msg(message=f'{now} | error：con_wallet_profit {traceback.format_exc()}', ser='Alarm')
            logger.error(f'con_wallet_profit -->> {traceback.format_exc()}')

    async def get_profit_all(self):
        global settle
        settle = await self.get_settle()
        res_wallet = await self.contract_run()
        res_order = await contract_run_order()

        settle_all = settle['all']


        msg_wallet = [f"{res_wallet['time']}~~",
                      f"钱包:{res_wallet['profit_loss']['today']:,}",
                      f"钱包:{res_wallet['profit_loss']['month']:,}",
                      f"钱包:{res_wallet['profit_loss']['all']:,}",
                      f"钱包:{int(res_wallet['profit_loss']['all'] + settle_all):,}"] if res_wallet else ["", "", "", "", ""]

        msg_order = [f"{res_order['time']}",
                     f"订单:{res_order['profit_loss']['today']:,}",
                     f"订单:{res_order['profit_loss']['month']:,}",
                     f"订单:{int(res_order['profit_loss']['all'] - settle_all):,}",
                     f"订单:{res_order['profit_loss']['all']:,}"] if res_order else ["", "", "", "", ""]

        msg_title = ["时间:", "当日盈亏 ", "当月盈亏 ", "累积盈亏 ", '总计(+提币) ']
        mess_quant_web = ""
        if res_wallet or res_order:
            msg = "【合约】"
            for i in range(5):
                msg += f"`\n{msg_title[i]} {msg_order[i]}`"
                # msg += f"`\n{msg_title[i]} {msg_wallet[i].ljust(13, ' ')} {msg_order[i]}`"

            mess_quant_web = msg
            sql = f"insert into spot_contract_pnl (`category`,`wallet`,`order`,`detail`) values ('contract','{res_wallet['profit_loss']['today']}','{res_order['profit_loss']['today']}','{mess_quant_web}')"
            logger.info(sql)
            await G_MysqlSession.insert_sql(sql=sql)
            sendmessage.send_telegram_msg_mdv2(msg, 'spot_ProfitLoss')
            # sendmessage.send_telegram_msg(msg, 'spot_contract_profitLoss')
        monitor.get_a_monitor(event_name='hy_profit_loss', msg=mess_quant_web)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(con_wallet_profit().get_profit_all())
