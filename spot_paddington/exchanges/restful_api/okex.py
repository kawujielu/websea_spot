import datetime, time
import hmac
import json
import math
import base64
from operator import itemgetter
from many_configs.account_config import EXTERNAL_ACCOUNTS
from many_configs import global_variable
from scaffold.aiohttp import G_RequestSession
from many_configs.exchange_config import EXCHANGE_CONFIG
from libs.utils import digit_to_string
from libs.utils import round_down
from loguru import logger


class OkexApi:
    exchange_name = "okex"

    def __init__(self, api_key=None, secret=None, password=None, flag='0'):
        self._apiKey_ = api_key if api_key else EXTERNAL_ACCOUNTS[self.exchange_name]["apiKey"]
        self._secret_ = secret if secret else EXTERNAL_ACCOUNTS[self.exchange_name]["secret"]
        self._password_ = password if password else EXTERNAL_ACCOUNTS[self.exchange_name]["password"]
        self.flag = flag if flag == "1" else EXTERNAL_ACCOUNTS[self.exchange_name]["flag"]
        self.url = EXCHANGE_CONFIG[self.exchange_name]['spot_restful']

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
        m = hmac.new(self._secret_.encode('utf-8'), query_string.encode('utf-8'), digestmod='sha256')
        e = base64.b64encode(m.digest())
        return str(e, encoding='utf-8')

    def get_timestamp(self):
        now = datetime.datetime.utcnow()
        t = now.isoformat("T", "milliseconds")
        return t + "Z"

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
        timestamp = self.get_timestamp()
        body = json.dumps(data) if method == 'POST' else ''
        request_path = args['url'] + self.parse_params_to_str(data)
        url = self.url + request_path

        args['header'] = dict()
        result = {}
        if signed:
            # 所有REST私有请求头都必须包含以下内容：
            # args['header']['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'
            args['header']['Content-Type'] = 'application/json'
            args['header']['OK-ACCESS-KEY'] = self._apiKey_
            args['header']['OK-ACCESS-SIGN'] = self._generate_signature(timestamp, method, request_path, body)
            args['header']['OK-ACCESS-TIMESTAMP'] = str(timestamp)
            args['header']['OK-ACCESS-PASSPHRASE'] = self._password_
            args['header']['x-simulated-trading'] = self.flag

        async with G_RequestSession.request.request(method=method,
                                                    url=url,
                                                    headers=args['header'],
                                                    data=body,
                                                    # proxy='http://127.0.0.1:51436',
                                                    timeout=5) as r:
            result['content'] = await r.text()

            result['code'] = r.status
        return result

    async def wallet_free(self, currency=None):
        # GET /api/v3/account (HMAC SHA256)
        args = dict()
        args['url'] = '/api/v5/account/balance'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        if currency:
            args['data']['ccy'] = currency
        result = await self.request(args)
        logger.info(result)
        if result['code'] == 200:
            content = json.loads(result['content'])
            result = {i['ccy'].upper(): float(i['availBal']) for i in content['data'][0]['details'] if
                      float(i['cashBal'])}
            return result
        else:
            return result

    async def wallet(self, currency=None):
        # GET /api/v3/account (HMAC SHA256)
        args = dict()
        args['url'] = '/api/v5/account/balance'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        if currency:
            args['data']['ccy'] = currency
        result = await self.request(args)
        if result['code'] == 200:
            content = json.loads(result['content'])
            result = {i['ccy']: float(i['cashBal']) for i in content['data'][0]['details'] if float(i['cashBal'])}
            return result
        else:
            return result

    async def create_order(self, symbol, side, amount, price, type='LIMIT', tdMode='cash'):
        # POST /api/v5/trade/order
        """
        :param symbol:
        :param tdMode:交易模式 保证金模式：isolated：逐仓 ；cross：全仓。非保证金模式：cash：非保证金
        :param side:订单方向 buy：买， sell：卖
        :param type:订单类型 market：市价单,limit：限价单,post_only：只做maker单,fok：全部成交或立即取消,ioc：立即成交并取消剩余,optimal_limit_ioc：市价委托立即成交并取消剩余（仅适用交割、永续）
        :param amount:委托数量
        :param price: 委托价格，仅适用于limit、post_only、fok、ioc类型的订单
        :param timeInForce:
        :return:
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
            amount = round_down(amount, precision['amount_precision'])
        if precision['price_precision'] == 0:
            price = int(price)
        else:
            price = round(price, precision['price_precision'])

        if precision['minQty'] > amount:
            return {'content': {"code": -1013, "msg": f"Filter failure:{amount}小于最小下单量{precision['minQty']} "},
                    'code': 400}

        args = dict()
        # args['url'] = '/api/v5/trade/batch-orders'
        args['url'] = '/api/v5/trade/order'
        args['method'] = 'POST'
        args['signed'] = True
        args['data'] = dict()

        args['data']['instId'] = symbol
        args['data']['tdMode'] = tdMode
        args['data']['side'] = side.lower()
        args['data']['ordType'] = type.lower()
        args['data']['sz'] = amount
        args['data']['px'] = digit_to_string(price)
        result = await self.request(args)
        if result['code'] == 200:
            data = json.loads(result['content'])['data'][0]
            return {'orderId': data['ordId'], 'sMsg': data['sMsg']}
        else:
            return result

    async def get_orders(self, symbol, orderId):
        # 获取订单信息
        # GET /api/v5/trade/order
        """
        :param symbol:
        :param orderId:
        :return:
        state:订单状态 canceled：撤单成功 live：等待成交 partially_filled：部分成交 filled：完全成交
        """
        args = dict()
        args['url'] = '/api/v5/trade/order'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['ordId'] = orderId
        args['data']['instId'] = symbol
        result = await self.request(args)

        if result['code'] == 200:
            res = json.loads(result['content'])
            if res['code'] == '0':
                res['status'] = res['data'][0]['state'].upper()
                res['fillsz'] = float(res['data'][0]['fillSz'])
            return res
        else:
            return result

    async def get_open_orders(self, symbol=None, instType='SPOT'):
        # 获取未成交订单列表
        args = dict()
        args['url'] = '/api/v5/trade/orders-pending'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['instType'] = instType
        if symbol:
            args['data']['instId'] = symbol
        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def cancel_order(self, symbol, orderId=None):
        # POST /api/v5/trade/cancel-order
        """
        :param symbol:
        :param orderId: 订单ID， ordId和clOrdId必须传一个，若传两个，以ordId为主
        :return:
        """
        args = dict()
        args['url'] = '/api/v5/trade/cancel-order'
        args['method'] = 'POST'
        args['signed'] = True
        args['data'] = dict()
        args['data']['instId'] = symbol
        if orderId:
            args['data']['ordId'] = orderId

        result = await self.request(args)
        if result['code'] == 200:
            res = json.loads(result['content'])
            if res['code'] == '0' and res['data'][0]['sCode'] == '0':
                res['status'] = 'CANCELED'
            else:
                res['status'] = res.get('msg', 'failed')
            return res
        else:
            return result

    async def depth(self, symbol, limit=5):
        # GET /api/v5/market/books
        """
        :param symbol:
        :param orderId: 订单ID， ordId和clOrdId必须传一个，若传两个，以ordId为主
        :return:
        """
        args = dict()
        args['url'] = '/api/v5/market/books'
        args['method'] = 'GET'
        args['signed'] = False
        args['data'] = dict()
        args['data']['instId'] = symbol
        if limit:
            args['data']['sz'] = limit

        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])['data'][0]
        else:
            return result

    async def precision(self, symbol=None, instType='SPOT'):
        # GET /api/v5/public/instruments
        """
        :param symbol:产品类型 SPOT：币币,MARGIN：币币杠杆,SWAP：永续合约,FUTURES：交割合约,OPTION：期权
        :param orderId: 订单ID， ordId和clOrdId必须传一个，若传两个，以ordId为主
        :return:
        """
        args = dict()
        args['url'] = '/api/v5/public/instruments'
        args['method'] = 'GET'
        args['signed'] = False
        args['data'] = dict()
        args['data']['instType'] = instType
        if symbol:
            args['data']['instId'] = symbol
        result = await self.request(args)

        if result['code'] == 200:
            i = json.loads(result['content'])['data'][0]
            precision = {}

            precision['price_precision'] = -math.ceil(math.log10(float(float(i['tickSz']))))
            precision['minQty'] = float(i['minSz'])
            precision['amount_precision'] = -math.ceil(math.log10(float(float(i['lotSz']))))
            return precision
        else:
            return result

    async def get_trades(self, symbol=None, orderId=None, instType='SPOT'):
        # 成交明细
        # GET /api/v5/trade/fills
        args = dict()
        args['url'] = '/api/v5/trade/fills'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['instType'] = instType
        if symbol:
            args['data']['instId'] = symbol
        if orderId:
            args['data']['ordId'] = orderId
        result = await self.request(args)
        if result['code'] == 200:
            res = []
            for i in json.loads(result['content'])['data']:
                ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(float(i['ts']) / 1000)))
                d = {
                    'side': i['side'].upper(),
                    'amount': float(i['fillSz']),
                    'tradeId': i['tradeId'],
                    'price': float(i['fillPx']),
                    'fee': i['fee'],
                    'feecoin': i['feeCcy'],
                    'time': ts,
                    'orderId': i['ordId'],
                    'symbol': symbol,
                    'exchange': self.exchange_name

                }
                res.append(d)
            return res
        else:
            return result

    async def get_trades_history(self, symbol=None, instType='SPOT', startTime=None, endTime=None):
        # 成交明细
        # GET /api/v5/trade/fills
        args = dict()
        args['url'] = '/api/v5/trade/fills'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['instType'] = instType
        if symbol:
            args['data']['instId'] = symbol
        if startTime:
            args['data']['begin'] = startTime
        if endTime:
            args['data']['end'] = endTime
        result = await self.request(args)
        if result['code'] == 200:
            res = []
            for i in json.loads(result['content'])['data']:
                ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(float(i['ts']) / 1000)))
                d = {
                    'side': i['side'].upper(),
                    'amount': float(i['fillSz']),
                    'tradeId': i['tradeId'],
                    'price': float(i['fillPx']),
                    'fee': i['fee'],
                    'feecoin': i['feeCcy'],
                    'time': ts,
                    'orderId': i['ordId'],
                    'symbol': symbol,
                    'exchange': self.exchange_name

                }
                res.append(d)
            return res
        else:
            return result


okex_instance = OkexApi()
global_variable.EXTERNAL_EXCHANGE_INSTANCES[okex_instance.exchange_name] = okex_instance

if __name__ == '__main__':
    import asyncio

    api = {'apiKey': "ea1ca7de-40f6-4629-9924-061abdb03046", 'secret': "DC8784AFC1CDC4EC0663E54929CCDA42",
           'password': 'Ok123456.', 'flag': '1'}

    # a = Client(apiKey=api['apiKey'], secret=api['secret']).wallet()
    symbol = 'OKB-USDT'
    side = 'BUY'
    amount = 20
    price = 31.493
    ok = OkexApi(api_key=api['apiKey'], secret=api['secret'], password=api['password'], flag=api['flag'])
    # a = asyncio.run(ok.create_order(symbol=symbol, side=side, amount=amount, price=price))
    a = asyncio.run(ok.depth('ETH-USDT'))

    #
    # ok_wallet = {i['ccy']: float(i['cashBal']) for i in a['data'][0]['details'] if float(i['cashBal'])}
    # 531499829424390144 531499528474689536
    # a = ok.get_open_orders(symbol=symbol, orderId='531501991852343296')
    # a = ok.get_orderssss(symbol=symbol,)
    # a = ok.get_orderssss(symbol=symbol, orderId='531496949611069440')
    # a = asyncio.run(ok.get_trades(symbol=symbol, orderId='535467976917610496'))
    # a = asyncio.run(ok.cancel_order(symbol=symbol, orderId='535467976917610496'))
    # a = ok.precision(symbol=symbol)