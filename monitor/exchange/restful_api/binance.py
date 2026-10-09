import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
import math
import asyncio
import time
import hmac
import hashlib
import json
from datetime import datetime
from operator import itemgetter
from libs.requestSession import G_RequestSession


class BinanceApi:
    exchange_name = "bn"

    def __init__(self, apiKey, secret):
        self._apiKey_ = apiKey
        self._secret_ = secret
        self.url = 'https://api.binance.com'
        # self.url = 'https://testnet.binance.vision'  # test
        self.deposit_status = {'0': 'pending', '6': 'credited but cannot withdraw', '1': '成功'}
        self.withdraw_status = {'0': '已发送确认Email', '1': '已被用户取消', '2': '等待确认', '3': '被拒绝', '4': '处理中', '5': '提现交易失败',
                                '6': '提现完成'}

    def _order_params(self, data):
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

    def _generate_signature(self, data):
        ordered_data = self._order_params(data)
        query_string = '&'.join(["{}={}".format(d[0], d[1]) for d in ordered_data])
        m = hmac.new(self._secret_.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256)
        return m.hexdigest()

    async def request(self, args):
        data = args.get('data', None)
        method = args['method']
        signed = args.get('signed', False)
        args['timeout'] = 10
        if signed:
            # generate signature
            args['data']['timestamp'] = int(time.time() * 1000)
            args['data']['signature'] = self._generate_signature(args['data'])
        if data:
            # sort post params
            args['data'] = self._order_params(args['data'])
            # Remove any arguments with values of None.
            null_args = [i for i, (key, value) in enumerate(args['data']) if value is None]
            for i in reversed(null_args):
                del args['data'][i]
        result = {}
        if args['method']:
            args['params'] = '&'.join('%s=%s' % (data[0], data[1]) for data in args['data'])
            headers = {'Accept': 'application/json', 'User-Agent': 'binance/python', 'X-MBX-APIKEY': self._apiKey_}
            # async with aiohttp.ClientSession(timeout=10, connector=TCPConnector(verify_ssl=False)) as session:
            async with G_RequestSession.request.request(method=method,
                                                        url=args['url'],
                                                        params=args['params'],
                                                        headers=headers,
                                                        # proxy='http://127.0.0.1:7890',
                                                        timeout=5) as r:
                result['content'] = await r.text()
            result['code'] = r.status
            return result

    async def wallet_free(self):
        # GET /api/v3/account (HMAC SHA256)
        args = dict()
        args['url'] = '{}/api/v3/account'.format(self.url)
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['timestamp'] = int(time.time() * 1000)
        result = await self.request(args)
        if result['code'] == 200:
            result = {i['asset'].upper(): float(i['free']) for i in json.loads(result['content'])['balances'] if
                      float(i['free'])}
            return result
        else:
            return result

    async def wallet(self):
        # GET /api/v3/account (HMAC SHA256)
        args = dict()
        args['url'] = '{}/api/v3/account'.format(self.url)
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['timestamp'] = int(time.time() * 1000)
        result = await self.request(args)
        if result['code'] == 200:
            result = {i['asset']: float(i['free']) + float(i['locked']) for i in
                      json.loads(result['content'])['balances'] if float(i['free']) or float(i['locked'])}
            return result
        else:
            return result

    async def create_order(self, symbol, side, amount, price, type='LIMIT', timeInForce='GTC'):
        # Post /api/v3/account (HMAC SHA256)
        # (symbol=symbol,side='BUY',type='LIMIT',quantity=1,price=10,timeInForce='GTC')
        """
        下单
        :param symbol:
        :param side:
        :param type: LIMIT 限价单,MARKET 市价单,STOP_LOSS 止损单,STOP_LOSS_LIMIT 限价止损单,TAKE_PROFIT 止盈单,TAKE_PROFIT_LIMIT 限价止盈单,LIMIT_MAKER 限价只挂单
        :param quantity:
        :param price:
        :param timeInForce: GTC	成交为止,订单会一直有效，直到被成交或者取消。IOC 无法立即成交的部分就撤销,订单在失效前会尽量多的成交。FOK	无法全部立即成交就撤销
        :return:
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
            dd = precision['price_precision']
            price = "%.*f" % (dd, price)
        if precision['minQty'] > amount:
            return {
                'content': json.dumps({"code": -1013, "msg": f"Filter failure:{amount}小于最小下单量{precision['minQty']} "}),
                'code': 400}

        if precision['minQty_quote'] > float(amount) * float(price):
            return {'content': json.dumps({"code": -1013,
                                           "msg": f"Filter failure:[amount:{amount},price:{price}] 下单总价值:{float(amount) * float(price)}小于{precision['minQty_quote']} "}),
                    'code': 400}
        args = dict()
        args['url'] = '{}/api/v3/order'.format(self.url)
        args['method'] = 'POST'
        args['signed'] = True
        args['data'] = dict()
        args['data']['symbol'] = symbol.replace('-', '')
        args['data']['side'] = side
        args['data']['type'] = type
        args['data']['quantity'] = str(amount)
        args['data']['price'] = str(price)
        args['data']['timeInForce'] = timeInForce
        args['data']['timestamp'] = int(time.time() * 1000)
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def get_open_orders(self, symbol=None):
        args = dict()
        args['url'] = '{}/api/v3/openOrders'.format(self.url)
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        if symbol:
            args['data']['symbol'] = symbol.replace('-', '')
        args['data']['timestamp'] = int(time.time() * 1000)
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def get_orders(self, symbol, orderId):
        """
        NEW	订单被交易引擎接
        PARTIALLY_FILLED 部分订单被成交
        FILLED 订单完全成交
        CANCELED 用户撤销了订单
        PENDING_CANCEL 撤销中（目前并未使用）
        REJECTED 订单没有被交易引擎接受，也没被处理
        EXPIRED 订单被交易引擎取消，比如：LIMIT FOK 订单没有成交
        :param symbol:
        :param orderId:
        :return:
        {
          "symbol": "LTCBTC", // 交易对
          "orderId": 1, // 系统的订单ID
          "orderListId": -1, // OCO订单的ID，不然就是-1
          "clientOrderId": "myOrder1", // 客户自己设置的ID
          "price": "0.1", // 订单价格
          "origQty": "1.0", // 用户设置的原始订单数量
          "executedQty": "0.0", // 交易的订单数量
          "cummulativeQuoteQty": "0.0", // 累计交易的金额
          "status": "NEW", // 订单状态
          "timeInForce": "GTC", // 订单的时效方式
          "type": "LIMIT", // 订单类型， 比如市价单，现价单等
          "side": "BUY", // 订单方向，买还是卖
          "stopPrice": "0.0", // 止损价格
          "icebergQty": "0.0", // 冰山数量
          "time": 1499827319559, // 订单时间
          "updateTime": 1499827319559, // 最后更新时间
          "isWorking": true, // 订单是否出现在orderbook中
          "workingTime":1499827319559,
          "origQuoteOrderQty": "0.000000", // 原始的交易金额
          "selfTradePreventionMode": "NONE",
          "preventedMatchId": 0,            // 这仅在订单因 STP 而过期时可见
          "preventedQuantity": "1.200000"   // 这仅在订单因 STP 而过期时可见
        }
        """
        args = dict()
        args['url'] = '{}/api/v3/order'.format(self.url)
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['symbol'] = symbol.replace('-', '')
        args['data']['orderId'] = orderId
        args['data']['timestamp'] = int(time.time() * 1000)
        result = await self.request(args)
        if result['code'] == 200:
            res = json.loads(result['content'])
            res['time'] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(res['time'] / 1000)))
            res['fillsz'] = float(res['executedQty'])

            return res
        else:
            return result

    async def get_allorders(self, symbol):
        args = dict()
        args['url'] = '{}/api/v3/allOrders'.format(self.url)
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['symbol'] = symbol.replace('-', '')
        # args['data']['orderId'] = orderId
        # args['data']['timestamp'] = int(time.time() * 1000)
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def get_Trades(self, symbol, orderId=None):
        # 历史成交数据
        # GET /api/v3/myTrades (HMAC SHA256)
        """

        :param symbol:
        :param orderId:
        :return: [
                  {
                    "symbol": "BNBBTC", // 交易对
                    "id": 28457, // trade ID
                    "orderId": 100234, // 订单ID
                    "orderListId": -1, // OCO订单的ID，不然就是-1
                    "price": "4.00000100", // 成交价格
                    "qty": "12.00000000", // 成交量
                    "quoteQty": "48.000012", // 成交金额
                    "commission": "10.10000000", // 交易费金额
                    "commissionAsset": "BNB", // 交易费资产类型
                    "time": 1499865549590, // 交易时间
                    "isBuyer": true, // 是否是买家
                    "isMaker": false, // 是否是挂单方
                    "isBestMatch": true
                  }
                ]
        """
        args = dict()
        args['url'] = '{}/api/v3/myTrades'.format(self.url)
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['symbol'] = symbol.replace('-', '')
        if orderId:
            args['data']['orderId'] = orderId
        result = await self.request(args)
        if result['code'] == 200:
            res = json.loads(result['content'])
            result = []
            for i in res:
                side = 'BUY' if i['isBuyer'] else 'SELL'
                ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(i['time'] / 1000)))
                result.append({'tradeId': i['id'], 'symbol': symbol, 'orderId': i['orderId'], 'price': i['price'],
                               'amount': i['qty'], 'fee': i['commission'], 'feecoin': i['commissionAsset'],
                               'side': side, 'time': ts, 'exchange': self.exchange_name})
            return result
        else:
            return result

    async def get_Trades_history(self, symbol, orderId=None, startTime=None, endTime=None):
        # 历史成交数据
        # GET /api/v3/myTrades (HMAC SHA256)
        """

        :param symbol:
        :param orderId:
        :return: [
                  {
                    "symbol": "BNBBTC", // 交易对
                    "id": 28457, // trade ID
                    "orderId": 100234, // 订单ID
                    "orderListId": -1, // OCO订单的ID，不然就是-1
                    "price": "4.00000100", // 成交价格
                    "qty": "12.00000000", // 成交量
                    "quoteQty": "48.000012", // 成交金额
                    "commission": "10.10000000", // 交易费金额
                    "commissionAsset": "BNB", // 交易费资产类型
                    "time": 1499865549590, // 交易时间
                    "isBuyer": true, // 是否是买家
                    "isMaker": false, // 是否是挂单方
                    "isBestMatch": true
                  }
                ]
        """
        args = dict()
        args['url'] = '{}/api/v3/myTrades'.format(self.url)
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['symbol'] = symbol.replace('-', '')
        if orderId:
            args['data']['orderId'] = orderId
        if startTime:
            args['data']['startTime'] = startTime
        if endTime:
            args['data']['endTime'] = endTime
        result = await self.request(args)
        if result['code'] == 200:
            res = json.loads(result['content'])
            result = []
            for i in res:
                side = 'BUY' if i['isBuyer'] else 'SELL'
                ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(i['time'] / 1000)))
                result.append({'tradeId': i['id'], 'symbol': symbol, 'orderId': i['orderId'], 'price': i['price'],
                               'amount': i['qty'], 'fee': i['commission'], 'feecoin': i['commissionAsset'],
                               'side': side, 'time': ts, 'exchange': self.exchange_name})
            return result
        else:
            return result

    async def cancel_order(self, symbol, orderId):
        args = dict()
        args['url'] = '{}/api/v3/order'.format(self.url)
        args['method'] = 'DELETE'
        args['signed'] = True
        args['data'] = dict()
        args['data']['symbol'] = symbol.replace('-', '')
        args['data']['orderId'] = orderId
        args['data']['timestamp'] = int(time.time() * 1000)
        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def cancel_symbol(self, symbol):
        # DELETE /api/v3/openOrders
        args = dict()
        args['url'] = '{}/api/v3/openOrders'.format(self.url)
        args['method'] = 'DELETE'
        args['signed'] = True
        args['data'] = dict()
        args['data']['symbol'] = symbol.replace('-', '')
        args['data']['timestamp'] = int(time.time() * 1000)
        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def cancelReplace(self, symbol, side, orderId, amount, price, type='LIMIT',
                            cancelReplaceMode='STOP_ON_FAILURE', timeInForce='GTC'):
        # POST /api/v3/order/cancelReplace
        """
        :param symbol:
        :param orderId:
        :param cancelReplaceMode: 指定类型：STOP_ON_FAILURE - 如果撤消订单失败将不会继续重新下单。
                                          ALLOW_FAILURE - 不管撤消订单是否成功都会继续重新下单。
        :return:
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
            dd = precision['price_precision']
            price = "%.*f" % (dd, price)

        args = dict()
        args['url'] = '{}/api/v3/order/cancelReplace'.format(self.url)
        args['method'] = 'POST'
        args['signed'] = True
        args['data'] = dict()
        args['data']['symbol'] = symbol.replace('-', '')
        args['data']['side'] = side
        args['data']['type'] = type
        args['data']['cancelReplaceMode'] = cancelReplaceMode
        args['data']['cancelOrderId'] = str(orderId)
        args['data']['quantity'] = amount
        args['data']['timeInForce'] = timeInForce
        args['data']['price'] = price
        result = await self.request(args)

        if result['code'] == 200:
            res = json.loads(result['content'])
        else:
            res = json.loads(result['content'])['data']

        result = []
        orderIds = None
        cancel_status = False
        if res['cancelResult'] == 'SUCCESS':
            i = res['cancelResponse']
            result.append(
                {'status': i['status'], 'symbol': symbol, 'orderId': i['orderId'], 'price': float(i['price']),
                 'amount': float(i['origQty']), 'side': side, 'exchange': self.exchange_name, 'time': ''})
            cancel_status = True
        if res['newOrderResult'] == 'SUCCESS':
            i = res['newOrderResponse']
            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(i['transactTime'] / 1000)))
            result.append(
                {'status': i['status'], 'symbol': symbol, 'orderId': i['orderId'], 'price': float(i['price']),
                 'amount': float(i['origQty']), 'side': side, 'exchange': self.exchange_name, 'time': ts})
            orderIds = i['orderId']

        return result, orderIds, cancel_status

    async def depth(self, symbol, limit=5):
        # 当前委托
        # GET /api/v3/depth
        """
        :param symbol:
        :param limit: 默认 100; 最大 5000. 可选值:[5, 10, 20, 50, 100, 500, 1000, 5000] 如果 limit > 5000, 最多返回5000条数据.
        :return:
        """
        args = dict()
        args['url'] = '{}/api/v3/depth'.format(self.url)
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

    async def precision(self, symbol):
        # 当前委托
        # GET /api/v3/depth
        args = dict()
        args['url'] = '{}/api/v3/exchangeInfo'.format(self.url)
        args['method'] = 'GET'
        args['signed'] = False
        args['data'] = dict()
        args['data']['symbol'] = symbol.replace('-', '')
        result = await self.request(args)

        if result['code'] == 200:
            res = json.loads(result['content'])['symbols'][0]['filters']
            precision = {}
            for i in res:
                if i['filterType'] == 'PRICE_FILTER':
                    precision['minPrice'] = float(i['minPrice'])
                    precision['price_precision'] = -math.ceil(math.log10(float(float(i['tickSize']))))

                if i['filterType'] == 'LOT_SIZE':
                    precision['minQty'] = float(i['minQty'])
                    precision['amount_precision'] = -math.ceil(math.log10(float(float(i['stepSize']))))

                if i['filterType'] == 'MIN_NOTIONAL':
                    precision['minQty_quote'] = float(i['minNotional'])
            return precision
        else:
            return result

    async def deposit_history(self):
        # 获取充值历史(支持多网络) (USER_DATA)
        # GET /sapi/v1/capital/deposit/hisrec (HMAC SHA256)
        """
        :return:0(0:pending,6: credited but cannot withdraw, 1:success)
        """
        args = dict()
        args['url'] = '{}/sapi/v1/capital/deposit/hisrec'.format(self.url)
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
                tmp['currency'] = i['coin']
                tmp['address'] = i['address']
                tmp['hash'] = i.get('txId', '')
                tmp['amount'] = i['amount']
                tmp['fee'] = i.get('transactionFee', 0)
                tmp['side'] = 'deposit'
                tmp['ctime'] = int(i['insertTime'] / 1000)
                tmp['mtime'] = int(i['insertTime'] / 1000)
                tmp['time'] = datetime.fromtimestamp(tmp['ctime']).strftime("%Y-%m-%d %H:%M:%S")
                tmp['status'] = str(i['status'])
                tmp['status1'] = self.deposit_status.get(str(i['status']), str(i['status']))
                mm.append(tmp)
            return mm

        else:
            return result

    async def withdraw_history(self):
        # 获取提币历史 (支持多网络) (USER_DATA)
        # GET /sapi/v1/capital/withdraw/history (HMAC SHA256)
        """
        :return: status	INT	NO	0(0:已发送确认Email,1:已被用户取消 2:等待确认 3:被拒绝 4:处理中 5:提现交易失败 6 提现完成)
        """
        args = dict()
        args['url'] = '{}/sapi/v1/capital/withdraw/history'.format(self.url)
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
                tmp['currency'] = i['coin']
                tmp['address'] = i['address']
                tmp['hash'] = i.get('txId', '')
                tmp['amount'] = i['amount']
                tmp['fee'] = i.get('transactionFee', 0)
                tmp['side'] = 'withdraw'
                tmp['ctime'] = datetime.strptime(i['applyTime'], "%Y-%m-%d %H:%M:%S").timestamp() if i['applyTime'] else ""
                tmp['mtime'] = datetime.strptime(i['completeTime'], "%Y-%m-%d %H:%M:%S").timestamp() if i['completeTime'] else ""
                tmp['time'] = datetime.fromtimestamp(tmp['ctime']).strftime("%Y-%m-%d %H:%M:%S") if tmp['ctime'] else ""
                tmp['status'] = str(i['status'])
                tmp['status1'] = self.withdraw_status.get(str(i['status']), str(i['status']))
                mm.append(tmp)
            return mm

        else:
            return result

    async def deposit_address(self, currency):
        # 获取充值地址 (支持多网络) (USER_DATA)
        # GET /sapi/v1/capital/deposit/address (HMAC SHA256)
        # 如果不发送 network, 将按该币种默认网络返回结果；
        # 可以在接口Get /sapi/v1/capital/config/getall (HMAC SHA256)的返回值中某币种的networkList 获取 network网络字段和isDefault是否为默认网络。
        args = dict()
        args['url'] = '{}/sapi/v1/capital/withdraw/history'.format(self.url)
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['coin'] = currency
        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def margin_transfer(self, currency, amount, type):
        # 全仓杠杆账户划转 执行现货账户与全仓杠杆账户之间的划转
        args = dict()
        args['url'] = '{}/sapi/v1/margin/transfer'.format(self.url)
        args['method'] = 'POST'
        args['signed'] = True
        args['data'] = dict()
        args['data']['asset'] = currency
        args['data']['amount'] = amount
        args['data']['type'] = type  # 1: 主账户向全仓杠杆账户划转 2: 全仓杠杆账户向主账户划转
        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def margin_loan(self, currency, amount, symbol, isIsolated=False):
        # 杠杆账户借贷 申请借贷
        # 如果 isIsolated = “TRUE”, 表示逐仓借贷，此时 symbol 必填
        # 如果isIsolated = “FALSE” 表示全仓借贷
        args = dict()
        args['url'] = '{}/sapi/v1/margin/loan'.format(self.url)
        args['method'] = 'POST'
        args['signed'] = True
        args['data'] = dict()
        args['data']['asset'] = currency
        args['data']['amount'] = amount
        if isIsolated:
            args['data']['symbol'] = symbol
        args['data']['isIsolated'] = isIsolated  # 是否逐仓杠杆，"TRUE", "FALSE", 默认 "FALSE"

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def margin_repay(self, currency, amount, symbol, isIsolated=False):
        # 杠杆账户归还借贷 获取杠杆账户归还借贷
        args = dict()
        args['url'] = '{}/sapi/v1/margin/repay'.format(self.url)
        args['method'] = 'POST'
        args['signed'] = True
        args['data'] = dict()
        args['data']['asset'] = currency
        args['data']['amount'] = amount
        if isIsolated:
            args['data']['symbol'] = symbol
        args['data']['isIsolated'] = isIsolated  # 是否逐仓杠杆，"TRUE", "FALSE", 默认 "FALSE"

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def margin_allAssets(self, ):
        # 获取所有杠杆资产信息
        args = dict()
        args['url'] = '{}/sapi/v1/margin/allAssets'.format(self.url)
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def margin_loan_list(self, currency=None, isolatedSymbol=None, txId=None, startTime=None, endTime=None, page=1, size=10):
        # 查询借贷记录
        """
        必须发送txId 或 startTime，txId 优先。
        响应返回为降序排列。
        如果发送isolatedSymbol，返回指定逐仓symbol指定asset的借贷记录。
        查询时间范围最大不得超过30天。
        若startTime和endTime没传，则默认返回最近7天数据
        """
        args = dict()
        args['url'] = '{}/sapi/v1/margin/loan'.format(self.url)
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()

        if currency:
            args['data']['asset'] = currency
        if isolatedSymbol:
            args['data']['isolatedSymbol'] = isolatedSymbol  # 逐仓symbol
        if txId:
            args['data']['txId'] = txId  # tranId in POST /sapi/v1/margin/loan
        if startTime:
            args['data']['startTime'] = startTime
        if endTime:
            args['data']['endTime'] = endTime
        args['data']['current'] = page  # 当前查询页。 开始值 1。 默认:1
        args['data']['size'] = size  # 默认:10 最大:100
        print(args)
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def margin_repay_list(self, currency=None, isolatedSymbol=None, txId=None, startTime=None, endTime=None, page=1, size=10):
        # 查询还贷记录
        """
        必须发送txId 或 startTime，txId 优先。
        响应返回为降序排列。
        如果发送isolatedSymbol，返回指定逐仓symbol指定asset的借贷记录。
        查询时间范围最大不得超过30天。
        若startTime和endTime没传，则默认返回最近7天数据
        """
        args = dict()
        args['url'] = '{}/sapi/v1/margin/repay'.format(self.url)
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()

        if currency:
            args['data']['asset'] = currency
        if isolatedSymbol:
            args['data']['isolatedSymbol'] = isolatedSymbol
        if txId:
            args['data']['txId'] = txId
        if startTime:
            args['data']['startTime'] = startTime
        if endTime:
            args['data']['endTime'] = endTime
        args['data']['current'] = page  # 当前查询页。 开始值 1。 默认:1
        args['data']['size'] = size  # 默认:10 最大:100
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def margin_maxBorrowable(self, currency=None, isolatedSymbol=None):
        # 查询账户最大可借贷额度
        args = dict()
        args['url'] = '{}/sapi/v1/margin/maxBorrowable'.format(self.url)
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        result = await self.request(args)
        args['data']['asset'] = currency
        if isolatedSymbol:
            args['data']['isolatedSymbol'] = isolatedSymbol

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def margin_account(self):
        # 获取所有杠杆资产信息
        args = dict()
        args['url'] = '{}/sapi/v1/margin/account'.format(self.url)
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def contract_account(self):
        # 获取所有杠杆资产信息
        args = dict()
        args['url'] = '{}/fapi/v2/account'.format(self.url)
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result


if __name__ == '__main__':
    api = {'apiKey': '',
           'secret': ''}
    bb = BinanceApi(apiKey=api['apiKey'], secret=api['secret'])
    wallet = asyncio.run(bb.wallet())
    from pprint import pprint

    pprint(wallet)
