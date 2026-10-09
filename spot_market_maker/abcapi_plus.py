
import ujson
import traceback
import asyncio
import json
import time
import hashlib
import random
import string
import aiohttp
import config
import threading
import ssl
from loguru import logger
from libs.utils import digit_to_string
from libs import recode_msg


class AbcApi(object):

    def __init__(self, token, secret_key, limit=20):

        self.host = config.host
        self._token_ = token
        self._secret_key_ = secret_key
        self.session = {}
        # self.sslcontext = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        # self.sslcontext.check_hostname = False
        # self.sslcontext.verify_mode = ssl.CERT_NONE
        # self.sslcontext.set_ciphers("ALL")
        self.sslcontext = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.sslcontext.minimum_version = ssl.TLSVersion.TLSv1_2
        self.sslcontext.check_hostname = False
        self.sslcontext.verify_mode = ssl.CERT_NONE
        # Using the EOS default ciphers
        self.sslcontext.set_ciphers('AES256-SHA:DHE-RSA-AES256-SHA:AES128-SHA:DHE-RSA-AES128-SHA')
        self.is_full = 1
        self.limit = limit

    def __del__(self):
        session_name = threading.current_thread().name
        if self.session.get(session_name):              # 实例化未调用过任何接口，session为空
            asyncio.run(self.session[session_name].close())

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

        if 'data' not in args:
            args['data'] = {}
        result = {}
        args['headers'].update(self.mkHeader(args['data']))

        session_name = threading.current_thread().name
        if not self.session.get(session_name):
            logger.info(f"aiohttp limits {self.limit}")
            connector = aiohttp.TCPConnector(limit=self.limit, keepalive_timeout=50, enable_cleanup_closed=True,
                                             ssl=self.sslcontext, ttl_dns_cache=10 * 60)
            self.session[session_name] = aiohttp.ClientSession(base_url=self.host, timeout=3, connector=connector)
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

            result['code'] = r.status
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
        args['url'] = '/openApi/wallet/list'
        args['method'] = 'GET'
        args['data'] = dict()
        if currency:
            args['data']['currency'] = currency
        else:
            args['data']['show_all'] = 1

        result = await self.request(args)

        if result['code'] == 200:
            return ujson.loads(result['content'])
        else:
            return result

    async def edit_asyncio(self, order_sn, symbol, amount=None, price=None):
        args = dict()
        args['url'] = '/openApi/entrust/upOrder'
        args['method'] = 'POST'
        args['data'] = dict()
        args["data"]["order_sn"] = order_sn

        if price:
            price_precision = int(config.SYMBOLS_ORDER_CONDITION[symbol].get("price", 8))
            args['data']['price'] = digit_to_string(round(price, price_precision) if price_precision else round(price))

        if amount:
            amount_precision = int(config.SYMBOLS_ORDER_CONDITION[symbol].get("amount", 6))
            min_quantity = float(config.SYMBOLS_ORDER_CONDITION[symbol].get("minQuantity", 0))
            amount = max(amount, random.uniform(min_quantity, min_quantity * 2))
            max_quantity = float(config.SYMBOLS_ORDER_CONDITION[symbol].get("maxQuantity"))
            amount = min(amount, random.uniform(max_quantity, max_quantity * 0.8)) if max_quantity else amount

            args['data']['amount'] = digit_to_string(round(amount, amount_precision) if amount_precision else round(amount))

        try:
            res = await self.request(args)
            res = json.loads(res['content'])
            if res["errno"] != 0:
                res["token"] = self._token_
                res["args"] = str(args)
                logger.info(f"add_error {symbol}-{args['data']['amount']}-{args['data']['price']}-{res}")

            args['data']['ctime'] = int(time.time())
            res["args"] = args

        except (BaseException, Exception) as e:
            msg = f"{traceback.format_exc()}"
            logger.info(f"add_error {msg}")
            res = {"errno": -1, "msg": f"{symbol}下单异常"}
            return res
        return res

    async def add_asyncio(self, symbol, type, amount, price):
        amount_precision = int(config.SYMBOLS_ORDER_CONDITION[symbol].get("amount", 6))
        price_precision = int(config.SYMBOLS_ORDER_CONDITION[symbol].get("price", 8))

        min_quantity = float(config.SYMBOLS_ORDER_CONDITION[symbol].get("minQuantity", 0))
        amount = max(amount, random.uniform(min_quantity, min_quantity * 2))
        max_quantity = float(config.SYMBOLS_ORDER_CONDITION[symbol].get("maxQuantity"))
        amount = min(amount, random.uniform(max_quantity, max_quantity * 0.8)) if max_quantity else amount

        # 委托挂单
        args = dict()
        args['url'] = '/openApi/entrust/add'
        args['method'] = 'POST'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        args['data']['type'] = type
        args['data']['amount'] = digit_to_string(round(amount, amount_precision) if amount_precision else round(amount))
        args['data']['price'] = digit_to_string(round(price, price_precision) if price_precision else round(price))


        try:
            res = await self.request(args)
            res = json.loads(res['content'])
            if res["errno"] != 0:
                res["token"] = self._token_
                res["args"] = str(args)
                logger.info(f"add_error {symbol}-{args['data']['amount']}-{args['data']['price']}-{res}")

            args['data']['ctime'] = int(time.time())
            res["args"] = args

        except (BaseException, Exception) as e:
            msg = f"{traceback.format_exc()}"
            logger.info(f"add_error {msg}")
            res = {"errno": -1, "msg": f"{symbol}下单异常"}
            return res
        return res

    async def add_batch_asyncio(self, orders):
        temp_orders = []
        for order in orders:
            symbol = order["symbol"]
            amount = order["amount"]
            price = order["price"]

            amount_precision = int(config.SYMBOLS_ORDER_CONDITION[symbol].get("amount", 6))
            price_precision = int(config.SYMBOLS_ORDER_CONDITION[symbol].get("price", 8))

            min_quantity = float(config.SYMBOLS_ORDER_CONDITION[symbol].get("minQuantity", 0))
            amount = max(amount, random.uniform(min_quantity, min_quantity * 2))
            max_quantity = float(config.SYMBOLS_ORDER_CONDITION[symbol].get("maxQuantity"))
            amount = min(amount, random.uniform(max_quantity, max_quantity * 0.8)) if max_quantity else amount

            amount = digit_to_string(round(amount, amount_precision) if amount_precision else round(amount))
            price = digit_to_string(round(price, price_precision) if price_precision else round(price))

            temp_orders.append({
                "symbol": symbol,
                "type": order["type"],
                "amount": amount,
                "price": price,
                # "deal_type": 'GTC', # 成交类型：GTC：一直有效直到取消（默认）, IOC：立即成交否则取消，FOK：全部成交否则取消, PO：只做Maker否则取消;（不传默认GTC
            })

        if not temp_orders:
            logger.error(f"add_batch_asyncio {temp_orders=} empty !")
            return

        # 委托挂单
        args = dict()
        args['url'] = '/openApi/entrust/batchAdd'
        args['method'] = 'POST'
        args['data'] = dict()
        args['data']["orders"] = json.dumps(temp_orders)

        try:
            res = await self.request(args)
            res = json.loads(res['content'])
            if res["errno"] != 0:
                res["token"] = self._token_
                res["args"] = str(args)
                logger.info(f"add_batch_asyncio {orders=}-{res}")

            res['ctime'] = int(time.time())
            res["args"] = temp_orders

        except (BaseException, Exception) as e:
            msg = f"{traceback.format_exc()}"
            logger.info(f"add_error {msg}")
            res = {"errno": -1, "msg": f"下单异常"}
            return res
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
        :param order_ids: 订单id 列表
        :return:
        """
        # 委托撤单
        args = dict()
        args['url'] = '/openApi/entrust/cancel'
        args['method'] = 'POST'
        args['data'] = dict()
        cancel_list = ','.join(order_ids)
        args['data']['order_ids'] = cancel_list
        # args['data']['symbol'] = symbol

        res = {"errno": -1, "msg": f"撤单异常"}
        try:
            result = await self.request(args)

            if result['code'] == 200:
                re = json.loads(result['content'])
                success_cancel = re['result']['success']
                fail_cancel = re['result']['fail']
                if fail_cancel:
                    logger.info(f"cancel-spot {self._token_[-6:]} {fail_cancel}")
                    return {"errno": -1, "msg": f"撤单异常", "fail": fail_cancel}

                return re
            logger.info(f"cancel-spot {self._token_[-6:]} {result}")
        except (BaseException, Exception) as e:
            msg = f"{traceback.format_exc()}"
            logger.info(f"cancel-spot {msg}")
        return res

    async def current_list(self, symbol):
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
        args['url'] = '/openApi/entrust/currentList'
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        # args['data']['type'] = type
        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def current_list_step(self, symbol, order_sn=None, direct='next', limit=100):
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
        args['url'] = '/openApi/entrust/currentList'
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        args['data']['from'] = order_sn
        args['data']['direct'] = direct
        args['data']['limit'] = limit

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def current_list_order_details(self, symbol, number):
        current_list = []
        all_current_list = []
        res_last = await self.current_list(symbol)

        if res_last.get('result', 0):
            length = len(res_last['result']) - 1
            last_id = res_last['result'][length]['order_sn']

            for i in res_last['result']:
                if i['status'] == 1 or i['status'] == 2:
                    current_list.append(i)
            all_current_list.append(res_last['result'])
            flag = True
            step_times = 0
            while flag:
                if step_times > 10:
                    message = f"{symbol} {self._token_[-8:]} 当前委托过多，检查撤单失败订单"
                    logger.error(f"current_list_order_details-{symbol} {self._token_[-8:]} {len(current_list)=} {current_list[:1]=} {current_list[-1:]=} {len(all_current_list)} {all_current_list=}")
                    await recode_msg.recode_error_msg(message, 'send_telegram_important_msg_url')
                    break
                start_id = last_id
                res = await self.current_list_step(symbol, start_id, 'prev', 100)
                step_times += 1
                if len(res.get('result', [])) == 1:
                    break
                if res.get('result', 0):
                    length = len(res['result']) - 1
                    last_id = res['result'][length]['order_sn']
                    for i in res['result']:

                        if i['status'] == 1 or i['status'] == 2:
                            if i not in current_list:
                                current_list.append(i)
                    all_current_list.append(res['result'])
                    if len(current_list) >= number:
                        break
                else:
                    flag = False

            return current_list
        else:
            return current_list

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

if __name__ == '__main__':
    # apikey = {'token': "420c7bc61f89eed8d144304bb45af59f", 'secret_key': "cukk8ouh9mtu5jtww9a0"}
    apikey = {'token': "3f57905a03a32432fae784037cb44f4c", 'secret_key': "sx4n8k2nh8hfz5gjs672"}
    # apikey = {'token': "4185ee92b273de729bdb5618296875e5", 'secret_key': "unn8hmmeywer9sx67y13"}
    ao = AbcApi(**apikey)
    #d = asyncio.run(ao.add_batch_asyncio([{"price": 3700, "amount": 1, "type": "buy-limit", "symbol": "ETH-USDT"}, {"price": 3600, "amount": 1, "type": "buy-limit", "symbol": "ETH-USDT"}]))
    #d = asyncio.run(ao.edit_asyncio("", "ETH-USDT", 1.2))

    # d = asyncio.run(ao.market_detail(symbol='BTC-USDT'))
    # d = asyncio.run(ao.market_24kline(symbol='BTC-USDT'))
    # d = asyncio.run(ao.kline(symbol='BTC-USDT', period='5min', size=150))
    # d = asyncio.run(ao.depth(symbol='BTC-USDT'))
    # d = asyncio.run(ao.gears_depth(symbol='BTC-USDT'))
    # d = asyncio.run(ao.trades(symbol='BTC-USDT'))
    # d = asyncio.run(ao.symbols())
    # d = asyncio.run(ao.precision())
    d = asyncio.run(ao.current_list(symbol='BTC-USDT'))
    # d = asyncio.run(ao.current_all(symbol='BTC-USDT', number=100))
    # d = asyncio.run(ao.current_steps(symbol='BTC-USDT'))
    # d = asyncio.run(ao.history_list(symbol='BTC-USDT'))
    # d = asyncio.run(ao.history_steps(symbol='BTC-USDT'))
    # d = asyncio.run(ao.deal('BL123456789987523'))
    # d = asyncio.run(ao.wallet(currency='USDT'))
    # d = asyncio.run(ao.add(symbol='BTC-USDT', type='buy-limit', price=29066, amount=0.1))
    # d = asyncio.run(ao.cancel(symbol='BTC-USDT', order_ids='BL961684677183958VRUWAR'))
    print(d)
