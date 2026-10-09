import time, datetime
import hmac
import json
import math
import base64
import hashlib
import requests
from operator import itemgetter
from urllib.parse import urlencode
from libs.requestSession import G_RequestSession
import asyncio
from datetime import datetime


class MexcApi:
    exchange_name = "mxc"

    def __init__(self, apiKey=None, secret=None):
        self._apiKey_ = apiKey
        self._secret_ = secret

        self.url = "https://api.mexc.com"
        self.prefix = "/api/v3"
        self.recv_window = str(5000)
        self.deposit_status = {'1': '小额充值', '2': '延迟到账', '3': '大额充值', '4': '等待中', '5': '入账成功', '6': '审核中', '7': '驳回'}
        self.withdraw_status = {'1': '提交申请', '2': '审核中', '3': '等待处理', '4': '处理中', '5': '等待打包', '6': '等待确认', '7': '提现成功', '8': '提现失败',
                                '9': '已取消', '10': '手动入账'}
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

        precision = await self.precision(symbol)
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

    async def deposit_history(self):
        # 获取充值历史(支持多网络) (USER_DATA)
        # GET /api/v3/capital/deposit/hisrec
        """
        :return: {1: '小额充值', 2: '延迟到账', 3: '大额充值', 4: '等待中', 5: '入账成功', 6: '审核中', 7: '驳回'}
        """
        args = dict()
        args['url'] = '/api/v3/capital/deposit/hisrec'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        result = await self.request(args)

        if result['code'] == 200:
            res = json.loads(result['content'])
            mm = []
            for i in res:
                tmp = {}
                tmp['exchange'] = self.exchange_name
                tmp['id'] = i['txId']
                tmp['currency'] = i['coin'].split('-')[0]
                tmp['address'] = i['address']
                tmp['hash'] = i.get('txId', '')
                tmp['amount'] = i['amount']
                tmp['fee'] = i.get('transactionFee', 0)
                tmp['side'] = 'deposit'
                tmp['ctime'] = int(i['insertTime'] / 1000)
                tmp['mtime'] = int(i['insertTime'] / 1000)
                tmp['time'] = datetime.fromtimestamp(tmp['ctime']).strftime("%Y-%m-%d %H:%M:%S")
                tmp['status'] = str(i['status'])
                tmp['status1'] = self.deposit_status.get(tmp['status'], tmp['status'])
                mm.append(tmp)
            return mm

        else:
            return result

    async def withdraw_history(self):
        # 获取提币历史 (支持多网络) (USER_DATA)
        # /api/v3/capital/withdraw/history
        """
        :return: {1: '提交申请', 2: '审核中', 3: '等待处理', 4: '处理中', 5: '等待打包', 6: '等待确认', 7: '提现成功', 8: '提现失败',
                                  9: '已取消', 10: '手动入账'}
        """
        args = dict()
        args['url'] = '/api/v3/capital/withdraw/history'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        result = await self.request(args)
        if result['code'] == 200:
            res = json.loads(result['content'])
            mm = []
            for i in res:
                tmp = {}
                tmp['exchange'] = self.exchange_name
                tmp['id'] = i['id']
                tmp['currency'] = i['coin'].split('-')[0]
                tmp['address'] = i['address']
                tmp['hash'] = i.get('txId', '')
                tmp['amount'] = i['amount']
                tmp['fee'] = i.get('transactionFee', 0)
                tmp['side'] = 'withdraw'
                tmp['ctime'] = int(i['applyTime'] / 1000)
                tmp['mtime'] = int(i['updateTime'] / 1000)
                tmp['time'] = datetime.fromtimestamp(tmp['ctime']).strftime("%Y-%m-%d %H:%M:%S")
                tmp['status'] = str(i['status'])
                tmp['status1'] = self.withdraw_status.get(tmp['status'], tmp['status'])
                mm.append(tmp)
            return mm

        else:
            return result

    async def getall(self):
        args = dict()
        args['url'] = '/api/v3/capital/config/getall'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        result = await self.request(args)
        if result['code'] == 200:
            res = json.loads(result['content'])
            return res

        else:
            return result

    async def deposit_address(self, currency):
        # 获取充值地址 (支持多网络) (USER_DATA)
        # /api/v3/capital/deposit/address
        args = dict()
        args['url'] = '/api/v3/capital/deposit/address'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['coin'] = currency
        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result


if __name__ == '__main__':
    from pprint import pprint

    api = {'apiKey': '',
           'secret': ''}

    bb = MexcApi(apiKey=api['apiKey'], secret=api['secret'])
    amount = 0.0003000012323
    price = 22409.00000000123233
    symbol = 'WBTC-USDT'
    side = 'SELL'
    print(amount * price)
    orderId = '0074ad09fd8548878d20bd7b669d9607'
    wallet = asyncio.run(bb.wallet_free())

    pprint(wallet)
