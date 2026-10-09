import asyncio
import math
import sys, os

file = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(file)

from scaffold.aiohttp import G_RequestSession
from many_configs import global_variable


class BinanceApi():
    def __init__(self):
        self.ex = 'bn'

    async def get_precision(self):
        precision_list = {}
        url = f'https://api.binance.com/api/v3/exchangeInfo'
        try:
            async with G_RequestSession.request.get(url=url, timeout=10) as r:
                res = await r.json()
                for i in res['symbols']:
                    precision = {}
                    for j in i['filters']:
                        if j['filterType'] == 'PRICE_FILTER':
                            precision['minPrice'] = float(j['minPrice'])
                            precision['price_precision'] = -math.ceil(math.log10(float(float(j['tickSize']))))

                        if j['filterType'] == 'LOT_SIZE':
                            precision['minQty'] = float(j['minQty'])
                            precision['amount_precision'] = -math.ceil(math.log10(float(float(j['stepSize']))))

                        if j['filterType'] == 'NOTIONAL':
                            precision['minQtyQuote'] = float(j['minNotional'])

                    precision_list[i['baseAsset'] + '-' + i['quoteAsset']] = precision
        except:
            pass

        global_variable.PRECISION[self.ex] = precision_list


class OkexApi:
    def __init__(self):
        self.ex = 'okex'

    async def get_precision(self):
        precision_list = {}
        url = 'https://www.okx.com/api/v5/public/instruments?instType=SPOT'
        try:
            async with G_RequestSession.request.get(url=url, timeout=10) as r:
                res = await r.json()
                if res['code'] == '0':
                    for i in res['data']:
                        precision = {}
                        precision['price_precision'] = -math.ceil(math.log10(float(float(i['tickSz']))))
                        precision['minQty'] = float(i['minSz'])
                        precision['amount_precision'] = -math.ceil(math.log10(float(float(i['lotSz']))))
                        precision_list[i['instId']] = precision

        except:
            pass
        global_variable.PRECISION[self.ex] = precision_list


class GateioApi:
    def __init__(self, ):
        self.ex = 'gate'

    async def get_precision(self):
        precision_list = {}
        url = 'https://api.gateio.ws/api/v4/spot/currency_pairs'
        try:
            async with G_RequestSession.request.get(url=url, timeout=10) as r:
                res = await r.json()
                for i in res:
                    if i['trade_status'] != 'untradable':
                        precision_list[i['base'] + '-' + i['quote']] = {'price_precision': i['precision'],
                                                                        'amount_precision': i['amount_precision'],
                                                                        'minQty': i.get('min_base_amount', 0),
                                                                        'minQtyQuote': i['min_quote_amount']
                                                                        }

        except:
            pass
        global_variable.PRECISION[self.ex] = precision_list


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
                        precision_list[(i['bc'] + '-' + i['qc']).upper()] = {'price_precision': i['pp'],
                                                                             'amount_precision': i['ap'],
                                                                             'minQty': float(i['minoa']),
                                                                             'minQtyQuote': float(i['minov']),
                                                                             }

        except:
            pass
        global_variable.PRECISION[self.ex] = precision_list


class MexcApi:
    def __init__(self):
        self.ex = 'mxc'

    async def get_precision(self):
        precision_list = {}
        url = 'https://api.mexc.com/api/v3/exchangeInfo'
        try:
            async with G_RequestSession.request.get(url=url, timeout=10) as r:
                res = await r.json()
                for i in res['symbols']:
                    precision_list[i['baseAsset'] + '-' + i['quoteAsset']] = \
                        {'price_precision': i['quotePrecision'],
                         'amount_precision': i['baseAssetPrecision'],
                         'minQty': i['baseSizePrecision'],
                         'minQtyQuote': i['quoteAmountPrecision'],
                         'is_api': i['isSpotTradingAllowed'],
                         }
        except:
            pass
        global_variable.PRECISION[self.ex] = precision_list


class BitgetApi:
    def __init__(self):
        self.ex = 'bitget'

    async def get_precision(self):
        precision_list = {}
        url = 'https://api.bitget.com/api/v2/spot/public/symbols'
        try:
            async with G_RequestSession.request.get(url=url, timeout=10) as r:
                res = await r.json()
                for i in res['data']:
                    precision_list[i['baseCoin'] + '-' + i['quoteCoin']] = \
                        {'price_precision': int(i['pricePrecision']),
                         'amount_precision': int(i['quantityPrecision']),
                         'minQty': float(i['minTradeAmount']),
                         'minQtyQuote': float(i['minTradeUSDT']),
                         'status': i['status'],
                         }
        except:
            pass
        global_variable.PRECISION[self.ex] = precision_list


class KrakenApi:
    def __init__(self):
        self.ex = 'kraken'

    async def get_precision(self):
        precision_list = {}
        url = 'https://api.kraken.com/0/public/AssetPairs'
        try:
            async with G_RequestSession.request.get(url=url, timeout=10) as r:
                res = await r.json()
                for s, detail in res['result'].items():
                    precision_list[f"{detail['base']}-{detail['quote']}"] = \
                        {'price_precision': int(detail['pair_decimals']),
                         'amount_precision': int(detail['lot_decimals']),
                         'minQty': float(detail['ordermin']),
                         'minQtyQuote': float(detail['costmin']),
                         'status': detail['status'],
                         }
        except:
            pass
        global_variable.PRECISION[self.ex] = precision_list


exchanges = {
    'bn': BinanceApi(),
    'okex': OkexApi(),
    'hb': HuobiApi(),
    'gate': GateioApi(),
    'mxc': MexcApi(),
    'bitget': BitgetApi(),
    'kraken': KrakenApi(),
}


async def PRECISION():
    exs = [exchanges[i] for i in global_variable.PRECISION]
    try:
        tasks = [asyncio.create_task(ex.get_precision()) for ex in exs]
        await asyncio.wait(tasks)
    except:
        pass


if __name__ == '__main__':
    asyncio.run(PRECISION())
