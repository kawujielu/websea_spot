import asyncio
import threading
import ssl
import websockets
import ujson
from exchanges.spot_ws.okex import OKEX_WS_PRIVATE_URL, okex_ws
from exchanges.spot_ws.gateio import GATE_WS_PRIVATE_URL, gate_ws
from exchanges.spot_ws.binance import BN_WS_USERDATE_URL, bn_ws
import time
from loguru import logger
import traceback
from many_configs import global_variable
from exchanges.spot_ws.mexc import MEXC_WS_USERDATE_URL, mexc_ws
from exchanges.spot_ws.huobi import HUOBI_WS_USERDATE_URL, huobi_ws
from many_configs.global_variable import WS_EXCEPTION_SLEEP_TIME, ORDER_RESTART_DELAY_TIME
from libs.recode_msg import recode_error_msg
from async_timeout import timeout
import datetime
from scaffold.libs import ping_enhance
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

bn_status = {
    'NEW': 'live',
    'PARTIALLY_FILLED': 'partially_filled',
    'FILLED': 'filled',
    'CANCELED': 'canceled'
}

gate_status = {
    'put': 'live',
    'update': 'filled',
    'finish': 'canceled'
}

huobi_status = {
    'submitted': 'live',
    'partial-filled': 'partially_filled',
    'filled': 'filled',
    'partial-canceled': 'partially_canceled',
    'canceled': 'canceled',
}

mexc_status = {
    1: 'live',
    2: 'filled',
    3: 'partially_filled',
    4: 'canceled',
    5: 'partially_canceled'
}


