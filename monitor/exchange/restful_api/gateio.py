import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
import asyncio
import traceback
import time
import hmac
import json
import hashlib
from datetime import datetime
from libs.requestSession import G_RequestSession


class GateioApi:
    exchange_name = "gate"

    def __init__(self, apiKey=None, secret=None):
        self._apiKey_ = apiKey
        self._secret_ = secret
        self.url = "https://api.gateio.ws"
        self.prefix = "/api/v4"
        self.order_status = {'open': 'new', 'closed': 'filled', 'cancelled': 'cancelled'}
        self.deposit_status = {'DONE': '完成', 'CANCEL': '已取消', 'REQUEST': '请求中', 'MANUAL': '待人工审核', 'BCODE': '充值码操作',
                               'EXTPEND': '已经发送等待确认', 'FAIL': '链上失败等待确认', 'INVALID': '无效订单', 'VERIFY': '验证中',
                               'PROCES': '处理中', 'PEND': ' 处理中', 'DMOVE': '待人工审核',
                               'SPLITPEND': 'cny提现大于5w, 自动分单'}
        self.withdraw_status = {'DONE': '完成', 'CANCEL': '已取消', 'REQUEST': '请求中', 'MANUAL': '待人工审核', 'BCODE': '充值码操作',
                                'EXTPEND': '已经发送等待确认', 'FAIL': '链上失败等待确认', 'INVALID': '无效订单', 'VERIFY': '验证中',
                                'PROCES': '处理中', 'PEND': ' 处理中', 'DMOVE': '待人工审核',
                                'SPLITPEND': 'cny提现大于5w, 自动分单'}

    async def gen_sign(self, method, url, t, query_string=None, payload_string=None):
        m = hashlib.sha512()
        m.update((payload_string or "").encode('utf-8'))
        hashed_payload = m.hexdigest()
        s = '%s\n%s\n%s\n%s\n%s' % (method, url, query_string or "", hashed_payload, t)
        sign = hmac.new(self._secret_.encode('utf-8'), s.encode('utf-8'), hashlib.sha512).hexdigest()
        return sign

    async def parse_params_to_str(self, data: dict) -> dict:
        params = {k: v for k, v in data.items()}
        url = '?'
        for key, value in params.items():
            url = url + str(key) + '=' + str(value) + '&'
        return url[0:-1]

    async def request(self, args):
        data = args.get('data', {})
        method = args['method']
        signed = args.get('signed', False)
        cookies = args.get('cookies', {})
        args['timeout'] = 15
        timestamp = str(time.time())
        request_path = '' if method == 'POST' else (await self.parse_params_to_str(data))
        query_string = '' if method == 'POST' else request_path.replace('?', '')
        body = json.dumps(data) if method == 'POST' else ''
        host = args['url'].replace(self.url, '')
        args['header'] = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        result = {}

        if signed:
            args['header']['KEY'] = self._apiKey_
            args['header']['Timestamp'] = timestamp
            args['header']['SIGN'] = await self.gen_sign(method, host, timestamp, query_string, body)
        async with G_RequestSession.request.request(method=method,
                                                    url=args['url'],
                                                    params=query_string,
                                                    data=body,
                                                    headers=args['header'],
                                                    # proxy='http://127.0.0.1:7890',
                                                    timeout=int(args['timeout'])) as r:
            result['content'] = await r.text()

            result['code'] = r.status
        return result

    async def request1(self, args):
        data = args.get('data', {})
        method = args['method']
        signed = args.get('signed', False)
        cookies = args.get('cookies', {})
        args['timeout'] = 15
        timestamp = str(time.time())
        request_path = '' if method == 'POST' else (await self.parse_params_to_str(data))
        query_string = '' if method == 'POST' else request_path.replace('?', '')
        body = json.dumps([data]) if method == 'POST' else ''
        host = args['url'].replace(self.url, '')
        args['header'] = dict()
        result = {}

        if signed:
            args['header']['KEY'] = self._apiKey_
            args['header']['Timestamp'] = timestamp
            args['header']['SIGN'] = await self.gen_sign(method, host, timestamp, query_string, body)

        async with G_RequestSession.request.request(method=method,
                                                    url=args['url'],
                                                    params=args['data'],
                                                    data=args['data'],
                                                    headers=args['header'],
                                                    proxy='http://127.0.0.1:7890',
                                                    timeout=int(args['timeout'])) as r:
            result['content'] = await r.text()

        result['code'] = r.status
        return result

    async def wallet(self, ):
        # 折算成USDT GET /spot/accounts
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/spot/accounts'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()

        result = await self.request(args)

        if result['code'] == 200:
            res = json.loads(result['content'])
            return {i['currency'].upper(): float(i['available']) + float(i['locked']) for i in res}
        else:
            return result

    async def wallet_free(self, ):
        # 折算成USDT GET /spot/accounts
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/spot/accounts'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()

        result = await self.request(args)
        print(result)
        if result['code'] == 200:
            res = json.loads(result['content'])
            return {i['currency'].upper(): float(i['available']) for i in res if float(i['available'])}
        else:
            return result

    async def wallet_saved_address(self, currency):
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/wallet/saved_address'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()

        args['data']['currency'] = currency
        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
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
        precision = await self.precision(symbol)

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
        # 買賣方向. Buy：買入, Sell：賣出
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/spot/orders'
        args['method'] = 'POST'
        args['signed'] = True
        args['data'] = dict()

        args['data']['currency_pair'] = symbol.replace('-', '_')
        args['data']['account'] = account
        args['data']['side'] = side.lower()
        args['data']['type'] = type
        args['data']['amount'] = str(amount)
        args['data']['price'] = str(price)
        result = await self.request(args)
        if result['code'] == 200 or result['code'] == 201:
            data = json.loads(result['content'])
            data['orderId'] = data['id']
            data['status'] = self.order_status.get(data['status'], data['status']).upper()
            return data
        else:
            return result

    async def get_orders(self, symbol, orderId):
        # 查询单个订单详情
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/spot/orders/{orderId}'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['currency_pair'] = symbol.replace('-', '_')
        # args['data']['limit'] = 10
        result = await self.request(args)
        if result['code'] == 200:
            res = json.loads(result['content'])
            res['status'] = self.order_status.get(res['status'], res['status']).upper()
            res['fillsz'] = float(res['filled_total']) / float(res['avg_deal_price']) if float(res.get('avg_deal_price', 0)) else 0

            return res
        else:
            return result

    async def get_open_orders(self, symbol, status):
        # 查询订单列表
        """
        :param symbol:
        :param status: status: 基于状态查询订单列表,open - 挂单中 finished - 已结束
        :return:
        """
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/spot/orders'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['currency_pair'] = symbol.replace('-', '_')
        args['data']['status'] = status

        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def cancel_order(self, symbol, orderId):
        # 撤销单个订单
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/spot/orders/{orderId}'
        args['method'] = 'DELETE'
        args['signed'] = True
        args['data'] = dict()
        args['data']['currency_pair'] = symbol.replace('-', '_')
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def depth(self, symbol, limit=5):
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/spot/order_book'
        args['method'] = 'GET'
        args['signed'] = False
        args['data'] = dict()
        args['data']['currency_pair'] = symbol.replace('-', '_')
        args['data']['limit'] = limit

        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def precision(self, symbol=None):
        args = dict()
        args['url'] = f"{self.url}{self.prefix}/spot/currency_pairs/{symbol.replace('-', '_')}"
        args['method'] = 'GET'
        args['signed'] = False
        args['data'] = dict()
        result = await self.request(args)
        print(result)
        if result['code'] == 200:
            content = json.loads(result['content'])
            precision = {'price_precision': content['precision'], 'amount_precision': content['amount_precision'],
                         'minQty': float(content['min_base_amount'])}
            return precision
        else:
            return result

    async def get_Trades(self, symbol, orderId):
        # 查询单个订单详情
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/spot/my_trades'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['currency_pair'] = symbol.replace('-', '_')
        args['data']['order_id'] = orderId
        # args['data']['limit'] = 10
        result = await self.request(args)
        print(result)
        if result['code'] == 200:
            # return json.loads(result['content'])
            res = []
            for i in json.loads(result['content']):
                ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(i['create_time'])))
                d = {
                    'side': i['side'].upper(),
                    'amount': float(i['amount']),
                    'tradeId': i['id'],
                    'price': float(i['price']),
                    'fee': i['fee'],
                    'feecoin': i['fee_currency'],
                    'time': ts,
                    'orderId': i['order_id'],
                    'symbol': symbol,
                    'exchange': self.exchange_name
                }
                res.append(d)
            return res
        else:
            return result

    async def deposit_history(self, start=None, end=None):
        # 获取充值历史(支持多网络) (USER_DATA)
        # GET /wallet/deposits
        """
        :return: {'DONE': '完成', 'CANCEL': '已取消', 'REQUEST': '请求中', 'MANUAL': '待人工审核', 'BCODE': '充值码操作',
                  'EXTPEND': '已经发送等待确认', 'FAIL': '链上失败等待确认', 'INVALID': '无效订单', 'VERIFY': '验证中',
                  'PROCES': '处理中', 'PEND': ' 处理中', 'DMOVE': '待人工审核',
                  'SPLITPEND': 'cny提现大于5w, 自动分单'}
        """
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/wallet/deposits'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        if start:
            args['data']['from'] = start
        if end:
            args['data']['to'] = end
        result = await self.request(args)

        if result['code'] == 200:
            res = json.loads(result['content'])
            mm = []
            for i in res:
                print(i)
                tmp = {}
                tmp['exchange'] = self.exchange_name
                tmp['id'] = i['id']
                tmp['currency'] = i['currency']
                tmp['address'] = i['address']
                tmp['hash'] = i.get('txid', '')
                tmp['amount'] = i['amount']
                tmp['fee'] = i.get('fee', 0)
                tmp['side'] = 'deposit'
                tmp['ctime'] = int(i['timestamp'])
                tmp['mtime'] = int(i['timestamp'])
                tmp['time'] = datetime.fromtimestamp(tmp['ctime']).strftime("%Y-%m-%d %H:%M:%S")
                tmp['status'] = i['status']
                tmp['status1'] = self.deposit_status.get(i['status'], i['status'])
                mm.append(tmp)
            return mm

        else:
            return result

    async def withdraw_history(self, start=None, end=None):
        # GET /wallet/deposit_address
        """
        :return: status	{'DONE': '完成', 'CANCEL': '已取消', 'REQUEST': '请求中', 'MANUAL': '待人工审核', 'BCODE': '充值码操作',
                  'EXTPEND': '已经发送等待确认', 'FAIL': '链上失败等待确认', 'INVALID': '无效订单', 'VERIFY': '验证中',
                  'PROCES': '处理中', 'PEND': ' 处理中', 'DMOVE': '待人工审核',
                  'SPLITPEND': 'cny提现大于5w, 自动分单'}
        """
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/wallet/withdrawals'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        if start:
            args['data']['from'] = start
        if end:
            args['data']['to'] = end
        result = await self.request(args)
        if result['code'] == 200:
            res = json.loads(result['content'])
            mm = []
            for i in res:
                tmp = {}
                tmp['exchange'] = self.exchange_name
                tmp['id'] = i['id']
                tmp['currency'] = i['currency'].upper()
                tmp['address'] = i['address']
                tmp['hash'] = i.get('txid', '')
                tmp['amount'] = i['amount']
                tmp['fee'] = i.get('fee', 0)
                tmp['side'] = 'withdraw'
                tmp['ctime'] = int(i['timestamp'])
                tmp['mtime'] = int(i['timestamp'])
                tmp['time'] = datetime.fromtimestamp(tmp['ctime']).strftime("%Y-%m-%d %H:%M:%S")
                tmp['status'] = i['status']
                tmp['status1'] = self.withdraw_status.get(i['status'], i['status'])
                mm.append(tmp)
            return mm

        else:
            return result

    async def deposit_address(self, currency):
        # 获取充值地址 (支持多网络) (USER_DATA)
        # /wallet/deposit_address
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/wallet/deposit_address'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['currency'] = currency
        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def wallet_transfers(self, currency, from_account, to_account, amount, currency_pair):
        # 获取充值地址 (支持多网络) (USER_DATA)
        # /wallet/deposit_address
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/wallet/transfers'
        args['method'] = 'POST'
        args['signed'] = True
        args['data'] = dict()
        args['data']['currency'] = currency
        args['data']['from'] = from_account
        args['data']['to'] = to_account
        args['data']['amount'] = amount
        args['data']['currency_pair'] = currency_pair
        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def margin_accounts(self, ):
        # 获取充值地址 (支持多网络) (USER_DATA)
        # /wallet/deposit_address
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/margin/accounts'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def margin_account_book(self, currency, from_account, to_account, amount, currency_pair):
        # 获取充值地址 (支持多网络) (USER_DATA)
        # /wallet/deposit_address
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/margin/account_book'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['currency'] = currency
        args['data']['from'] = from_account
        args['data']['to'] = to_account
        args['data']['amount'] = amount
        args['data']['currency_pair'] = currency_pair
        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def margin_cross_transferable(self, currency, ):
        # 全仓杠杆允许的最大转出
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/margin/cross/transferable'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['currency'] = currency
        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def margin_transferable(self, currency, currency_pair):
        # 全仓杠杆允许的最大转出
        args = dict()
        args['url'] = f'{self.url}{self.prefix}/margin/transferable'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['currency'] = currency
        args['data']['currency_pair'] = currency_pair
        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result


if __name__ == "__main__":
    api = {'apiKey': '', 'secret': '', }
    bb = GateioApi(apiKey=api['apiKey'], secret=api['secret'])
    a = '2023-11-25 15:47:09'
    wallet = asyncio.run(bb.wallet())
    print(wallet)
