# coding=utf-8
import traceback
import pandas as pd
import time, asyncio
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libs import heartbeat, sendmessage, requestSession
from contract import contract_setting
from config import infor_contract, monitor, infor_load

SYMBOL_PRO = {'BTC-USDT': 0.008, 'ETH-USDT': 0.008}
SYMBOL_PRO_OTHER = 0.02
url = infor_load.contract_host + '/qapi-v1/market/kline'
sleep_timeout = 60 * 5
period = '5min'
a = 0.005
KLINE_LEVEL = {
    1: 0.02,
    3: 0.04 + a,
    5: 0.065 + a,
    10: 0.09 + a
}

KLINE_LEVEL = {k: round(v + 0.005, 3) for k, v in KLINE_LEVEL.items()}


def get_level(level):
    for k, v in KLINE_LEVEL.items():
        if level <= k:
            return v


async def getklinepro():
    symbols = contract_setting.get_symbols()
    t = time.time() - 5 * 60
    temp = []
    error = ""
    for symbol in symbols:
        data = {
            'symbol': symbol,
            'period': period,
            'size': 2
        }
        async with requestSession.G_RequestSession.request.get(url=url, params=data, timeout=10) as r:
            res = await r.json()
            if res.get('errno') == 0 and res['result']['ts'] and float(res['result']['ts']) > t and res['result']['data']:
                res = res['result']['data'][-1]
                side = 1 if float(res['close']) >= float(res['open']) else -1
                res['symbol'] = symbol
                # res['pro'] = (float(res['high']) / float(res['low']) - 1) * side
                res['pro'] = (1 - float(res['low']) / float(res['high'])) if float(res['close']) <= float(res['open']) else (float(res['high']) / float(res['low']) - 1)
                level = infor_contract.SYMBOLS_CONTRACT_PAIR_DANGEROUS_LEVEL.get(symbol, 3)
                pro = get_level(level)
                res['level'] = level
                res['PRO'] = SYMBOL_PRO.get(symbol, pro if pro else 0.001)
                temp.append(res)
            elif res.get('errno') and res.get('errno') != 0 and not res['result']['data']:
                error += f"{symbol} {res}\n"
    if error:
        sendmessage.send_telegram_msg(message=f"【合约】k线报错:\n{error}", ser='kline')

    df = pd.DataFrame(temp)
    df['time'] = pd.to_datetime(df['id'] + 8 * 3600, unit='s')
    df = df[['time', 'symbol', 'pro', 'PRO', 'level']][abs(df['pro']) > df['PRO']]
    # mes = '5minK线,值班人员注意是否有异常(如插针,价格波动较大等),如有异常及时通知相关负责人\n' \
    #       '项目方的币或者非主流币,注意价格和成交量是否异常(变化较大),如有异常及时通知风控部门\n'
    mes = ""
    mess_quant_web, mess_quant_web_Emerg = "", ""

    if not df.empty:
        for i in range(len(df)):
            symbol = df['symbol'].iloc[i]
            curr = symbol.split('-')[0]
            if symbol not in infor_contract.SYMBOLS_CONTRACT_PAIR:
                side = '[项目方]'
                continue
            else:
                side = ''
            pro = round(df['pro'].iloc[i] * 100, 2)
            PRO = round(df['PRO'].iloc[i] * 100, 2)
            level = df['level'].iloc[i]
            mes += f"{symbol} pro:{pro}%(>{PRO}% 等级:{level}){side}\n"
            mess_quant_web += f"<b style='color:#FF0000'>{symbol}</b> pro:{pro}%(>{PRO}%){side}<br>"
        if mes != "":
            mes = f"【合约】{period} k线波动较大 ({int(sleep_timeout / 60)}min/次)\n" + mes
            sendmessage.send_telegram_msg(message=mes, ser='kline')

        # df_emergency = df[['time', 'symbol', 'pro']][abs(df['pro']) > 0.5]
        SYMBOL = ['BTC-USDT']
        df_emergency = df[['time', 'symbol', 'pro']][((~df['symbol'].isin(SYMBOL)) & (abs(df['pro']) > 0.3)) | (df['symbol'].isin(SYMBOL))]
        if df_emergency.empty:
            print("acc_kline| 暂无异常1")
        else:
            mes_alarm = f'【合约】{period}k线\n'
            for i in range(len(df_emergency)):
                symbol = df_emergency['symbol'].iloc[i]
                curr = symbol.split('-')[0]
                if curr in infor_contract.SYMBOLS_LIST_PROJECT:
                    side = '[项目方]'
                else:
                    side = ''
                pro = round(df_emergency['pro'].iloc[i] * 100, 2)
                mes_alarm += f"{symbol} pro:{pro}%{side}\n"
            # sendmessage.send_telegram_msg(message=mes_alarm, ser='kline')

    monitor.get_a_monitor(event_name='kline', msg=mess_quant_web)


async def contract_run():
    while True:
        try:
            await getklinepro()
            await heartbeat.i_live_well(server='合约5minK线', frequency=60 * 11, index=31)
            print('ok')
        except Exception as e:
            error_msg = f"con_acc_kline {traceback.format_exc()}"
            sendmessage.send_telegram_msg(message=f'{error_msg}', ser='Alarm')
        finally:
            await asyncio.sleep(sleep_timeout)


if __name__ == '__main__':
    asyncio.run(contract_run())
