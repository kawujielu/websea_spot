# coding=utf-8
import asyncio
import pandas as pd
import copy, time, datetime
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs.database.getmysql import G_MysqlSession
from libs import heartbeat, sendmessage, get_time
from config import infor, monitor
from spot import spot_setting

# 不提示警告
pd.set_option('mode.chained_assignment', None)

acc_id = infor.acc_id
sleep_timeout = 60 * 5
monitor_d = {'1H': 'bb1h', '10min': 'bb10min'}


async def data_profit(now, LEN, PROFIT1, PROFIT, H, TIME):
    ts = int(time.time() - TIME * 2 * 60)
    ts = get_time.ATime().timestamp_to_timearray(ts)
    # sql = f"select A.id,A.symbol ,amountSell 'amountSell|base',amountQuoteSell 'amountSell|quote',amountQuoteSell/amountSell 'rateSell|base_quote', lenSell ,amountBuy 'amountBuy|base' ,amountQuoteBuy 'amountBuy|quote'," \
    #       f"amountQuoteBuy/amountBuy 'rateBuy|base_quote',lenBuy ,amountQuoteSell/amountSell-amountQuoteBuy/amountBuy '已实现盈亏/每枚币|quote'," \
    #       f"LEAST(amountBuy,amountSell)*(amountQuoteSell/amountSell-amountQuoteBuy/amountBuy) '已实现盈亏|quote',amountSell-amountBuy '未实现盈亏枚数|base',amountQuoteSell+amountQuoteBuy 'amountVol|quote',lenSell+lenBuy 'len' " \
    #       f"from" \
    #       f"(select id ,symbol ,abs(sum(amount)) amountSell,abs(sum(amountQuote)) amountQuoteSell,count(amount) lenSell from mongoorders where amount<0  and ts >='{ts}' group by id,symbol ) as A," \
    #       f"(select id ,symbol,abs(sum(amount)) amountBuy ,abs(sum(amountQuote)) amountQuoteBuy,count(amount) lenBuy from mongoorders where amount>0 and ts >='{ts}'  group by id,symbol ) as B " \
    #       f"where A.id = B.id and A.symbol = B.symbol  ;"
    # print(sql)
    sql = f"select id ,symbol,side ,abs(sum(amount)) amount,abs(sum(amountQuote)) amountQuote,count(amount) len from mongoorders where ts >='{ts}' group by id,symbol,side"
    results, title = await G_MysqlSession.fetch_all(sql=sql)
    temp = pd.DataFrame(list(results), columns=title, )

    if not temp.empty:

        temp['rate'] = temp['amountQuote'] / temp['amount']

        temp1 = temp[temp['side'] == 'sell']
        temp2 = temp[temp['side'] == 'buy']
        temp1.rename(
            columns={'amount': 'amountsell', 'amountQuote': 'amountQuotesell', 'len': 'lensell', 'rate': 'ratesell'},
            inplace=True)
        temp2.rename(columns={'amount': 'amountbuy', 'amountQuote': 'amountQuotebuy', 'len': 'lenbuy', 'rate': 'ratebuy'},
                     inplace=True)

        temp = pd.merge(temp1, temp2, on=['id', 'symbol'], how='inner')
        temp['amountVol|quote'] = temp['amountQuotesell'] + temp['amountQuotebuy']
        temp['len'] = temp['lensell'] + temp['lenbuy']
        temp['已实现盈亏/每枚币|quote'] = temp['ratesell'] - temp['ratebuy']
        temp['未实现盈亏枚数|base'] = temp['amountsell'] - temp['amountbuy']
        temp['已实现盈亏枚数|base'] = 0

        mess_quant_web = ''
        if temp.empty:
            pass
        else:
            temp['rate_quote'] = 1
            rate = await spot_setting.getRate(['BTC-USDT', 'ETH-USDT'])
            for i in range(len(temp)):
                symbol = temp['symbol'].iloc[i].split('-')[1]
                temp['rate_quote'].iloc[i] = float(rate[symbol + '-USDT'])
                temp['已实现盈亏枚数|base'].iloc[i] = min(temp['amountsell'].iloc[i], temp['amountbuy'].iloc[i])

            temp['已实现盈亏|quote'] = temp['已实现盈亏枚数|base'] * temp['已实现盈亏/每枚币|quote']
            temp['已实现盈亏|U'] = temp['已实现盈亏|quote'] * temp['rate_quote']
            temp = temp.sort_values(by=["已实现盈亏|U"], ascending=False)
            df = copy.deepcopy(temp)
            print(df.columns)
            # 高频套利--temp---------------------------------------------------------------------------------------------------------
            # print(temp)
            temp = temp[((temp['len'] > LEN) & (temp['已实现盈亏|U'] > PROFIT1)) | (temp['已实现盈亏|U'] > PROFIT)]
            mes = ''
            if len(temp) > 0:
                for i in range(len(temp)):
                    id = int(temp['id'].iloc[i])
                    symbol = temp['symbol'].iloc[i]
                    lenSell = int(temp['lensell'].iloc[i])
                    lenBuy = int(temp['lenbuy'].iloc[i])
                    sell_amount = round(temp['amountsell'].iloc[i], 2)
                    buy_amount = round(temp['amountbuy'].iloc[i], 2)
                    profit = round(temp['已实现盈亏|U'].iloc[i], 2)
                    mes += f"● id:{id}\n" \
                           f"   【{symbol}】\n" \
                           f"    卖:{sell_amount}个({lenSell}次)\n" \
                           f"    买:{buy_amount}个({lenBuy}次)\n" \
                           f"   已实现盈利U:{profit}U\n\n"
                    mess_quant_web += f"<b style='color:#FF0000'>{symbol} {id}</b><br>" \
                                      f"&emsp;S:{sell_amount} B:{buy_amount}<br>" \
                                      f"&emsp;LEN S:{lenSell} B:{lenBuy}<br>" \
                                      f"&emsp;盈利U:{profit}<br>"
                mess_quant_web = f"<b style='color:#0000CD'>--------现货-{H}-----------</b><br>" + mess_quant_web
                message = f"【现货】{H}。1、LEN>{LEN}次 and 盈利>{PROFIT1}U);2、盈利>{PROFIT}U\n{mes}"
                sendmessage.send_telegram_msg(message=message, ser='spot_info')
        monitor.get_a_monitor(event_name=monitor_d[H], msg=mess_quant_web)

        #     # 三角套利--df--------------------------------------------------------------------------------------------------
        #     # df['base'], df['quote'] = df['symbol'].str.split('-')
        #     df[['base', 'quote']] = df['symbol'].str.split('-', expand=True)
        #     df_all = df.groupby(['id', 'base'])['len'].sum().reset_index()
        #     df_all = df_all[(df_all['len'] > LEN) & (~df_all['id'].isin(['1456624']))]
        #     if not df_all.empty:
        #         mess = ""
        #         for i in range(len(df_all)):
        #             id = df_all['id'].iloc[i]
        #             symbol_base = df_all['base'].iloc[i]
        #             df1 = df[(df['base'] == symbol_base) & (df['id'] == id)]
        #             mess += f"【{symbol_base}】-id:{int(id)}\n"
        #             for j in range(len(df1)):
        #                 mess += f"{df1['symbol'].iloc[0]} 买:{round(df1['amountsell'].iloc[j], 2)}个({df1['lensell'].iloc[j]}次) 卖:{round(df1['amountbuy'].iloc[j], 2)}个({df1['lenbuy'].iloc[j]}次)\n"
        #         print(mess)
        #         if mess != '':
        #             message = f"【现货】疑似高频交易,请排查一下。{H},LEN>{LEN}次\n" + mess
        #             sendmessage.send_telegram_msg(message=message, ser='spot_info')
        # event_name = 'bb5to10min' if H == '10min' else 'bb1to2h'
        # monitor.get_a_monitor(event_name=event_name, msg=mess_quant_web)
        print(f'{now} |  高频交易-现货  wait {H}')


async def run(now):
    # now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    hour_stamp = int(time.time() - time.time() % (60 * 60))
    now_stamp = int(time.time())  # 当前时间
    await data_profit(now=now, LEN=5, PROFIT1=0.5, PROFIT=100, H='10min', TIME=7.5)
    if abs(hour_stamp - now_stamp) < 60 * 5:
        await data_profit(now=now, LEN=30, PROFIT1=3, PROFIT=500, H='1H', TIME=60)


async def spot_run():
    while True:
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            await run(now)
            await heartbeat.i_live_well(server='现货高频监控', frequency=60 * 16, index=31)
            print('现货高频监控 ok')
            await asyncio.sleep(sleep_timeout)
        except Exception as e:
            print(f'{now} | error : 高频交易-现货 {e}')
            sendmessage.send_telegram_msg(f'{now} | error：高频交易-现货 ', 'Alarm')

            await asyncio.sleep(sleep_timeout / 2)


if __name__ == '__main__':
    asyncio.run(spot_run())
