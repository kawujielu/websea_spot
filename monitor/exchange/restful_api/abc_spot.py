import datetime
import json
import logging
import time
import hashlib
import random
import string
import aiohttp
import urllib3
import requests
import ssl
import asyncio
import threading
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
from config.infor_load import spot_host
from aiohttp import TCPConnector

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

host = "https://exq.wtest.club"
contract_host = "https://coq.wtest.club"

SYMBOLS_ORDER_CONDITION = {}


class AApi(object):

    def __init__(self, token, secret_key, flag='', debug=True):
        self.host = spot_host if not flag else 'https://oapi.websea.com'
        self.contract_host = contract_host

        self._token_ = token
        self._secret_key_ = secret_key
        self.session = {}
        self.sslcontext = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.sslcontext.check_hostname = False
        self.sslcontext.verify_mode = ssl.CERT_NONE
        self.sslcontext.set_ciphers("ALL")

    # def __del__(self):
    #     session_name = threading.current_thread().name
    #     if self.session[session_name]:
    #         asyncio.run(self.session[session_name].close())

    # http 带签名的header生成方法
    def mkHeader(self, data: dict):
        ran_str = ''.join(random.sample(string.ascii_letters + string.digits, 5))
        Nonce = "%d_%s" % (int(time.time()), ran_str)
        header = dict()
        header['Token'] = self._token_
        header['Nonce'] = Nonce
        header['Signature'] = self.sign(Nonce, data)

        return header

    # 签名生成方法
    def sign(self, Nonce, data: dict):
        tmp = list()
        tmp.append(self._token_)
        tmp.append(self._secret_key_)
        tmp.append(Nonce)
        for d, x in data.items():
            tmp.append(str(d) + "=" + str(x))
        return hashlib.sha1(''.join(sorted(tmp)).encode("utf8")).hexdigest()

    async def request(self, args):
        if 'timeout' not in args:
            args['timeout'] = 3

        if 'method' not in args:
            args['method'] = 'GET'
        else:
            args['method'] = args['method'].upper()

        # header设置
        if 'headers' not in args:
            args['headers'] = {}

        if 'user-agent' not in args['headers']:
            args['headers'][
                'user-agent'] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"

        # Cookies
        cookies = {}
        if 'cookies' in args:
            cookies = args['cookies']

        if 'data' not in args:
            args['data'] = {}
        result = {}
        args['headers'].update(self.mkHeader(args['data']))

        session_name = threading.current_thread().name
        if not self.session.get(session_name):
            connector = aiohttp.TCPConnector(limit=100, ssl=self.sslcontext)
            self.session[session_name] = aiohttp.ClientSession(cookies=cookies, timeout=3, connector=connector)
        data, params = {}, {}
        method = args['method'].upper()
        if method in ["GET"]:
            params = args['data']
        else:
            data = args['data']

        request_data = dict(
            method=method,
            url=args['url'],
            headers=args['headers'],
            timeout=args['timeout'],
            data=data,
            params=params,
        )
        async with self.session[session_name].request(**request_data) as r:
            result['content'] = await r.text()
            """
            # ck = {}  
            # for cookie in r.cookies:  
            #     ck.update({cookie.name: cookie.value})  
            # result['cookies'] = ck  
            # result['headers'] = r.headers  
            # result['content'] = r.text()
            """
            result['code'] = r.status
        if result['code'] != 200:
            logging.info(f"ERROR:'url':{args['url']},'result':{result['content']}")
        await self.session[session_name].close()
        return result

    async def kline(self, symbol, period, size):
        # 获取K线
        """
        {
        "errno":	0,
        "errmsg":	"success",
        "result":	{
            "symbol":"EOS-USDT",
            "period":"1min",
            "ts":"1499223904680",
            "data":	[{
                "id":	K线id,
                "amount":	成交量,
                "count":	成交笔数,
                "open":	开盘价,
                "close":	收盘价,当K线为最晚的一根时，是最新成交价
                "low":	最低价,
                "high":	最高价,
                "vol":	成交额,	即	sum(每一笔成交价	*	该笔的成交量)
                } ]
            }
        }
        :param symbol:  如BTC_USDT 交易对
        :param type:  K线类型：1min,	5min,	15min,	30min, 1hour,	6hour,	12hour,	1day,	1week
        :param size:  获取数量，范围：[1,2000]
        :return:
        """
        args = dict()
        args['url'] = self.host + '/openApi/market/kline'
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        args['data']['period'] = period
        args['data']['size'] = size

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def depth(self, symbol):
        """
        {
            "errno":	0,
            "errmsg":	"success",
            "result":	{
                    "symbol":"EOS-USDT",
                    "ts":1499223904680,
                    "bids":	[[7964,	0.0678],	//	[price,	amount]
                            [7963,	0.9162]，...]
                    "asks":	[ [7979,	0.0736],
                            [7980,	1.0292],...]
                            }
        }
        :param symbol:  如BTC_USDT 交易对
        :return:
        """
        args = dict()
        args['url'] = self.host + '/openApi/market/depth'
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['symbol'] = symbol

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def gears_depth(self, symbol):
        '''
        {
        "errno":	0,
        "errmsg":	"success",
        "result":	{
            "symbol":"EOS-USDT",
            "ts":1499223904680,
            "asks":[
            {
            "gear":	"1",
            "price":	6322.22,
            "number":	0.0041
            }
            ],
            "bids":[
            {
            "gear":	"1",
            "price":	6322.22,
            "number":	0.0041 ]
            } }
            }

        :param symbol:
        :param depth:  例如：深度(0.0001,0.00001,0.000001)
        :return:
        '''
        args = dict()
        args['url'] = self.host + '/openApi/market/gears_depth'
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        # args['data']['depth'] = depth

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def trades(self, symbol, size):
        """
            {
            "errno":0,
            "errmsg":"success",
            "result":{
                    "symbol":"EOS-USDT",
                    "ts":"1499223904680",
                    "data":	[{
                            "id":17592256642623,
                            "amount":0.04,
                            "price":1997,
                            "direction":"buy",
                            "ts":1502448920106
                            },....
                            ] }
            }
            :param symbol: 如BTC_USDT 交易对
            :param size:  获取数量，范围：[1,2000]
            :return:
            """
        args = dict()
        args['url'] = self.host + '/openApi/market/trade'
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        args['data']['size'] = size

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result
    
    async def market_24kline(self, symbol):
        """
            {
                "errno":0,
                "errmsg":"success",
                "result":{
                    "id":1499184000,
                    "amount":37593.0266,
                    "count":1234,
                    "open":1935.2,
                    "close":1879,
                    "low":1856,
                    "high":1940,
                    "vol":71031537.978665
                }
            }
            :param symbol: 如BTC-USDT 交易对
            :return:
            """
        args = dict()
        args['url'] = '{host}/openApi/market/detail'.format(host=self.host)
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['symbol'] = symbol

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'].encode('utf-8'))
        else:
            return result

    async def symbols(self):
        """
        {"errno":	0,
        "errmsg":	"success",
        "result":	[
        {
        "id":1223,
        "symbol":	"BTC-USDT",
        "base_currency":	"BTC",
        "quote_currency":	"USDT",
        "min_size":	0.0000001,
        "max_size":	10000,
        "min_price":	0.001,
        "max_price":1000,
        "maker_fee":0.002,
        "taker_fee":0.002
        },
        ] }
        :return:
        """
        args = dict()
        args['url'] = self.host + '/openApi/market/symbols'
        args['method'] = 'GET'
        args['data'] = dict()

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def wallet(self, currency=None, show_all=0):
        """
        {
        "errno":	0,
        "errmsg":	"success",
        "result":	[
            { "currency":	"BTC",
              "available":	"0.2323",
              "frozen":	"0"
            }, ]
    	}
        :param currency:交易对
        :param show_all:是否需要全部币种（1：需要，不传则有资产的 才有）
        :return:
        """
        # 查询我的资产
        args = dict()
        args['url'] = self.host + '/openApi/wallet/list'
        args['method'] = 'GET'
        args['data'] = dict()
        if currency:
            args['data']['currency'] = currency
        if show_all:
            args['data']['show_all'] = show_all
        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def add_asyncio(self, symbol, type, amount, price):
        amount_precision = int(SYMBOLS_ORDER_CONDITION[symbol].get("amount", 6))
        price_precision = int(SYMBOLS_ORDER_CONDITION[symbol].get("price", 8))
        # 委托挂单
        args = dict()
        args['url'] = self.host + '/openApi/entrust/add'
        args['method'] = 'POST'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        args['data']['type'] = type
        args['data']['amount'] = round(amount, amount_precision) if amount_precision else round(amount)
        args['data']['price'] = round(price, price_precision) if price_precision else round(price)
        res = await self.request(args)
        try:
            res = json.loads(res['content'])
            if res["errno"] != 0:
                res["token"] = self._token_
                res["args"] = str(args)
                print("add_asyncio res ", self._token_, symbol, res)
            else:
                print(f'{symbol}| {type}', "amount: " + str(args['data']['amount']),
                      "price: " + str(args['data']['price']), res)
        except (BaseException, Exception) as e:
            raise e
        return res

    async def cancel(self, order_ids):
        """
        #注意，返回成功仅代表撤销申请成功，撤销是否成功从委托详情中获取
        {
        "errno":	0,
        "errmsg":	"success",
        "result":{
            "success":["1","3"],
            "failed":["2","4"]
            }
        }
        :param order_ids: 订单id,批量逗号分隔
        :return:
        """
        # 委托撤单
        args = dict()
        args['url'] = self.host + '/openApi/entrust/cancel'
        args['method'] = 'POST'
        args['data'] = dict()
        args['data']['order_ids'] = order_ids
        # args['data']['symbol'] = symbol

        result = await self.request(args)

        if result['code'] == 200:
            re = json.loads(result['content'])
            success_cancel_num = len(re['result']['success'])
            fail_cancel_num = len(re['result']['fail'])
            print(self._token_, "success", success_cancel_num, "fail", fail_cancel_num)

            return json.loads(result['content'])
        else:
            return result

    async def currentList(self, symbol):
        #  当前委托
        """
        {
        "errno":	0,
        "errmsg":	"success",
        "result":	[{
            "order_id":121,
            "order_sn":"BL123456789987523",
            "symbol":"MCO-BTC",
            "ctime":"2018-10-02	10:33:33",
            "type":"2",
            "side":"buy",
            "price":"0.123456",
            "number":"1.0000",
            "total_price":"0.123456",
            "deal_number":"0.00000",
            "deal_price":"0.00000",
            "status":1 17.
            }, ...
            }
        :param symbol: 交易对(当前交易对必传,全部交易对不传)
        :param type: 1=买入,2=卖出,不传即查全部
        :return:
        """
        args = dict()
        args['url'] = self.host + '/openApi/entrust/currentList'
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        # args['data']['type'] = type
        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result


    async def detail(self, order_sn):
        # 成交记录详情
        """
        {
        "errno":	0,
        "errmsg":	"success",
        "result":{
            "entrust":{
            "order_id":121,
            "order_sn":"BL123456789987523",
            "symbol":"MCO-BTC",
            "ctime":"2018-10-02	10:33:33",
            "type":"2",
            "side":"buy",
            "price":"0.123456",
            "number":"1.0000",
            "total_price":"0.123456",
            "deal_number":"0.00000",
            "deal_price":"0.00000",
            "status":1
            },
        }
        :param order_sn:订单编号
        :return:
        """
        args = dict()
        args['url'] = self.host + '/openApi/entrust/detail'
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['order_sn'] = order_sn

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def precision(self, symbol):

        args = dict()
        args['url'] = self.host + '/openApi/market/precision'
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['symbol'] = symbol

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result


