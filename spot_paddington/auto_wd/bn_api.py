import asyncio
import time
import hmac
import hashlib
import json
from operator import itemgetter

import loguru

from many_configs.account_config import EXTERNAL_ACCOUNTS
from many_configs import global_variable
from scaffold.aiohttp import G_RequestSession
from many_configs.exchange_config import EXCHANGE_CONFIG
from libs.recode_msg import recode_error_msg


class BinanceApi:
    exchange_name = "bn"

    def __init__(self, api_key=None, secret=None):
        self._apiKey_ = api_key if api_key else EXTERNAL_ACCOUNTS[self.exchange_name]["apiKey"]
        self._secret_ = secret if secret else EXTERNAL_ACCOUNTS[self.exchange_name]["secret"]
        self.url = EXCHANGE_CONFIG[self.exchange_name]['spot_restful']

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
            # async with aiohttp.ClientSession(timeout=10, connector=TCPConnector(verify_ssl=False)) as session:
            async with G_RequestSession.request.request(method=method,
                                                        url=args['url'],
                                                        params=args['params'],
                                                        headers=headers,
                                                        # proxy='http://127.0.0.1:7890',
                                                        timeout=5) as r:
                result['content'] = await r.text()
            result['code'] = r.status
            return result

    async def deposit_hisrec(self, start_ts):
        # GET /sapi/v1/capital/deposit/hisrec
        args = dict()
        args['url'] = '{}/sapi/v1/capital/deposit/hisrec'.format(self.url)
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['timestamp'] = int(time.time() * 1000)
        args['data']['startTime'] = start_ts
        result = await self.request(args)
        if result['code'] == 200:
            his = json.loads(result['content'])
            loguru.logger.info(f"deposit_hisrec {start_ts=} {his=}")
            return his
        else:
            msg = f"deposit_hisrec error {start_ts} {result}"
            await recode_error_msg(msg, "spot_hedge")
            return None

    async def withdraw_hisrec(self, start_ts, coin=None, limit=1000):
        """
        GET /sapi/v1/capital/withdraw/history — 查询提币记录。
        :param start_ts: 起始时间（毫秒）
        :param coin: 可选币种
        :param limit: 默认 1000，最大 1000
        :return: 提币记录列表；status=6 表示提现完成
        注意: startTime 与 endTime 间隔不得超过 90 天
        """
        args = dict()
        args['url'] = '{}/sapi/v1/capital/withdraw/history'.format(self.url)
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = {
            'timestamp': int(time.time() * 1000),
            'startTime': start_ts,
            'limit': limit,
        }
        if coin:
            args['data']['coin'] = coin
        result = await self.request(args)
        if result['code'] == 200:
            his = json.loads(result['content'])
            loguru.logger.info(f"withdraw_hisrec {start_ts=} {his=}")
            return his
        else:
            msg = f"withdraw_hisrec error {start_ts} {result}"
            await recode_error_msg(msg, "spot_hedge")
            return None


bn_instance = BinanceApi()


if __name__ == "__main__":
    start = int(time.time() * 1000) - 86400 * 1000
    asyncio.run(bn_instance.withdraw_hisrec(start_ts=start))
