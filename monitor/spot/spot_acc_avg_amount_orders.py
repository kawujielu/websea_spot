# coding=utf-8
import time, asyncio
import pandas as pd
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spot.spot_setting import getRate
from libs.database.getmysql import G_MysqlSession
from libs import heartbeat, sendmessage
from libs.get_time import ATime

sleep_timeout = 60 * 5


def get_Date(df):
    if not df.empty:
        df = df.groupby(['symbol'])[['amount', 'amountQuote']].sum().reset_index()
    return df


async def run(COEF, CNY):
    rate = await getRate(['BTC-USDT', 'ETH-USDT'])
    now_ts = time.time()
    MIN_TIME = 60 * 20
    last_time = ATime().timestamp_to_timearray(int(now_ts - MIN_TIME))
    last_week = ATime().timestamp_to_timearray(int(now_ts - 60 * 60 * 24 * 8))
    last_day = ATime().timestamp_to_timearray(int(now_ts - 60 * 60 * 24 * 1))
    # sql = f"select * from mongoorders where ts >'{last_week}';"
    sql = f"select * from mongoorders where symbol in (select symbol from mongoorders where ts > '{last_time}' group by symbol) and ts >'{last_week}';"
    re, title = await G_MysqlSession.fetch_all(sql=sql)
    df = pd.DataFrame(list(re), columns=title)

    df['amount'] = df['amount'].abs()
    df['amountQuote'] = df['amountQuote'].abs()
    df_last_week = df[df['ts'] <= last_day]
    df_last_now = df[df['ts'] >= last_day]
    print('week', df_last_week)
    print('now', df_last_now)
    df_last_week = get_Date(df_last_week)
    df_last_now = get_Date(df_last_now)

    df_last_now['rate'] = None
    for i in range(len(df_last_now)):
        curr = df_last_now['symbol'].iloc[i].split('-')[1]
        df_last_now['rate'].iloc[i] = float(rate[curr + '-USDT'])

    if not df_last_week.empty and not df_last_now.empty:
        dff = pd.merge(df_last_now, df_last_week, how='left', on=['symbol'])
        dff = dff.fillna(0)
        dff['cny'] = dff['amountQuote_x'] * dff['rate']
        dff['coef'] = dff['amount_x'] / (dff['amount_y'] / 7)
        dff = dff[(dff['cny'] > CNY) & (dff['coef'] >= COEF)]

        if dff.empty:
            print('----------empty-----------')
        else:
            dff = dff.sort_values(by=["cny"], ascending=True)
            mess = f"【现货】{int(MIN_TIME / 60)}min内有交易的交易对。当前1天的成交量与历史一周日均成交量对比。({int(sleep_timeout / 60)})min/s\n成交量>{int(CNY)}U,倍数>{COEF}倍\n"
            for i in range(len(dff)):
                symbol = dff['symbol'].iloc[i]
                amount = round(dff['amount_x'].iloc[i], 2)
                amount_last = round(dff['amount_y'].iloc[i] / 7, 2)
                cny = int(dff['cny'].iloc[i])
                coef = round(dff['coef'].iloc[i], 2)
                mess += f"【{symbol}】\n" \
                        f"近1天成交量：{amount}\n" \
                        f"近1周日均量：{amount_last}\n" \
                        f"USDT：{cny}({coef}倍)\n\n"
            sendmessage.send_telegram_msg(message=mess, ser='spot_info')
    elif df_last_week.empty and not df_last_now.empty:

        df_last_now['cny'] = df_last_now['amountQuote'] * df_last_now['rate']
        dff = df_last_now[df_last_now['cny'] > CNY]
        if not dff.empty:
            dff = dff.sort_values(by=["cny"], ascending=True)
            mess = f"【现货】20min内有交易的交易对。当前1天的成交量。一周内没有成交量 ({int(sleep_timeout / 60)}min/s)\n成交量>{CNY}U\n"
            for i in range(len(dff)):
                symbol = dff['symbol'].iloc[i]
                amount = round(dff['amount'].iloc[i], 2)
                cny = round(dff['cny'].iloc[i], 2)
                amountQuote = round(dff['amountQuote'].iloc[i] / 7, 2)
                mess += f"【{symbol}】\n" \
                        f"近1天成交量：{amount}\n" \
                        f"U：{cny}U\n\n"
            sendmessage.send_telegram_msg(message=mess, ser='spot_info')


async def spot_run():
    while True:
        try:
            await run(COEF=10, CNY=1000)
            await heartbeat.i_live_well(server='Abc成交量监控', frequency=60 * 15, index=30)
            await asyncio.sleep(sleep_timeout)
        except Exception as e:
            print('error : acc_avg_amount_oders')
            sendmessage.send_telegram_msg(message='error : acc_avg_amount_oders',
                                          ser='Alarm')
            await asyncio.sleep(sleep_timeout / 2)


if __name__ == "__main__":
    asyncio.run(spot_run())
