import asyncio
import math
import json
import requests
from datetime import datetime
import sys, os

file = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(file)
from config.infor_load import spot_host
from libs.requestSession import G_RequestSession
from config.infor import SYMBOLS_LIST, SYMBOLS_PAIR
from config.infor_contract import SYMBOLS_CONTRACT_PAIR
from libs import heartbeat, sendmessage

SYMBOLS = SYMBOLS_LIST
ERROR = []
PRECISION_EXCHANGE_PRICE = {}
PRECISION_EXCHANGE = {}

path = sys.path[0]
filename = f'{path}/spot_exchange_symbols.json'


class BinanceApi():
    def __init__(self, ):
        self.ex = 'bn'

    async def get_precision(self):
        precision_list = {}
        url = f'https://api.binance.com/api/v3/exchangeInfo'
        try:
            async with G_RequestSession.request.get(url=url, timeout=10) as r:
                res = await r.json()
                for i in res['symbols']:
                    if i['status'] in ['TRADING', 'PENDING_TRADING']:
                        precision = {}
                        for j in i['filters']:
                            if j['filterType'] == 'PRICE_FILTER':
                                precision['minPrice'] = float(j['minPrice'])
                                precision['price_precision'] = -math.ceil(math.log10(float(float(j['tickSize']))))

                            if j['filterType'] == 'LOT_SIZE':
                                precision['minQty'] = float(j['minQty'])
                                precision['amount_precision'] = -math.ceil(math.log10(float(float(j['stepSize']))))
                        precision_list[i['baseAsset'] + '-' + i['quoteAsset']] = precision
        except:
            ERROR.append(self.ex)

        PRECISION_EXCHANGE[self.ex] = precision_list

    async def get_precision_price(self):
        precision_list = {}
        url = 'https://api.binance.com/api/v3/ticker/price'
        try:
            async with G_RequestSession.request.get(url=url, timeout=10) as r:
                res = await r.json()
                precision_list = {i['symbol']: i['price'] for i in res}
        except:
            ERROR.append(f'{self.ex}_price')
        PRECISION_EXCHANGE_PRICE[self.ex] = precision_list


class OkexApi:
    def __init__(self, ):
        self.ex = 'okex'

    async def get_precision(self):
        precision_list = {}
        url = 'https://www.okx.com/api/v5/public/instruments?instType=SPOT'
        try:
            async with G_RequestSession.request.get(url=url, timeout=10) as r:
                res = await r.json()
                if res['code'] == '0':
                    for i in res['data']:
                        if i['state'] in ['live']:
                            precision = {}
                            precision['price_precision'] = -math.ceil(math.log10(float(float(i['tickSz']))))
                            precision['minQty'] = float(i['minSz'])
                            precision['amount_precision'] = -math.ceil(math.log10(float(float(i['lotSz']))))
                            # precision['amount_precision'] = -math.ceil(math.log10(float(float(i['tickSz']))))
                            precision_list[i['instId']] = precision

        except:
            ERROR.append(self.ex)
        PRECISION_EXCHANGE[self.ex] = precision_list

    async def get_precision_price(self):
        precision_list = {}
        url = 'https://www.okx.com/api/v5/market/tickers?instType=SPOT'
        try:
            async with G_RequestSession.request.get(url=url, timeout=10) as r:
                res = await r.json()
                if res['code'] == '0':
                    for i in res['data']:
                        precision_list[i['instId']] = i['last']
        except:
            ERROR.append(f'{self.ex}_price')
        PRECISION_EXCHANGE_PRICE[self.ex] = precision_list


class GateioApi:
    def __init__(self, ):
        self.ex = 'gate'

    async def get_precision(self):
        precision_list = {}
        # 交易状态 trade_status
        # - untradable: 不可交易
        # - buyable: 可买
        # - sellable: 可卖
        # - tradable: 买卖均可交易
        url = 'https://api.gateio.ws/api/v4/spot/currency_pairs'
        try:
            async with G_RequestSession.request.get(url=url, timeout=10) as r:
                res = await r.json()
                for i in res:
                    if i['trade_status'] not in ['untradable']:
                        precision_list[i['base'] + '-' + i['quote']] = {'price_precision': i['precision'], 'amount_precision': i['amount_precision']}

        except:
            ERROR.append(self.ex)
        PRECISION_EXCHANGE[self.ex] = precision_list

    async def get_precision_price(self):
        precision_list = {}
        url = 'https://api.gateio.ws/api/v4/spot/tickers'
        try:
            async with G_RequestSession.request.get(url=url, timeout=10) as r:
                res = await r.json()
                precision_list = {i['currency_pair'].replace('_', '-'): i['last'] for i in res}

        except:
            ERROR.append(f'{self.ex}_price')
        PRECISION_EXCHANGE_PRICE[self.ex] = precision_list