if __name__ == '__main__':
    # apikey = {'token': "cukk8ouh9mtu5jtww9a0", 'secret_key': "420c7bc61f89eed8d144304bb45af59f"}
    # apikey = {'token': "27fa0db14cfc87092eaa77ca913008c8", 'secret_key': "3gpores65d17jb0fb9xp"}
    # apikey = {'token': "f56d8d9b7a92b495e84119b3c53558a5", 'secret_key': "g0bbteibtlhovkr9jozs"}
    # apikey = {'token': "g0bbteibtlhovkr9jozs", 'secret_key': "f56d8d9b7a92b495e84119b3c53558a5"}
    # apikey = {'token': "unn8hmmeywer9sx67y13", 'secret_key': "4185ee92b273de729bdb5618296875e5"}
    apikey = {'token': "cb95edcac135b5a28ed76233abca5b00", 'secret_key': "t8leukegp3t487kzj9xf"}
    apikey = {"token": "dfab8bd76d7fea39e4aa6af328cbd187", "secret_key": "l8nemtb6r1diqmksp721"}
    # apikey = {'token': '78fc47c5590f77ca42d1e2c3bb432813', 'secret_key': '5e5yg7ga285hctuqrtpb'}
    # ao = AApi(**apikey)
    ao = AApi(token=apikey['token'], secret_key=apikey['secret_key'])  #, host='https://oapi.websea.com')
    #
    #d = asyncio.run(ao.wallet())
    #d = asyncio.run(ao.trades(symbol='BTC-USDT', size=5))
    d = asyncio.run(ao.market_24kline('BTC-USDT'))
    print(d)

    from config.infor import spot_account

    #
    # async def aa():
    #     task = []
    #     for k, v in spot_account.items():
    #         print(k, v)
    #         if v.get('apikey') and v['apikey'].get('token', '') and v['apikey'].get('sk', ''):
    #             ao = AApi(token=v['apikey']['token'], secret_key=v['apikey']['sk'])
    #             task.append(asyncio.create_task(ao.wallet()))
    #     for i in task:
    #         await i

    # res = {i['currency']: float(i['available']) + float(i['frozen']) for i in res['result']}
    # print(k, res)
    # await asyncio.sleep(1)

    #
    #
    # asyncio.run(aa())

    pass
