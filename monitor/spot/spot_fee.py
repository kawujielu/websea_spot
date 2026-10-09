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
from spot.spot_setting import getRateUsdt
from bson.objectid import ObjectId
from config import infor_contract, monitor

acc_id = infor_contract.acc_id_contract


# 添加过滤条件成交量>1000u 或者成交人数>15人。 id 只按照成交量最多展示top3


async def get_con_fee(AMOUNT_U, USER_LEN):
    time_zero, date_zero_time = get_time.ATime().today_zero()
    nowtime = datetime.datetime.now()
    now = nowtime.strftime('%Y-%m-%d %H:%M:%S')

    if nowtime.hour == 0:
        date_zero_time = date_zero_time - 24 * 60 * 60
        time_zero = get_time.ATime().timestamp_to_timearray(date_zero_time)

    sql = f"""SELECT id user_id,symbol,sum(abs(amountQuote)) amountQuote,sum(feeQuote) feeQuote from mongoorders WHERE ts >"{time_zero}" and id not in {tuple(acc_id)} group by id,symbol """
    mm, title = await G_MysqlSession.fetch_all(sql)
    mess_quant_web = ""
    if mm:
        df = pd.DataFrame(mm, columns=title)
        df[['base', 'quote']] = df['symbol'].str.split('-', expand=True)

        rate_usdt = await getRateUsdt([f'{i}-USDT' for i in df['quote'].unique()])
        df_rate = pd.DataFrame([{'quote': k, 'QuoteUsdt': v} for k, v in rate_usdt.items()])
        df = pd.merge(df, df_rate, on=['quote'], how='left')
        df['vol'] = df['amountQuote'] * df['QuoteUsdt']
        df['fee'] = df['feeQuote'] * df['QuoteUsdt']

        user_all = df['user_id'].unique()
        symbols_all = df['symbol'].unique()

        msg = f"💰*现货交易信息总汇*💰\n" \
              f"{now}-{time_zero}\n" \
              f"*手续费:{int(df['fee'].sum())}U 成交量:{int(df['vol'].sum())}U 成交人数:{len(user_all)} 交易对:{len(symbols_all)}*\n" \
              f"添加过滤条件成交量>{AMOUNT_U}u 或者成交人数>{USER_LEN}人。 id 只按照成交量最多展示top3\n"

        df1 = df.groupby(['symbol'])[['fee', 'vol']].sum().reset_index()
        df1 = df1.sort_values(by=["vol"], ascending=False)
        for j in range(len(df1)):
            s = df1['symbol'].iloc[j]
            fee_s = df1['fee'].iloc[j]
            vol_s = int(df1['vol'].iloc[j])
            df2 = df[df['symbol'] == s]
            df2 = df2.groupby(['user_id'])[['fee', 'vol']].sum().reset_index()
            df2 = df2.sort_values(by=["vol"], ascending=False)
            user_s = len(df2['user_id'].unique())
            if vol_s >= AMOUNT_U or user_s >= USER_LEN:
                msg += f"【{s}】手续费:{int(fee_s)}U 成交量:{vol_s}U 成交人数:{user_s}\n"
                for i in range(len(df2)):
                    user_id = df2['user_id'].iloc[i]
                    fee = df2['fee'].iloc[i]
                    vol = df2['vol'].iloc[i]
                    msg += f"         -  id:{user_id} 手续费:{int(fee)}U 成交量:{int(vol)}U \n"
                    if i >= 2:
                        break
        print(msg)
        sendmessage.send_telegram_msg_mdv2(message=msg, ser='spot_info')
        mess_quant_web = msg
    monitor.get_a_monitor(event_name='bb_freeze', msg=mess_quant_web)


async def spot_run():
    try:
        await get_con_fee(AMOUNT_U=1000, USER_LEN=15)
        await heartbeat.i_live_well(server='现货费用统计', frequency=60 * 60 * 2, index=35)
        logger.info(f"现货费用统计 ok")
    except:
        mm = traceback.format_exc()
        sendmessage.send_telegram_msg(f'现货费用统计\n{mm}', ser='Alarm')
        logger.error(f" error:现货费用统计")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(spot_run())
