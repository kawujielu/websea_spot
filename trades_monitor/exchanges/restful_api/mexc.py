import time, datetime
import hmac
import json
import math
import base64
import hashlib
import requests
from operator import itemgetter
from urllib.parse import urlencode
from many_configs.account_config import EXTERNAL_ACCOUNTS
from many_configs import global_variable
from scaffold.aiohttp import G_RequestSession
import asyncio


class MexcApi:
    exchange_name = "mxc"

    def __init__(self, api_key=None, secret=None):
        self._apiKey_ = api_key if api_key else EXTERNAL_ACCOUNTS[self.exchange_name]["apiKey"]
        self._secret_ = secret if secret else EXTERNAL_ACCOUNTS[self.exchange_name]["secret"]

        self.url = "https://api.mexc.com"
        self.prefix = "/api/v3"
        self.recv_window = str(5000)
        # self.url = url

    def _order_params(self, data):
        """Convert params to list with signature as last element
        :param data:
        :return:
        """
        has_signature = False
        params = []
        for key, value in data.items():
            if key == 'signature':
                has_signature = True
            else:
                params.append((key, value))
        # sort parameters by key
        params.sort(key=itemgetter(0))
        if has_signature:
            params.append(('signature', data['signature']))
        return params

    def _generate_signature(self, timestamp, method, path, body):
        query_string = str(timestamp) + str(method) + str(path) + str(body)
        m = hmac.new(bytes(self._secret_, encoding='utf-8'), bytes(query_string, encoding='utf-8'), digestmod='sha256')
        return base64.b64encode(m.digest())

    def genSignature(self, timestamp, body):
        param_str = str(timestamp) + self._apiKey_ + self.recv_window + body

        hash = hmac.new(bytes(self._secret_, "utf-8"), param_str.encode("utf-8"), hashlib.sha256)
        signature = hash.hexdigest()
        return signature

    def pre_hash(timestamp, method, request_path, body):
        return str(timestamp) + str.upper(method) + request_path + body

    async def parse_params_to_str(self, data: dict) -> dict:
        params = {k: v for k, v in data.items()}
        url = '?'
        for key, value in params.items():
            url = url + str(key) + '=' + str(value) + '&'
        return url[0:-1]

    async def _sign_v3(self, req_time, sign_params=None):
        if sign_params:
            print('data', sign_params)
            sign_params = urlencode(sign_params)
            # to_sign = "{}&recvWindow={}&timestamp={}".format(sign_params, self.recv_window, req_time)
            to_sign = "{}&timestamp={}".format(sign_params, req_time)
        else:
            print('-123')
            to_sign = "timestamp={}".format(req_time)

        sign = hmac.new(self._secret_.encode('utf-8'), to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
        return sign

    async def request(self, args):
        data = args.get('data', {})
        method = args['method']
        signed = args.get('signed', False)
        kwargs = dict()
        args['timeout'] = 15
        timestamp = str(int(time.time() * 10 ** 3))

        request_path = '' if method == 'POST' else (await self.parse_params_to_str(data))
        # query_string = '' if method == 'POST' else request_path.replace('?', '')
        # body = json.dumps(data) if method == 'POST' else ''
        # host = self.prefix + args['url']

        args['header'] = dict()
        args['header']['Content-Type'] = 'application/json'
        args['header']['X-MEXC-APIKEY'] = self._apiKey_

        url = self.url + args['url']
        if 'https://www.mexc.com' in args['url']:
            url = args['url']

        if signed:
            data['signature'] = await self._sign_v3(timestamp, data)
            data['timestamp'] = timestamp
        result = {}

        async with G_RequestSession.request.request(method=method,
                                                    url=url,
                                                    params=data,
                                                    data=kwargs,
                                                    headers=args['header'],
                                                    # proxy='http://127.0.0.1:7890',
                                                    timeout=int(args['timeout'])) as r:
            result['content'] = await r.text()
            result['code'] = r.status

        return result

    async def wallet_free(self, ):
        # /spot/v3/private/account
        args = dict()
        args['url'] = '/api/v3/account'
        # args['url'] = '/spot/v1/account'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()

        result = await self.request(args)
        if result['code'] == 200:
            res = json.loads(result['content'])
            res = {i['asset']: float(i['free']) for i in res['balances'] if float(i['free'])}
            return res
        else:
            return result

    async def wallet(self, ):
        # /spot/v3/private/account
        args = dict()
        args['url'] = '/api/v3/account'
        # args['url'] = '/spot/v1/account'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()

        result = await self.request(args)

        if result['code'] == 200:
            res = json.loads(result['content'])
            res = {i['asset']: float(i['free']) + float(i['locked']) for i in res['balances'] if
                   float(i['free']) or float(i['locked'])}
            return res
        else:
            return result

    async def account(self, ):
        # /spot/v3/private/account
        args = dict()
        args['url'] = '/api/v3/account'
        # args['url'] = '/spot/v1/account'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()

        result = await self.request(args)

        if result['code'] == 200:
            res = json.loads(result['content'])
            res = {i['asset']: float(i['free']) + float(i['locked']) for i in res['balances'] if
                   float(i['free']) or float(i['locked'])}
            return res
        else:
            return result

    async def create_order(self, symbol, side, amount, price, type='LIMIT'):
        # POST /spot/v3/private/order
        # 价格精度和数量精度对下单没有影响，主要是api会限制交易对，有些币对不能api交易。

        if self.exchange_name in global_variable.PRECISION.keys():
            precision = global_variable.PRECISION[self.exchange_name].get(symbol, {})
        else:
            global_variable.PRECISION[self.exchange_name] = {}
            precision = {}

        if not precision:
            precision = await self.precision(symbol)
            global_variable.PRECISION[self.exchange_name][symbol] = precision
        if precision['is_api']:
            return {'content': {"code": -1013,
                                "msg": f"Filter failure:mexc does not have market symbol {symbol}[不支持api交易]"},
                    'code': 400}

        if precision['amount_precision'] == 0:
            amount = int(amount)
        else:
            amount = round(amount, precision['amount_precision'])
        if precision['price_precision'] == 0:
            price = int(price)
        else:
            price = round(price, precision['price_precision'])

        if precision['minQty'] > amount:
            return {'content': {"code": -1013, "msg": f"Filter failure:{amount}小于最小下单量{precision['minQty']} "},
                    'code': 400}
        if precision['minQty_quote'] > amount * price:
            return {'content': {"code": -1013,
                                "msg": f"Filter failure:[amount:{amount},price:{price}] 下单总价值:{amount * price}小于{precision['minQty_quote']} "},
                    'code': 400}
        # 買賣方向. Buy：買入, Sell：賣出
        args = dict()
        # Creates and validates a new order but does not send it into the matching engine.
        # args['url'] = '/api/v3/order/test'
        args['url'] = '/api/v3/order'
        args['method'] = 'POST'
        args['signed'] = True
        args['data'] = dict()

        args['data']['symbol'] = symbol.replace('-', '')
        args['data']['side'] = side.upper()
        args['data']['type'] = type.upper()
        args['data']['quantity'] = str(amount)
        args['data']['price'] = str(price)

        result = await self.request(args)
        print(result)
        if result['code'] == 200:
            res = json.loads(result['content'])
            res['status'] = "NEW"
            res['orderId'] = res['orderId']
            return res
        else:
            return result

    async def get_orders(self, symbol, orderId):
        # 当前挂单
        args = dict()
        args['url'] = '/api/v3/order'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['symbol'] = symbol.replace('-', '')
        args['data']['orderId'] = orderId
        result = await self.request(args)

        if result['code'] == 200:
            res = json.loads(result['content'])
            res['status'] = res['status'].upper()
            res['fillsz'] = float(res['executedQty'])
            return res
        else:
            return result

    async def get_open_orders(self, symbol, orderId=None):
        # 查询订单
        # POST /spot/v3/private/open-orders

        args = dict()
        args['url'] = '/api/v3/order'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['symbol'] = symbol.replace('-', '')
        if orderId:
            args['data']['orderId'] = orderId

        result = await self.request(args)
        if result['code'] == 200:

            return json.loads(result['content'])
        else:
            return result

    async def get_open_orders_all(self, symbol, ):
        # 查询订单
        # POST /spot/v3/private/open-orders

        args = dict()
        args['url'] = '/api/v3/allOrders'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['symbol'] = symbol.replace('-', '')

        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def cancel_order(self, symbol, orderId=None):
        # 撤销单个订单
        # DELETE /spot/orders/{order_id}
        args = dict()
        args['url'] = f'/api/v3/order'
        args['method'] = 'DELETE'
        args['signed'] = True
        args['data'] = dict()
        args['data']['symbol'] = symbol.replace('-', '')
        if orderId:
            args['data']['orderId'] = orderId
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def depth(self, symbol, limit=5, ):
        # /spot/v3/public/quote/depth
        args = dict()
        args['url'] = '/api/v3/depth'
        args['method'] = 'GET'
        args['signed'] = False
        args['data'] = dict()
        args['data']['symbol'] = symbol.replace('-', '')
        args['data']['limit'] = limit

        result = await self.request(args)
        if result['code'] == 200:

            return json.loads(result['content'])
        else:
            return result

    async def precision(self, symbol=None):
        # GET /spot/v3/public/symbols
        args = dict()
        args['url'] = f'/api/v3/exchangeInfo'
        args['method'] = 'GET'
        args['signed'] = False
        args['data'] = dict()
        args['data']['symbol'] = symbol.replace('-', '')

        result = await self.request(args)
        if result['code'] == 200:
            content = json.loads(result['content'])
            i = content['symbols'][0]
            # if i['isSpotTradingAllowed']:  # 是否允许api现货交易
            precision = {'price_precision': i['quotePrecision'],
                         'amount_precision': i['baseAssetPrecision'],
                         'minQty_quote': i['quoteAmountPrecision'],
                         'is_api': i['isSpotTradingAllowed'],
                         }
            return precision
        else:
            return result
        #

    async def get_Trades(self, symbol, orderId):
        # 查询单个订单详情
        # get /spot/v3/private/history-orders
        args = dict()
        args['url'] = f'/api/v3/myTrades'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['symbol'] = symbol.replace('-', '')
        if orderId:
            args['data']['orderId'] = orderId
        result = await self.request(args)
        if result['code'] == 200:
            res = []
            for i in json.loads(result['content']):
                ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(float(i['time']) / 1000)))
                d = {
                    'side': 'BUY' if i['isBuyer'] else 'SELL',
                    'amount': float(i['qty']),
                    'tradeId': i['id'],
                    'price': float(i['price']),
                    'fee': i['commission'],
                    'feecoin': i['commissionAsset'],
                    'time': ts,
                    'orderId': i['orderId'],
                    'symbol': symbol,
                    'exchange': self.exchange_name
                }
                res.append(d)
            return res
        else:
            return result

    async def currency(self, currency=None):
        args = dict()
        args['url'] = f'https://www.mexc.com/open/api/v2/market/coin/list'
        args['method'] = 'GET'
        args['signed'] = False
        args['data'] = dict()
        if currency:
            args['data']['currency'] = currency

        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result


