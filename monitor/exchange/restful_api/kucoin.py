import asyncio
import traceback
import time
import hmac
import json
import math
import hashlib
import base64
from libs.requestSession import G_RequestSession


class KucoinApi:
    exchange_name = "kucoin"

    def __init__(self, api_key=None, secret=None, password=None):
        self._apiKey_ = api_key
        self._secret_ = secret
        self._password_ = password
        # self.url = EXCHANGE_CONFIG[self.exchange_name]['spot_restful']
        self.url = 'https://api.kucoin.com'
        # self.order_status = {'open': 'new', 'closed': 'filled', 'cancelled': 'cancelled'}

    def signature(self, str_to_sign):
        return base64.b64encode(hmac.new(self._secret_.encode('utf-8'), str_to_sign.encode('utf-8'), hashlib.sha256).digest())

    def passphrase(self):
        return base64.b64encode(hmac.new(self._secret_.encode('utf-8'), self._password_.encode('utf-8'), hashlib.sha256).digest())

    def parse_params_to_str(self, data: dict) -> dict:
        params = {k: v for k, v in data.items()}
        url = '?'
        for key, value in params.items():
            url = url + str(key) + '=' + str(value) + '&'
        return url[0:-1]

    async def request(self, args):
        data = args.get('data', {})
        method = args['method']
        signed = args.get('signed', False)
        args['timeout'] = 15
        data_json = json.dumps(data)
        timestamp = int(time.time() * 1000)
        request_path = data_json if method == "POST" else self.parse_params_to_str(data)
        str_to_sign = str(timestamp) + method + args['url'] + request_path

        args['header'] = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        result = {}

        if signed:
            args['header']['KC-API-SIGN'] = self.signature(str_to_sign)
            args['header']['KC-API-TIMESTAMP'] = str(timestamp)
            args['header']['KC-API-KEY'] = self._apiKey_
            args['header']['KC-API-PASSPHRASE'] = self.passphrase()
            args['header']['KC-API-KEY-VERSION'] = 2
            args['header']['Content-Type'] = "application/json"

        async with G_RequestSession.request.request(method=method,
                                                    url=args['url'],
                                                    data=data_json,
                                                    headers=args['header'],
                                                    timeout=int(args['timeout'])) as r:
            result['content'] = await r.text()
            result['code'] = r.status
        return result

    async def wallet(self, currency, type="trade"):
        # 折算成USDT GET /spot/accounts
        args = dict()
        args['url'] = f'{self.url}/api/v1/accounts'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        if currency:
            args['data']['currency'] = currency
        args['data']['type'] = type
        result = await self.request(args)

        if result['code'] == 200:
            res = json.loads(result['content'])
            return {i['currency'].upper(): float(i['balance']) for i in res if float(i['balance'])}
        else:
            return result

    async def wallet_free(self, currency, type="trade"):
        # 折算成USDT GET /spot/accounts
        args = dict()
        args['url'] = f'{self.url}/api/v1/accounts'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        if currency:
            args['data']['currency'] = currency
        args['data']['type'] = type
        result = await self.request(args)
        if result['code'] == 200:
            res = json.loads(result['content'])
            return {i['currency'].upper(): float(i['available']) for i in res if float(i['available'])}
        else:
            return result

    async def create_order(self, symbol, side, amount, price, type='limit', account='spot'):
        """
        :param symbol:
        :param side:
        :param amount:
        :param price:
        :param type:
        :param account:
        :return:
        挂单中的委托状态是 open ，在数量全部成交之前保持为 open 。
        如果被全部吃掉，则订单结束，状态变成 closed 。
        假如全部成交之前，订单被撤销，不管是否有部分成交，状态都会变为 cancelled
        gateio 对于价格精度和数量精度 没有限制
        """
        if self.exchange_name in global_variable.PRECISION.keys():
            precision = global_variable.PRECISION[self.exchange_name].get(symbol, {})
        else:
            global_variable.PRECISION[self.exchange_name] = {}
            precision = {}
        if not precision:
            precision = await self.precision(symbol)
            global_variable.PRECISION[self.exchange_name][symbol] = precision

        if precision['amount_precision'] == 0:
            amount = int(amount)
        else:
            amount = round(amount, precision['amount_precision'])
        if precision['price_precision'] == 0:
            price = int(price)
        else:
            price = round(price, precision['price_precision'])
        if precision.get('minQty') > amount:
            return {'content': {"code": -1013, "msg": f"Filter failure:{amount}小于最小下单量{precision['minQty']} "},
                    'code': 400}
        if precision.get('minQtyQuote') > amount * price:
            return {'content': {"code": -1013,
                                "msg": f"Filter failure:[amount:{amount},price:{price}] 下单总价值:{amount * price}小于{precision['minQtyQuote']} "},
                    'code': 400}
        # 買賣方向. Buy：買入, Sell：賣出
        args = dict()
        args['url'] = f'{self.url}/api/v1/orders'
        args['method'] = 'POST'
        args['signed'] = True
        args['data'] = dict()

        args['data']['symbol'] = symbol
        args['data']['side'] = side.lower()
        args['data']['type'] = type
        args['data']['size'] = str(amount)
        args['data']['price'] = digit_to_string(price)
        result = await self.request(args)
        if result['code'] == 200 or result['code'] == 201:
            data = json.loads(result['content'])
            data['orderId'] = data['orderId']
            data['status'] = "NEW"
            return data
        else:
            return result

    async def get_orders(self, symbol, orderId):
        # 查询单个订单详情
        args = dict()
        args['url'] = f'{self.url}/api/v1/orders/{orderId}'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        result = await self.request(args)
        if result['code'] == 200:
            res = json.loads(result['content'])
            res['status'] = "NEW" if res['isActive'] else "CANCELLED"
            res['fillsz'] = float(res['dealSize'])
            return res
        else:
            return result

    async def cancel_order(self, symbol, orderId):
        # 撤销单个订单
        args = dict()
        args['url'] = f'{self.url}/api/v1/orders/{orderId}'
        args['method'] = 'DELETE'
        args['signed'] = True
        args['data'] = dict()
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def depth(self, symbol, limit=5):
        args = dict()
        args['url'] = f'{self.url}/api/v1/market/orderbook/level2_20'
        args['method'] = 'GET'
        args['signed'] = False
        args['data'] = dict()
        args['data']['symbol'] = symbol

        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def precision(self, symbol=None):
        args = dict()
        args['url'] = f"{self.url}/api/v2/symbols"
        args['method'] = 'GET'
        args['signed'] = False
        args['data'] = dict()

        market = 'USDS' if symbol.split('-')[1] == 'USDT' else ''
        if market:
            args['data']['market'] = market

        result = await self.request(args)
        if result['code'] == 200:
            content = json.loads(result['content'])
            for i in content:
                if i['symbol'] == symbol:
                    # -math.ceil(math.log10(float(float(i['lotSz']))))
                    precision = {'price_precision': -math.ceil(math.log10(float(float(i['priceIncrement'])))),
                                 'amount_precision': -math.ceil(math.log10(float(float(i['baseIncrement'])))),
                                 'minQtyQuote': float(content.get('minFunds')),
                                 'minQty': float(i.get('v', 0))}
                    return precision
        else:
            return result

    async def get_trades(self, symbol, orderId):
        # 查询单个订单详情
        args = dict()
        args['url'] = f'{self.url}/api/v1/fills'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['symbol'] = symbol
        args['data']['orderId'] = orderId
        # args['data']['limit'] = 10
        result = await self.request(args)
        print(result)
        if result['code'] == 200:
            res = []
            for i in json.loads(result['items']):
                ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(i['createdAt'] / 1000)))
                d = {
                    'side': i['side'].upper(),
                    'size': float(i['amount']),
                    'tradeId': i['tradeId'],
                    'price': float(i['price']),
                    'fee': i['fee'],
                    'feecoin': i['feeCurrency'],
                    'time': ts,
                    'orderId': i['orderId'],
                    'symbol': symbol,
                    'exchange': self.exchange_name
                }
                res.append(d)
            return res
        else:
            return result


kucoin_instance = KucoinApi()

if __name__ == "__main__":
    pass
