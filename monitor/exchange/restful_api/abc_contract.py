import datetime
import json
import logging
import time
import hashlib
import random
import string
import aiohttp
import ujson
import urllib3
import requests
import ssl
import asyncio
import threading
import numpy as np
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
from config.infor_load import contract_host
from libs.requestSession import G_RequestSession

# urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
host = "https://exq.wtest.club"
# contract_host = "https://coq.wtest.club"

# 获取后台支持的交易对
condition_url = 'https://exq.wtest.club/openApi/market/precision'
default_condition = {}


class AApi:
    def __init__(self, token=None, secret_key=None):
        self._token_ = token
        self._secret_key_ = secret_key
        self.host = contract_host
        self.session = {}
        self.sslcontext = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.sslcontext.check_hostname = False
        self.sslcontext.verify_mode = ssl.CERT_NONE
        self.sslcontext.set_ciphers("ALL")

        # http请求方法

    # def __del__(self):
    #     session_name = threading.current_thread().name
    #     if self.session[session_name]:
    #         asyncio.run(self.session[session_name].close())

    # http 带签名的header生成方法
    def mkHeader(self, data: dict):
        ran_str = ''.join(random.sample(string.ascii_letters + string.digits, 5))
        Nonce = "%d_%s" % (int(time.time() * 1000), ran_str)
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
        sign = args.get('sign', True)

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
        if sign:
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

    async def request1(self, args):
        if 'timeout' not in args:
            args['timeout'] = 3

        if 'method' not in args:
            args['method'] = 'GET'
        else:
            args['method'] = args['method'].upper()
        sign = args.get('sign', True)

        # header设置
        if 'headers' not in args:
            args['headers'] = {}

        if 'user-agent' not in args['headers']:
            args['headers'][
                'user-agent'] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"

        if 'data' not in args:
            args['data'] = {}
        result = {}
        if sign:
            args['headers'].update(self.mkHeader(args['data']))
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
        # print(request_data)
        async with G_RequestSession.request.request(**request_data) as r:
            result['content'] = await r.text()

            result['code'] = r.status
        if result['code'] != 200:
            logging.info(f"ERROR:'url':{args['url']},'result':{result['content']}")

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
        args['url'] = '{}/qapi-v1/market/kline'.format(self.host)
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

    async def depth_contract(self, symbol):
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
        args['url'] = '{}/qapi-v1/market/depth'.format(self.host)
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
        args['url'] = '{}/openApi/market/gears_depth'.format(self.host)
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        # args['data']['depth'] = depth

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'].decode('utf-8'))
        else:
            return result

    async def gears_depth1(self, symbol, depth):
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
        args['url'] = '{}/openApi/market/gears_depth'.format(self.host)
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        args['data']['depth'] = depth

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'].decode('utf-8'))
        else:
            return result

    async def gears_depth_contract(self, symbol, depth=None):
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
        args['url'] = '{}/openApi/contract/gears_depth'.format(self.host)
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        if depth:
            args['data']['depth'] = depth

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'].decode('utf-8'))
        else:
            return result

    async def trades(self, symbol=None):
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
        args['url'] = '{}/qapi-v1/market/mark-price'.format(self.host)
        args['method'] = 'GET'
        args['data'] = dict()
        if symbol:
            args['data']['symbol'] = symbol

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def trades_contract(self, symbol, size=None):
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
                            "direction":"buy",//主动成交方向
                            "ts":1502448920106
                            },....
                            ] }
            }
            :param symbol: 如BTC_USDT 交易对
            :param size:  获取数量，范围：[1,2000]
            :return:
            """
        args = dict()
        args['url'] = '{}/qapi-v1/market/trade'.format(self.host)
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        print(args)
        if size:
            args['data']['size'] = size

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
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
        args['url'] = '{}/openApi/market/symbols'.format(self.host)
        args['method'] = 'GET'
        args['data'] = dict()

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'].decode('utf-8'))
        else:
            return result

    async def symbols_contract(self):
        """
        {"errno":	0,
        "errmsg":	"success",
        "result":	[
        {
        "id":1223,
        "symbol":	"BTC-USDT",
        "base_currency":	"BTC", //交易货币币种
        "quote_currency":	"USDT",//计价货币币种
        "min_size":	0.0000001,     //最小交易数量
        "max_size":	10000,        //最大交易数量
        "min_price":0.001,       //最小交易价格
        "max_price":1000,        //最大交易价格
        "maker_fee":0.002,      //挂单手续费，取值范围0~1之间，如 （0.1为10%）
        "contract_size': '0.001'       //面值
        },
        ] }
        :return:
        """
        # 系统支持交易对查询
        args = dict()
        args['url'] = '{}/openApi/contract/symbols'.format(self.host)
        args['method'] = 'GET'
        args['data'] = dict()

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'].decode('utf-8'))
        else:
            return result

    async def wallet(self, currency=None):
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
        args['url'] = '{}/openApi/wallet/list'.format(self.host)
        args['method'] = 'GET'
        args['data'] = dict()
        if currency:
            args['data']['currency'] = currency
        args['data']['show_all'] = 1

        result = await self.request(args)

        if result['code'] == 200:
            # logger.info("success",json.loads(result['content'].decode('utf-8')))
            return json.loads(result['content'].decode('utf-8'))
        else:
            # logger.error("failed%s"%result)
            return result

    async def wallet_contract(self, symbol=None):
        """
        { "errno": 0,
        "errmsg": "success",
        "result": {[{
            "symbol": "ETH-USDT",//交易对
            "avail": "20",//可用USDT
            "hold": "1",//持仓保证金
            "frozen": 0,//委托冻结保证金
            }]}
        }
        """
        # 合约总资产列表

        args = dict()
        args['url'] = '{}/qapi-v1/funds/walletList'.format(self.host)
        args['method'] = 'GET'
        args['data'] = dict()
        if symbol:
            args['data']['symbol'] = symbol
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def rate(self, symbol):
        """
        {
        "errno":	0,
        "errmsg":	"success",
        "result":	{
            "maker_fee":	0.00025,
            "taker_fee":0.00026
            }
        }
        :param symbol:  交易对
        :return:
        """
        # 查询交易费率
        args = dict()
        args['url'] = '{}/openApi/entrust/rate'.format(self.host)
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['symbol'] = symbol

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'].decode('utf-8'))
        else:
            return result

    async def add(self, symbol, type, amount, price):
        """
            {
            "errno":	0,
            "errmsg":	"success",
            "result":	{
                "order_sn":	"BL786401542840282676"
                }
            }
            :param symbol:  交易对 如BTC-USDT
            :param type: 订单类型：buy-market：市价买,	sell-market：市价卖,	buy-limit：限价买, sell-limit：限价卖
            :param amount: 限价单表示下单数量，市价买单时表示买多少 钱(usdt)，市价卖单时表示卖多少币(btc)
            :param price: 下单价格，市价单不传该参数
            :return:
            """
        # 委托挂单
        args = dict()
        args['url'] = '{}/openApi/entrust/add'.format(self.host)
        args['method'] = 'POST'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        args['data']['type'] = type
        args['data']['amount'] = amount
        args['data']['price'] = price

        result = await self.request(args)

        if result['code'] == 200:
            ret = json.loads(result['content'].decode('utf-8'))
            # if ret.get("errno")==0:
            # logger.info("%s trade success --> %s"%(symbol,ret))
            # else:
            # logger.error("%s trade failed --> %s"%(symbol,ret))
            return ret
        else:
            # logger.error("server error --> %s"%result)
            return result

    async def add_contract(self, symbol, contract_type, type, lever_rate, price, amount, trigger_price=None):
        """
            {"errno": 0,
            "errmsg": "success",
            "result": {
                "order_id": "BL786401542840282676"
                   }
            }
            :param symbol:  合约交易对名称 如BTC-USDT
            :param contract_type: 类型 open开仓 close平仓
            :param type: 委托类型 buy-limit（普通买单）sell-limit（普通卖 单）buy-market（市场买单）sell-market（市场 卖单）buy-plan（计划买单） sell-plan（计划卖 单）
            :param lever_rate: 杠杆倍数（开仓必填，平仓不填）
            :param price: 委托价
            :param amount: 张数
            :param trigger_price: 触发价格 计划委托必传
            :return:
        """
        # 下单 合约开仓/平仓
        args = dict()
        args['url'] = '{}/openApi/contract/add'.format(self.host)
        args['method'] = 'POST'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        args['data']['contract_type'] = contract_type
        args['data']['lever_rate'] = lever_rate
        args['data']['type'] = type
        args['data']['amount'] = amount
        args['data']['price'] = price
        if trigger_price:
            args['data']['trigger_price'] = trigger_price
        result = await self.request(args)
        if result["code"] == 200:
            ret = json.loads(result['content'].decode('utf-8'))
            return ret
        else:
            return result

    async def cancel(self, symbol, order_ids):
        args = dict()
        args['url'] = '{}/qapi-v1/entrust/cancel'.format(self.host)
        args['method'] = 'POST'
        args['data'] = dict()
        args['data']['symbol'] = order_ids
        args['data']['order_ids'] = symbol

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def currentList(self, symbol, limit=100, is_full=1):

        args = dict()
        args['url'] = '{}/qapi-v1/entrust/currentList'.format(self.host)
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        args['data']['limit'] = limit
        args['data']['is_full'] = is_full  # 1逐仓，2全仓

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def contract_direct_list(self, symbol, order_sn=None, direct='next', limit=100):
        args = dict()
        args['url'] = '{}/openApi/contract/currentList'.format(self.host)
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        args['data']['from'] = order_sn
        args['data']['direct'] = direct
        args['data']['limit'] = limit

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'].decode('utf-8'))
        else:
            return result

    # def historyList(self, symbol, type, fromid, direct, limit):
    async def historyList(self, symbol, limit, fromid, direct):
        # 我的历史委托
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
        :param symbol: 如BTC_USDT 交易对
        :param type: 1=买入,2=卖出,不传即查全部
        :param fromid: 查询起始order_id  比如122
        :param direct: 查询方向(默认	prev)，prev	向前，时间（或	ID） 倒序；next	向后，时间（或	ID）正序）。（举例一 列数：1，2，3，4，5。from=4，prev有3，2，1； next只有5）
        :param limit: 分页返回的结果集数量，默认为20，最大为100
        :return:
        """
        args = dict()
        args['url'] = '{}/openApi/entrust/historyList'.format(self.host)
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        # args['data']['type'] = type
        args['data']['from'] = fromid
        args['data']['direct'] = direct
        args['data']['limit'] = limit

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'].decode('utf-8'))
        else:
            return result

    async def position_contract(self, symbol=None):
        """
        { "errno": 0,
        "errmsg": "success",
        "result": [{
            "type": 1,//1多仓 2空仓
            "symbol": "ETH-USDT",//交易对
            "lever_rate": 10,//杠杆倍数
            "amount": "10",//持有数量
            "profit": "10",//已实现盈亏
            "open_price_avg": "0.3",//开仓均价
            "bood": "6",//冻结保证金(usdt)
            "contract_frozen": "5",//委托冻结(张数)
            "settle_rate": "0.1",//当期资金结算费用
            "equity": "3.4",//账户权益（usdt）
            "avail": "20",//可用(usdt)
            "risk_rate": "1.1",//风险率
            "liquidation_price": "0.9"//强平价
            "avail_amount":"50"//可平数量(张数）
            "un_profit":"0"//未实现盈亏
            }]
        }
        :param symbol: 交易对(当前交易对必传,全部交易对不传)
        :return:
        """
        args = dict()
        args['url'] = '{}/qapi-v1/funds/position'.format(self.host)
        args['method'] = 'GET'
        args['data'] = dict()
        if symbol:
            args['data']['symbol'] = symbol
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
        args['url'] = '{}/openApi/entrust/detail'.format(self.host)
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['order_sn'] = order_sn

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'].decode('utf-8'))
        else:
            return result

    async def detail_contract(self, order_id):
        # 成交记录详情
        """
        {
            "errno": 0,
            "errmsg": "success",
             "result": {[{
                "order_id": "BG5000181583375122413SZXEIX",//订单号
                "ctime": 1576746253,//成交时间
                "symbol": "ETH-USDT",//交易对
                "price": "1",//成交价格
                "amount": 0,//成交数量
                "bood": 10,//保证金
                "profit": "10",//盈亏
                "fee": 0,//手续费
                }]}
        }
        :param order_sn:订单编号
        :return:
        """
        args = dict()
        args['url'] = '{}/openApi/contract/detail'.format(self.host)
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['order_id'] = order_id

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'].decode('utf-8'))
        else:
            return result

    async def precision(self, symbol):

        args = dict()
        args['url'] = '{}/qapi-v1/symbol/precision'.format(self.host)
        args['method'] = 'GET'
        args['sign'] = False
        args['data'] = dict()
        args['data']['symbol'] = symbol

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def precision_contract(self, symbol=None):
        """
        {
        "errno": 0,
        "errmsg": "success",
        "result": {
            "ETH-USDT": {
                "amount": "3",          //数量精度
                "minQuantity": "0.01",  //委托最小单量
                "maxQuantity": "10000", //委托最大单量
                "price": "4",           //价格精度
                "minPrice": "100",      //委托最低价
                "maxPrice": "5000"      //委托最高价
                },……
            }
        }
        :param symbol:交易对，非必填，不填时返回所有交易对精度
        return :
        """
        # 合约交易精度
        args = dict()
        # args['url'] = '{}/openApi/contract/precision'.format(self.host)
        args['url'] = '{}/qapi-v1/symbol/symbols'.format(self.host)
        args['method'] = 'GET'
        args['data'] = dict()
        if symbol:
            args['data']['symbol'] = symbol

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def index_contract(self, symbol=None):
        """
        {
        "errno": 0,
        "errmsg": "success",
        "result": [{
            "symbol":"BTC-USDT",
            "price":"7865.23", //标记价
            "ts":1587925500000
            }]
        }
        :param symbol:交易对，不传即全部
        return :
        """
        # 获取标记价
        args = dict()
        args['url'] = '{}/openApi/contract/index'.format(self.host)
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['symbol'] = symbol

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'].decode('utf-8'))
        else:
            return result

    async def hold_contract(self, symbol=None):
        """
        {
        "errno": 0,
        "errmsg": "success",
        "result": [{
            "symbol":"BTC-USDT",
            "volume":123,     //持仓量
            "ts":1587925500000
            }]
        }
        :param symbol:交易对，不传即全部
        return :
        """
        # 获取标记价
        args = dict()
        args['url'] = '{}/openApi/contract/hold'.format(self.host)
        args['method'] = 'GET'
        args['data'] = dict()
        if symbol:
            args['data']['symbol'] = symbol

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'].decode('utf-8'))
        else:
            return result

    async def markPrice_contract(self, symbol=None):
        """
        {
        "errno": 0,
        "errmsg": "success",
        "result": [{
            "symbol":"BTC/USDT",
            "markPrice":9669.863157894737,
            "price":{
                "huobi":9667.37,
                "abc":9667.87,
                "okex":9667.4,
                "bitfinex":9674.3,
                "binance":9669.79
                },
            "ratio":{
                "huobi":20,
                "abc":5,
                "okex":20,
                "bitfinex":25,
                "binance":25
                }
            },……
            ]
        }
        :param symbol:交易对，不传即全部
        return :
        """
        # 获取标记价
        args = dict()
        args['url'] = '{}/openApi/contract/markPrice'.format(self.host)
        args['method'] = 'GET'
        args['data'] = dict()
        if symbol:
            args['data']['symbol'] = symbol

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'].decode('utf-8'))
        else:
            return result

    async def funding_rate(self, symbol):

        # 获取标记价
        args = dict()
        args['url'] = '{}/qapi-v1/symbol/capitalRate'.format(self.host)
        args['method'] = 'GET'
        args['sign'] = False

        args['data'] = dict()
        if symbol:
            args['data']['symbol'] = symbol

        result = await self.request1(args)

        if result['code'] == 200:
            res = ujson.loads(result['content'])
            return float(res['result']["capitalRate"]) * 100
        else:
            return result

    async def funding_rate_all(self, symbols):
        usdt_busd_zone_list = {}
        error = []
        for symbol in symbols:
            f = await self.funding_rate(symbol)
            if isinstance(f, float):
                usdt_busd_zone_list[symbol] = f
            else:
                error.append(symbol)
            # await asyncio.sleep(0.2)
        return usdt_busd_zone_list, error

    def digit_to_string(d):
        return np.format_float_positional(d, trim='-')

    async def contract_add(self, symbol, side, amount, price, lever_rate, contract_type="close", is_full=None):
        SYMBOLS_CONTRACT_CONDITION = (await self.precision(symbol))['result']
        SYMBOLS_CONTRACT_CONDITION = (await self.precision(symbol))['result']

        amount_precision = int(SYMBOLS_CONTRACT_CONDITION[symbol].get("amount", 6))
        price_precision = int(SYMBOLS_CONTRACT_CONDITION[symbol].get("price", 8))
        faceValue = float(SYMBOLS_CONTRACT_CONDITION[symbol].get("faceValue"))
        maxQuantity = float(SYMBOLS_CONTRACT_CONDITION[symbol].get("maxQuantity"))
        minQuantity = float(SYMBOLS_CONTRACT_CONDITION[symbol].get("minQuantity"))
        # 委托挂单
        args = dict()
        args['url'] = '{}/qapi-v1/entrust/add'.format(self.host)
        args['method'] = 'POST'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        args['data']['contract_type'] = {'open': 1, 'close': 2}[contract_type]
        args['data']['lever_rate'] = lever_rate

        args['data']['type'] = side

        args['data']['amount'] = round(amount, amount_precision) if amount_precision else round(amount)
        args['data']['price'] = round(price, price_precision) if price_precision else round(price)
        args['data']['is_full'] = is_full
        result = await self.request(args)
        return result


if __name__ == '__main__':
    apikey = {'token': "4d630813f6faa69fb90611bd73ae148c", 'secret_key': "tac0gklb3lw9xz2mz3fe"}
    ao = AApi(**apikey)

    symbol = 'BTC-USDT'
    d = asyncio.run(ao.precision(symbol, ))
    print(d)
