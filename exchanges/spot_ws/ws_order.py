import json
import asyncio
import threading
import ssl
import websockets
import ujson
import base64
import uuid
from exchanges.spot_ws.okex import OKEX_WS_PRIVATE_URL, okex_ws
from exchanges.spot_ws.gateio import GATE_WS_PRIVATE_URL, gate_ws
from exchanges.spot_ws.binance import BN_WS_USERDATE_URL, bn_ws
import time
from loguru import logger
import traceback
from scaffold.mysql import Hedge_MysqlSession
from exchanges.spot_ws.mexc import MEXC_WS_USERDATE_URL, mexc_ws
from exchanges.spot_ws.huobi import HUOBI_WS_USERDATE_URL, huobi_ws
from exchanges.spot_ws.bitget import BITGET_WS_PRIVATE_URL, bitget_ws
from many_configs.global_variable import WS_EXCEPTION_SLEEP_TIME, ORDER_RESTART_DELAY_TIME
from libs.recode_msg import recode_error_msg
from async_timeout import timeout
import datetime
from scaffold.libs import ping_enhance
from many_configs import global_variable
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from many_configs.exchange_config import EXCHANGE_CONFIG
from exchanges.restful_api.kraken import kraken_instance

'''
okex status:
    canceled:撤单成功
    live:等待成交
    partially_filled:部分成交
    filled:完全成交
bn status:
    NEW:订单被交易引擎接
    PARTIALLY_FILLED:部分订单被成交
    FILLED:订单完全成交
    CANCELED:用户撤销了订单
    PENDING_CANCEL:撤销中（目前并未使用）
    REJECTED:订单没有被交易引擎接受，也没被处理
    EXPIRED:订单被交易引擎取消，比如：(LIMIT FOK 订单没有成交,市价单没有完全成交,强平期间被取消的订单,交易所维护期间被取消的订单)
    EXPIRED_IN_MATCH:表示订单由于 STP 触发而过期 （e.g. 带有 EXPIRE_TAKER 的订单与订单簿上属于同账户或同 tradeGroupId 的订单撮合）
gate status:
    put: order creation
    update: order fill update
    finish: order closed or cancelled
'''

okex_status = {
    'live': 'new'

}
bn_status = {
    'NEW': 'new',
    'PARTIALLY_FILLED': 'partially_filled',
    'FILLED': 'filled',
    'CANCELED': 'canceled'
}

gate_status = {
    'put': 'new',
    'update': 'filled',
    'finish': 'canceled'
}

huobi_status = {
    'submitted': 'new',
    'partial-filled': 'partially_filled',
    'filled': 'filled',
    'partial-canceled': 'partially_canceled',
    'canceled': 'canceled',
}

mexc_status = {
    1: 'new',
    2: 'filled',
    3: 'partially_filled',
    4: 'canceled',
    5: 'partially_canceled'
}

huobi_type = {
    'buy-limit': 'BUY',
    'sell-limit': 'SELL'
}

bitget_status = {
    'live': 'new'
}


# todo ws订阅正常，数据还需要测试
#  问题： 1、ws推送的数据 插入数据库会不会存在重复
#        2、是否要插入逐笔成交表(trades表)
#        3、ws和restful一起是否会导致数据混乱
async def insert_orders_db(orders, is_api=True):
    select_sql = f"SELECT * FROM orders_ws where orderId='{orders['orderId']}'"
    res = await Hedge_MysqlSession.fetch_all(select_sql)
    if res:
        insert_sql = f"UPDATE orders_ws set status ='{orders['status'].upper()}',fillsz='{orders['fillsz']}' where orderId='{orders['orderId']}'"
    else:
        insert_sql = "INSERT ignore INTO orders_ws (exchange,orderId,symbol,price, side, amount,`time`,status, fillsz, is_api) " \
                     f"VALUES ('{orders['exchange']}','{orders['orderId']}','{orders['symbol']}','{orders['price']}'," \
                     f"'{orders['side'].upper()}','{orders['amount']}','{orders['time']}','{orders['status'].upper()}'," \
                     f"'{orders['fillsz']}', '{is_api}')"
    await Hedge_MysqlSession.insert(insert_sql)


async def insert_trades_db(trades):
    insert_sql = f"INSERT ignore INTO trades_ws (exchange,tradeId,orderId,symbol,price, side, amount,`time`,fee,feecoin) " \
                 f"VALUES ('{trades['exchange']}','{trades['tradeId']}','{trades['orderId']}','{trades['symbol']}','{trades['price']}'," \
                 f"'{trades['side'].upper()}','{trades['amount']}','{trades['time']}','{trades['fee']}','{trades['feecoin']}')"
    await Hedge_MysqlSession.insert(insert_sql)