async def get_bn_wallet(thread_name='bnThread'):
    exchange = 'bn'
    while True:
        try:
            print(f"{thread_name}-----start_ws")
            listen_key = (await bn_ws.new_listen_key())['listenKey']
            logger.info(f'{exchange} ws_wallet {listen_key= }')
            async with websockets.connect(f'{BN_WS_USERDATE_URL}{listen_key}', close_timeout=0.01,
                                          ping_interval=15,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as webs:
                while True:
                    await bn_ws.put_listen_key(listen_key)
                    async with timeout(ORDER_RESTART_DELAY_TIME):
                        message = await webs.recv()
                    msg = ujson.loads(message)
                    logger.info(f'{exchange} ws_wallet {msg}')
                    if msg['e'] == 'executionReport':
                        pass
                    if msg['e'] == 'balanceUpdate':
                        pass
                    if msg['e'] == 'outboundAccountPosition':
                        if not global_variable.WALLET_EXCHANGE_CURRENCY.get(exchange, {}):
                            global_variable.WALLET_EXCHANGE_CURRENCY[exchange] = {}
                        for i in msg['B']:
                            global_variable.WALLET_EXCHANGE_CURRENCY[exchange].update({i['a']: float(i['f'])})
                            global_variable.WALLET_EXCHANGE_CURRENCY[exchange] = \
                                global_variable.WALLET_EXCHANGE_CURRENCY[exchange]
        except asyncio.TimeoutError:
            msg = f"现货对冲 wallet {thread_name} {ORDER_RESTART_DELAY_TIME}时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_error_msg(msg, server="spot_hedge_order")
        except Exception as e:
            msg = f"现货对冲 wallet  {thread_name}  {traceback.format_exc()}"
            logger.error(msg)
            await recode_error_msg(msg, server="spot_hedge_order")
        finally:
            await asyncio.sleep(WS_EXCEPTION_SLEEP_TIME)


async def get_okex_wallet(is_subscribe='subscribe', thread_name='okexThread'):
    exchange = 'okex'
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
                    logger.info(f'{exchange} ws_wallet {msg}')
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
            msg = f"wallet {thread_name} {ORDER_RESTART_DELAY_TIME}时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_error_msg(msg, server="spot_hedge_order")
        except Exception as e:
            msg = f"{e} {traceback.format_exc()}"
            logger.error(msg)
            await recode_error_msg(msg, server="spot_hedge_order")

        finally:
            await asyncio.sleep(WS_EXCEPTION_SLEEP_TIME)


async def get_gate_wallet(is_subscribe='subscribe', thread_name='gateThread'):
    exchange = 'gate'
    while True:
        try:
            print(f"{thread_name}-----start_ws")
            async with websockets.connect(GATE_WS_PRIVATE_URL, close_timeout=0.01, ping_interval=15,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as webs:
                request = {
                    "time": int(time.time()),
                    "channel": "spot.balances",
                    "event": is_subscribe,
                    "payload": ["!all"]
                }
                request['auth'] = gate_ws.gen_sign(request['channel'], request['event'], request['time'])
                asyncio.create_task(webs.send(ujson.dumps(request)))
                while True:
                    async with timeout(ORDER_RESTART_DELAY_TIME):
                        message = await webs.recv()
                    msg = ujson.loads(message)
                    logger.info(f'{exchange} ws_wallet {msg}')
                    if msg['channel'] == 'spot.balances' and msg['event'] == "update" and msg.get('result', []):
                        if not global_variable.WALLET_EXCHANGE_CURRENCY.get(exchange, {}):
                            global_variable.WALLET_EXCHANGE_CURRENCY[exchange] = {}
                        for i in msg.get('result', []):
                            global_variable.WALLET_EXCHANGE_CURRENCY[exchange].update(
                                {i['currency'].upper(): float(i['available'])})
                            global_variable.WALLET_EXCHANGE_CURRENCY[exchange] = \
                                global_variable.WALLET_EXCHANGE_CURRENCY[exchange]
        except asyncio.TimeoutError:
            msg = f"wallet {thread_name} {ORDER_RESTART_DELAY_TIME}时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_error_msg(msg, server="spot_hedge_order")
        except Exception as e:
            msg = f"{e} {traceback.format_exc()}"
            logger.error(msg)
            await recode_error_msg(msg, server="spot_hedge_order")

        finally:
            await asyncio.sleep(WS_EXCEPTION_SLEEP_TIME)


async def get_hb_wallet(is_subscribe='subscribe', thread_name='hbThread'):
    exchange = 'hb'
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
                logger.info(f'hb auth {message}')
                data = {
                    "action": 'sub',
                    "ch": "accounts.update#2"}
                asyncio.create_task(webs.send(ujson.dumps(data)))

                while True:
                    async with timeout(ORDER_RESTART_DELAY_TIME):
                        message = await webs.recv()
                    msg = ujson.loads(message)
                    logger.info(f'{exchange} ws_wallet {msg}')
                    if msg.get('action', '') == 'ping':
                        data = {
                            'action': 'pong',
                            'data': {'ts': time.time() * 1000}
                        }
                        await webs.send(ujson.dumps(data))
                        continue
                    else:
                        if 'push' == msg['action'] and msg.get('data', {}):
                            currency = msg['data']['currency'].upper()
                            available = msg['data']['available']
                            if not global_variable.WALLET_EXCHANGE_CURRENCY.get(exchange, {}):
                                global_variable.WALLET_EXCHANGE_CURRENCY[exchange] = {}
                            global_variable.WALLET_EXCHANGE_CURRENCY[exchange].update({currency: float(available)})
                            global_variable.WALLET_EXCHANGE_CURRENCY[exchange] = \
                                global_variable.WALLET_EXCHANGE_CURRENCY[exchange]
        except asyncio.TimeoutError:
            msg = f"wallet {thread_name} {ORDER_RESTART_DELAY_TIME}时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_error_msg(msg, server="spot_hedge_order")
        except Exception as e:
            msg = f"{e} {traceback.format_exc()}"
            logger.error(msg)
            await recode_error_msg(msg, server="spot_hedge_order")
        finally:
            await asyncio.sleep(WS_EXCEPTION_SLEEP_TIME)


async def get_mxc_wallet(is_subscribe='subscribe', thread_name='mxcThread'):
    exchange = 'mxc'
    # MEXC_WS_USERDATE_URL = EXCHANGE_CONFIG[exchange]['private_ws']
    while True:
        try:
            print(f"{thread_name}-----start_ws")
            listen_key = (await mexc_ws.new_listen_key())['listenKey']
            print(listen_key)
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
                    logger.info(f'{exchange} ws_wallet {msg}')
                    if msg.get('c', '') == 'spot@private.account.v3.api':
                        if not global_variable.WALLET_EXCHANGE_CURRENCY.get(exchange, {}):
                            global_variable.WALLET_EXCHANGE_CURRENCY[exchange] = {}
                        global_variable.WALLET_EXCHANGE_CURRENCY[exchange].update({msg['d']['a']: float(msg['d']['f'])})
                        global_variable.WALLET_EXCHANGE_CURRENCY[exchange] = \
                            global_variable.WALLET_EXCHANGE_CURRENCY[exchange]
        except asyncio.TimeoutError:
            msg = f"现货对冲 wallet {thread_name} {ORDER_RESTART_DELAY_TIME}时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_error_msg(msg, server="spot_hedge_order")
        except Exception as e:
            msg = f"现货对冲 wallet  {thread_name}  {traceback.format_exc()}"
            logger.error(msg)
            await recode_error_msg(msg, server="spot_hedge_order")
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
                    logger.info(f'{exchange} ws_wallet {msg}')

                    #  {'channel': 'balances', 'type': 'snapshot', 'data': [], 'sequence': 1}
                    if "channel" in msg and msg["channel"] == "balances":
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
            logger.error(msg)
            await recode_error_msg(msg, server="spot_hedge_order")
        except Exception as e:
            msg = f"现货对冲 wallet {thread_name} {traceback.format_exc()}"
            logger.error(msg)
            await recode_error_msg(msg, server="spot_hedge_order")
        finally:
            await asyncio.sleep(WS_EXCEPTION_SLEEP_TIME)


if __name__ == '__main__':
    asyncio.run(get_kraken_wallet())

    # 抹茶钱包没有ws
    # is_subscribe = 'subscribe'
    # okex_thread = threading.Thread(target=asyncio.run, args=(get_okex_wallet(),), name="okTread")
    # bn_thread = threading.Thread(target=asyncio.run, args=(get_bn_wallet(),), name='bnTread')
    # gate_thread = threading.Thread(target=asyncio.run, args=(get_gate_wallet(),), name='gateTread')
    # hb_thread = threading.Thread(target=asyncio.run, args=(get_hb_wallet(),), name='hbTread')
    # mxc_thread = threading.Thread(target=asyncio.run, args=(get_mxc_wallet(),), name='mxcThread')
    # # exchange_t = [okex_thread, bn_thread, gate_thread, hb_thread]
    # exchange_t = [mxc_thread]
    # for t in exchange_t:
    #     t.start()
    # for t in exchange_t:
    #     t.join()
