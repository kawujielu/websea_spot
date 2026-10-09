import traceback
import threading
import time
import hashlib
import random
import string
import aiohttp
import ssl
import ujson
import json
import requests
from libs import libs_price

CONTRACT_LEVER_RATE = 5
CONTRACT_LEVER_RATE_1000X = 500


def get_contract_precision():
    condition_url = 'https://coqv.websea.work' + "/qapi-v1/symbol/precision"

    try:
        res = requests.get(condition_url, timeout=2, verify=False)
        if res.status_code == 200:
            symbols_contract_condition = ujson.loads(res.text)["result"]
            return symbols_contract_condition
        else:
            print("获取失败，contract precision 将使用默认值", res)
    except BaseException as e:
        print("合约精度获取失败! contract precision 将使用默认值: precision error", e, traceback.format_exc())
    try:
        default_contract_precision = libs_price.get_precision_config(name='contract_redis_precision')
        symbols_contract_condition = default_contract_precision
    except BaseException as e:
        print("合约精度从redis获取失败！precision error", e, traceback.format_exc())
        symbols_contract_condition = {}

    return symbols_contract_condition


SYMBOLS_CONTRACT_CONDITION = get_contract_precision()


class AbcApi(object):

    def __init__(self, token, secret_key):
        self.host = 'https://exqv.websea.work'
        self.contract_host = "https://coqv.websea.work"

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
        self.is_full = 1  # 逐仓
        self.logger = None

    def make_header(self, data: dict):
        ran_str = ''.join(random.sample(string.ascii_letters + string.digits, 5))
        nonce = "%d_%s" % (int(time.time() * 1000), ran_str)
        header = dict()
        header['Token'] = self._token_
        header['Nonce'] = nonce
        header['Signature'] = self.sign(nonce, data)

        return header

    def sign(self, Nonce, data: dict):
        tmp = list()
        tmp.append(self._token_)
        tmp.append(self._secret_key_)
        tmp.append(Nonce)
        for d, x in data.items():
            tmp.append(str(d) + "=" + str(x))

        return hashlib.sha1(''.join(sorted(tmp)).encode("utf8")).hexdigest()

    # def __del__(self):
    #     session_name = threading.current_thread().name
    #     if self.session.get(session_name):  # 实例化未调用过任何接口，session为空
    #         asyncio.run(self.session[session_name].close())

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
        args['headers'].update(self.make_header(args['data']))

        session_name = threading.current_thread().name
        if not self.session.get(session_name):
            connector = aiohttp.TCPConnector(limit=500, ssl=self.sslcontext, ttl_dns_cache=10 * 60, )
            self.session[session_name] = aiohttp.ClientSession(base_url=self.contract_host, timeout=3,
                                                               connector=connector)
        data, params = {}, {}
        method = args['method'].upper()
        if method in ["GET"]:
            params = args['data']
        else:
            data = args['data']

        async with self.session[session_name].request(method=method,
                                                      url=args['url'],
                                                      headers=args['headers'],
                                                      timeout=args['timeout'],
                                                      data=data,
                                                      params=params, ) as r:
            result['content'] = await r.text()
            result['code'] = r.status
        return result

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
        args['url'] = '/qapi-v1/funds/walletList'
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        args['data']['is_full'] = is_full if is_full else self.is_full

        result = await self.request(args)

        if result['code'] == 200:
            return ujson.loads(result['content'])
        else:
            return result

    async def precision(self):

        args = dict()
        args['url'] = '/qapi-v1/symbol/precision'
        args['method'] = 'GET'
        args['data'] = dict()

        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def contract_add(self, symbol, type, amount, price, is_full=None):
        price_precision = int(SYMBOLS_CONTRACT_CONDITION[symbol].get("price", 8))
        # 委托挂单
        args = dict()
        args['url'] = '/qapi-v1/entrust/add'
        args['method'] = 'POST'
        args['data'] = dict()
        args['data']['symbol'] = symbol
        args['data']['contract_type'] = "open"
        if symbol.split("-")[0] == "BTC1000X":
            args['data']['lever_rate'] = CONTRACT_LEVER_RATE_1000X
        else:
            args['data']['lever_rate'] = CONTRACT_LEVER_RATE

        args['data']['type'] = type

        args['data']['price'] = round(price, price_precision) if price_precision else round(price)

        amount = amount / float(SYMBOLS_CONTRACT_CONDITION[symbol]["faceValue"])
        amount = min(float(SYMBOLS_CONTRACT_CONDITION[symbol]["maxQuantity"]) * random.uniform(0.9, 1),
                     int(amount))
        amount = max(float(SYMBOLS_CONTRACT_CONDITION[symbol]["minQuantity"]) * random.uniform(1, 1.2),
                     int(amount))
        args['data']['amount'] = int(amount)
        args['data']['is_full'] = is_full if is_full else self.is_full

        try:
            res = await self.request(args)
            res = ujson.loads(res['content'])
            if res["errno"] != 0:
                res["token"] = self._token_
                res["args"] = str(args)
                self.logger.info(f"contract_add_error {symbol}-{args['data']['amount']}-{args['data']['price']}-{res}")

            args['data']['ctime'] = int(time.time())
            res["args"] = args

        except (BaseException, Exception) as e:
            msg = f"{traceback.format_exc()}"
            self.logger.info(f"contract_add_error {msg}")
            res = {"errno": -1, "msg": f"{symbol}下单异常"}
            return res
        return res

    async def contract_position(self, symbol="", is_full=None):
        """
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
        :param symbol:
        :param is_full:
        :return:
        """
        args = dict()
        args['url'] = '/qapi-v1/funds/position'
        args['method'] = 'GET'
        args['data'] = dict()
        if symbol:
            args['data']['symbol'] = symbol
        args['data']['is_full'] = is_full if is_full else self.is_full
        result = await self.request(args)

        if result['code'] == 200:
            return ujson.loads(result['content'])
        else:
            return result

    async def contract_cancel(self, order_ids=None, symbol=None):
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
        args['url'] = '/qapi-v1/entrust/cancel'
        args['method'] = 'POST'
        args['data'] = dict()
        if symbol:
            args['data']['symbol'] = symbol
        else:
            args['data']['order_ids'] = order_ids

        try:
            result = await self.request(args)

            if result['code'] == 200:
                re = ujson.loads(result['content'])
                if re["errno"] == 0:
                    success_cancel_num = len(re['result']['successList'])
                    fail_cancel_num = len(re['result']['failList'])
                    if fail_cancel_num:
                        self.logger.info(f"contract_cancel {re['result']['failList']}")
                    return ujson.loads(result['content'])
            self.logger.info(f"contract_cancel {result}")
        except (BaseException, Exception) as e:
            msg = f"{traceback.format_exc()}"
            self.logger.info(f"contract_cancel {msg}")
            res = {"errno": -1, "msg": f"{symbol}撤单异常"}
            return res

    async def contract_current_list(self, symbol, is_full=None):
        args = dict()
        args['url'] = '/qapi-v1/entrust/currentList'
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

    async def contract_current_steps(self, symbol, order_sn=None, direct='next', limit=100, is_full=None):
        args = dict()
        args['url'] = '/qapi-v1/entrust/currentList'
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

    async def detail_contract(self, order_id):
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
        :param order_id:订单编号
        :return:
        """
        args = dict()
        args['url'] = '/openApi/contract/detail'
        args['method'] = 'GET'
        args['data'] = dict()
        args['data']['order_id'] = order_id

        result = await self.request(args)

        if result['code'] == 200:
            return ujson.loads(result['content'])
        else:
            return result

    async def contract_current_all(self, symbol, number, is_full=None):
        contract_list = []
        res_last = await self.contract_current_list(symbol, is_full)

        if res_last.get('result', 0):
            length = len(res_last['result']) - 1
            last_id = res_last['result'][length]['order_id']

            for i in res_last['result']:
                if i['status'] == 1 or i['status'] == 2:
                    contract_list.append(i)
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
                            if i not in contract_list:
                                contract_list.append(i)
                    if len(contract_list) >= number:
                        break
                else:
                    flag = False

            return contract_list
        else:
            return contract_list

    async def contract_current_cancel(self, symbol, number, is_full=None):
        contract_list = []
        res_last = await self.contract_current_list(symbol, is_full)

        if res_last.get('result', 0):
            length = len(res_last['result']) - 1
            last_id = res_last['result'][length]['order_id']

            for i in res_last['result']:
                if i['status'] == 4:
                    contract_list.append(i)
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

                        if i['status'] == 4:
                            if i not in contract_list:
                                contract_list.append(i)
                    if len(contract_list) >= number:
                        break
                else:
                    flag = False

            return contract_list
        else:
            return contract_list
