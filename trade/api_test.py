import threading
import loguru
import traceback
import asyncio
import ujson
import time
import hashlib
import random
import string
import aiohttp
import requests
import ssl
from libs.utils import digit_to_string


class AbcApi:

    def __init__(self, token, secret_key):
        from many_configs import abc_config

        self.host = abc_config.host
        self.contract_host = abc_config.contract_host
        self._token_ = token
        self._secret_key_ = secret_key
        self.session = {}
        self.sslcontext = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.sslcontext.check_hostname = False
        self.sslcontext.verify_mode = ssl.CERT_NONE
        self.sslcontext.set_ciphers("ALL")
        self.is_full = 1

    def __del__(self):
        session_name = threading.current_thread().name
        if self.session.get(session_name):             # 实例化未调用过任何接口，session为空
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
            connector = aiohttp.TCPConnector(limit=100, keepalive_timeout=50, enable_cleanup_closed=True,
                                             ssl=self.sslcontext, ttl_dns_cache=10 * 60)
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
        return result

    def sync_request(self, args):
        r = ''
        if 'timeout' not in args:
            args['timeout'] = 30

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

        args['headers'].update(self.mkHeader(args['data']))
        s = requests.session()
        if args['method'] == 'GET':
            s.keep_alive = False
            r = requests.get(args['url'], params=args['data'], cookies=cookies, headers=args['headers'],
                             timeout=int(args['timeout']), verify=False)
        elif args['method'] == 'POST':
            r = requests.post(args['url'], data=args['data'], cookies=cookies, headers=args['headers'],
                              timeout=int(args['timeout']), verify=False)

        result = {}
        result['code'] = r.status_code
        ck = {}
        for cookie in r.cookies:
            ck.update({
                cookie.name: cookie.value
            })
        result['cookies'] = ck
        result['headers'] = r.headers
        result['content'] = r.content

        return result

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
        args['url'] = '{host}/openApi/market/depth'.format(host=self.host)
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['symbol'] = symbol

        result = await self.request(args)

        if result['code'] == 200:
            return ujson.loads(result['content'])
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
        args['url'] = '{host}/openApi/market/trade'.format(host=self.host)
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        args['data']['size'] = size

        result = await self.request(args)

        if result['code'] == 200:
            return ujson.loads(result['content'].encode('utf-8'))
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
            return ujson.loads(result['content'].encode('utf-8'))
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
        args['url'] = self.host + '/openApi/wallet/list'
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
        from many_configs import global_variable

        if not global_variable.SYMBOLS_ORDER_CONDITION.get(symbol):
            print("{} 价格精度错误没有配置------------------->>>>>>>>>".format(symbol, ))
            return
        amount_precision = int(global_variable.SYMBOLS_ORDER_CONDITION.get(symbol, {}).get("amount", 6))
        price_precision = int(global_variable.SYMBOLS_ORDER_CONDITION.get(symbol, {}).get("price", 8))
        # min_quantity = float(global_variable.SYMBOLS_ORDER_CONDITION.get(symbol, {}).get("minQuantity", 0))
        max_quantity = float(global_variable.SYMBOLS_ORDER_CONDITION.get(symbol, {}).get("maxQuantity", 0))
        # amount = max(amount, random.uniform(min_quantity, min_quantity * 2))
        amount = min(amount, max_quantity * 0.95)
        args = dict()
        args['url'] = '{host}/openApi/entrust/add'.format(host=self.host)
        args['method'] = 'POST'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        args['data']['type'] = type
        args['data']['amount'] = digit_to_string(round(amount, amount_precision) if amount_precision else round(amount))
        args['data']['price'] = digit_to_string(round(price, price_precision) if price_precision else round(price))

        try:
            result = await self.request(args)
            if result['code'] == 200:
                res = ujson.loads(result['content'])
                errno = res.get("errno")
                if errno == 0:
                    res["heartbeat"] = True
                    return res
                else:
                    loguru.logger.info(f"spot-add-error {self._token_[-6:]}, {symbol}, {res}")
            else:
                loguru.logger.info(f"spot-add-error-{result}")
        except BaseException as e:
            loguru.logger.info(f"spot-add-error-{symbol}-{type}-{traceback.format_exc()} {repr(e)}")

    async def spot_add_plus(self, symbol, amount, price=None, spec_price_flag=False):
        # 委托挂单
        from many_configs import global_variable

        if not global_variable.SYMBOLS_ORDER_CONDITION.get(symbol):
            print("{} 价格精度错误没有配置------------------->>>>>>>>>".format(symbol, ))
            return
        amount_precision = int(global_variable.SYMBOLS_ORDER_CONDITION.get(symbol, {}).get("amount", 6))
        price_precision = int(global_variable.SYMBOLS_ORDER_CONDITION.get(symbol, {}).get("price", 8))
        max_quantity = float(global_variable.SYMBOLS_ORDER_CONDITION.get(symbol, {}).get("maxQuantity", 0))
        min_quantity = float(global_variable.SYMBOLS_ORDER_CONDITION.get(symbol, {}).get("minQuantity", 0))
        if amount < min_quantity:
            res = {"heartbeat": True}
            return res
        amount = min(amount, max_quantity * 0.95)
        args = dict()
        args['url'] = '{host}/openApi/entrust/brush'.format(host=self.host)
        args['method'] = 'POST'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        args['data']['amount'] = digit_to_string(round(amount, amount_precision) if amount_precision else round(amount))
        if price and spec_price_flag:
            args['data']['price'] = digit_to_string(round(price, price_precision) if price_precision else round(price))

        try:
            result = await self.request(args)
            if result['code'] == 200:
                res = ujson.loads(result['content'])
                errno = res.get("errno")
                if errno == 0:
                    res["heartbeat"] = True
                    return res
                else:
                    loguru.logger.info(f"spot_add_plus-error {self._token_[-6:]}, {symbol}, {res}")
            else:
                loguru.logger.info(f"spot_add_plus-error-{result}")
        except BaseException as e:
            loguru.logger.info(f"spot_add_plus-error-{symbol}-{type}-{traceback.format_exc()} {repr(e)}")

    async def contract_add(self, symbol, type, amount, price, contract_type="open", is_full=None):
        from many_configs import global_variable, contract_currency_config
        if not global_variable.SYMBOLS_CONTRACT_CONDITION.get(symbol):
            print("{} 合约价格精度错误没有配置------------------->>>>>>>>>".format(symbol, ))
            return
        amount_precision = int(global_variable.SYMBOLS_CONTRACT_CONDITION[symbol].get("amount", 6))
        price_precision = int(global_variable.SYMBOLS_CONTRACT_CONDITION[symbol].get("price", 8))
        # 委托挂单
        args = dict()
        args['url'] = self.contract_host + '/qapi-v1/entrust/add'
        args['method'] = 'POST'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        args['data']['contract_type'] = contract_type
        args['data']['lever_rate'] = contract_currency_config.CONTRACT_LEVER_RATE

        args['data']['type'] = type
        amount = amount / float(global_variable.SYMBOLS_CONTRACT_CONDITION[symbol]["faceValue"])
        amount = min(float(global_variable.SYMBOLS_CONTRACT_CONDITION[symbol]["maxQuantity"]) * random.uniform(0.9, 1),
                     int(amount))
        amount = max(float(global_variable.SYMBOLS_CONTRACT_CONDITION[symbol]["minQuantity"]) * random.uniform(1, 1.2),
                     int(amount))
        args['data']['amount'] = digit_to_string(int(amount))  # round(amount, amount_precision) if amount_precision else round(amount)
        args['data']['price'] = digit_to_string(round(price, price_precision) if price_precision else round(price))
        args['data']['is_full'] = is_full if is_full else self.is_full
        # print(args)
        try:
            result = await self.request(args)
            if result['code'] == 200:

                res = ujson.loads(result['content'])
                errno = res.get("errno")
                if errno == 0:
                    res["heartbeat"] = True
                    return res
                else:
                    loguru.logger.info(f"contract_add-{symbol}-{type}-{self._token_[-6:]}-"
                                       f"{str(args['data']['price'])}-{str(args['data']['amount'])}-"
                                       f"{str(ujson.loads(result['content']))}")
            else:
                loguru.logger.info(f"contract_add-error {symbol} {result}")  # return result
        except BaseException as e:
            loguru.logger.info(f"contract_add-error-{symbol}-{type}-{self._token_}-"
                               f"{traceback.format_exc()} {repr(e)}")

    async def contract_add_plus(self, symbol, amount, price=None, spec_price_flag=False):
        from many_configs import global_variable
        if not global_variable.SYMBOLS_CONTRACT_CONDITION.get(symbol):
            print("{} 合约价格精度错误没有配置------------------->>>>>>>>>".format(symbol, ))
            return
        price_precision = int(global_variable.SYMBOLS_CONTRACT_CONDITION[symbol].get("price", 8))
        amount = amount / float(global_variable.SYMBOLS_CONTRACT_CONDITION[symbol]["faceValue"])
        amount = min(float(global_variable.SYMBOLS_CONTRACT_CONDITION[symbol]["maxQuantity"]) * random.uniform(0.9, 1),
                     int(amount))
        amount = max(float(global_variable.SYMBOLS_CONTRACT_CONDITION[symbol]["minQuantity"]) * random.uniform(1, 1.2),
                     int(amount))

        # 委托挂单
        args = dict()
        args['url'] = self.contract_host + '/qapi-v1/entrust/brush'
        args['method'] = 'POST'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        args['data']['amount'] = digit_to_string(int(amount))
        if price and spec_price_flag:
            args['data']['price'] = digit_to_string(round(price, price_precision) if price_precision else round(price))

        try:
            result = await self.request(args)
            print(result)
            if result['code'] == 200:

                res = ujson.loads(result['content'])
                errno = res.get("errno")
                if errno == 0:
                    res["heartbeat"] = True
                    return res
                else:
                    loguru.logger.info(f"contract_add_plus-{symbol}-{self._token_[-6:]}-"
                                       f"{str(args['data']['amount'])}-"
                                       f"{str(ujson.loads(result['content']))}")
            else:
                loguru.logger.info(f"contract_add_plus-error {symbol} {result}")  # return result
        except BaseException as e:
            loguru.logger.info(f"contract_add_plus-error-{symbol}-{self._token_}-"
                               f"{traceback.format_exc()} {repr(e)}")

    async def contract_cancel(self, order_ids=None, symbol=None):
        args = dict()
        args['url'] = self.contract_host + '/qapi-v1/entrust/cancel'
        args['method'] = 'POST'
        args['data'] = dict()
        if symbol:
            args['data']['symbol'] = symbol
        else:
            cancel_list = ','.join(order_ids)
            args['data']['order_ids'] = cancel_list

        res = {"errno": -1, "msg": f"合约{symbol= }撤单异常"}

        try:
            result = await self.request(args)

            if result['code'] == 200:
                re = ujson.loads(result['content'])
                cancel_num = len(re['result']['successList'])
                fail_cancel_num = len(re['result']['failList'])
                if fail_cancel_num:
                    loguru.logger.info(f"contract_cancel-error {self._token_[-6:]} {symbol= }  {len(re['result']['failList'])}")
                    return res
                return re
            else:
                loguru.logger.info(f"contract_cancel-error, {self._token_}, {symbol= } ， {result}")
        except (BaseException, Exception) as e:
            msg = f"{traceback.format_exc()}"
            loguru.logger.info(f"contract_cancel-error {symbol= }  {msg}")
        return res

    async def cancel(self, order_ids=None, symbol=None):
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
        args['url'] = '{host}/openApi/entrust/cancel'.format(host=self.host)
        args['method'] = 'POST'
        args['data'] = dict()
        if order_ids:
            cancel_list = ','.join(order_ids)
            args['data']['order_ids'] = cancel_list
        if symbol:
            args['data']['symbol'] = symbol

        res = {"errno": -1, "msg": f"现货{symbol= }撤单异常"}

        try:
            result = await self.request(args)

            if result['code'] == 200:
                re = ujson.loads(result['content'])
                success_cancel_num = len(re['result']['success'])
                fails = re['result']['fail']
                if fails:
                    loguru.logger.info(f"cancel-spot-error {self._token_[-6:]} {symbol= } {len(re['result']['fail'])}")
                    return res
                return re
            else:
                loguru.logger.info(f"cancel-spot-error {self._token_[-6:]} {symbol= } {result}")
        except (BaseException, Exception) as e:
            msg = f"{traceback.format_exc()}"
            loguru.logger.info(f"cancel-spot {symbol= } {msg}")
        return res

    async def current_list(self, symbol, order_sn=None, direct='pre', limit=100):
        args = dict()
        args['url'] = '{host}/openApi/entrust/currentList'.format(host=self.host)
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        if order_sn:
            args['data']['from'] = order_sn
        args['data']['direct'] = direct
        args['data']['limit'] = limit

        result = await self.request(args)

        if result['code'] == 200:
            return ujson.loads(result['content'])
        else:
            print("current_list", result)  # return result

    async def current_steps(self, symbol, order_sn=None, direct='next', limit=100):
        args = dict()
        args['url'] = '{host}/openApi/entrust/currentList'.format(host=self.host)
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        if order_sn:
            args['data']['from'] = order_sn
        args['data']['direct'] = direct
        args['data']['limit'] = limit

        result = await self.request(args)

        if result['code'] == 200:
            return ujson.loads(result['content'])
        else:
            return result

    async def contract_current_steps(self, symbol, order_sn=None, direct='next', limit=100, is_full=None):
        args = dict()
        args['url'] = '{host}/qapi-v1/entrust/currentList'.format(host=self.contract_host)
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        args['data']['from'] = order_sn
        args['data']['direct'] = direct
        args['data']['limit'] = limit
        args['data']['is_full'] = is_full if is_full else self.is_full

        result = await self.request(args)

        if result['code'] == 200:
            return ujson.loads(result['content'])
        else:
            return result

    async def current_all(self, symbol, number):
        current_list = []
        res_last = await self.current_list(symbol)

        if res_last.get('result', 0):
            length = len(res_last['result']) - 1
            last_id = res_last['result'][length]['order_sn']

            for i in res_last['result']:
                if i['status'] == 1 or i['status'] == 2:
                    current_list.append(i)
            flag = True
            while flag:
                start_id = last_id
                res = await self.current_steps(symbol, start_id, 'prev', 100)
                if len(res.get('result', [])) == 1:
                    break
                if res.get('result', 0):
                    length = len(res['result']) - 1
                    last_id = res['result'][length]['order_sn']
                    for i in res['result']:

                        if i['status'] == 1 or i['status'] == 2:
                            if i['order_sn'] not in current_list:
                                current_list.append(i)
                    if len(current_list) >= number:
                        break
                else:
                    flag = False

            return current_list
        else:
            return current_list

    async def contract_current_list(self, symbol, is_full=None):
        args = dict()
        args['url'] = self.contract_host + '/qapi-v1/entrust/currentList'
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        # args['data']['type'] = type
        args['data']['is_full'] = is_full if is_full else self.is_full
        result = await self.request(args)

        if result['code'] == 200:
            return ujson.loads(result['content'])
        else:
            return result

    async def contract_current_all(self, symbol, number, is_full=None):
        current_list = []
        res_last = await self.contract_current_list(symbol, is_full)

        if res_last.get('result', 0):
            length = len(res_last['result']) - 1
            last_id = res_last['result'][length]['order_id']

            for i in res_last['result']:
                if i['status'] == 1 or i['status'] == 2:
                    current_list.append(i)
            flag = True
            while flag:
                start_id = last_id
                res = await self.contract_current_steps(symbol, start_id, 'prev', 100, is_full)
                if len(res.get('result', [])) == 1:
                    break
                if res.get('result', 0):
                    length = len(res['result']) - 1
                    last_id = res['result'][length]['order_id']
                    for i in res['result']:

                        if i['status'] == 1 or i['status'] == 2:
                            if i['order_id'] not in current_list:
                                current_list.append(i)
                    if len(current_list) >= number:
                        break
                else:
                    flag = False

            return current_list
        else:
            return current_list

    async def contract_wallet(self, symbol="", is_full=None):
        """
       {
        "errno": 0,
        "errmsg": "success",
        "result":[{
               "symbol": "ETH-USDT",
               "avail": "20",
               "hold": "1",
               "frozen": 0
            }]
        }

        :param is_full:模式 1逐仓，2全仓
        :param symbol:交易对
        :return:
        """
        # 查询我的资产
        args = dict()
        args['url'] = self.contract_host + '/qapi-v1/funds/walletList'
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        args['data']['is_full'] = is_full if is_full else self.is_full

        result = await self.request(args)

        if result['code'] == 200:
            return ujson.loads(result['content'])
        else:
            return result

    async def contract_position(self, symbol="", is_full=None):
        '''
        {
            "errno": 0,
            "errmsg": "success",
            "result": [
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
        '''
        args = dict()
        args['url'] = self.contract_host + '/qapi-v1/funds/position'
        args['method'] = 'GET'
        args['data'] = dict()
        if symbol:
            args['data']['symbol'] = symbol
        args['data']['is_full'] = is_full if is_full else self.is_full
        try:
            result = await self.request(args)
            if result['code'] == 200:
                return ujson.loads(result['content'])
            else:
                result = []
                loguru.logger.info(f"contract_position-error!!, {self._token_}, {result}")
                return result
        except (BaseException, Exception) as e:
            result = []
            msg = f"{traceback.format_exc()}"
            loguru.logger.info(f"contract_position-error!! {self._token_= }  {msg}")
            return result


    def contract_index(self):
        args = dict()
        args['url'] = '{host}/openApi/contract/markPrice'.format(host=self.contract_host)
        args['method'] = 'GET'
        args['data'] = dict()
        print(args)
        result = self.sync_request(args)

        if result['code'] == 200:
            return ujson.loads(result['content'].encode('utf-8'))
        else:
            return result

    async def async_contract_index(self):
        args = dict()
        args['url'] = '{host}/qapi-v1/market/mark-price'.format(host=self.contract_host)
        args['method'] = 'GET'
        args['timeout'] = 5
        args['data'] = dict()
        print(args)
        result = await self.request(args)

        if result['code'] == 200:
            return ujson.loads(result['content'])
        else:
            return result


