import loguru
import traceback

import urllib.parse
from typing import Dict, Any
import time
import hmac
import json
import base64
import hashlib
from loguru import logger
from libs.utils import digit_to_string
from libs.utils import round_down

import asyncio
import traceback
from scaffold.aiohttp import G_RequestSession

from many_configs.exchange_config import EXCHANGE_CONFIG
from many_configs.account_config import EXTERNAL_ACCOUNTS
from many_configs import global_variable


class KrakenApi:
    exchange_name = "kraken"

    def __init__(self, api_key=None, secret=None):
        self._apiKey_ = api_key if api_key else EXTERNAL_ACCOUNTS[self.exchange_name]["apiKey"]
        self._secret_ = secret if secret else EXTERNAL_ACCOUNTS[self.exchange_name]["secret"]
        self.url = EXCHANGE_CONFIG[self.exchange_name]['spot_restful']

    def parse_params_to_str(self, data: dict) -> dict:
        params = {k: v for k, v in data.items()}
        url = '?'
        for key, value in params.items():
            url = url + str(key) + '=' + str(value) + '&'
        return url[0:-1]

    def _get_kraken_signature(self, urlpath: str, data: dict, nonce: str) -> str:
        """
        生成Kraken API签名
        """
        post_data = urllib.parse.urlencode(data)
        encoded = (str(nonce) + post_data).encode()
        message = urlpath.encode() + hashlib.sha256(encoded).digest()

        signature = hmac.new(base64.b64decode(self._secret_),
                             message,
                             hashlib.sha512)
        sig_digest = base64.b64encode(signature.digest())
        return sig_digest.decode()

    async def request(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送请求到Kraken API
        """
        data = args.get('data', {})
        method = args['method']
        signed = args.get('signed', False)
        endpoint = args['url']
        get_path = '' if method == "POST" else self.parse_params_to_str(data)
        url = self.url + endpoint + get_path

        headers = {
            'User-Agent': 'Kraken Python Client',
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        if signed:
            nonce = str(int(time.time() * 1000))
            data['nonce'] = nonce
            headers['API-Key'] = self._apiKey_
            headers['API-Sign'] = self._get_kraken_signature(endpoint, data, nonce)

        try:
            async with G_RequestSession.request.request(
                    method=method,
                    url=url,
                    headers=headers,
                    data=urllib.parse.urlencode(data) if data else None,
                    timeout=10
            ) as response:
                result = {
                    'content': await response.text(),
                    'code': response.status
                }
                return result
        except Exception as e:
            logger.error(f"{traceback.format_exc()}")
            return {'code': 500, 'content': str(e)}

    async def wallet(self) -> Dict[str, float]:
        """
        获取账户余额
        """
        args = {
            'url': '/0/private/Balance',
            'method': 'POST',
            'signed': True,
            'data': {}
        }

        result = await self.request(args)
        if result['code'] == 200:
            data = json.loads(result['content'])
            if data.get('error'):
                return {'code': 400, 'content': str(data['error'])}

            balances = {}
            for asset, amount in data['result'].items():
                # Kraken在某些资产前加X或Z，需要处理
                clean_asset = asset[1:] if asset.startswith('X') or asset.startswith('Z') else asset
                balances[clean_asset] = float(amount)
            return {k: v for k, v in balances.items() if v > 0}
        return result

    async def wallet_free(self) -> Dict[str, float]:
        """
        获取可用余额
        """
        return await self.wallet()  # Kraken API不直接提供冻结/可用余额区分

    async def create_order(self, symbol: str, side: str, amount: float,
                           price: float, type: str = 'limit',
                           force: str = 'gtc') -> Dict[str, Any]:
        """
        创建订单
        """
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
        if precision.get('minQty') > amount:
            return {'content': {"code": -1013, "msg": f"Filter failure:{amount}小于最小下单量{precision['minQty']} "},
                    'code': 400}
        if precision.get('minQtyQuote') > amount * price:
            return {'content': {"code": -1013,
                                "msg": f"Filter failure:[amount:{amount},price:{price}] 下单总价值:{amount * price}小于{precision['minQtyQuote']} "},
                    'code': 400}

        args = {
            'url': '/0/private/AddOrder',
            'method': 'POST',
            'signed': True,
            'data': {
                'pair': symbol.replace('-', ''),
                'type': side.lower(),
                'ordertype': type.lower(),
                'volume': str(amount),
            }
        }

        if type.lower() == 'limit':
            args['data']['price'] = digit_to_string(price)

        if force == 'ioc':
            args['data']['timeinforce'] = 'IOC'
        elif force == 'fok':
            args['data']['timeinforce'] = 'FOK'

        result = await self.request(args)
        if result['code'] == 200:
            data = json.loads(result['content'])
            logger.info(f"{self.exchange_name}-create_order {data=}")

            if data.get('error'):
                return {'code': 400, 'content': str(data['error'])}
            return {
                'orderId': data['result']['txid'][0],
                'status': 'NEW'
            }
        return result

    async def get_orders(self, symbol: str, orderId: str) -> Dict[str, Any]:
        """
        获取订单信息
        """
        args = {
            'url': '/0/private/QueryOrders',
            'method': 'POST',
            'signed': True,
            'data': {
                'txid': orderId
            }
        }

        result = await self.request(args)
        if result['code'] == 200:
            data = json.loads(result['content'])
            logger.info(f"{self.exchange_name}-get_orders {data=}")
            if data.get('error'):
                return {'code': 400, 'content': str(data['error'])}

            order = data['result'][orderId]
            status_map = {
                'pending': 'NEW',
                'open': 'NEW',
                'closed': 'FILLED',
                'canceled': 'CANCELED',
                'expired': 'EXPIRED'
            }

            return {
                'status': status_map.get(order['status'], order['status'].upper()),
                'fillsz': float(order.get('vol_exec', 0)),
                'price': float(order['price']),
                'amount': float(order['vol']),
                "open_time": order['opentm']
            }
        return result

    async def get_open_orders(self) -> Dict[str, Any]:
        """
        获取订单信息
        """
        args = {
            'url': '/0/private/OpenOrders',
            'method': 'POST',
            'signed': True,
            'data': {
            }
        }

        result = await self.request(args)
        if result['code'] == 200:
            data = json.loads(result['content'])
            logger.info(f"{self.exchange_name}-get_open_orders {data=}")
            if data.get('error'):
                return {'code': 400, 'content': str(data['error'])}
            loguru.logger.info(f"{data=}")

        return result

    async def get_trades(self, symbol: str, orderId: str):
        """
        获取订单的成交明细

        Args:
            symbol: 交易对
            orderId: 订单ID
        Returns:
            List[Dict]: 成交明细列表
            Dict: 错误信息
        """
        open_time = time.time() - 600
        try:
            res = await self.get_orders(symbol, orderId)
            if res:
                open_time = res["open_time"] - 1
        except:
            pass
        try:
            args = {
                'url': '/0/private/TradesHistory',  # Kraken的交易历史API端点
                'method': 'POST',
                'signed': True,
                'data': {
                    'txid': orderId,  # Kraken使用txid作为订单ID
                    'start': open_time,
                }
            }


            result = await self.request(args)
            if result['code'] == 200:
                data = json.loads(result['content'])

                # 检查API错误
                if data.get('error'):
                    return {
                        'code': 400,
                        'content': str(data['error'])
                    }

                res = []
                trades = data['result']['trades']
                logger.info(f"get_trades {open_time} {trades=}")
                # 处理每笔成交
                for trade_id, trade in trades.items():
                    # 只处理与指定订单相关的成交
                    if trade.get('ordertxid') == orderId:
                        # Kraken的时间戳是Unix时间戳
                        ts = time.strftime(
                            "%Y-%m-%d %H:%M:%S",
                            time.localtime(int(float(trade['time'])))
                        )
                        fee_currency = symbol.split('-')[-1]
                        # 构建统一格式的成交记录
                        d = {
                            'side': 'BUY' if trade['type'] == 'buy' else 'SELL',
                            'amount': float(trade['vol']),  # 成交数量
                            'tradeId': trade_id,  # 成交ID
                            'price': float(trade['price']),  # 成交价格
                            'fee': abs(float(trade['fee'])),  # 手续费
                            'feecoin': fee_currency,  # 手续费币种
                            'time': ts,  # 成交时间
                            'orderId': orderId,  # 订单ID
                            'symbol': symbol,  # 交易对
                            'exchange': self.exchange_name  # 交易所名称
                        }
                        res.append(d)

                return res
            else:
                return result

        except Exception as e:
            logger.error(f"Get trades error: {traceback.format_exc()}")
            return {
                'code': 500,
                'content': str(e)
            }

    async def cancel_order(self, symbol: str, orderId: str) -> Dict[str, Any]:
        """
        取消订单
        """
        args = {
            'url': '/0/private/CancelOrder',
            'method': 'POST',
            'signed': True,
            'data': {
                'txid': orderId
            }
        }

        result = await self.request(args)
        if result['code'] == 200:
            data = json.loads(result['content'])
            logger.info(f"{self.exchange_name}-cancel_order {data=}")
            if data.get('error'):
                return {'code': 400, 'content': str(data['error'])}
            return data['result']
        return result

    async def cancel_all_orders(self) -> Dict[str, Any]:
        """
        取消订单
        """
        args = {
            'url': '/0/private/CancelAll',
            'method': 'POST',
            'signed': True,
            'data': {
            }
        }

        result = await self.request(args)
        if result['code'] == 200:
            data = json.loads(result['content'])
            logger.info(f"{self.exchange_name}-CancelAll {data=}")
            if data.get('error'):
                return {'code': 400, 'content': str(data['error'])}
            return data['result']
        return result

    async def depth(self, symbol: str, limit: int = 5) -> Dict[str, Any]:
        """
        获取订单簿深度
        """
        args = {
            'url': '/0/public/Depth',
            'method': 'GET',
            'signed': False,
            'data': {
                'pair': symbol.replace('-', ''),
                'count': limit
            }
        }

        result = await self.request(args)
        if result['code'] == 200:
            data = json.loads(result['content'])
            if data.get('error'):
                return {'code': 400, 'content': str(data['error'])}

            # Kraken返回的第一个键是交易对名称
            market_data = list(data['result'].values())[0]
            return {
                'asks': [[float(price), float(amount), timestamp]
                         for price, amount, timestamp in market_data['asks']],
                'bids': [[float(price), float(amount), timestamp]
                         for price, amount, timestamp in market_data['bids']]
            }
        return result

    async def precision(self, symbol: str) -> Dict[str, Any]:
        """
        获取交易对精度信息
        """
        args = {
            'url': '/0/public/AssetPairs',
            'method': 'GET',
            'signed': False,
            'data': {
                'pair': symbol.replace('-', '')
            }
        }

        result = await self.request(args)
        if result['code'] == 200:
            data = json.loads(result['content'])
            if data.get('error'):
                return {'code': 400, 'content': str(data['error'])}

            pair_data = list(data['result'].values())[0]
            return {
                'price_precision': pair_data['pair_decimals'],
                'amount_precision': pair_data['lot_decimals'],
                'minQty': float(pair_data['ordermin']),
                'minQtyQuote': 0.0001  # Kraken没有直接提供最小交易金额，这是一个估计值
            }
        return result

    async def get_ws_token(self):
        """获取Kraken WebSocket Token"""
        args = {
            'url': '/0/private/GetWebSocketsToken',
            'method': 'POST',
            'signed': True,
            'data': {}
        }
        result = await self.request(args)
        if result['code'] == 200:
            data = json.loads(result['content'])
            if not data.get('error'):
                return data['result']['token']
        return None



kraken_instance = KrakenApi()
global_variable.EXTERNAL_EXCHANGE_INSTANCES[kraken_instance.exchange_name] = kraken_instance

if __name__ == '__main__':
    import asyncio
    api = {'apiKey': 'Ac0cs+LmAdrvTDQ7VhiODdA3Oenn+ozumtgl2YsSy/gJLkHajSVe0hEp',
           'secret': 'LTMHPokskn9KcEjD+qgavfClZZE61t8oZTkayezzC22DDdQw0HXjxt1L32wS5ibNFB1BTXybirWnOAqu9PZYYQ=='}

    kraken_instance = KrakenApi(api["apiKey"], api["secret"])
    symbol = 'USDQ-USDT'
    side = 'BUY'
    amount = 5
    price = 0.8
    order_id = 'O52Q4U-RPA3O-CXZ6FA'

    async def test_main():

        # res1 = await kraken_instance.create_order(symbol=symbol, side=side, amount=amount, price=price)
        # res2 = await kraken_instance.cancel_order(symbol=symbol, orderId=order_id)
        #res22 = await kraken_instance.cancel_all_orders()
        #res21 = await kraken_instance.cancel_all_orders()

        res3 = await kraken_instance.wallet()
        # res4 = await kraken_instance.get_orders(symbol, order_id)
        # res5 = await kraken_instance.get_trades(symbol, order_id)
        print(res3)

    asyncio.run(test_main())

