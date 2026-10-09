import time, datetime
import hmac
import json
import base64
from operator import itemgetter
from loguru import logger
from libs.requestSession import G_RequestSession
from datetime import datetime


class BitgetApi:
    exchange_name = "bitget"

    def __init__(self, apiKey=None, secret=None, password=None):
        self._apiKey_ = apiKey
        self._secret_ = secret
        self._password_ = password
        self.url = 'https://api.bitget.com'
        self.deposit_status = {'0': 'pending', '6': 'credited but cannot withdraw', '1': '成功'}
        self.withdraw_status = {'pending': '确认中', 'fail': '失败', 'success': '成功', }

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
        # ordered_data = self._order_params(data)
        # query_string = '&'.join(["{}={}".format(d[0], d[1]) for d in ordered_data])
        query_string = str(timestamp) + str(method) + str(path) + str(body)
        # m = hmac.new(self._secret_.encode('utf-8'), query_string.encode('utf-8'), digestmod='sha256')
        m = hmac.new(bytes(self._secret_, encoding='utf-8'), bytes(query_string, encoding='utf-8'), digestmod='sha256')
        e = base64.b64encode(m.digest())
        return str(e, encoding='utf-8')
        # return base64.b64encode(m.digest())

    def pre_hash(timestamp, method, request_path, body):
        return str(timestamp) + str.upper(method) + request_path + body

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
        kwargs = dict()
        kwargs['timeout'] = 15
        # timestamp = self.get_timestamp()
        timestamp = int(time.time() * 1000)
        body = json.dumps(data) if method == 'POST' else ''
        request_path = args['url'] + self.parse_params_to_str(data)
        url = self.url + request_path

        args['header'] = dict()

        if signed:
            # 所有REST私有请求头都必须包含以下内容：
            # args['header']['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'
            args['header']['Content-Type'] = 'application/json'
            args['header']['ACCESS-KEY'] = self._apiKey_
            args['header']['ACCESS-SIGN'] = self._generate_signature(timestamp, method, request_path, body)
            args['header']['ACCESS-TIMESTAMP'] = str(timestamp)
            args['header']['ACCESS-PASSPHRASE'] = self._password_
            args['header']['localeg'] = 'zh-CN'  # 支持多语言, 如：中文(zh-CN),英语(en-US)"""
        result = {}
        if args['method']:
            async with G_RequestSession.request.request(method=method,
                                                        url=url,
                                                        headers=args['header'],
                                                        data=body,
                                                        # proxy='http://127.0.0.1:7890',
                                                        timeout=15) as r:
                result['content'] = await r.text()
                result['code'] = r.status
                print(result)
            return result

    async def wallet(self):
        # GET /api/spot/v1/account/assets
        args = dict()
        args['url'] = '/api/v2/spot/account/assets'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        result = await self.request(args)
        if result['code'] == 200:
            result = {i['coin']: float(i['available']) + float(i['frozen']) for i in
                      json.loads(result['content'])['data'] if float(i['available']) or float(i['frozen'])}
            return result
        else:
            return result

    async def wallet_free(self):
        # GET /api/spot/v1/account/assets
        args = dict()
        args['url'] = '/api/v2/spot/account/assets'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        result = await self.request(args)
        if result['code'] == 200:
            result = {i['coin']: float(i['available']) for i in
                      json.loads(result['content'])['data'] if float(i['available'])}
            return result
        else:
            return result

    async def add(self, symbol, side, amount, price, type='limit', force='gtc'):
        # POST /api/spot/v1/trade/orders
        """
        :param symbol:
        :param side:
        :param amount:
        :param price:
        :param type:
        :param force:normal	不用特殊控制类型订单,post_only	postOnly类型订单,fok	全部成交或立即取消（FOK）,ioc	立即成交并取消剩余（IOC）
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

        if precision['minQtyQuote'] > float(amount) * float(price):
            return {'content': json.dumps({"code": -1013,
                                           "msg": f"Filter failure:[amount:{amount},price:{price}] 下单总价值:{float(amount) * float(price)}小于{precision['minQtyQuote']} "}),
                    'code': 400}
        args = dict()
        args['url'] = '/api/v2/spot/trade/place-order'
        # args['url'] = '/api/spot/v1/trade/orders'
        args['method'] = 'POST'
        args['signed'] = True
        args['data'] = dict()

        args['data']['symbol'] = symbol.replace('-', '')
        args['data']['side'] = side.lower()
        args['data']['orderType'] = type.lower()
        args['data']['size'] = amount
        args['data']['price'] = price
        args['data']['force'] = force
        print(args)
        result = await self.request(args)
        print(result)

        # if result['code'] == 200:
        #     print(result)
        #     data = json.loads(result['content'])['data']
        #     return {'orderId': data['orderId'], 'status': 'NEW'}
        # else:
        return result

    async def create_order(self, symbol, side, amount, price, type='limit', force='gtc'):
        result = await self.add(symbol, side, amount, price, type, force)
        if result['code'] == 200:
            data = json.loads(result['content'])['data']
            return {'orderId': data['orderId'], 'status': 'NEW'}
        elif result['code'] == 400:
            content = json.loads(result['content'])
            error_precision = [
                {"code": "41103", "msg": "param delegatePrice scale error error"},
                {"code": "40808", "msg": "Parameter verification exception size checkBDScale error value=0.00025 checkScale=4"}

            ]
            error_precision = [i['code'] for i in error_precision]
            if content.get('code') in error_precision:
                precision = await self.precision(symbol)
                result = await self.add(symbol, side, amount, price)
                # 修改精度
                if result['code'] == 200:
                    data = json.loads(result['content'])['data']
                    print(data)
                    return {'orderId': data['orderId'], 'status': 'NEW'}
            return {'code': 400, 'content': content}
        return result

    async def get_orders(self, symbol, orderId):
        # 获取订单信息
        # 根据订单id或者自定义id获取订单
        # POST /api/spot/v1/trade/orderInfo
        """
        参数名	参数类型	是否必须	描述
        symbol	String	是	产品ID
        orderId	String	是	订单id
        clientOrderId	String	否	自定义id
        :param symbol:
        :param orderId:
        :return:
        """
        args = dict()
        args['url'] = '/api/v2/spot/trade/orderInfo'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['orderId'] = orderId
        # args['data']['symbol'] = symbol.replace('-', '')
        result = await self.request(args)
        if result['code'] == 200:
            res = json.loads(result['content'])['data'][0]
            res['fillsz'] = float(res['baseVolume'])
            res['status'] = res['status'].upper()
            if res['status'] == 'CANCELLED':
                res['status'] = 'CANCELED'
            return res
        else:
            return result

    async def get_open_orders(self, symbol=None):
        # 获取未成交和部分成交未撤单的订单
        # POST /api/spot/v1/trade/open-orders
        args = dict()
        args['url'] = '/api/spot/v1/trade/open-orders'
        args['method'] = 'POST'
        args['signed'] = True
        args['data'] = dict()
        if symbol:
            args['data']['instId'] = symbol.replace('-', '')
        result = await self.request(args)
        return result

    async def cancel_order(self, symbol, orderId=None):
        # POST /api/spot/v1/trade/cancel-order
        args = dict()
        # args['url'] = '/api/v2/spot/trade/orderInfo'
        args['url'] = '/api/v2/spot/trade/cancel-order'
        args['method'] = 'POST'
        args['signed'] = True
        args['data'] = dict()
        if orderId:
            args['data']['orderId'] = orderId
        args['data']['symbol'] = symbol.replace('-', '')
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def depth(self, symbol, limit=5):
        # GET /api/spot/v1/market/depth
        args = dict()
        args['url'] = '/api/v2/spot/market/merge-depth'
        args['method'] = 'GET'
        args['signed'] = False
        args['data'] = dict()
        args['data']['symbol'] = symbol.replace('-', '')
        args['data']['limit'] = limit
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])['data']
        else:
            return result

    async def precision(self, symbol, ):
        # GET /api/spot/v1/public/product
        """
        :param symbol:产品类型 SPOT：币币,MARGIN：币币杠杆,SWAP：永续合约,FUTURES：交割合约,OPTION：期权
        :param orderId: 订单ID， ordId和clOrdId必须传一个，若传两个，以ordId为主
        :return:
        """
        args = dict()
        args['url'] = '/api/v2/spot/public/symbols'
        args['method'] = 'GET'
        args['signed'] = False
        args['data'] = dict()
        args['data']['symbol'] = symbol.replace('-', '')
        result = await self.request(args)

        if result['code'] == 200:
            res = json.loads(result['content'])['data']
            precision = {}
            for i in res:
                precision['price_precision'] = int(i['pricePrecision'])
                precision['amount_precision'] = int(i['quantityPrecision'])
                precision['minQty'] = float(i['minTradeAmount'])
                precision['minQtyQuote'] = float(i['minTradeUSDT'])
            return precision
        else:
            return result

    async def get_trades(self, symbol, orderId):
        # 成交明细
        # 获取成交的历史明细
        # POST /api/spot/v1/trade/fills
        """参数名	参数类型	是否必须	描述
        symbol	String	是	产品Id
        orderId	String	否	订单ID
        after	String	否	传入 orderId， 在这 orderId 之前的数据 desc
        before	String	否	传入 orderId 在这 orderId 之后的数据 asc
        limit	Integer	否	返回结果的数量，默认100，最大 500"""
        args = dict()
        args['url'] = '/api/v2/spot/trade/fills'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['symbol'] = symbol.replace('-', '')
        args['data']['orderId'] = orderId
        args['data']['limit'] = 100
        result = await self.request(args)
        if result['code'] == 200:
            res = []
            dd = json.loads(result['content'])
            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(float(dd['requestTime']) / 1000)))
            for i in dd['data']:
                d = {
                    'side': i['side'].upper(),
                    'amount': float(i['size']),
                    'tradeId': i['tradeId'],
                    'price': float(i['priceAvg']),
                    'fee': abs(float(i['feeDetail']['totalFee'])),
                    'feecoin': i['feeDetail']['feeCoin'],
                    'time': ts,
                    'orderId': i['orderId'],
                    'symbol': symbol,
                    'exchange': self.exchange_name
                }
                res.append(d)
            return res
        else:
            return result

    async def deposit_history(self, startTime=int(time.time() * 1000 - 60 * 60 * 24 * 1000), endTime=int(time.time() * 1000)):
        args = dict()
        args['url'] = '/api/v2/spot/wallet/deposit-records'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['startTime'] = startTime
        args['data']['endTime'] = endTime
        print(args)
        result = await self.request(args)

        if result['code'] == 200:
            res = json.loads(result['content'])
            mm = []
            for i in res['data']:
                tmp = {}
                tmp['exchange'] = self.exchange_name
                tmp['id'] = i['id']
                tmp['currency'] = i['coin']
                tmp['address'] = i['address']
                tmp['hash'] = i.get('tradeId', '')
                tmp['amount'] = i['amount']
                tmp['fee'] = i.get('fee', 0)
                tmp['side'] = 'deposit'
                tmp['ctime'] = int(float(i['cTime']) / 1000)
                tmp['mtime'] = int(float(i['uTime'] / 1000))
                tmp['time'] = datetime.fromtimestamp(tmp['ctime']).strftime("%Y-%m-%d %H:%M:%S")
                tmp['status'] = str(i['status'])
                tmp['status1'] = self.deposit_status.get(str(i['status']), str(i['status']))
                mm.append(tmp)
            return mm

        else:
            return result

    async def withdraw_history(self, startTime=int(time.time() * 1000 - 60 * 60 * 24 * 1000), endTime=int(time.time() * 1000)):
        args = dict()
        args['url'] = '/api/v2/spot/wallet/withdrawal-records'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['startTime'] = startTime
        args['data']['endTime'] = endTime
        result = await self.request(args)
        if result['code'] == 200:
            res = json.loads(result['content'])
            mm = []
            for i in res['data']:
                tmp = {}
                tmp['exchange'] = self.exchange_name
                tmp['id'] = i['orderId']
                tmp['currency'] = i['coin']
                tmp['address'] = i['toAddress']
                tmp['hash'] = i.get('tradeId', '')
                tmp['amount'] = i['amount']
                tmp['fee'] = i.get('fee', 0)
                tmp['side'] = 'withdraw'
                tmp['ctime'] = int(float(i['cTime'] / 1000))
                tmp['mtime'] = int(float(i['uTime'] / 1000))
                tmp['time'] = datetime.fromtimestamp(tmp['ctime']).strftime("%Y-%m-%d %H:%M:%S")
                tmp['status'] = str(i['status'])
                tmp['status1'] = self.withdraw_status.get(str(i['status']), str(i['status']))
                mm.append(tmp)
            return mm

        else:
            return result


bitget_instance = BitgetApi()

if __name__ == '__main__':
    from pprint import pprint
    import asyncio

    api = {'apiKey': '', 'secret': '', 'password': ''}
    ao = BitgetApi(**api)
    symbol = 'BTC-USDT'
    side = 'BUY'
    amount = 0.00031
    price = 34537.111
    orderId = '1101081436268969984'
    a = asyncio.run(ao.withdraw_history())
    print(a)
