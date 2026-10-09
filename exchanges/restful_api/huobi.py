import asyncio
import datetime
import base64
import json
import traceback
from urllib import parse
import urllib
import time
import hmac
import hashlib
from many_configs.account_config import EXTERNAL_ACCOUNTS
from many_configs import global_variable
from scaffold.aiohttp import G_RequestSession
from many_configs.exchange_config import EXCHANGE_CONFIG
from libs.utils import digit_to_string
from libs.utils import round_down
from loguru import logger


class HuobiApi:
    exchange_name = "hb"

    def __init__(self, api_key=None, secret=None):
        self._apiKey_ = api_key if api_key else EXTERNAL_ACCOUNTS[self.exchange_name]["apiKey"]
        self._secret_ = secret if secret else EXTERNAL_ACCOUNTS[self.exchange_name]["secret"]
        self.url = EXCHANGE_CONFIG[self.exchange_name]['spot_restful']
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
        data = args.get('data', None)
        method = args['method']
        cookies = args.get('cookies', {})
        signed = args.get('signed', False)
        args['timeout'] = 15

        # 对于 GET 请求，每个方法自带的参数都需要进行签名运算。
        # 对于 POST 请求，每个方法自带的参数不进行签名认证，并且需要放在 body 中。
        body = json.dumps(data) if method == 'POST' else ''
        data = dict() if method == 'POST' else data
        result = {}
        if signed:
            data['AccessKeyId'] = self._apiKey_
            data['SignatureVersion'] = "2"
            data['SignatureMethod'] = "HmacSHA256"
            Timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
            data['Timestamp'] = Timestamp
            data['Signature'] = await self.generate_signature(method, params=data, request_path=args['url'])

        args['header'] = dict()
        if method == 'GET':
            args['header']["Content-type"] = "application/x-www-form-urlencoded"
            args['header']["User-Agent"] = 'USER_AGENT1.1.5_201217_alpha'
        else:
            args['header']["Accept"] = "application/json"
            args['header']["Content-type"] = "application/json"
            args['header']["User-Agent"] = 'USER_AGENT1.1.5_201217_alpha'

        async with G_RequestSession.request.request(method=method,
                                                    url=args['url'],
                                                    params=data,
                                                    data=body,
                                                    headers=args['header'],
                                                    # proxy='http://127.0.0.1:7890',
                                                    timeout=int(args['timeout'])) as r:
            result['content'] = await r.text()
            result['code'] = r.status
        return result

    async def accountsId(self):
        # GET /api/v3/account (HMAC SHA256)
        args = dict()
        args['url'] = f'{self.url}/v1/account/accounts'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        result = await self.request(args)
        if result['code'] == 200:
            content = json.loads(result['content'])
            acc = {i['type']: str(i['id']) for i in content['data']}
            return acc
        else:
            return result

    async def wallet_free(self):
        # GET /api/v3/account (HMAC SHA256)
        args = dict()
        if not self.spot_id:
            self.spot_id = (await self.accountsId())['spot']
        args['url'] = f'{self.url}/v1/account/accounts/{self.spot_id}/balance'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['timestamp'] = int(time.time() * 1000)
        result = await self.request(args)
        if result['code'] == 200:
            content = json.loads(result['content'])
            result = {i['currency'].upper(): float(i['available']) for i in content['data']['list'] if
                      i['type'] == 'trade' and float(i['available'])}
            return result
        else:
            return result

    async def wallet(self):
        # GET /api/v3/account (HMAC SHA256)
        args = dict()
        if not self.spot_id:
            self.spot_id = (await self.accountsId())['spot']
        args['url'] = f'{self.url}/v1/account/accounts/{self.spot_id}/balance'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        args['data']['timestamp'] = int(time.time() * 1000)
        result = await self.request(args)
        if result['code'] == 200:
            content = json.loads(result['content'])
            result = {i['currency'].upper(): float(i['balance']) for i in content['data']['list'] if
                      float(i['balance'])}
            return result
        else:
            return result

    async def add(self, symbol, side, amount, price, type, account):
        # POST /v1/order/orders/place
        # 精度不对，不会反馈订单
        if self.exchange_name in global_variable.PRECISION.keys():
            precision = global_variable.PRECISION[self.exchange_name].get(symbol, {})
        else:
            global_variable.PRECISION[self.exchange_name] = {}
            precision = {}

        if not precision:
            precision = await self.precision(symbol)
            global_variable.PRECISION[self.exchange_name][symbol] = precision

        if precision['amount_precision'] == 0:
            amount = int(amount)
        else:
            amount = round_down(amount, precision['amount_precision'])
        if precision['price_precision'] == 0:
            price = int(price)
        else:
            price = round(price, precision['price_precision'])
        if precision['minQty'] > amount:
            return {
                'content': json.dumps({"code": -1013, "msg": f"Filter failure:{amount}小于最小下单量{precision['minQty']} "}),
                'code': 400}
        if precision['minQtyQuote'] > amount * price:
            return {'content': json.dumps({"code": -1013,
                                           "msg": f"Filter failure:[amount:{amount},price:{price}] 下单总价值:{amount * price}小于{precision['minQtyQuote']} "}),
                    'code': 400}

        args = dict()
        if not self.spot_id:
            self.spot_id = (await self.accountsId())['spot']
        args['url'] = f'{self.url}/v1/order/orders/place'
        args['method'] = 'POST'
        args['signed'] = True
        args['data'] = dict()
        args['data']['account-id'] = self.spot_id
        args['data']['symbol'] = symbol.replace('-', '').lower()
        args['data']['type'] = side.lower() + '-' + type.lower()
        args['data']['amount'] = str(amount)
        args['data']['price'] = digit_to_string(price)
        args['data']['source'] = account

        result = await self.request(args)
        return result

    async def create_order(self, symbol, side, amount, price, type='LIMIT', account='spot-api'):
        result = await self.add(symbol, side, amount, price, type, account)
        if result['code'] == 200:
            content = json.loads(result['content'])
            if content['err-code'] in ['order-orderamount-precision-error',
                                       'order-orderprice-precision-error']:

                precision = await self.precision(symbol)
                global_variable.PRECISION[self.exchange_name][symbol] = precision
                result = await self.add(symbol, side, amount, price, type, account)
                if result['code'] == 200:
                    content = json.loads(result['content'])
                    content['orderId'] = content.get('data', '')
                    content['status'] = content['status']
                    return content
            else:
                content['orderId'] = content.get('data', '')
                content['status'] = content['status']
                return content
        return result

    async def get_orders(self, symbol, orderId):
        # 查询订单详情
        # /v1/order/orders/{order-id}
        """
        :param symbol:
        :param orderId:
        :return:
        created：已创建，该状态订单尚未进入撮合队列。
        submitted : 已挂单等待成交，该状态订单已进入撮合队列当中。
        partial-filled : 部分成交，该状态订单在撮合队列当中，订单的部分数量已经被市场成交，等待剩余部分成交。
        filled : 已成交。该状态订单不在撮合队列中，订单的全部数量已经被市场成交。
        partial-canceled : 部分成交撤销。该状态订单不在撮合队列中，此状态由partial-filled转化而来，订单数量有部分被成交，但是被撤销。
        canceling : 撤销中。该状态订单正在被撤销的过程中，因订单最终需在撮合队列中剔除才会被真正撤销，所以此状态为中间过渡态。
        canceled : 已撤销。该状态订单不在撮合订单中，此状态订单没有任何成交数量，且被成功撤销。
        """
        order_status = {'submitted': 'new'}
        args = dict()
        args['url'] = f'{self.url}/v1/order/orders/{orderId}'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        result = await self.request(args)

        if result['code'] == 200:
            res = json.loads(result['content'])
            res['status'] = order_status.get(res['data']['state'], res['data']['state']).upper()
            res['fillsz'] = float(res['data']['field-amount'])

            return res
        else:
            return result

    async def get_open_orders(self, orderId=None):
        # 查询订单
        # GET /v1/order/orders/{order-id}
        args = dict()
        args['url'] = f'{self.url}/v1/order/orders/{orderId}'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()

        result = await self.request(args)
        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def cancel_order(self, symbol, orderId):
        # POST /v1/order/orders/{order-id}/submitcancel
        args = dict()
        args['url'] = f'{self.url}/v1/order/orders/{orderId}/submitcancel'
        args['method'] = 'POST'
        args['signed'] = True
        args['data'] = dict()
        args['data']['symbol'] = symbol.replace('-', '').lower()
        result = await self.request(args)

        if result['code'] == 200:
            return json.loads(result['content'])
        else:
            return result

    async def depth(self, symbol, limit=5, type='step0'):
        args = dict()
        args['url'] = f'{self.url}/market/depth'
        args['method'] = 'GET'
        args['signed'] = False
        args['data'] = dict()
        args['data']['symbol'] = symbol.replace('-', '').lower()
        args['data']['depth'] = limit
        args['data']['type'] = type

        result = await self.request(args)
        if result['code'] == 200:
            res = json.loads(result['content'])
            return res['tick']
        else:
            return result

    async def precision(self, symbol=None):
        # symbols 查询的交易对组合，不填表示所有交易对，多个交易对请使用 , 分隔
        args = dict()
        args['url'] = f'{self.url}/v1/settings/common/market-symbols'
        args['method'] = 'GET'
        args['signed'] = False
        args['data'] = dict()
        args['data']['symbols'] = symbol.replace('-', '').lower()
        result = await self.request(args)
        if result['code'] == 200:
            info = json.loads(result['content'])['data'][0]
            precision = {'price_precision': info['pp'], 'amount_precision': info['ap'], 'minQty': float(info['minoa']),
                         'minQtyQuote': float(info['minov'])}
            return precision
        else:
            return result

    async def get_trades(self, symbol, orderId):
        # 成交明细
        # GET /v1/order/orders/{order-id}/matchresults
        args = dict()
        args['url'] = f'{self.url}/v1/order/orders/{orderId}/matchresults'
        args['method'] = 'GET'
        args['signed'] = True
        args['data'] = dict()
        result = await self.request(args)
        if result['code'] == 200:
            res = []
            for i in json.loads(result['content'])['data']:
                ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(float(i['created-at']) / 1000)))
                # fee-deduct-currency 抵扣类型
                # filled-points 抵扣数量（可为ht或hbpoint）
                if i['fee-deduct-currency']:
                    fee = i['filled-points']
                    feecoin = i['fee-deduct-currency']
                else:
                    fee = i['filled-fees']
                    feecoin = i['fee-currency']

                d = {
                    'side': i['type'].replace('-limit', ''),
                    'amount': float(i['filled-amount']),
                    'tradeId': i['trade-id'],
                    'price': float(i['price']),
                    'fee': fee,
                    'feecoin': feecoin,
                    'time': ts,
                    'orderId': i['order-id'],
                    'symbol': symbol,
                    'exchange': self.exchange_name
                }
                res.append(d)
            return res

        else:
            return result


