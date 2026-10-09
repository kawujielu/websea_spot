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
from config import infor_contract, monitor
from exchange.restful_api.abc_interfaces import AINTERFACES

acc_id = infor_contract.acc_id_contract

PROFITLOSS_ALL = 50
PROFITLOSS = 50
VOL = 10000
msg_len = 3500
a_interfaces = AINTERFACES()


def get_num(amount):
    if abs(amount) > 100:
        amount = f"{int(amount):,}"
    elif abs(amount) > 10:
        amount = f"{round(amount, 2):,}"
    elif round(abs(amount), 3) > 0:
        amount = f"{round(amount, 3):,}"
    else:
        amount = "-"
    return amount


async def get_con_fee():
    time_zero, date_zero_time = get_time.ATime().today_zero()

    nowtime = datetime.datetime.now()
    now = nowtime.strftime('%Y-%m-%d %H:%M:%S')
    mess_quant_web = ""
    if nowtime.hour == 0 and abs(date_zero_time - time.time()) < 60 * 2:
        date_zero_time = date_zero_time - 24 * 60 * 60
        time_zero = get_time.ATime().timestamp_to_timearray(date_zero_time)
    # userid_futurefee = [str(i) for i in (await a_interfaces.userid_futurefee())['result']]

    # sql = f"""SELECT user_id,symbol,fee,profitLoss,amount,facevalue,price,ordersource from contract_mongoorders WHERE ts >"{time_zero}" and user_id in {tuple(acc_id)} """
    sql = f"""SELECT symbol,type,count(distinct `order`) order_num,sum(profitLoss) profitLoss,sum(amount*facevalue) amount,sum(amount*price*facevalue) amountQuote from contract_mongoorders WHERE ts >"{time_zero}" and user_id in {tuple(acc_id)} group by symbol,type"""
    print('acc_id', acc_id)
    print('sql', sql)
    mm, title = await G_MysqlSession.fetch_all(sql)
    if mm:
        df = pd.DataFrame(mm, columns=title)
        symbols = df['symbol'].unique()
        df['coef'] = 1
        # 开多+，平多- 、开空-，平空+
        df['coef'][df['type'].isin(['平多', '开空'])] = -1
        # df['net_amount'] = df['amount'] * df['coef']
        # df['net_amountQuote'] = df['amountQuote'] * df['coef'] * (-1).__int__()
        df['amountQuote'] = df['amountQuote'].astype(int)
        df['profitLoss'] = df['profitLoss'].astype(int)
        df['amount'] = df['amount'].__round__(2)
        df1 = df.groupby(['symbol'])[['order_num', 'profitLoss', 'amount', 'amountQuote']].sum().reset_index()
        df1 = df1.iloc[df1[['profitLoss', 'amountQuote']].abs().sum(axis=1).sort_values().index]
        print(df1)

        length = {}

        length['coin'] = max([len(s.split('-')[0]) for s in df1['symbol'].unique()] + [len(['coin'])])
        length['order_num'] = max(2, len('orderNum'))
        length['profitLoss'] = max([len(get_num(s)) for s in df1['profitLoss'].unique()] + [len(['盈利'])])
        length['amount'] = max([len(get_num(s)) for s in df1['amount'].unique()] + [len(['amount'])])
        length['amountQuote'] = max([len(get_num(s)) for s in df1['amountQuote'].unique()] + [len(['vol'])])

        msg = ""
        for i in range(len(df1)):
            symbol = df1['symbol'].iloc[i]
            coin = symbol.split('-')[0]
            order_num = df1['order_num'].iloc[i]
            profitLoss = get_num(df1['profitLoss'].iloc[i])
            amount = get_num(df1['amount'].iloc[i])
            amountQuote = get_num(df1['amountQuote'].iloc[i])
            msg += f"""`{coin.center(length['coin'], " ")} {str(order_num).center(length['order_num'], " ")} {str(amount).ljust(length['amount'], " ")} {str(amountQuote).ljust(length['amountQuote'], " ")} {str(profitLoss).center(length['profitLoss'], " ")}` \n"""

        if msg:
            msg = f"""{now}-{time_zero}\n*`{"coin".center(length['coin'], " ")} {"数".center(length['order_num'], " ")} {"amount".ljust(length['amount'], " ")} {"vol".ljust(length['amountQuote'], " ")} {"盈利".rjust(length['profitLoss'], " ")}`* \n""" + msg

            sendmessage.send_telegram_msg_mdv2(f'{msg}', ser='quant_deal_history')


async def contract_run():
    try:
        await get_con_fee()
        logger.info(f"合约费用统计-量化账户 ok")
    except:
        mm = traceback.format_exc()
        sendmessage.send_telegram_msg(f'合约费用统计-量化账户\n{mm}', ser='Alarm')
        logger.error(f" error:合约费用统计-量化账户")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(contract_run())