class BinanceUserDataStream:
    def __init__(self, api_key, private_key_path, exchange='bn'):
        self.api_key = api_key
        self.private_key_path = private_key_path
        self.ws_url = "wss://ws-api.binance.com/ws-api/v3"
        self.exchange = exchange
        self.ws = None

        # 加载私钥
        with open(private_key_path, "rb") as f:
            self.private_key = serialization.load_pem_private_key(
                f.read(),
                password=None
            )
            if not isinstance(self.private_key, ed25519.Ed25519PrivateKey):
                raise ValueError("Provided key is not an Ed25519 private key")

    def _generate_signature(self, timestamp):
        message = f"apiKey={self.api_key}&timestamp={timestamp}"
        signature = base64.b64encode(
            self.private_key.sign(message.encode("utf-8"))
        ).decode()
        return signature

    async def authenticate(self):
        try:
            timestamp = int(time.time() * 1000)
            signature = self._generate_signature(timestamp)

            auth_request = {
                "id": str(uuid.uuid4()),
                "method": "session.logon",
                "params": {
                    "apiKey": self.api_key,
                    "signature": signature,
                    "timestamp": timestamp
                }
            }

            await self.ws.send(json.dumps(auth_request))
            response = await self.ws.recv()
            response_data = json.loads(response)

            if response_data.get("status") == 200:
                logger.info(f"{self.exchange} Successfully authenticated")
                return True
            else:
                logger.info(f"{self.exchange} Authentication failed: {response_data}")
                return False

        except Exception as e:
            logger.info(f"{self.exchange} Error during authentication: {traceback.format_exc()}")
            return False

    async def connect(self):
        try:
            self.ws = await websockets.connect(self.ws_url, close_timeout=0.01,
                                               ping_interval=15,
                                               max_queue=128, compression=None,
                                               ssl=ssl._create_unverified_context())

            if not await self.authenticate():
                return False

            subscribe_request = {
                "id": str(uuid.uuid4()),
                "method": "userDataStream.subscribe",
                "params": {}
            }

            await self.ws.send(json.dumps(subscribe_request))
            response = await self.ws.recv()
            response_data = json.loads(response)

            if response_data.get("status") == 200:
                logger.info(f"{self.exchange} Successfully subscribed to user data stream")
                return True
            else:
                logger.info(f"{self.exchange} Failed to subscribe: {response_data}")
                return False

        except Exception as e:
            logger.info(f"{self.exchange} Error connecting to WebSocket: {traceback.format_exc()}")
            return False

    async def process_message(self, msg):
        if msg['e'] == 'executionReport':
            order = msg
            symbol = order['s'].upper()
            if symbol.endswith('USDT'):
                symbol = symbol[:-4] + '-USDT'
            if symbol.endswith('BTC'):
                symbol = symbol[:-3] + '-BTC'

            status = bn_status.get(order['X'], order['X'])
            order_info = {
                'exchange': self.exchange,
                'orderId': order['i'],
                'symbol': symbol,
                'fillsz': order['z'],
                'side': order['S'],
                'amount': order['q'],
                'price': order['p'],
                'status': status,
                'time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(order['E'] / 1000)))
            }
            logger.info(f'{self.exchange} ws order_info {order_info}')
            await insert_orders_db(order_info)

            if status in ['partially_filled', 'filled']:
                trade_info = {
                    'exchange': self.exchange,
                    'orderId': order['i'],
                    'symbol': symbol,
                    'side': order['S'],
                    'amount': order['l'],
                    'price': order['L'],
                    'fee': order['n'],
                    'feecoin': order['N'],
                    'tradeId': order['t'],
                    'time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(order['T'] / 1000)))
                }
                logger.info(f'{self.exchange} ws trade_info {trade_info}')
                await insert_trades_db(trade_info)

        elif msg['e'] == 'outboundAccountPosition':
            logger.info(f'{self.exchange} ws_wallet {msg}')
            if not global_variable.WALLET_EXCHANGE_CURRENCY.get(self.exchange, {}):
                global_variable.WALLET_EXCHANGE_CURRENCY[self.exchange] = {}
            for i in msg['B']:
                global_variable.WALLET_EXCHANGE_CURRENCY[self.exchange].update({i['a']: float(i['f'])})
                global_variable.WALLET_EXCHANGE_CURRENCY[self.exchange] = \
                    global_variable.WALLET_EXCHANGE_CURRENCY[self.exchange]

    async def listen(self):
        try:
            while True:
                async with timeout(ORDER_RESTART_DELAY_TIME):
                    message = await self.ws.recv()
                msg = ujson.loads(message)
                logger.info(f'{self.exchange} listen msg {msg}')
                msg = msg.get('event')
                if msg:
                    await self.process_message(msg)

        except asyncio.TimeoutError:
            msg = f"order {self.exchange} {ORDER_RESTART_DELAY_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
        except websockets.exceptions.ConnectionClosed:
            logger.error(f"{self.exchange} WebSocket connection closed")
        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")

    async def close(self):
        if self.ws:
            logout_request = {
                "id": str(uuid.uuid4()),
                "method": "session.logout"
            }
            await self.ws.send(json.dumps(logout_request))
            await self.ws.close()


