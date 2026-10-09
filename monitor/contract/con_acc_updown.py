# coding=utf-8
import asyncio
import copy
import traceback
import loguru

import pandas as pd
import time, datetime, json, requests
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import infor_contract, infor_load
from libs import heartbeat, sendmessage

symbols_out = infor_contract.SYMBOLS_CONTRACT_OUT
Ups_Downs_PRO = 0.25
sleep_timeout = 60 * 10


def ups_downs(last_up_down, start_time):
    url = infor_load.web_url_perp
    html = requests.get(url, timeout=5).json()
    df = pd.DataFrame(html['result'])
    data = df[~df["name"].isin(symbols_out)]
    data[u'increase1'] = data[u'increase'].str.strip('%').astype(float) / 100
    data['symbol'] = data['currency'] + '-' + data['tradeCurrency']
    df = data[(abs(data['increase1']) > Ups_Downs_PRO) & (data['symbol'].isin(infor_contract.SYMBOLS_CONTRACT_PAIR))]
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    end_time = time.time()
    if not df.empty:
        df = df.reindex(df['increase1'].abs().sort_values(ascending=True).index)
        df_up_down = dict(zip(df['symbol'], df['increase']))
        increase = set(df_up_down.keys()) - set(last_up_down.keys())
        reduce = set(last_up_down.keys()) - set(df_up_down.keys())
        df_up_down_dict = dict(zip(df['symbol'], df['increase1']))
        up_down_dict = [df_up_down_dict.get(s, 0) / last_up_down.get(s, 0) for s in df_up_down if last_up_down.get(s)]
        if increase or reduce or any(v > 2 or v < 0.5 for v in up_down_dict) or abs(end_time - start_time) >= 60 * 60:
            message = f'{now}\n【合约】涨跌幅超过{Ups_Downs_PRO * 100}%,请相关同事注意.({int(sleep_timeout / 60)}min/次)\n{df_up_down}'
            sendmessage.send_telegram_msg(message, ser='kline')
            last_up_down = copy.deepcopy(df_up_down_dict)
            start_time = copy.deepcopy(end_time)

    # btc usdt 紧急预警 -------------------------------------------------------------------
    BTCPRO = 0.06
    USDTPRO = 0.02
    PROBTCUSDT = [{'currency': 'BTC', 'pro': BTCPRO, 'tradeCurrency': 'USDT'},
                  {'currency': 'USDT', 'pro': USDTPRO, 'tradeCurrency': 'USDT'}]
    df_pro = pd.DataFrame(PROBTCUSDT)
    df_btc_usdt = pd.merge(data, df_pro, on=['currency', 'tradeCurrency'], how='inner')
    df_btc_usdt = df_btc_usdt[abs(df_btc_usdt['increase1']) >= df_btc_usdt['pro']]
    if not df_btc_usdt.empty:
        df_btc_usdt['symbol'] = df_btc_usdt['currency'] + '/' + df_btc_usdt['tradeCurrency']
        df_btc_usdt = df_btc_usdt.reindex(df['increase1'].abs().sort_values(ascending=True).index)
        df_btc_usdt_dict = dict(zip(df_btc_usdt['symbol'], df_btc_usdt['increase']))
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        message = f"【合约】{now} ({int(sleep_timeout / 60)}min/次)\n涨跌幅超过「BTC:{BTCPRO * 100}%,USDT:{USDTPRO * 100}%」,请相关同事注意.\n{df_btc_usdt_dict}"
        sendmessage.send_telegram_msg(message, ser='kline')
    print(f'{now} | 合约 A_ups_down wait {sleep_timeout}')
    return last_up_down, start_time


async def contract_run():
    last_up_down = {}
    start_time = time.time()
    while True:
        try:
            last_up_down, start_time = ups_downs(last_up_down, start_time)
            await heartbeat.i_live_well(server='合约涨跌服务监控', frequency=60 * 21, index=36)
            await asyncio.sleep(sleep_timeout)
        except Exception as e:
            msg = f'contract_run A_ups_down\n{traceback.format_exc()}'
            loguru.logger.error(msg)
            sendmessage.send_telegram_msg(msg, ser='Alarm')
            await asyncio.sleep(sleep_timeout / 3)


if __name__ == '__main__':
    asyncio.run(contract_run())
