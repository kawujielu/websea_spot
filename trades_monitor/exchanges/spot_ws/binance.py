import random
import asyncio
import time
import hmac
import hashlib
import json
from operator import itemgetter
from many_configs.account_config import EXTERNAL_ACCOUNTS
from scaffold.aiohttp import G_RequestSession
import websockets
import ssl
import ujson

BN_WS_PRIVATE_URL = 'wss://testnet.binance.vision/ws-api/v3'
BN_WS_USERDATE_URL = 'wss://testnet.binance.vision/ws/'  # test


class BinanceWs:
    exchange_name = "bn"

    def __init__(self, api_key=None, secret=None):
        self._apiKey_ = api_key if api_key else EXTERNAL_ACCOUNTS[self.exchange_name]["apiKey"]
        self._secret_ = secret if secret else EXTERNAL_ACCOUNTS[self.exchange_name]["secret"]
        # self.url = 'https://api.binance.com'
        self.url = 'https://testnet.binance.vision'  # test

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
            async with G_RequestSession.request.request(method=method,
                                                        url=args['url'],
                                                        params=args['params'],
                                                        headers=headers,
                                                        timeout=5) as r:
                result['content'] = await r.text()
            result['code'] = r.status
            return result

    async def new_listen_key(self):
        args = dict()
        args['url'] = '{}/api/v3/userDataStream'.format(self.url)
        args['method'] = 'POST'
        args['signed'] = False
        args['data'] = dict()
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def put_listen_key(self, listen_key):
        args = dict()
        args['url'] = '{}/api/v3/userDataStream'.format(self.url)
        args['method'] = 'PUT'
        args['signed'] = False
        args['data'] = dict()
        args['data']['listenKey'] = listen_key
        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result


bn_ws = BinanceWs()


async def test():
    async with websockets.connect(BN_WS_PRIVATE_URL, close_timeout=0.01,
                                  ping_interval=15,
                                  max_queue=128, compression=None,
                                  ssl=ssl._create_unverified_context()) as webs:
        # order_params = {
        #     "symbol": "BTCUSDT",
        #     "limit": 5,
        #     "apiKey": EXTERNAL_ACCOUNTS['bn']["apiKey"],
        #     "timestamp": int(time.time() * 1000)
        # }
        account_params = {
            "apiKey": EXTERNAL_ACCOUNTS['bn']["apiKey"],
            "timestamp": int(time.time() * 1000)
        }
        account_params['signature'] = bn_ws._generate_signature(account_params)
        asyncio.create_task(webs.send(ujson.dumps({
            "id": random.random(0, 1000000),
            "method": "account.status",
            # "method": "allOrders",  #
            "params": account_params,
        })))
        message = await asyncio.wait_for(webs.recv(), 2 * 30)
        msg = ujson.loads(message)
        print(msg)


if __name__ == '__main__':
    pass