class HuobiApi:
    def __init__(self, ):
        self.ex = 'hb'

    async def get_precision(self):
        precision_list = {}
        url = 'https://api.huobi.pro/v1/settings/common/market-symbols'
        try:
            async with G_RequestSession.request.get(url=url, timeout=10) as r:
                res = await r.json()
                for i in res['data']:
                    if i['state'] == 'online':
                        precision_list[(i['bc'] + '-' + i['qc']).upper()] = {'price_precision': i['pp'], 'amount_precision': i['ap']}

        except:
            ERROR.append(self.ex)
        PRECISION_EXCHANGE[self.ex] = precision_list


class MexcApi:
    def __init__(self, ):
        self.ex = 'mexc'

    async def get_precision(self):
        precision_list = {}
        url = 'https://api.mexc.com/api/v3/exchangeInfo'
        try:
            async with G_RequestSession.request.get(url=url, timeout=10) as r:
                res = await r.json()
                for i in res['symbols']:
                    precision_list[i['baseAsset'] + '-' + i['quoteAsset']] = {'price_precision': i['quotePrecision'], 'amount_precision': i['baseAssetPrecision']}
        except:
            ERROR.append(self.ex)
        PRECISION_EXCHANGE[self.ex] = precision_list

    async def get_precision_price(self):
        precision_list = {}
        url = 'https://api.mexc.com/api/v3/ticker/price'
        try:
            async with G_RequestSession.request.get(url=url, timeout=10) as r:
                res = await r.json()
                precision_list = {i['symbol']: i['price'] for i in res}

        except:
            ERROR.append(f'{self.ex}_price')
        PRECISION_EXCHANGE_PRICE[self.ex] = precision_list


class BitgetApi:
    def __init__(self, ):
        self.ex = 'bitget'

    async def get_precision(self):
        # 上架状态 status
        # offline 维护
        # gray 灰度
        # online 上线
        precision_list = {}
        url = 'https://api.bitget.com/api/v2/spot/public/symbols'
        try:
            async with G_RequestSession.request.get(url=url, timeout=10) as r:
                res = await r.json()
                if float(res['code']) == 0:
                    for i in res['data']:
                        if i['status'] in ['online']:
                            precision_list[i['baseCoin'] + '-' + i['quoteCoin']] = {'price_precision': i['pricePrecision'], 'amount_precision': i['quantityPrecision']}
        except:
            ERROR.append(self.ex)
        PRECISION_EXCHANGE[self.ex] = precision_list


class BybitApi:
    def __init__(self, ):
        self.ex = 'bybit'

    async def get_precision(self):
        precision_list = {}
        url = 'https://api.bybit.com/spot/v3/public/symbols'
        try:
            async with G_RequestSession.request.get(url=url, timeout=10) as r:
                res = await r.json()
                if float(res['retCode']) == 0:
                    for i in res['result']['list']:
                        price_precision = -math.ceil(math.log10(float(float(i['minPricePrecision']))))
                        amount_precision = -math.ceil(math.log10(float(float(i['basePrecision']))))
                        precision_list[i['baseCoin'] + '-' + i['quoteCoin']] = {'price_precision': price_precision, 'amount_precision': amount_precision, }
        except:
            ERROR.append(self.ex)
        PRECISION_EXCHANGE[self.ex] = precision_list


