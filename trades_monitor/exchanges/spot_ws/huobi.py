import datetime
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
import hmac
import base64
import hashlib
from many_configs.account_config import EXTERNAL_ACCOUNTS
from urllib import parse
import urllib
import asyncio

HUOBI_WS_USERDATE_URL = 'wss://api.huobi.pro/ws/v2'


class HuobiWs:
    exchange_name = "hb"

    def __init__(self, api_key=None, secret=None):
        self._apiKey_ = api_key if api_key else EXTERNAL_ACCOUNTS[self.exchange_name]["apiKey"]
        self._secret_ = secret if secret else EXTERNAL_ACCOUNTS[self.exchange_name]["secret"]
        self.url = 'https://api.huobi.pro'
        self.spot_id = None

    async def generate_signature(self, method, params, request_path):
        if request_path.startswith("http://") or request_path.startswith("https://"):
            host_url = urllib.parse.urlparse(request_path).hostname.lower()
            request_path = '/' + '/'.join(request_path.split('/')[3:])
        else:
            host_url = urllib.parse.urlparse(self.url).hostname.lower()
        sorted_params = sorted(params.items(), key=lambda d: d[0], reverse=False)
        encode_params = urllib.parse.urlencode(sorted_params)
        payload = [method, host_url, request_path, encode_params]
        payload = "\n".join(payload)
        payload = payload.encode(encoding="UTF8")
        secret_key = self._secret_.encode(encoding="utf8")
        digest = hmac.new(secret_key, payload, digestmod=hashlib.sha256).digest()
        signature = base64.b64encode(digest)
        signature = signature.decode()
        return signature

    async def request(self, args):
        data = {}
        method = args['method']
        data['accessKey'] = self._apiKey_
        data['signatureMethod'] = "HmacSHA256"
        data['signatureVersion'] = "2.1"
        data['timestamp'] = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
        data['signature'] = await self.generate_signature(method, params=data, request_path=args['url'])
        data['authType'] = 'api'
        return data

    async def get_ws_header(self):
        args = dict()
        args['url'] = f'{self.url}/ws/v2'
        args['method'] = 'GET'
        result = await self.request(args)
        return result


huobi_ws = HuobiWs()

if __name__ == '__main__':
    asyncio.run(huobi_ws.get_ws_header())