mexc_instance = MexcApi()
global_variable.EXTERNAL_EXCHANGE_INSTANCES[mexc_instance.exchange_name] = mexc_instance

if __name__ == '__main__':
    from pprint import pprint

    # api = {'apiKey': 'mx0vglcflJDghnCxuE', 'secretkey': 'd0f71ce9fe3f489693ace988186c52a7', }
    api = {'apiKey': 'mx0vglObuhQkpFLJIZ',
           'secret': '10b552b8ef924b5bb187c4390f0c3c8b'}

    bb = MexcApi(api_key=api['apiKey'], secret=api['secret'])
    # wallet = asyncio.run(bb.wallet())
    amount = 0.0003000012323
    price = 22409.00000000123233
    symbol = 'WBTC-USDT'
    side = 'SELL'
    print(amount * price)
    # wallet = asyncio.run(bb.create_order(symbol=symbol, side=side, amount=amount, price=price))
    # orderId = '254ac55cacb344728c97a59ffdb373a4'
    orderId = '0074ad09fd8548878d20bd7b669d9607'
    # wallet = asyncio.run(bb.cancel_order(symbol, orderId=orderId))
    # wallet = asyncio.run(bb.get_orders(symbol, orderId=orderId))
    # wallet = asyncio.run(bb.get_Trades(symbol, orderId=orderId))
    # wallet = asyncio.run(bb.wallet())
    wallet = asyncio.run(bb.wallet_free())
    # wallet = asyncio.run(bb.depth(symbol=symbol, limit=5))
    # wallet = asyncio.run(bb.precision(symbol="RAK-USDT"))
    pprint(wallet)