class AbcApi:
    def __init__(self, ):
        self.ex = 'abc'

    async def get_precision(self):
        precision_list = {}
        url = spot_host + '/openApi/market/precision'
        payload = {}
        headers = {}

        try:
            async with G_RequestSession.request.get(url=url, timeout=10) as r:
                res = await r.json()
                print(res)
                if res['errno'] == 0:
                    for symbol, i in res['result'].items():
                        precision_list[symbol] = {'price_precision': i['price'],
                                                  'amount_precision': i['amount']}

        except:
            ERROR.append(self.ex)

        PRECISION_EXCHANGE[self.ex] = precision_list

    async def get_precision_price(self):
        precision_list = {}
        # url = spot_host + ''
        # try:
        #     async with G_RequestSession.request.get(url=url, timeout=10) as r:
        #         res = await r.json()
        #         if float(res['code']) == 0:
        #             precision_list = res['data']
        # except:
        #     ERROR.append(f'{self.ex}_price')
        PRECISION_EXCHANGE_PRICE[self.ex] = precision_list


async def spot_exchange_symbols():
    exchanges = {'bn': BinanceApi(),
                 'okex': OkexApi(),
                 'gate': GateioApi(),
                 'bitget': BitgetApi(),
                 'abc': AbcApi(),
                 # 'hb': HuobiApi('hb'),
                 # 'mxc': MexcApi('mxc'),
                 # 'bybit': BybitApi('bybit'),
                 }
    try:
        EXCHANGE_SYMBOLS_LAST = json.load(open(filename))
    except:
        EXCHANGE_SYMBOLS_LAST = {i: {} for i in exchanges}
        EXCHANGE_SYMBOLS_LAST['time'] = ""
        # json.dump(exchange_symbols_last, open(filename, 'w'))

    for ex, Api in exchanges.items():
        await Api.get_precision()
    if ERROR:
        mess = f'error：-->exchange spot_online_offline symbol {ERROR}'
        sendmessage.send_telegram_msg(message=mess, ser='Alarm')
        return
    PRECISION_EXCHANGE['time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    json.dump(PRECISION_EXCHANGE, open(filename, 'w'))
    last_time = EXCHANGE_SYMBOLS_LAST['time']
    now_time = PRECISION_EXCHANGE['time']
    msg = ""

    for ex, ex_symbols in PRECISION_EXCHANGE.items():
        if ex not in ['time', ]:
            if EXCHANGE_SYMBOLS_LAST.get(ex):
                online = set(ex_symbols) - set(EXCHANGE_SYMBOLS_LAST[ex])
                offline = set(EXCHANGE_SYMBOLS_LAST[ex]) - set(ex_symbols)
                if ex not in ['abc']:
                    # online = [f"{s}❗" if s in SYMBOLS_PAIR else s for s in online]
                    # offline = [f"{s}❗" if s in SYMBOLS_PAIR else s for s in offline]
                    online = [f"{s}[现|合]" if s in set(SYMBOLS_CONTRACT_PAIR) & set(SYMBOLS_PAIR) else f"{s}[合]" if s in SYMBOLS_CONTRACT_PAIR else f"{s}[现]" for s in online if s in SYMBOLS_CONTRACT_PAIR + SYMBOLS_PAIR]
                    offline = [f"{s}[现|合]" if s in set(SYMBOLS_CONTRACT_PAIR) & set(SYMBOLS_PAIR) else f"{s}[合]" if s in SYMBOLS_CONTRACT_PAIR else f"{s}[现]" for s in offline if s in SYMBOLS_CONTRACT_PAIR + SYMBOLS_PAIR]

                if online or offline:
                    msg += f"交易所：{ex}\n"
                    msg += f"      ● 上线：{'、'.join(online)}\n" if online else ""
                    msg += f"      ● 下线：{'、'.join(offline)}\n" if offline else ""
            else:
                msg += f'现货添加【{ex}】交易所上下线新币监控\n'
    if msg:
        message = f"{now_time} - {last_time}\n" \
                  f"【现货-交易对】上下线检测\n" \
                  f"其中 a-b[现] :a-b在abc现货区上线、a-b[合] :a-b在abc合约区上线。此时可以判断一下做市、对冲是否切换交易所\n{msg}"
        print(message)
        sendmessage.send_telegram_msg(message=message,
                                      ser='updata_currency')
    await heartbeat.i_live_well(server='【现货】交易所交易对上下线监控', frequency=60 * 61 * 2, index=29)


async def spot_run():
    try:
        await spot_exchange_symbols()
    except Exception as e:
        mess = f'error：-->exchange spot_online_offline symbol {e}'
        sendmessage.send_telegram_msg(message=mess, ser='Alarm')


if __name__ == '__main__':
    asyncio.run(spot_run())
