# coding=utf-8
import pandas as pd
import numpy as np
import asyncio, requests
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import infor_hedge, infor, extract_ip, infor_load
from libs import heartbeat, sendmessage
from libs.database.getmysql import G_MysqlSession
import json, datetime, sys, ccxt

path = sys.path[0]
filename = f'{path}/currency.json'

proxies = extract_ip.proxies
config_exchange = {
    # 'hb': 'huobipro',
    'bn': 'binance',
    # 'okex': 'okex5',
    # 'gateio': 'gateio',
    # 'mxc': 'mexc',
    # 'kucoin': 'kucoin',
    # 'coinbase': 'coinbase',
    # 'bitget': 'bitget',
    # 'kraken': 'kraken',
    'abc': 'abc',
}
sleep_timeout = 60 * 30


class GET_CURRENCY:
    def __init__(self):
        self.currency_last = {k: [] for k, v in config_exchange.items()}
        self.currency_now = {k: [] for k, v in config_exchange.items()}
        self.error = []

    async def last_currency1(self):
        try:
            sql = 'select exchange from exchange_online_currency;'
            results, title = await G_MysqlSession.fetch_all(sql=sql)
            if results:
                self.currency_last = json.loads(results[0][0])
        except:
            aa = {k: [] for k, v in config_exchange.items()}
            aa['time'] = ""
            self.currency_last = aa

    async def last_currency(self):
        try:
            self.currency_last = json.load(open(filename))
        except:
            self.currency_last['time'] = ""
            json.dump(self.currency_last, open(filename, 'w'))

    async def now_currency(self):
        for k, v in config_exchange.items():
            try:
                if k == 'abc':
                    url = infor_load.spot_host + '/openApi/market/precision'
                    self.currency_now[k] = infor.SYMBOLS_LIST
                elif k == 'mxc':
                    await self.get_mexc(k=k)
                else:
                    api = infor_hedge.config_exchange['hedge'][k]['apikey'] if k in ['bn', 'okex'] else {}
                    if proxies:
                        api['proxies'] = proxies
                    # self.currency_now[k] = list(getattr(ccxt, v)(api).fetch_currencies().keys())
                    res = getattr(ccxt, v)(api).fetch_currencies()
                    self.currency_now[k] = [k for k, v in res.items() if v['info']['trading']]

            except:
                print(k, 'error')
                self.error.append(k)
                self.currency_now[k] = self.currency_last[k]

        self.currency_now['time'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # mm = f"'{json.dumps(self.currency_now)}'"
        # sql = f'online exchange_online_currency set exchange={mm} where up=12'
        # print(sql)
        # get_data.commit_mysql(rds_db='spot', sql=sql)
        json.dump(self.currency_now, open(filename, 'w'))

    async def get_mexc(self, k='mexc'):
        url = "https://api.mexc.com/api/v3/exchangeInfo"
        res = requests.get(url).json()['symbols']
        # mm = [f"{i['baseAsset']}-{i['quoteAsset']}" for i in res if i['baseAsset'][-2:] not in ['3L', '3S']]
        mm = [f"{i['baseAsset']}" for i in res if i['baseAsset'][-2:] not in ['3L', '3S']]
        self.currency_now[k] = mm
        return mm

    async def run(self):

        await self.last_currency()
        await self.now_currency()
        time_last = self.currency_last['time']
        time_now = self.currency_now['time']

        msg = ""
        for ex, v in self.currency_now.items():
            if ex not in ['time']:

                if ex in self.currency_last.keys():
                    online = list(set(v) - set(self.currency_last[ex]))
                    offline = list(set(self.currency_last[ex]) - set(v))
                    if ex not in ['abc']:
                        online = [f"{s}❗" if s in infor.SYMBOLS_LIST else s for s in online]
                        offline = [f"{s}❗" if s in infor.SYMBOLS_LIST else s for s in offline]

                    if online or offline:
                        msg += f"交易所：{ex}\n"
                        msg += f"      ● 上线：{'、'.join(online)}\n" if online else ""
                        msg += f"      ● 下线：{'、'.join(offline)}\n" if offline else ""
                else:
                    msg += f'现货添加【{ex}】交易所上下线新币监控\n'
        if msg:
            message = f"{time_now} - {time_last}\n" \
                      f"【现货-交易币】上下线检测\n" \
                      f"其中 a❗表示abc已经上线了a\n{msg}"
            # sendmessage.send_telegram_msg(message=message,
            #                               ser='updata_currency')


async def spot_run():
    try:
        await GET_CURRENCY().run()
        await heartbeat.i_live_well(server='【现货】交易所新币上下线监控', frequency=60 * 61 * 2, index=29)
    except Exception as e:
        mess = f'error：-->exchange spot_online_offline currency {e}'
        sendmessage.send_telegram_msg(message=mess, ser='Alarm')


if __name__ == '__main__':
    asyncio.run(spot_run())
