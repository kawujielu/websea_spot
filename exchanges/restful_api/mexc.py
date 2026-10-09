import time
import hmac
import json
import base64
import hashlib
from operator import itemgetter
from urllib.parse import urlencode
from many_configs.account_config import EXTERNAL_ACCOUNTS
from many_configs import global_variable
from scaffold.aiohttp import G_RequestSession
import asyncio
from many_configs.exchange_config import EXCHANGE_CONFIG
from libs.utils import digit_to_string
from libs.utils import round_down
from loguru import logger

class MexcApi:
    exchange_name = "mxc"

    def __init__(self, api_key=None, secret=None):
        self._apiKey_ = api_key if api_key else EXTERNAL_ACCOUNTS[self.exchange_name]["apiKey"]
        self._secret_ = secret if secret else EXTERNAL_ACCOUNTS[self.exchange_name]["secret"]
        self.url = EXCHANGE_CONFIG[self.exchange_name]['spot_restful']
        self.prefix = "/api/v3"
        self.recv_window = str(5000)

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
            logger.info(sign_params)
            sign_params = urlencode(sign_params)
            # to_sign = "{}&recvWindow={}&timestamp={}".format(sign_params, self.recv_window, req_time)
            to_sign = "{}&timestamp={}".format(sign_params, req_time)
        else:
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
        if not precision['is_api']:
            return {'content': {"code": -1013,
                                "msg": f"Filter failure:mexc does not have market symbol {symbol}[不支持api交易]"},
                    'code': 400}

        if precision['amount_precision'] == 0:
            amount = int(amount)
        else:
            amount = round_down(amount, precision['amount_precision'])
        if precision['price_precision'] == 0:
            price = int(price)
        else:
            price = round(price, precision['price_precision'])

        if float(precision['minQty']) > amount:
            return {'content': {"code": -1013, "msg": f"Filter failure:{amount}小于最小下单量{precision['minQty']} "},
                    'code': 400}
        if float(precision['minQtyQuote']) > amount * price:
            return {'content': {"code": -1013,
                                "msg": f"Filter failure:[amount:{amount},price:{price}] 下单总价值:{amount * price}小于{precision['minQtyQuote']} "},
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
        args['data']['price'] = digit_to_string(price)

        result = await self.request(args)
        logger.info(result)
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
        args['data']['symbol'] = symbol
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
        args['data']['symbol'] = symbol

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
                         'minQtyQuote': i['quoteAmountPrecision'],
                         'minQty': i['baseSizePrecision'],
                         'is_api': i['isSpotTradingAllowed'],
                         }
            return precision
        else:
            return result
        #

    async def get_trades(self, symbol, orderId):
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


mexc_instance = MexcApi()
global_variable.EXTERNAL_EXCHANGE_INSTANCES[mexc_instance.exchange_name] = mexc_instance

if __name__ == '__main__':
    bb = MexcApi()
    wallet = asyncio.run(bb.wallet_free())