# huobi_instance = HuobiApi()
# global_variable.EXTERNAL_EXCHANGE_INSTANCES[huobi_instance.exchange_name] = huobi_instance


async def main():
    exchanges = [HuobiApi(api_key='b7e15bdd-bgbfh5tv3f-0bf80824-d95e5',
                          secret='4a340036-a21a5241-c8805729-c4b1c')]
    try:
        tasks = [asyncio.create_task(ex.depth('BTC-USDT')) for ex in exchanges]
        await asyncio.wait(tasks)
    except:
        logger.error(f"{traceback.format_exc()}")


if __name__ == "__main__":
    # asyncio.run(main())
    api = {'apiKey': '197feb7b-bn2wed5t4y-25df15af-e0f03',
           'secret': '49eb1b08-67a413d5-766287c6-9e185'}
    bb = HuobiApi(api_key=api['apiKey'], secret=api['secret'])
    amount = 0.0050
    price = 1200
    symbol = 'ETH-USDT'
    side = 'BUY'
    # wallet = asyncio.run(bb.create_order(symbol=symbol, side=side, amount=amount, price=price))
    # orderId = '752104419267223'
    orderId = '752104586383076'
    # orderId = '289324676615'
    # orderId = '289332846754'
    # wallet = asyncio.run(bb.cancel_order(symbol, orderId=orderId))
    # wallet = asyncio.run(bb.get_orders(symbol, orderId=orderId))
    # wallet = asyncio.run(bb.get_trades(symbol, orderId=orderId))
    wallet = asyncio.run(bb.depth(symbol=symbol))
    # wallet = asyncio.run(bb.wallet_free())
    # wallet = asyncio.run(bb.precision(symbol))
    # wallet = asyncio.run(bb.accountsId())

