# coding=utf-8
import pandas as pd
import datetime, time, asyncio
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs import heartbeat, sendmessage
from libs.database.getmysql import G_MysqlSession
from spot.spot_setting import getRate, get_symbols
from config import infor, infor_load, monitor
from pymongo import MongoClient

# 不提示警告
pd.set_option('mode.chained_assignment', None)
volumeIds = infor_load.volume_ids


async def get_strategy():
    LEN = 2
    CNY = 100

    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(time.time() - 60 * 15)))
    Aid_strategy = {v['id']: v['Purpose'] for k, v in infor.spot_account.items() if 'volume' in v['Purpose']}

    Aid = list(Aid_strategy.keys())
    rate = await getRate(['USDT-USDT'])
    df_rate = []
    for symbol, amount in rate.items():
        df_rate.append({'currency': symbol, 'rate': float(amount)})
    df_rate = pd.DataFrame(df_rate)
    sql = f"select id,Aid,substring_index(symbol,'-',-1) as currency,symbol ,COUNT(DISTINCT `order`) len,sum(abs(amount)) amount,sum(abs(amountQuote)) amountQuote from mongoorders where Aid in ({','.join([str(i) for i in Aid])}) and ts >'{ts}' group by id,Aid,symbol;"

    results, title = await G_MysqlSession.fetch_all(sql=sql)
    df = pd.DataFrame(list(results), columns=title)
    df['currency'] = df['currency'] + '-USDT'
    df = pd.merge(df, df_rate, left_on=['currency'], right_on=['currency'], how='left')
    df['cny'] = df['amountQuote'] * df['rate']
    df = df[((df['Aid'].isin(volumeIds) & (df['len'] > LEN)) | ((~df['Aid'].isin(volumeIds)) & (df['cny'] > CNY)))]
    mess = ''
    if not df.empty:
        A_id = df['Aid'].unique()
        for aid in A_id:
            df_aid = df[df['Aid'] == aid]
            aid = int(aid)
            mess += f'------【{aid}:{Aid_strategy[aid]}】------\n'
            for i in range(len(df_aid)):
                symbol = df_aid['symbol'].iloc[i]
                id = df_aid['id'].iloc[i]
                count = df_aid['len'].iloc[i]
                amount = round(df_aid['amount'].iloc[i], 2)
                amountQuote = int(df_aid['amountQuote'].iloc[i])
                cny = int(df_aid['cny'].iloc[i])
                # mess += f'{id, symbol, count, amount, amountQuote}\n'
                mess += f'【{symbol}:{id}】\n' \
                        f'订单数:{count}\n' \
                        f'amount:{amount}\n' \
                        f'amountQuote:{amountQuote}\n' \
                        f'cny:{cny}\n'
    mess_quant_web = ""
    if mess != '':
        message = f'【现货】10min,刷量策略订单数超过{LEN},其他策略成交量超过{CNY}U\n' + mess
        sendmessage.send_telegram_msg(message=message,
                                      ser='spot_ProfitLoss')
        mess_quant_web = message.replace('\n', '<br>')
    monitor.get_a_monitor(event_name='strategy_monitor', msg=mess_quant_web)


async def get_data_profit(sql, rate):
    results, title = await G_MysqlSession.fetch_all(sql=sql)
    df = pd.DataFrame(list(results), columns=title)

    df['当前价格'] = None
    df['盈亏'] = None
    df['盈亏|cny'] = None

    for i in range(len(df)):
        symbol = df['symbol'].iloc[i]
        curr1, curr2 = symbol.split('-')
        df['当前价格'].iloc[i] = float(rate[symbol])
        now_price = df['当前价格'].iloc[i]
        avg_price = df['净成交均价'].iloc[i]
        amount = df['净成交|base'].iloc[i]
        amount_quote = df['净成交|quote'].iloc[i]
        if amount != 0:
            profit = (now_price - avg_price) * amount
        else:
            profit = amount_quote
        df['盈亏'].iloc[i] = profit
        df['盈亏|cny'].iloc[i] = int(profit * float(rate[curr2 + '-USDT']))

    return df


