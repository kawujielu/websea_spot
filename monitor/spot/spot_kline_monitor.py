import os
import sys
import time
import datetime
import requests
import asyncio
import traceback

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
sys.path.append(PROJECT_ROOT)

import exchange.restful_api.abc_spot as spot_api


class Strategy:

    def __init__(self):
        # self.rest = spot_api.AApi(
        #     "dfab8bd76d7fea39e4aa6af328cbd187",
        #     "l8nemtb6r1diqmksp721"
        # )
        self.black_list = ['MULTI-USDT']
        pass

    async def main(self):
        # while 1:
        try:
            await self.check_symbol()
            await self.run()
        except:
            print(f"报错:{traceback.format_exc()}")
        # await asyncio.sleep(1800)
    
    async def check_symbol(self):
        # 获取所有现货交易对
        rest = spot_api.AApi("key", "secret")
        res = await rest.symbols()
        symbol_list = [i['symbol'] for i in res['result']]

        # 只取正在运行的交易对
        run_symbol_list = []
        for s in symbol_list:
            rest = spot_api.AApi("key", "secret")
            res = await rest.depth(s)
            if res['result']['bids'] != [] and res['result']['asks'] != [] and s not in self.black_list:
                if s in ['EURR-USDT', 'USDR-USDT']:
                    continue
                run_symbol_list.append(s)
            await asyncio.sleep(0.1)
        self.run_symbols = run_symbol_list
        print(f"总共{len(symbol_list)}个交易对,正在运行{len(run_symbol_list)}个交易对")
    
    async def run(self):
        # 成交间隔时间间隔
        trade_mess = ""
        for s in self.run_symbols:
            rest = spot_api.AApi("key", "secret")
            res = await rest.trades(symbol=s, size=3)
            deal_ts_list = [int(time.time())]
            for i in res['result']['data']:
                deal_ts_list.append(int(i['ts']))
            for prev, curr in zip(deal_ts_list, deal_ts_list[1:]):
                if abs(curr - prev) > 300:
                    if s not in trade_mess:
                        trade_mess += f"现货{s}成交时间间隔{abs(curr - prev)}秒\n"
            await asyncio.sleep(0.1)
        trade_mess = trade_mess if trade_mess else "现货所有交易对刷量正常\n"
        print(trade_mess)

        # K线监控
        kline_mess = ""
        for s in self.run_symbols:
            rest = spot_api.AApi("key", "secret")
            res = await rest.kline(symbol=s, period='15m', size=4)
            count = 0
            k_err = 0
            if res['result']:
                for i in res['result']['data']:
                    count += int(i['count'])
                    if float(i['open']) == float(i['close']) == float(i['low']) == float(i['high']):
                        k_err += 1
                if count <= 2 or k_err >= 2:
                    kline_mess += f"现货{s}K线数据异常,近1h成交{count}笔,连续{k_err}根15min K线走平\n"
            await asyncio.sleep(0.1)
        kline_mess = kline_mess if kline_mess else "现货所有交易对K线数据正常"
        print(kline_mess)
        # 当前时间
        hour = datetime.datetime.now().hour
        time_tag = False
        if hour in [8, 16, 0]:
            time_tag = True
        if "正常" in trade_mess and "正常" in kline_mess and not time_tag:
            return
        error_mess = trade_mess + kline_mess
        # 发送TG报警
        TOKEN = "6431006677:AAFPjHsu3ZiowA8vyKYPmK8-b-XSPnBUu3Q"
        CHAT_ID = "-5146526727"
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {
            "chat_id": CHAT_ID,
            "text": error_mess,
        }
        res = requests.post(url, data=data)
        print(res.json())

        # 成交量和成交笔数监控  只有一条数据,无法判断
        # trade_mess = ""
        # for s in symbol_list:
        #     rest = spot_api.AApi("key", "secret")
        #     res = await rest.market_24kline(symbol=s)
        #     {'errno': 0, 'errmsg': 'success', 'result': {'id': 1772268143, 'amount': '22524.144699589317622952', 'count': 52485, 'open': '67926.3', 'close': '63717.7', 'low': '63049.3', 'high': '68145.6', 'vol': '1475432900.481179999999818669'}}


if __name__ == '__main__':
    asyncio.run(Strategy().main())