async def get_bn_order(thread_name='bnThread'):
    exchange = 'bn'
    while True:
        try:
            print(f"{thread_name}-----start_ws")
            user_stream = BinanceUserDataStream(
                api_key="bNZEZwtfCDc5EVUCBNe5HGDUeZe7pvEhxzrp8PynMrL5UORfCOIC9Hwgx8MPy7Ir",
                private_key_path="/home/ubuntu/code/spot_paddington/pems/private_key.pem",
                exchange=exchange
            )

            if await user_stream.connect():
                try:
                    await user_stream.listen()
                finally:
                    await user_stream.close()

        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")
        finally:
            await asyncio.sleep(WS_EXCEPTION_SLEEP_TIME)


async def get_okex_order(is_subscribe='subscribe', thread_name='okexThread'):
    exchange = 'okex'
    # OKEX_WS_PRIVATE_URL = EXCHANGE_CONFIG[exchange]['private_ws']
    while True:
        try:
            print(f"{thread_name}-----start_ws")
            async with websockets.connect(OKEX_WS_PRIVATE_URL, close_timeout=0.01, ping_interval=15,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as webs:
                headers = okex_ws.get_ws_header()
                asyncio.create_task(webs.send(f'{{"op": "login", "args": [{ujson.dumps(headers)}]}}'))
                async with timeout(2 * 30):
                    await webs.recv()
                asyncio.create_task(webs.send(
                    ujson.dumps(
                        {
                            "op": is_subscribe,
                            "args": [{
                                "channel": "orders",
                                "instType": "SPOT",
                            }]
                        }
                    )))
                asyncio.create_task(webs.send(
                    ujson.dumps(
                        {
                            "op": is_subscribe,
                            "args": [{
                                "channel": "balance_and_position",
                                # "instType": "SPOT",
                            }]
                        }
                    )))
                webs.ping = ping_enhance(webs, "ping")
                while True:
                    async with timeout(ORDER_RESTART_DELAY_TIME):
                        message = await webs.recv()
                    if message == "pong":  # 判断推送来的消息类型：如果是服务器的心跳
                        continue
                    msg = ujson.loads(message)
                    print(f'{exchange} ws_order', msg)
                    if msg.get('arg', {}).get('channel') == 'orders' and msg.get('data', []):
                        orders = msg['data']
                        for order in orders:
                            status = okex_status.get(order['state'], order['state'])
                            order_info = {'exchange': exchange, 'orderId': order['ordId'], 'symbol': order['instId'],
                                          'side': order['side'], 'fillsz': order['accFillSz'],
                                          'amount': order['sz'], 'price': order['px'], 'status': status,
                                          'time': time.strftime('%Y-%m-%d %H:%M:%S',
                                                                time.localtime(int(int(order['uTime']) / 1000)))}
                            print(f'{exchange} ws order_info', order_info)
                            await insert_orders_db(order_info)
                            if status in ['partially_filled', 'filled']:
                                trade_info = {'exchange': exchange, 'orderId': order['ordId'],
                                              'symbol': order['instId'],
                                              'side': order['side'], 'amount': order['fillSz'],
                                              'price': order['fillPx'],
                                              'fee': order['fillFee'], 'feecoin': order['fillFeeCcy'],
                                              'tradeId': order['tradeId'],
                                              'time': time.strftime('%Y-%m-%d %H:%M:%S',
                                                                    time.localtime(int(int(order['uTime']) / 1000)))}
                                print(f'{exchange} ws trade_info', trade_info)
                                await insert_trades_db(trade_info)
                    if msg.get('arg', {}).get('channel') == 'balance_and_position' and msg.get('data', []):
                        print(f'{exchange} ws_wallet {msg}')
                        if not global_variable.WALLET_EXCHANGE_CURRENCY.get(exchange, {}):
                            global_variable.WALLET_EXCHANGE_CURRENCY[exchange] = {}
                        if msg.get('data', []):
                            orders = msg['data'][0]['balData']
                            for order in orders:
                                global_variable.WALLET_EXCHANGE_CURRENCY[exchange].update(
                                    {order['ccy'].upper(): float(order['cashBal'])})
                                global_variable.WALLET_EXCHANGE_CURRENCY[exchange] = \
                                    global_variable.WALLET_EXCHANGE_CURRENCY[exchange]
        except asyncio.TimeoutError:
            msg = f"order {exchange} {ORDER_RESTART_DELAY_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            # await recode_error_msg(msg, server="spot_hedge")
        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")
        finally:
            await asyncio.sleep(WS_EXCEPTION_SLEEP_TIME)


async def get_gate_order(is_subscribe='subscribe', thread_name='gateThread'):
    exchange = 'gate'
    # GATE_WS_PRIVATE_URL = EXCHANGE_CONFIG[exchange]['private_ws']
    while True:
        try:
            print(f"{thread_name}-----start_ws")
            async with websockets.connect(GATE_WS_PRIVATE_URL, close_timeout=0.01, ping_interval=15,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as webs:
                request = {
                    "time": int(time.time()),
                    "channel": "spot.orders",
                    "event": is_subscribe,
                    "payload": ["!all"]
                }
                request['auth'] = gate_ws.gen_sign(request['channel'], request['event'], request['time'])
                asyncio.create_task(webs.send(ujson.dumps(request)))
                trades_request = {
                    "time": int(time.time()),
                    "channel": "spot.usertrades",
                    "event": "subscribe",
                    "payload": ["!all"]
                }
                trades_request['auth'] = gate_ws.gen_sign(trades_request['channel'], trades_request['event'],
                                                          trades_request['time'])
                asyncio.create_task(webs.send(ujson.dumps(trades_request)))
                balances_request = {
                    "time": int(time.time()),
                    "channel": "spot.balances",
                    "event": is_subscribe,
                    "payload": ["!all"]
                }
                balances_request['auth'] = gate_ws.gen_sign(balances_request['channel'], balances_request['event'],
                                                            balances_request['time'])
                asyncio.create_task(webs.send(ujson.dumps(balances_request)))
                while True:
                    async with timeout(ORDER_RESTART_DELAY_TIME):
                        message = await webs.recv()
                    msg = ujson.loads(message)
                    print(f'{exchange} ws_order', msg)
                    if msg['channel'] == 'spot.orders' and msg['event'] == "update" and msg.get('result', []):
                        orders = msg['result']
                        for order in orders:
                            status = gate_status.get(order['event'], order['event'])
                            order_info = {'exchange': exchange, 'orderId': order['id'],
                                          'symbol': order['currency_pair'].replace('_', '-'),
                                          'side': order['side'],
                                          'fillsz': float(order['filled_total']) / float(
                                              order['avg_deal_price']) if float(order.get('avg_deal_price', 0)) else 0,
                                          'amount': order['amount'], 'price': order['price'], 'status': status,
                                          'time': time.strftime('%Y-%m-%d %H:%M:%S',
                                                                time.localtime(int(order['update_time'])))}
                            print(f'{exchange} ws order_info', order_info)
                            await insert_orders_db(order_info)
                    if msg['channel'] == 'spot.usertrades' and msg['event'] == "update" and msg.get('result', []):
                        trades = msg['result']
                        for trade in trades:
                            trade_info = {'exchange': exchange, 'orderId': trade['order_id'],
                                          'symbol': trade['currency_pair'].replace('_', '-'),
                                          'side': trade['side'], 'amount': trade['amount'], 'price': trade['price'],
                                          'fee': trade['fee'], 'feecoin': trade['fee_currency'],
                                          'tradeId': trade['id'],
                                          'time': time.strftime('%Y-%m-%d %H:%M:%S',
                                                                time.localtime(int(trade['create_time'])))}
                            print(f'{exchange} ws trade_info', trade_info)
                            await insert_trades_db(trade_info)
                    if msg['channel'] == 'spot.balances' and msg['event'] == "update" and msg.get('result', []):
                        print(f'{exchange} ws_wallet {msg}')
                        if not global_variable.WALLET_EXCHANGE_CURRENCY.get(exchange, {}):
                            global_variable.WALLET_EXCHANGE_CURRENCY[exchange] = {}
                        for i in msg.get('result', []):
                            global_variable.WALLET_EXCHANGE_CURRENCY[exchange].update(
                                {i['currency'].upper(): float(i['available'])})
                            global_variable.WALLET_EXCHANGE_CURRENCY[exchange] = \
                                global_variable.WALLET_EXCHANGE_CURRENCY[exchange]
        except asyncio.TimeoutError:
            msg = f"order {exchange} {ORDER_RESTART_DELAY_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            # await recode_error_msg(msg, server="spot_hedge")
        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")
        finally:
            await asyncio.sleep(WS_EXCEPTION_SLEEP_TIME)


async def get_hb_order(is_subscribe='subscribe', thread_name='hbThread'):
    exchange = 'hb'
    # HUOBI_WS_USERDATE_URL = EXCHANGE_CONFIG[exchange]['private_ws']
    while True:
        try:
            print(f"{thread_name}-----start_ws")
            async with websockets.connect(HUOBI_WS_USERDATE_URL, close_timeout=0.01,
                                          ping_interval=15,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as webs:
                sign = await huobi_ws.get_ws_header()
                asyncio.create_task(webs.send(
                    ujson.dumps({
                        "action": "req",
                        "ch": "auth",
                        "params": sign
                    })))
                async with timeout(2 * 30):
                    message = await webs.recv()
                print('hb auth', ujson.loads(message))
                sub = 'sub' if is_subscribe == 'subscribe' else 'unsub'
                asyncio.create_task(webs.send(
                    ujson.dumps({
                        "action": sub,
                        "ch": "orders#*"
                    })))
                while True:
                    async with timeout(ORDER_RESTART_DELAY_TIME):
                        message = await webs.recv()
                    msg = ujson.loads(message)
                    print(f'{exchange} ws_order', msg)
                    if msg.get('action', '') == 'ping':
                        data = {
                            'action': 'pong',
                            'data': {'ts': time.time() * 1000}
                        }
                        await webs.send(ujson.dumps(data))
                        continue
                    if 'orders#' in msg.get('ch', '') and msg.get('data', {}):
                        order = msg['data']
                        symbol = order['symbol'].upper()
                        if symbol.endswith('USDT'):
                            symbol = symbol.upper()[:-4] + '-USDT'
                        if symbol.upper().endswith('BTC'):
                            symbol = symbol.upper()[:-3] + '-BTC'
                        event_type = order['eventType']
                        if event_type in ['creation', 'trade', 'cancellation']:
                            status = huobi_status.get(order['orderStatus'], order['orderStatus'])
                            order_info = {'exchange': exchange, 'orderId': order['orderId'],
                                          'fillsz': order.get('execAmt', 0),
                                          'symbol': symbol, 'side': huobi_type.get(order['type'], order['type']),
                                          'amount': order['orderSize'], 'price': order['orderPrice'], 'status': status}
                            if event_type == 'creation':
                                order_info['time'] = time.strftime('%Y-%m-%d %H:%M:%S',
                                                                   time.localtime(int(order['orderCreateTime'])))
                            if event_type == 'cancellation':
                                order_info['time'] = time.strftime('%Y-%m-%d %H:%M:%S',
                                                                   time.localtime(int(order['lastActTime'])))
                            if event_type == 'trade':
                                order_info['time'] = time.strftime('%Y-%m-%d %H:%M:%S',
                                                                   time.localtime(int(order['tradeTime'])))
                            print(f'{exchange} ws order_info', order_info)
                            await insert_orders_db(order_info)
                        if event_type == 'trade':
                            trade = msg['data']
                            trade_info = {'exchange': exchange, 'orderId': trade['orderId'],
                                          'symbol': symbol,
                                          'side': huobi_type.get(trade['type'], trade['type']),
                                          'amount': trade['tradeVolume'],
                                          'price': trade['tradePrice'],
                                          'fee': None, 'feecoin': None,
                                          'tradeId': trade['tradeId'],
                                          'time': time.strftime('%Y-%m-%d %H:%M:%S',
                                                                time.localtime(int(trade['tradeTime'])))}

                            print(f'{exchange} ws trade_info', trade_info)
                            await insert_trades_db(trade_info)
        except asyncio.TimeoutError:
            msg = f"order {exchange} {ORDER_RESTART_DELAY_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            # await recode_error_msg(msg, server="spot_hedge")
        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")
        finally:
            await asyncio.sleep(WS_EXCEPTION_SLEEP_TIME)


async def get_mxc_order(is_subscribe='subscribe', thread_name='mxcThread'):
    exchange = 'mxc'
    # MEXC_WS_USERDATE_URL = EXCHANGE_CONFIG[exchange]['private_ws']
    while True:
        try:
            print(f"{thread_name}-----start_ws")
            listen_key = (await mexc_ws.new_listen_key())['listenKey']
            print(listen_key)
            global_variable.WS_LISTEN_KEY[exchange] = listen_key
            async with websockets.connect(f'{MEXC_WS_USERDATE_URL}?listenKey={listen_key}', close_timeout=0.01,
                                          ping_interval=15,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as webs:
                sub = "SUBSCRIPTION" if is_subscribe == 'subscribe' else 'UNSUBSCRIPTION'
                asyncio.create_task(webs.send(
                    ujson.dumps(
                        {
                            "method": sub,
                            "params": [
                                "spot@private.deals.v3.api",
                                "spot@private.orders.v3.api",
                                "spot@private.account.v3.api"
                            ]
                        }
                    )))
                webs.ping = ping_enhance(webs, ujson.dumps({"method": "PING"}))
                while True:
                    # await mexc_ws.put_listen_key(listen_key)
                    async with timeout(ORDER_RESTART_DELAY_TIME):
                        message = await webs.recv()
                    msg = ujson.loads(message)
                    print(f'{exchange} ws_order', msg)
                    if msg.get('c', '') == 'spot@private.orders.v3.api' and msg.get('d', {}):
                        order = msg['d']
                        symbol = msg['s']
                        if symbol.endswith('USDT'):
                            symbol = symbol.upper()[:-4] + '-USDT'
                        if symbol.upper().endswith('BTC'):
                            symbol = symbol.upper()[:-3] + '-BTC'
                        status = mexc_status.get(order['s'], order['s'])
                        order_info = {'exchange': exchange, 'orderId': order['i'],
                                      'symbol': symbol, 'fillsz': order['cv'],
                                      'side': 'buy' if order['S'] == 1 else 'sell',
                                      'amount': order['v'], 'price': order['p'], 'status': status,
                                      'time': time.strftime('%Y-%m-%d %H:%M:%S',
                                                            time.localtime(int(msg['t'] / 1000)))}
                        print(f'{exchange} ws order_info', order_info)
                        await insert_orders_db(order_info)
                    if msg.get('c', '') == 'spot@private.deals.v3.api' and msg.get('d', {}):
                        trade = msg['d']
                        symbol = msg['s']
                        if symbol.endswith('USDT'):
                            symbol = symbol.upper()[:-4] + '-USDT'
                        if symbol.upper().endswith('BTC'):
                            symbol = symbol.upper()[:-3] + '-BTC'
                        trade_info = {'exchange': exchange, 'orderId': trade['i'],
                                      'symbol': symbol,
                                      'side': 'buy' if order['S'] == 1 else 'sell', 'amount': trade['v'],
                                      'price': trade['p'],
                                      'fee': trade['n'], 'feecoin': trade['N'],
                                      'tradeId': trade['t'],
                                      'time': time.strftime('%Y-%m-%d %H:%M:%S',
                                                            time.localtime(int(msg['t'] / 1000)))}
                        print(f'{exchange} ws trade_info', trade_info)
                        await insert_trades_db(trade_info)
                    if msg.get('c', '') == 'spot@private.account.v3.api':
                        print(f'{exchange} ws_wallet {msg}')
                        if not global_variable.WALLET_EXCHANGE_CURRENCY.get(exchange, {}):
                            global_variable.WALLET_EXCHANGE_CURRENCY[exchange] = {}
                        global_variable.WALLET_EXCHANGE_CURRENCY[exchange].update({msg['d']['a']: float(msg['d']['f'])})
                        global_variable.WALLET_EXCHANGE_CURRENCY[exchange] = \
                            global_variable.WALLET_EXCHANGE_CURRENCY[exchange]
        except asyncio.TimeoutError:
            msg = f"order {exchange} {ORDER_RESTART_DELAY_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            # await recode_error_msg(msg, server="spot_hedge")
        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")
        finally:
            await asyncio.sleep(WS_EXCEPTION_SLEEP_TIME)


async def get_bitget_order(is_subscribe='subscribe', thread_name='bitgetThread'):
    exchange = 'bitget'

    # BITGET_WS_PRIVATE_URL = EXCHANGE_CONFIG[exchange]['private_ws']
    async def send_subscribe(bitget_symbol, webs):
        symbol_send_list = []
        for symbol in bitget_symbol:
            symbol_send = symbol.replace('-', '')
            symbol_send_list.append({
                "channel": "orders",
                "instType": "SPOT",
                "instId": symbol_send
            })
        if symbol_send_list:
            await webs.send(ujson.dumps({
                "op": is_subscribe,
                "args": symbol_send_list,
            }))
        asyncio.create_task(webs.send(
            ujson.dumps(
                {
                    "op": is_subscribe,
                    "args": [{
                        "channel": "account",
                        "instType": "SPOT",
                        "coin": "default"
                    }]
                }
            )))

    while True:
        try:
            print(f"{thread_name}-----start_ws")
            async with websockets.connect(BITGET_WS_PRIVATE_URL, close_timeout=0.01, ping_interval=15,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as webs:
                headers = bitget_ws.get_ws_header()
                asyncio.create_task(webs.send(f'{{"op": "login", "args": [{ujson.dumps(headers)}]}}'))
                async with timeout(2 * 30):
                    await webs.recv()
                bitget_symbol = []
                for currency, config in global_variable.SHARE_SYMBOL_HEDGE_CONFIG.items():
                    for ex, info in config['exchanges'].items():
                        if ex == 'bitget':
                            bitget_symbol.append(info['symbol'])
                await send_subscribe(bitget_symbol, webs)
                webs.ping = ping_enhance(webs, "ping")
                while True:
                    new_bitget_symbol = []
                    for currency, config in global_variable.SHARE_SYMBOL_HEDGE_CONFIG.items():
                        for ex, info in config['exchanges'].items():
                            if ex == 'bitget':
                                new_bitget_symbol.append(info['symbol'])
                    diff_symbol = set(bitget_symbol) ^ set(new_bitget_symbol)
                    if diff_symbol:
                        bitget_symbol = new_bitget_symbol
                        await send_subscribe(list(diff_symbol), webs)
                    async with timeout(ORDER_RESTART_DELAY_TIME):
                        message = await webs.recv()
                    if message == "pong":  # 判断推送来的消息类型：如果是服务器的心跳
                        print(datetime.datetime.now().strftime('%H:%M:%S.%f'), "get_bitget_order pong received.")
                        continue
                    msg = ujson.loads(message)
                    channel = msg.get('arg', {}).get('channel')
                    if channel == 'orders':
                        print(f'{exchange} ws_order', msg)
                        orders = msg.get('data', [])
                        for order in orders:
                            symbol = order['instId']
                            if symbol.upper().endswith('USDT'):
                                symbol = symbol.upper()[:-4] + '-USDT'
                            if symbol.upper().endswith('BTC'):
                                symbol = symbol.upper()[:-3] + '-BTC'
                            status = bitget_status.get(order['status'], order['status'])
                            notional_value = order.get('notional') if order.get('notional') else order['size']
                            order_info = {'exchange': exchange, 'orderId': order['orderId'],
                                          'symbol': symbol,
                                          'side': order['side'], 'fillsz': order['accBaseVolume'],
                                          'amount': float(notional_value) / float(order['price']) if order['side'] == 'buy' else
                                          order['size'],
                                          'price': order['price'], 'status': status,
                                          'time': time.strftime('%Y-%m-%d %H:%M:%S',
                                                                time.localtime(int(int(order['uTime']) / 1000)))}
                            print(f'{exchange} ws order_info', order_info)
                            await insert_orders_db(order_info)
                            if status == 'partially_filled':
                                trade_info = {'exchange': exchange, 'orderId': order['orderId'],
                                              'symbol': symbol, 'side': order['side'],
                                              'amount': order['baseVolume'], 'price': order['fillPrice'],
                                              'fee': abs(float(order['fillFee'])), 'feecoin': order['fillFeeCoin'],
                                              'tradeId': order.get('tradeId', order['orderId']),
                                              'time': time.strftime('%Y-%m-%d %H:%M:%S',
                                                                    time.localtime(int(int(order['uTime']) / 1000)))}
                                print(f'{exchange} ws trade_info', trade_info)
                                await insert_trades_db(trade_info)
                    elif channel == 'account':
                        print(f'{exchange} ws_wallet {msg}')
                        if not global_variable.WALLET_EXCHANGE_CURRENCY.get(exchange, {}):
                            global_variable.WALLET_EXCHANGE_CURRENCY[exchange] = {}
                        if msg.get('data', []):
                            wallets = msg['data']
                            for wallet in wallets:
                                global_variable.WALLET_EXCHANGE_CURRENCY[exchange].update(
                                    {wallet['coin'].upper(): float(wallet['available'])})
                                global_variable.WALLET_EXCHANGE_CURRENCY[exchange] = \
                                    global_variable.WALLET_EXCHANGE_CURRENCY[exchange]
                    else:
                        pass
        except asyncio.TimeoutError:
            msg = f"private ws {exchange} {ORDER_RESTART_DELAY_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            # await recode_error_msg(msg, server="spot_hedge")
        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")
        finally:
            await asyncio.sleep(WS_EXCEPTION_SLEEP_TIME)

async def get_kraken_wallet(is_subscribe='subscribe', thread_name='krakenThread'):
    exchange = 'kraken'
    KRAKEN_WS_PRIVATE_URL = EXCHANGE_CONFIG[exchange]['private_ws']

    while True:
        try:
            logger.info(f"{thread_name}-----start_ws")
            # 获取WebSocket Token
            token = await kraken_instance.get_ws_token()
            if not token:
                raise Exception("Failed to get WebSocket token")

            async with websockets.connect(
                    KRAKEN_WS_PRIVATE_URL,
                    close_timeout=0.01,
                    ping_interval=15,
                    max_queue=128,
                    compression=None,
                    ssl=ssl._create_unverified_context()
            ) as webs:

                # 订阅余额更新
                if is_subscribe == 'subscribe':
                    subscribe_message = {
                        "method": "subscribe",
                        "params": {
                            "channel": "balances",
                            "token": token
                        }
                    }
                    logger.info(f"{exchange} {subscribe_message}")
                    await webs.send(ujson.dumps(subscribe_message))

                # 保持连接的ping消息
                webs.ping = ping_enhance(webs, ujson.dumps({"method": "ping", "req_id": 101}))

                while True:
                    async with timeout(ORDER_RESTART_DELAY_TIME):
                        message = await webs.recv()
                    msg = ujson.loads(message)

                    #  {'channel': 'balances', 'type': 'snapshot', 'data': [], 'sequence': 1}
                    if "channel" in msg and msg["channel"] == "balances":
                        logger.info(f'{exchange} ws_wallet {msg}')
                        balances = msg["data"]
                        if exchange not in global_variable.WALLET_EXCHANGE_CURRENCY:
                            global_variable.WALLET_EXCHANGE_CURRENCY[exchange] = {}

                        # 更新余额信息
                        for balance_info in balances:
                            asset = balance_info["asset"]
                            balance = balance_info["balance"]
                            global_variable.WALLET_EXCHANGE_CURRENCY[exchange][asset] = balance

                        global_variable.WALLET_EXCHANGE_CURRENCY[exchange] = global_variable.WALLET_EXCHANGE_CURRENCY[exchange]
                        logger.info(f"{global_variable.WALLET_EXCHANGE_CURRENCY[exchange] = }")

                    # 处理心跳消息
                    else:
                        continue
        except asyncio.TimeoutError:
            msg = f"现货对冲 wallet {thread_name} {ORDER_RESTART_DELAY_TIME}时间未收到数据 触发TimeoutError 重启"
            await recode_error_msg(msg, server="spot_hedge_order")
        except Exception as e:
            msg = f"现货对冲 wallet {thread_name} {traceback.format_exc()}"
            await recode_error_msg(msg, server="spot_hedge_order")
        finally:
            await asyncio.sleep(WS_EXCEPTION_SLEEP_TIME)

async def put_ex_listen_key():
    while True:
        await asyncio.sleep(30 * 60)
        try:
            for ex, v in global_variable.WS_LISTEN_KEY.items():
                if ex in ['bn']:
                    await bn_ws.put_listen_key(v)
                elif ex in ['mxc']:
                    await mexc_ws.put_listen_key(v)
        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")


if __name__ == '__main__':
    is_subscribe = 'subscribe'
    # okex_thread = threading.Thread(target=asyncio.run, args=(get_okex_order(),), name="okThread")
    # bn_thread = threading.Thread(target=asyncio.run, args=(get_bn_order(),), name='bnThread')
    # gate_thread = threading.Thread(target=asyncio.run, args=(get_gate_order(),), name='gateThread')
    # hb_thread = threading.Thread(target=asyncio.run, args=(get_hb_order(),), name='bnThread')
    # mxc_thread = threading.Thread(target=asyncio.run, args=(get_mxc_order(),), name='mxcThread')
    bitget_thread = threading.Thread(target=asyncio.run, args=(get_bitget_order(),), name='bitgetThread')
    # exchange_t = [okex_thread, bn_thread, gate_thread, hb_thread, mxc_thread]
    exchange_t = [bitget_thread]
    for t in exchange_t:
        t.start()
    for t in exchange_t:
        t.join()