async def get_symbol_profit(rate, ts, PROFIT):
    sql = f"SELECT symbol,COUNT(DISTINCT  `order`) '成交次数' ,COUNT(DISTINCT id) '用户数',COUNT(DISTINCT DATE_FORMAT( ts ,'%Y-%m-%d')) '天数'," \
          f" SUM(amount) as '净成交|base',SUM(amountQuote) '净成交|quote',SUM(amountQuote)/SUM(amount)*(-1) '净成交均价'," \
          f"round(SUM(abs(amount))) as '总投资|base',round(SUM(abs(amountQuote))) '总投资|quote' from mongoorders " \
          f"where ts>'{ts}' GROUP BY symbol;"
    df = await get_data_profit(sql, rate)
    df = df[df['盈亏|cny'] > PROFIT * 10000]
    df = df.sort_values(by=["盈亏|cny"], ascending=True)
    return df


async def get_symbol_profit_id():
    PROFIT = 0.5  # 按照W计算
    DAY = 1

    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(time.time() - DAY * 24 * 60 * 60)))
    symbols = get_symbols()
    rate = await getRate(SYMBOLS_PAIR_USDT=symbols)
    df = await get_symbol_profit(rate, ts, PROFIT)
    if df.empty:
        print('------------empty-----------')
    else:
        symbol_tuple = tuple(df['symbol'])
        sql_id = f"SELECT id,symbol,COUNT(DISTINCT  `order`) '成交次数' ,SUM(amount) as '净成交|base',SUM(amountQuote) '净成交|quote'," \
                 f"SUM(amountQuote)/SUM(amount)*(-1) '净成交均价',round(SUM(abs(amount))) as '总投资|base'," \
                 f"round(SUM(abs(amountQuote))) '总投资|quote' from mongoorders where ts>'{ts}' and symbol in {symbol_tuple}" \
                 f" GROUP BY id,symbol;"
        df_ids = await get_data_profit(sql_id, rate)
        df_ids = df_ids.sort_values(by=['symbol', "盈亏|cny"], ascending=False)
        df_ids['id'] = df_ids['id'].astype(str)
        message = ""
        for i in range(len(df)):
            symbol = df['symbol'].iloc[i]
            count = df['成交次数'].iloc[i]
            user = df['用户数'].iloc[i]
            amount = round(df['净成交|base'].iloc[i], 2)
            side = 'buy' if amount > 0 else 'sell'
            amount_all = round(df['总投资|base'].iloc[i], 2)
            amount_all_quote = round(df['总投资|quote'].iloc[i], 2)
            avg_price = round(df['净成交均价'].iloc[i], 2)
            profit = int(df['盈亏'].iloc[i])
            cny = int(df['盈亏|cny'].iloc[i])
            pro = round(profit / amount_all_quote * 100, 2)
            df_id = df_ids[df_ids['symbol'] == symbol].iloc[:3]

            id = dict(zip(df_id['id'], df_id['盈亏|cny']))
            message += f"【{symbol}】\n" \
                       f"交易人数:{user}\n" \
                       f"交易次数:{count}\n" \
                       f"净成行为:{side}\n" \
                       f"净成交量:{amount}\n" \
                       f"总投资:{amount_all}\n" \
                       f"成交均价：{avg_price}\n" \
                       f"盈亏cny:{cny}\n" \
                       f"盈亏占比:{pro}%\n" \
                       f"IDS:{id}\n\n"

        if message != '':
            message = f"【现货】过去{DAY}天，盈利超过{PROFIT}W的交易对\n" + message
            sendmessage.send_telegram_msg(message=message,
                                          ser='spot_ProfitLoss')


async def spot_run():
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        MINUTE = datetime.datetime.now().minute
        HOUR = datetime.datetime.now().hour
        await get_strategy()
        if HOUR / 2 == 0 and MINUTE == 30:
            await get_symbol_profit_id()
        await heartbeat.i_live_well(server='现货交易', frequency=60 * 60 * 2, index=31)
        print(f'{now}|acc_orders_profit wait 2h')
    except:
        sendmessage.send_telegram_msg(f'{now} | error：acc_orders_profit', ser='Alarm')
        print(f'{now} | error : acc_orders_profit ')


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(spot_run())
    # asyncio.run(spot_run())
