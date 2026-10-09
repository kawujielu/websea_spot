import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
import time
import hmac
import json
import base64
import hashlib
from operator import itemgetter
from urllib.parse import urlencode
from many_configs.account_config import EXTERNAL_ACCOUNTS
from scaffold.aiohttp import G_RequestSession
import asyncio

MEXC_WS_USERDATE_URL = 'wss://wbs.mexc.com/ws'


class MexcWs:
    exchange_name = "mxc"

    def __init__(self, api_key=None, secret=None):
        self._apiKey_ = api_key if api_key else EXTERNAL_ACCOUNTS[self.exchange_name]["apiKey"]
        self._secret_ = secret if secret else EXTERNAL_ACCOUNTS[self.exchange_name]["secret"]

        self.url = "https://api.mexc.com"
        self.prefix = "/api/v3"
        self.recv_window = str(5000)
        # self.url = url

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
        query_string = str(timestamp) + str(method) + str(path) + str(body)
        m = hmac.new(bytes(self._secret_, encoding='utf-8'), bytes(query_string, encoding='utf-8'), digestmod='sha256')
        return base64.b64encode(m.digest())

    def genSignature(self, timestamp, body):
        param_str = str(timestamp) + self._apiKey_ + self.recv_window + body

        hash = hmac.new(bytes(self._secret_, "utf-8"), param_str.encode("utf-8"), hashlib.sha256)
        signature = hash.hexdigest()
        return signature

    def pre_hash(timestamp, method, request_path, body):
        return str(timestamp) + str.upper(method) + request_path + body

    async def parse_params_to_str(self, data: dict) -> dict:
        params = {k: v for k, v in data.items()}
        url = '?'
        for key, value in params.items():
            url = url + str(key) + '=' + str(value) + '&'
        return url[0:-1]

    async def _sign_v3(self, req_time, sign_params=None):
        if sign_params:
            print('data', sign_params)
            sign_params = urlencode(sign_params)
            # to_sign = "{}&recvWindow={}&timestamp={}".format(sign_params, self.recv_window, req_time)
            to_sign = "{}&timestamp={}".format(sign_params, req_time)
        else:
            print('-123')
            to_sign = "timestamp={}".format(req_time)

        sign = hmac.new(self._secret_.encode('utf-8'), to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
        return sign

    async def request(self, args):
        data = args.get('data', {})
        method = args['method']
        signed = args.get('signed', False)
        kwargs = dict()
        args['timeout'] = 15
        timestamp = str(int(time.time() * 10 ** 3))

        request_path = '' if method == 'POST' else (await self.parse_params_to_str(data))
        # query_string = '' if method == 'POST' else request_path.replace('?', '')
        # body = json.dumps(data) if method == 'POST' else ''
        # host = self.prefix + args['url']

        args['header'] = dict()
        args['header']['Content-Type'] = 'application/json'
        args['header']['X-MEXC-APIKEY'] = self._apiKey_

        url = self.url + args['url']

        if signed:
            data['signature'] = await self._sign_v3(timestamp, data)
            data['timestamp'] = timestamp
        result = {}

        async with G_RequestSession.request.request(method=method,
                                                    url=url,
                                                    params=data,
                                                    data=kwargs,
                                                    headers=args['header'],
                                                    timeout=int(args['timeout'])) as r:
            result['content'] = await r.text()
            result['code'] = r.status

        return result

    async def new_listen_key(self):
        args = dict()
        args['url'] = '/api/v3/userDataStream'
        args['method'] = 'POST'
        args['signed'] = True
        args['data'] = dict()

        result = await self.request(args)

        if result['code'] == 200:
            res = json.loads(result['content'])
            return res
        else:
            return result

    async def put_listen_key(self, listen_key):
        args = dict()
        args['url'] = '/api/v3/userDataStream'
        args['method'] = 'PUT'
        args['signed'] = True
        args['data'] = dict()
        args['data']['listenKey'] = listen_key
        result = await self.request(args)

        if result['code'] == 200:
            res = json.loads(result['content'])
            return res
        else:
            return result


mexc_ws = MexcWs()

if __name__ == '__main__':
    re = asyncio.run(mexc_ws.new_listen_key())
    print(re)
