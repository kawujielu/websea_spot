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
        self.host = "https://oapi.websea.work"
        self.risk_host = "https://riskapi.websea.work"
        self.risk_token = "c1cf4185b2bed317aeb6e6674491fbef"

        # self.risk_host = "https://riskapi.wbstests.net"
        # self.risk_token = "d5ee2eedfcf7adc285db4967bd86910d"

        self._token_ = token
        self._secret_key_ = secret_key
        self.session = {}
        self._precision_cache = {}  # symbol -> amount decimals (int)
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
            args['timeout'] = 10

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

    async def market_precision(self, symbol=None):
        """查询现货交易对精度 GET /openApi/market/precision；不传 symbol 返回全部。"""
        args = dict()
        args['url'] = f'{self.host}/openApi/market/precision'
        args['method'] = 'GET'
        args['data'] = dict()
        if symbol:
            args['data']['symbol'] = symbol
        try:
            result = await self.request(args)
            if result['code'] == 200:
                re = ujson.loads(result['content'])
                if re.get('errno') == 0:
                    return re.get('result') or {}
                loguru.logger.error(f"market_precision {symbol=} {re=}")
            else:
                loguru.logger.error(f"market_precision {args=} {result}")
        except (BaseException, Exception):
            loguru.logger.error(f"market_precision {traceback.format_exc()}")
        return {}

    async def amount_decimals(self, currency, quote="USDT", default=4, max_retry=5):
        """返回币种数量精度（小数位数）；失败 sleep 3s 重试，连续 max_retry 次失败用 default。"""
        symbol = f"{currency}-{quote}"
        if symbol in self._precision_cache:
            return self._precision_cache[symbol]
        for i in range(1, max_retry + 1):
            result = await self.market_precision(symbol)
            info = result.get(symbol) or {}
            raw = info.get("amount")
            if raw is not None:
                try:
                    decimals = int(float(raw))
                    self._precision_cache[symbol] = decimals
                    return decimals
                except (TypeError, ValueError):
                    pass
            loguru.logger.warning(
                f"amount_decimals 查询失败 {symbol=} 第{i}/{max_retry}次，3s后重试"
            )
            if i < max_retry:
                await asyncio.sleep(3)
        loguru.logger.error(f"amount_decimals 连续{max_retry}次失败 {symbol=}，使用默认 {default}")
        self._precision_cache[symbol] = default
        return default

    async def withdraw(self, currency, quantity, address, chain, memo=None):
        args = dict()
        args['url'] = f'{self.host}/openApi/wallet/withdraw'
        args['method'] = 'POST'
        args['data'] = dict()

        args['data']['address'] = address
        args['data']['amount'] = digit_to_string(quantity)
        args['data']['currency'] = currency
        args['data']['chain'] = chain
        if memo:
            args['data']['memo'] = memo

        try:
            loguru.logger.info(f"下单参数:{args=}")
            result = await self.request(args)

            if result['code'] == 200:
                re = ujson.loads(result['content'])
                loguru.logger.info(f"{currency} withdraw {re=}")
                return re
            else:
                loguru.logger.info(f"withdraw {args=} {result}")
        except (BaseException, Exception) as e:
            msg = f"{traceback.format_exc()}"
            loguru.logger.error(f"withdraw {args= } {msg}")

    async def withdraw_his(self, user_id, wd_id=None):
        args = dict()
        args['url'] = f'{self.risk_host}/api/open/get'
        args['method'] = 'GET'
        args['data'] = dict()

        args['data']['url'] = "risk/takeout"
        args['data']['token'] = self.risk_token
        args['data']['user_id'] = user_id
        if wd_id:
            args['data']['id'] = wd_id

        try:
            result = await self.request(args)

            if result['code'] == 200:
                re = ujson.loads(result['content'])
                loguru.logger.info(f"withdraw_his {re=}")
                return re['result']['data']
            else:
                loguru.logger.info(f"withdraw_his {args=} {result}")
        except (BaseException, Exception) as e:
            msg = f"{traceback.format_exc()}"
            loguru.logger.error(f"withdraw {args= } {msg}")

    async def deposit_his(self, user_id, min_time=None, max_time=None, page_size=100):
        """
        GET /api/transfer/cashinlist — 查询用户充值记录。
        :param user_id: 用户 id
        :param min_time: 开始时间（秒）
        :param max_time: 结束时间（秒）
        :param page_size: 分页大小，默认 100
        :return: 充值记录列表
        """
        rows, page = [], 1
        try:
            while True:
                args = {
                    "url": f"{self.risk_host}/api/transfer/cashinlist",
                    "method": "GET",
                    "data": {
                        "token": self.risk_token,
                        "user_id": user_id,
                        "page": page,
                        "page_size": page_size,
                    },
                    "timeout": 30,
                }
                if min_time is not None:
                    args["data"]["min_time"] = min_time
                if max_time is not None:
                    args["data"]["max_time"] = max_time

                result = await self.request(args)
                if result["code"] != 200:
                    loguru.logger.info(f"deposit_his {args=} {result}")
                    break
                re = ujson.loads(result["content"])
                data = (re.get("result") or {}).get("data") or []
                if not data:
                    break
                rows.extend(data)
                if len(data) < page_size:
                    break
                page += 1
                await asyncio.sleep(0.2)
            loguru.logger.info(f"deposit_his user_id={user_id} count={len(rows)}")
            return rows
        except (BaseException, Exception):
            msg = f"{traceback.format_exc()}"
            loguru.logger.error(f"deposit_his {msg}")
            return None


if __name__ == '__main__':
    # apikey = {'token': "7665d59224d56e497a142e9000i56478975", 'secret_key': "sm1w1u30nlduxv7fzkem"}
    apikey = {'token': "78fc47c5590f77ca42d1e2c3bb432813", 'secret_key': "5e5yg7ga285hctuqrtpb"}
    ao = AbcApi(**apikey)

    # d = asyncio.run(ao.withdraw("USDT", 5, "TE25rECxZEv5TAGJ2AStUtaSuf6Bgi31Tr", "TRC20"))
    # d = asyncio.run(ao.withdraw_his(196, wd_id=114686))
    d = asyncio.run(ao.deposit_his(196, min_time=int(time.time()) - 86400 * 7))
