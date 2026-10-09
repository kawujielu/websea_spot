# coding=utf-8
import time, datetime
import pandas as pd
import urllib3
import asyncio
import traceback
from loguru import logger
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.infor_contract import acc_id_contract
from libs.database.getmysql import G_MysqlSession
from libs import sendmessage, heartbeat, get_time
from config import monitor
from exchange.restful_api.abc_interfaces import AINTERFACES

# 不提示警告
pd.set_option('mode.chained_assignment', None)

acc_id = acc_id_contract
sleep_timeout = 60 * 20
a_interfaces = AINTERFACES()
monitor_d = {'10min': 'hy10m', '2hour': 'hy2h', '24hour': 'hy1d'}


def today_zero():
    today_data = datetime.datetime.now().date()
    date_zero_time = int(time.mktime(today_data.timetuple()))
    day_time = time.localtime(date_zero_time)
    time_zero = time.strftime('%Y-%m-%d %H:%M:%S', day_time)
    return time_zero


async def data_profit(hour, LENGTH, VOLAMOUNT, PROFITLOSS, userid_futurefee):
    delay_ts = 5 * 60
    mess_quant_web = ""
    if 'min' in hour:
        ts = int(time.time() - 60 * float(hour.replace('min', '')) - delay_ts)
    else:
        ts = int(time.time() - 60 * 60 * float(hour.replace('hour', '')) - delay_ts)
    dt = get_time.ATime().timestamp_to_timearray(ts)

    sql = f"""SELECT COUNT(DISTINCT `order`) len,user_id ,symbol,type,sum(amount*facevalue) amount,sum(amount*facevalue*price) amountQuote,SUM(profitLoss) profitLoss FROM contract_mongoorders 
              WHERE ts > "{dt}" and user_id not in {tuple(acc_id_contract + userid_futurefee)} GROUP BY user_id ,symbol,type"""
    results, title = await G_MysqlSession.fetch_all(sql)

    msg = ""
    msg_title = f"""👍*合约 过去{hour} 成交次数>{LENGTH}次 or 累计成交额>{int(VOLAMOUNT)}U or 盈亏>{PROFITLOSS}U ({int(sleep_timeout / 60)}min/次)*\n"""
    if results:
        data = pd.DataFrame(results, columns=title)
        data = data.sort_values(by=["profitLoss"], ascending=True)
        df = data.groupby(['symbol', 'user_id'])[['amount', 'amountQuote', 'profitLoss', 'len']].sum().reset_index()
        temp = df[(df['len'] > LENGTH) | (df['amountQuote'] > VOLAMOUNT) | (df['profitLoss'] > PROFITLOSS)]
        if not temp.empty:
            symbols = temp['symbol'].unique()
            for s in symbols:
                df1 = temp[temp['symbol'] == s]
                ids = df1['user_id'].unique()
                msg += f" 【{s}】\n"
                for id in ids:
                    df2 = data[(data['user_id'] == id) & (data['symbol'] == s)]
                    df2 = df2.sort_values(by=["type"], ascending=False)
                    msg += f"         - user_id:{id}\n"
                    for i in range(len(df2)):
                        type = df2['type'].iloc[i]
                        amount = df2['amount'].iloc[i]
                        amountQuote = df2['amountQuote'].iloc[i]
                        profitLoss = df2['profitLoss'].iloc[i]
                        l = df2['len'].iloc[i]
                        msg += f"               {type}:{round(amount, 4)} (盈利:{int(profitLoss)}U、成交额:{int(amountQuote)}U、{l}次)\n"
                if len(msg) > 3500:
                    sendmessage.send_telegram_msg_mdv2(message=msg_title + msg, ser='contract_info_user')
                    msg = ""
        if msg:
            sendmessage.send_telegram_msg_mdv2(message=msg_title + msg, ser='contract_info_user')
            mess_quant_web = msg_title + msg
    monitor.get_a_monitor(event_name=monitor_d[hour], msg=mess_quant_web)
    return msg


async def contract_run():
    while True:
        try:
            userid_futurefee = [str(i) for i in (await a_interfaces.userid_futurefee())['result']]
            msg1 = await data_profit(hour='10min', LENGTH=20, VOLAMOUNT=10000, PROFITLOSS=100, userid_futurefee=userid_futurefee)
            msg2 = await data_profit(hour="2hour", LENGTH=50, VOLAMOUNT=10 * 10000, PROFITLOSS=500, userid_futurefee=userid_futurefee)
            msg3 = await data_profit(hour="24hour", LENGTH=100, VOLAMOUNT=80 * 10000, PROFITLOSS=1000, userid_futurefee=userid_futurefee)
            msg = msg1 + msg2 + msg3
            # if msg:
            #     sendmessage.send_telegram_msg_mdv2(message=msg, ser='contract_info_user')

            logger.info(f'高频交易-合约  wait 1 h')
            await heartbeat.i_live_well(server='合约高频交易', frequency=60 * 60 * 1, index=35)
            time.sleep(sleep_timeout)
        except Exception as e:
            sendmessage.send_telegram_msg(message=f'error：高频交易-合约 {e}', ser='Alarm')
            time.sleep(sleep_timeout / 10)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(contract_run())
