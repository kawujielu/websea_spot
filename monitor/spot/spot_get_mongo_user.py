# coding=utf-8
import time, asyncio
import pandas as pd
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spot.spot_setting import getRate
from libs.database.getmysql import G_MysqlSession
from libs import heartbeat, sendmessage
from libs.get_time import ATime

sleep_timeout = 60 * 10

a_time = ATime()


async def run():
    end_time = int(time.time())
    start_time = end_time - 60 * 20

    end_time_dt = a_time.timestamp_to_timearray(end_time)
    start_time_dt = a_time.timestamp_to_timearray(start_time)

    sql = f"select symbol,id,side,sum(amount) amount,sum(amountQuote) amountQuote from mongoorders_user where ts between '{start_time_dt}' and '{end_time_dt}' GROUP BY symbol,id,side"
    results, title = await G_MysqlSession.fetch_all(sql)

    if results:
        df = pd.DataFrame(results, columns=title)
        symbols = df['symbol'].unique()

        msg = ""
        for symbol in symbols:
            msg += f"【{symbol}】\n"
            df1 = df[df['symbol'] == symbol]
            df1 = df1.reindex(df1['amountQuote'].abs().sort_values(ascending=False).index)
            for i in range(len(df1)):
                uid = df1['id'].iloc[i]
                side = df1['side'].iloc[i]
                amount = df1['amount'].iloc[i]
                amountQuote = df1['amountQuote'].iloc[i]
                msg += f"    uid:{uid} amount:{round(amount, 2)} ({side}:{int(amountQuote)})\n"

        if msg:
            mess = f"【现货】用户与交易账户的成交 ({int(sleep_timeout / 60)}min/次)\n" + msg
            sendmessage.send_telegram_msg(message=mess, ser='spot_info')


async def spot_run():
    while True:
        try:
            await run()
            await heartbeat.i_live_well(server='现货交易账户成交监控', frequency=60 * 31, index=30)

        except Exception as e:
            print(f'error:spot_get_mongo_user {e}')
            sendmessage.send_telegram_msg(message=f'error:spot_get_mongo_user {e}',
                                          ser='Alarm')

        finally:
            await asyncio.sleep(sleep_timeout)


if __name__ == "__main__":
    asyncio.run(spot_run())
