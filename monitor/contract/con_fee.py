# coding=utf-8
import pandas as pd
import datetime, time, asyncio
import traceback
from datetime import timedelta
from loguru import logger
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs.database.getmysql import G_MysqlSession
from libs import get_time, heartbeat, sendmessage
from bson.objectid import ObjectId
from config import infor_contract,monitor
from exchange.restful_api.abc_interfaces import AINTERFACES

acc_id = infor_contract.acc_id_contract

PROFITLOSS_ALL = 500
PROFITLOSS = 500
VOL = 10000
msg_len = 3500
a_interfaces = AINTERFACES()


async def get_con_fee():
    time_zero, date_zero_time = get_time.ATime().today_zero()

    nowtime = datetime.datetime.now()
    now = nowtime.strftime('%Y-%m-%d %H:%M:%S')
    mess_quant_web = ""
    if nowtime.hour == 0 and abs(date_zero_time - time.time()) < 60 * 2:
        date_zero_time = date_zero_time - 24 * 60 * 60
        time_zero = get_time.ATime().timestamp_to_timearray(date_zero_time)

    # time_zero = '2023-06-23 00:00:00'
    userid_futurefee = [str(i) for i in (await a_interfaces.userid_futurefee())['result']]

    sql = f"""SELECT user_id,symbol,fee,profitLoss ,amount,facevalue,price,ordersource from contract_mongoorders WHERE ts >"{time_zero}" and user_id not in {tuple(acc_id + userid_futurefee)} """
    mm, title = await G_MysqlSession.fetch_all(sql)
    if mm:
        df = pd.DataFrame(mm, columns=title)
        user_all = df['user_id'].unique()
        symbols_all = df['symbol'].unique()
        df['vol'] = df['amount'] * df['facevalue'] * df['price']
        # ordersource_all = df['profitLoss'][df['ordersource'] == '爆仓'].sum()
        msg = f"💰*合约交易信息总汇*💰\n" \
              f"{now}-{time_zero}\n" \
              f"交易对累积成交额:{VOL}U 交易对累积盈亏>{PROFITLOSS_ALL}U abs(某币对某用户盈利)>{PROFITLOSS}U\n" \
              f"*用户盈亏:{int(df['profitLoss'].sum())}U 手续费:{round(df['fee'].sum(), 2)}U 成交量:{int(df['vol'].sum())}U 人数:{len(user_all)} 币对:{len(symbols_all)}*\n"

        df1 = df.groupby(['symbol'])[['fee', 'profitLoss', 'vol']].sum().reset_index()
        df1 = df1.sort_values(by=["profitLoss"], ascending=True)
        for j in range(len(df1)):
            s = df1['symbol'].iloc[j]
            fee_s = df1['fee'].iloc[j]
            vol_s = df1['vol'].iloc[j]
            profitLoss_s = df1['profitLoss'].iloc[j]
            df2 = df[df['symbol'] == s]
            df2 = df2.groupby(['user_id'])[['fee', 'profitLoss', 'vol']].sum().reset_index()
            df2 = df2.sort_values(by=["profitLoss"], ascending=True)
            user_s = df2['user_id'].unique()
            df2 = df2[(abs(df2['profitLoss']) >= PROFITLOSS_ALL) | (df2['vol'] >= VOL)]
            msg_d = ""
            if not df2.empty:
                msg_d += f"【{s}】盈亏:{int(profitLoss_s)}U 手续费:{round(fee_s, 2)}U 量:{int(vol_s)}U 人数:{len(user_s)}\n"
                for i in range(len(df2)):
                    user_id = df2['user_id'].iloc[i]
                    fee = df2['fee'].iloc[i]
                    profitLoss = df2['profitLoss'].iloc[i]
                    vol = df2['vol'].iloc[i]
                    if abs(profitLoss) >= PROFITLOSS:
                        msg_d += f"         -  id:{user_id}:盈亏:{int(profitLoss)}U 手续费:{round(fee, 2)}U 量:{int(vol)}U \n"

                if len(msg) < msg_len and len(msg) + len(msg_d) < msg_len:
                    msg += msg_d
                elif len(msg) < msg_len and len(msg) + len(msg_d) > msg_len:
                    sendmessage.send_telegram_msg_mdv2(message=msg, ser='contract_info')
                    msg = msg_d
        if msg:
            sendmessage.send_telegram_msg_mdv2(message=msg, ser='contract_info')
            mess_quant_web = msg
        monitor.get_a_monitor(event_name='hb_open_close_amount', msg=mess_quant_web)

async def contract_run():
    try:
        await get_con_fee()
        await heartbeat.i_live_well(server='合约费用统计', frequency=60 * 60 * 2, index=35)
        logger.info(f"合约费用统计 ok")
    except:
        mm = traceback.format_exc()
        sendmessage.send_telegram_msg(f'合约费用统计\n{mm}', ser='Alarm')
        logger.error(f" error:合约费用统计")


if __name__ == "__main__":
    # asyncio.run(contract_run())
    loop = asyncio.get_event_loop()
    loop.run_until_complete(contract_run())
