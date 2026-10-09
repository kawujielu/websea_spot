# coding=utf-8
import asyncio
import pandas as pd
import time, datetime
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs.database.getmongo import G_MysqlSession
from libs import heartbeat, sendmessage, get_time
from spot import spot_setting
from config import infor

# 不提示警告
pd.set_option('mode.chained_assignment', None)

acc_id = infor.acc_id
# 间隔时间
TIME_HOUR = 1
# 累计成交量超过的阈值
AMOUNT_ALL_CNY = 10 * 10000
# 成交量超过的阈值
AMOUNT_CNY = 10000


async def order_vol():
    end_time = time.time().__int__()
    end_time_dt = get_time.ATime().timestamp_to_timearray(end_time)
    start_time = int(end_time - TIME_HOUR * 60 * 60)
    start_time_dt = get_time.ATime().timestamp_to_timearray(start_time)

    rate = await spot_setting.getRate(['USDT-USDT', 'BTC-USDT', 'ETH-USDT'])
    rate_quote = []
    for k, v in rate.items():
        rate_quote.append({'quote': k.split('-')[0], 'rate': float(v)})
    df_rate = pd.DataFrame(rate_quote)

    # demand = {'ts': {'$gte': start_time, '$lt': end_time}}
    # re, re1, data = await getMongo.AbcAssetPosition.asset_position_process_volume(demand, acc_id)
    sql = f"SELECT *,substring_index(symbol,'-',-1) quote,substring_index(symbol,'-',1) base  from mongoorders where ts > '{start_time_dt}'"
    result, titile = await G_MysqlSession.fetch_all(sql)
    df = pd.DataFrame(list(result), columns=titile)
    # df['用户投注'], df['赔率'] = df['odds_name'].str.split(' ', 1).str

    if not df.empty:
        df = pd.merge(df, df_rate, how='left', on=['quote'])
        df['total_u'] = df['rate'] * abs(df['amountQuote'])
        df['amount_abs'] = abs(df['amount'])
        df['amountquote_abs'] = abs(df['amountQuote'])

        df1 = df.groupby(['symbol'])[['total_u', 'amount_abs', 'amount', 'amountquote_abs']].sum().reset_index()
        # df1 = df.groupby(['symbol']).agg({'total_u': 'sum','amount':'sum',}).reset_index()
        df1 = df1[df1['total_u'] > AMOUNT_ALL_CNY]

        if df1.empty:
            print(f'{TIME_HOUR}小时内累计成交量没有超过{int(AMOUNT_ALL_CNY / 10000)}w')
        else:
            df1 = df1.sort_values(by=["total_u"], ascending=False)
            mes = f'现货{TIME_HOUR}小时累计成交量超过{int(AMOUNT_ALL_CNY / 10000)}wU\n' \
                  f'量化账户：正:buy，负:sell\n'
            for i in range(len(df1)):
                mes += 'symbol:{}\n 成交量:{}\n 累计成交量:{}\n 累计成交量CNY:{}\n'.format(df['symbol'].iloc[i],
                                                                                           round(df['amount_abs'].iloc[i], 2),
                                                                                           round(df['amountquote_abs'].iloc[i], 2),
                                                                                           round(df['total_u'].iloc[i], 2),
                                                                                           )

            syms = set(df['symbol'])
            df2 = df[df['symbol'].isin(list(syms))]
            df2 = df2.groupby(['symbol', 'id'])[[
                'total_u', 'amount_abs', 'amount', 'amountquote_abs']].sum().reset_index()

            df2 = df2[df2['total_u'] >= AMOUNT_CNY]
            df2 = df2.sort_values(by=["total_u"], ascending=False)

            if df2.empty:
                print(f'{TIME_HOUR}小时累计成交量超过{int(AMOUNT_CNY / 10000)}w，但是单个用户成交量没有超过10w')
                message = mes
            else:
                mess = f'单个账户，{TIME_HOUR}小时成交量超过{int(AMOUNT_CNY / 10000)}w\n'
                for i in range(len(df2)):
                    id = df2['id'].iloc[i]
                    symbol = df2['symbol'].iloc[i]
                    total_u = df2['total_u'].iloc[i]
                    df3 = df[(df['symbol'] == symbol) & (df['id'] == id)]
                    df3 = df3.groupby(['side'])['total_u', 'amount', 'amountQuote'].sum().reset_index()
                    mm = ''
                    for j in range(len(df3)):
                        side = "S" if df3['side'].iloc[j] == 'sell' else "B"
                        amount = df3['amount'].iloc[j]
                        amountQuote = df3['amountQuote'].iloc[j]
                        mm = "      {}:{}   [{}U]\n".format(side, round(amount, 2), round(amountQuote, 2))

                    mess += f"● ID:{id}\n" \
                            f"  【{symbol}】\n" + mm

                message = mes + '=' * 30 + '\n' + mess
                sendmessage.send_telegram_msg(message=message,
                                              ser='spot_info')


async def spot_run():
    try:
        await order_vol()
        await heartbeat.i_live_well(server='订单成交量监控', frequency=2.5 * 60 * 60, index=32)
        print('订单成交量监控 , ok')

    except Exception as e:
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sendmessage.send_telegram_msg(f'{now} | error：get_Mongo_Order {e}', 'Alarm')
        print(f'{now} | error : get_Mongo_Order {e}')


if __name__ == '__main__':
    asyncio.run(spot_run())
