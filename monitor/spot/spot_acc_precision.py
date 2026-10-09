# coding=utf-8
import requests
import time, asyncio
import pandas as pd
import urllib3
import collections
import datetime
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import infor_load, infor, monitor
from spot.spot_setting import get_symbols
from libs import requestSession, sendmessage, heartbeat

# urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
spot_host = infor_load.spot_host

Precision_pro_max = 0.6
Precision_pro_min = 0.6
sleep_timeout = 60 * 10


async def get_depth(symbols):
    url = spot_host + '/openApi/market/depth'
    temp = {}
    for symbol in symbols:
        data = {'symbol': symbol}
        async with requestSession.G_RequestSession.request.get(url=url, params=data, timeout=15) as r:
            temp[symbol] = await r.json()
    return temp


async def get_depth_precision():
    symbols = get_symbols()
    df = await get_depth(symbols)
    precision = requests.get(url=spot_host + '/openApi/market/precision', timeout=10, verify=False).json()['result']
    price_zero = {'bids_price': [], 'asks_price': []}
    not_precision = []
    all_d = []
    for symbol in symbols:
        if symbol not in infor.SYMBOLS_OUT and symbol in infor.SYMBOLS_PAIR and "-BTC" not in symbol:
            if symbol in precision.keys():
                data = collections.OrderedDict()
                data['symbol'] = symbol
                bids_price = df[symbol].get('result', {}).get('bids', [])
                asks_price = df[symbol].get('result', {}).get('asks', [])
                data['bids_price'] = bids_price[0][0] if bids_price else 0
                data['asks_price'] = asks_price[0][0] if asks_price else 0
                data['avg'] = (float(data['asks_price']) + float(data['bids_price'])) / 2
                data['minPrice'] = float(precision[symbol]['minPrice'])
                data['maxPrice'] = float(precision[symbol]['maxPrice'])

                data['min'] = data['avg'] * (1 - 0.07)
                data['min_pro'] = (data['min'] - data['minPrice']) / data['min'] if data['min'] else 0

                data['max'] = data['avg'] * (1 + 0.07)
                data['max_pro'] = (data['maxPrice'] - data['max']) / data['max'] if data['max'] else 0

                all_d.append(data)
                # print(symbol, data)
            else:
                not_precision.append(symbol)
    price_zero['bids_price'] = [i['symbol'] for i in all_d if not i['bids_price']]
    price_zero['asks_price'] = [i['symbol'] for i in all_d if not i['asks_price']]
    df_all = pd.DataFrame(all_d)
    df_all = df_all[(df_all['bids_price'] != 0) & (df_all['asks_price'] != 0)]

    if price_zero == {'bids_price': [], 'asks_price': []}:
        pass
    else:
        # sendmessage.send_telegram_msg(f"盘口没有价格：\n{price_zero}", ser='Alarm')
        sendmessage.send_telegram_msg(f"【现货】盘口没有价格：({int(sleep_timeout / 60)}min/次)\n{price_zero}", ser='precision')
        # print('价格获取失败的：', price_zero)
    if not_precision != []:
        # sendmessage.send_telegram_msg(f"没有配置精度：\n{not_precision}", ser='Alarm')
        sendmessage.send_telegram_msg(f"【现货】没有配置精度：({int(sleep_timeout / 60)}min/次)\n{not_precision}", ser='precision')
        # print('没有配置精度：', not_precision)
    return df_all


def data_mess(df, type):
    if df.empty:
        mess = ''
    else:
        mess = '\n'
        for i in range(len(df)):
            symbol = df['symbol'].iloc[i]
            sym1, sym2 = symbol.split('-')
            if sym1 in infor.SYMBOLS_LIST_PROJECT:
                side = '[项目方]\n请和"天驱"确认后再调整'
            else:
                side = '[做市]\n"DQ"登陆后台自行调整'
            bids_price = df['bids_price'].iloc[i]
            asks_price = df['asks_price'].iloc[i]
            avg = df['avg'].iloc[i]
            minPrice = df['minPrice'].iloc[i]
            maxPrice = df['maxPrice'].iloc[i]
            min = df['min'].iloc[i]
            min_pro = round(df['min_pro'].iloc[i] * 100, 2)
            max = df['max'].iloc[i]
            max_pro = round(df['max_pro'].iloc[i] * 100, 2)
            if type == 'min':
                mes = f"➤{symbol}{side}\n该币种下跌{min_pro}%后将触碰下限！\nbids1:{bids_price}\nasks1:{asks_price}\nmin:{min}\nmax:{max}\n委托最低价:{minPrice}\n委托最高价:{maxPrice}\nmin_pro:{min_pro}%\nmax_pro:{max_pro}%\n"
                mess = mess + mes
            elif type == 'max':
                mes = f"➤{symbol}{side}\n该币种上涨{max_pro}%后将触碰上线限！\nbids1:{bids_price}\nasks1:{asks_price}\nmin:{min}\nmax:{max}\n委托最低价:{minPrice}\n委托最高价:{maxPrice}\nmin_pro:{min_pro}%\nmax_pro:{max_pro}%\n"
                mess = mess + mes
            elif type == 'both':
                mes = f"➤{symbol}{side}\n该币种下跌{min_pro}%后将触碰下限！\n该币种上涨{max_pro}%后将触碰上线限！\nbids1:{bids_price}\nasks1:{asks_price}\nmin:{min}\nmax:{max}\n委托最低价:{minPrice}\n委托最高价:{maxPrice}\nmin_pro:{min_pro}%\nmax_pro:{max_pro}%\n"
                mess = mess + mes
    return mess


async def run():
    data = await get_depth_precision()
    df_min = data[(data['max_pro'] > Precision_pro_max) & (data['min_pro'] < Precision_pro_min)]
    df_max = data[(data['max_pro'] < Precision_pro_max) & (data['min_pro'] > Precision_pro_min)]
    df_min_max = data[(data['max_pro'] < Precision_pro_max) & (data['min_pro'] < Precision_pro_min)]
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    mess = f'【现货】{now} ({int(sleep_timeout / 60)}min/次)\n！！！当前价格接近价格区间 ！！！\n！！！请登陆后台自行调整 ！！！\n'
    data_min = data_mess(df_min, 'min')
    data_max = data_mess(df_max, 'max')
    data_both = data_mess(df_min_max, 'both')
    mess_quant_web = ''
    if data_min == '' and data_max == '' and data_both == '':
        pass
    else:
        message = mess + data_min + data_max + data_both
        mess_quant_web = message
        sendmessage.send_telegram_msg(message, ser='precision')
    monitor.get_a_monitor(event_name='price_range', msg=mess_quant_web)
    print(f"{now} | A_precision wait 10 min")


async def spot_run():
    while True:
        try:
            await run()
            await heartbeat.i_live_well(server='价格区间监控', frequency=60 * 21, index=30)
            await asyncio.sleep(sleep_timeout)
        except Exception as e:
            now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            sendmessage.send_telegram_msg(f'现货 A_precision\n{e}', ser='Alarm')
            print(f'{now} | error : A_precision -->> {e}')
            await asyncio.sleep(sleep_timeout / 3)


if __name__ == '__main__':
    asyncio.run(spot_run())