if __name__ == '__main__':
    # apikey = {'token': "420c7bc61f89eed8d144304bb45af59f", 'secret_key': "cukk8ouh9mtu5jtww9a0"}
    apikey = {'token': "f56d8d9b7a92b495e84119b3c53558a5", 'secret_key': "g0bbteibtlhovkr9jozs"}
    # apikey = {'token': "4185ee92b273de729bdb5618296875e5", 'secret_key': "unn8hmmeywer9sx67y13"}
    ao = AbcApi(**apikey)

    # d = asyncio.run(ao.market_detail(symbol='BTC-USDT'))
    d = asyncio.run(ao.market_24kline(symbol='BTC-USDT'))
    # d = asyncio.run(ao.kline(symbol='BTC-USDT', period='5min', size=150))
    # d = asyncio.run(ao.depth(symbol='BTC-USDT'))
    # d = asyncio.run(ao.gears_depth(symbol='BTC-USDT'))
    # d = asyncio.run(ao.trades(symbol='BTC-USDT', size=5))
    # d = asyncio.run(ao.symbols())
    # d = asyncio.run(ao.precision())
    # d = asyncio.run(ao.current_list(symbol='BTC-USDT'))
    # d = asyncio.run(ao.current_all(symbol='BTC-USDT', number=100))
    # d = asyncio.run(ao.current_steps(symbol='BTC-USDT'))
    # d = asyncio.run(ao.history_list(symbol='BTC-USDT'))
    # d = asyncio.run(ao.history_steps(symbol='BTC-USDT'))
    # d = asyncio.run(ao.deal('BL123456789987523'))
    # d = asyncio.run(ao.wallet(currency='USDT'))
    # d = asyncio.run(ao.add(symbol='DASH-USDT', type='sell-limit', price=50, amount=1))
    # d = asyncio.run(ao.cancel(symbol='BTC-USDT', order_ids='BL961684677183958VRUWAR'))
    print(d)

