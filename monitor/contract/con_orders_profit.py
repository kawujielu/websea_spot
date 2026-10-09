# coding=utf-8
import time
import pandas as pd
import asyncio
from loguru import logger
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import monitor
from config.infor_contract import acc_id_contract
from libs.database.getmongo import G_MysqlSession
from libs import sendmessage, heartbeat, get_time
from exchange.restful_api.abc_interfaces import AINTERFACES

# 不提示警告
pd.set_option('mode.chained_assignment', None)

acc_id = acc_id_contract
sleep_timeout = 60 * 10
a_interfaces = AINTERFACES()


async def data_profit(m, PRPFITLOSS, user_fee):
    if 'min' in m:
        ts = int(time.time() - 60 * int(m.replace('min', '')))
    elif 'hour' in m:
        ts = int(time.time() - 60 * 60 * int(m.replace('hour', '')))
    else:
        ts = int(time.time() - 60 * 60 * int(m.replace('day', '')))
    ts = get_time.ATime().timestamp_to_timearray(ts)

    sql = f"select user_id,symbol,type,sum(amount*facevalue) amount,sum(amount*facevalue*price) amountQuote,round(sum(profitLoss)) profitLoss,ordersource from contract_mongoorders " \
          f"where  ts >= '{ts}' and user_id not in {tuple(acc_id_contract + user_fee)} group by user_id,symbol,type,ordersource;"
    results, title = await G_MysqlSession.fetch_all(sql)
    temp = pd.DataFrame(results, columns=title)
    df_all = temp.groupby(['user_id', 'symbol'])['profitLoss'].sum().reset_index()
    df_all = df_all[df_all['profitLoss'] >= PRPFITLOSS]
    df_all = df_all.sort_values(by=["profitLoss"], ascending=True)
    mess = ""
    mess_quant_web = ""
    if not df_all.empty:
        temp = temp.sort_values(by=["type"], ascending=False)
        for i in range(len(df_all)):
            User_id = df_all['user_id'].iloc[i]
            symbol = df_all['symbol'].iloc[i]
            ProfitLoss = df_all['profitLoss'].iloc[i]
            df = temp[(temp['user_id'] == User_id) & (temp['symbol'] == symbol)]
            mess += f'【{symbol}-{User_id}】盈利:{int(ProfitLoss)}\n'
            mess_quant_web += f"<b style='color:#FF0000'>{symbol} {User_id} {ProfitLoss}</b><br>"
            for j in range(len(df)):
                ContractType = df['type'].iloc[j]
                Amount = df['amount'].iloc[j]
                Profit = df['profitLoss'].iloc[j]
                ProfitLoss = f'盈利：{Profit}' if ContractType not in ['开空', '开多'] else ''
                mess += f'      {ContractType}:{Amount} {ProfitLoss}\n'
                mess_quant_web += f"&emsp;{ContractType}:{Amount} {ProfitLoss}<br>"

        mess_quant_web = f"<b style='color:#000000'>--------合约-{m}H-----------</b><br>" + mess_quant_web
        message = f'➤【合约】过去{m} 盈利超过{PRPFITLOSS}️U, {m}/次\n' + mess
        sendmessage.send_telegram_msg(message=message, ser='contract_info_user')

    mess_quant_web_hy_liquidate = ""
    df1 = temp[temp['ordersource'] == '爆仓']
    if not df1.empty:
        msg = f"💥💥💥【合约】过去{m} 爆仓用户如下\n"
        df1 = df1.groupby(['user_id', 'symbol'])['profitLoss'].sum().reset_index()
        df2 = df1.sort_values(by=["user_id"], ascending=True)
        for i in range(len(df2)):
            uid = df2['user_id'].iloc[i]
            symbol = df2['symbol'].iloc[i]
            profitLoss = df2['profitLoss'].iloc[i]
            msg += f"uid:{uid} symbol:{symbol} 盈亏:{int(profitLoss)}U\n"
        sendmessage.send_telegram_msg(message=msg, ser='contract_info_user')
        mess_quant_web_hy_liquidate = msg
    monitor.get_a_monitor(event_name='hy_liquidate', msg=mess_quant_web_hy_liquidate)
    # event_name = 'hy1h' if m == 60 else 'hy1d'
    # monitor.get_a_monitor(event_name=event_name, msg=mess_quant_web)


async def contract_run():
    start_time = 0
    userid_futurefee = []
    while True:
        try:
            if time.time() - start_time >= 60 * 60 * 24:
                userid_futurefee = [str(i) for i in (await a_interfaces.userid_futurefee())['result']]
                start_time = time.time()
            await data_profit(m="10min", PRPFITLOSS=500, user_fee=userid_futurefee)
            await heartbeat.i_live_well(server='合约用户盈利', frequency=60 * 30, index=35)
            logger.info(f'con_orders_profit  wait 5min')
            await asyncio.sleep(sleep_timeout)
        except Exception as e:
            sendmessage.send_telegram_msg(message=f'error：合约用户盈利 {e}', ser='Alarm')
            logger.info(f'error : con_orders_profit {e}')
            await asyncio.sleep(sleep_timeout / 3)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(contract_run())
