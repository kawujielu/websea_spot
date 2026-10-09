import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
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
from scaffold.mysql import Hedge_MysqlSession
from many_configs import global_variable
from exchanges.spot_ws.mexc import MEXC_WS_USERDATE_URL, mexc_ws
from exchanges.spot_ws.huobi import HUOBI_WS_USERDATE_URL, huobi_ws

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


async def insert_orders_db(orders):
    insert_sql = "INSERT ignore INTO orders (exchange,orderId,symbol,price, side, amount,`time`,status) " \
                 "VALUES ('{}','{}','{}','{}','{}','{}','{}','{}') on duplicate key update status = values(status) " \
        .format(orders['exchange'], orders['orderId'], orders['symbol'], orders['price'], orders['side'],
                orders['amount'], orders['time'], orders['status'])
    await Hedge_MysqlSession.insert(insert_sql)


async def insert_trades_db(trades):
    insert_sql = "INSERT ignore INTO trades (exchange,tradeId,orderId,symbol,price, side, amount,`time`,fee,feecoin) " \
                 "VALUES ('{}','{}','{}','{}','{}','{}','{}','{}','{}','{}','{}')" \
        .format(trades['exchange'], trades['tradeId'], trades['orderId'], trades['symbol'], trades['price'],
                trades['side'],
                trades['amount'], trades['time'], trades['status'], trades['fee'], trades['feecoin'])
    await Hedge_MysqlSession.insert(insert_sql)


async def get_bn_wallet():
    exchange = 'bn'
    thread_name = threading.current_thread().name
    try:
        print(f"{thread_name}-----start_ws")
        listen_key = (await bn_ws.new_listen_key())['listenKey']
        async with websockets.connect(f'{BN_WS_USERDATE_URL}{listen_key}', close_timeout=0.01,
                                      ping_interval=15,
                                      max_queue=128, compression=None,
                                      ssl=ssl._create_unverified_context()) as webs:
            while True:
                message = await asyncio.wait_for(webs.recv(), 2 * 30)
                msg = ujson.loads(message)
                print('bn', msg)
                if msg['e'] == 'executionReport':
                    pass
                if msg['e'] == 'balanceUpdate':
                    pass
                if msg['e'] == 'outboundAccountPosition':
                    if not global_variable.WALLET_EXCHANGE_CURRENCY.get(exchange, {}):
                        global_variable.WALLET_EXCHANGE_CURRENCY[exchange] = {}
                    for i in msg['B']:
                        global_variable.WALLET_EXCHANGE_CURRENCY[exchange][i['a']] = float(i['f'])
    except asyncio.TimeoutError:
        msg = f"A {thread_name} 时间未收到数据 触发TimeoutError 重启"
        logger.error(msg)
    except Exception as e:
        logger.error(f"{e} {traceback.format_exc()}")


async def get_okex_wallet(is_subscribe='subscribe'):
    exchange = 'okex'
    thread_name = threading.current_thread().name
    try:
        print(f"{thread_name}-----start_ws")
        async with websockets.connect(OKEX_WS_PRIVATE_URL, close_timeout=0.01, ping_interval=15,
                                      max_queue=128, compression=None,
                                      ssl=ssl._create_unverified_context()) as webs:
            headers = okex_ws.get_ws_header()
            asyncio.create_task(webs.send(f'{{"op": "login", "args": [{ujson.dumps(headers)}]}}'))
            await asyncio.wait_for(webs.recv(), 2 * 30)
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
            while True:
                message = await asyncio.wait_for(webs.recv(), 1000)
                msg = ujson.loads(message)
                print('okex', msg)
                if not global_variable.WALLET_EXCHANGE_CURRENCY.get(exchange, {}):
                    global_variable.WALLET_EXCHANGE_CURRENCY[exchange] = {}
                    print(global_variable.WALLET_EXCHANGE_CURRENCY)
                if msg.get('data', []):
                    orders = msg['data'][0]['balData']
                    for order in orders:
                        global_variable.WALLET_EXCHANGE_CURRENCY[exchange][order['ccy'].upper()] = float(
                            order['cashBal'])

    except asyncio.TimeoutError:
        msg = f"A {thread_name} 时间未收到数据 触发TimeoutError 重启"
        logger.error(msg)
    except Exception as e:
        logger.error(f"{e} {traceback.format_exc()}")


async def get_gate_wallet(is_subscribe='subscribe'):
    exchange = 'gate'
    thread_name = threading.current_thread().name
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
                message = await asyncio.wait_for(webs.recv(), 2 * 10000000)
                msg = ujson.loads(message)
                print('gate', msg)
                if msg['channel'] == 'spot.balances' and msg['event'] == "update" and msg.get('result', []):
                    if not global_variable.WALLET_EXCHANGE_CURRENCY.get(exchange, {}):
                        global_variable.WALLET_EXCHANGE_CURRENCY[exchange] = {}
                        print(global_variable.WALLET_EXCHANGE_CURRENCY)
                    for i in msg.get('result', []):
                        global_variable.WALLET_EXCHANGE_CURRENCY[exchange][i['currency'].upper()] = float(
                            i['available'])
    except asyncio.TimeoutError:
        msg = f"A {thread_name} 时间未收到数据 触发TimeoutError 重启"
        logger.error(msg)
    except Exception as e:
        logger.error(f"{e} {traceback.format_exc()}")


async def get_hb_wallet(is_subscribe='subscribe'):
    exchange = 'hb'
    thread_name = threading.current_thread().name
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
            message = await asyncio.wait_for(webs.recv(), 2 * 30)
            print('hb auth', ujson.loads(message))
            data = {
                "action": 'sub',
                "ch": "accounts.update#2"}
            asyncio.create_task(webs.send(ujson.dumps(data)))

            while True:
                message = await asyncio.wait_for(webs.recv(), 2 * 10000000)
                msg = ujson.loads(message)
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
                        global_variable.WALLET_EXCHANGE_CURRENCY[exchange][currency] = float(available)

    except asyncio.TimeoutError:
        msg = f"A {thread_name} 时间未收到数据 触发TimeoutError 重启"
        logger.error(msg)
    except Exception as e:
        logger.error(f"{e} {traceback.format_exc()}")


if __name__ == '__main__':
    # 抹茶钱包没有ws
    is_subscribe = 'subscribe'
    okex_thread = threading.Thread(target=asyncio.run, args=(get_okex_wallet(),), name="okTread")
    bn_thread = threading.Thread(target=asyncio.run, args=(get_bn_wallet(),), name='bnTread')
    gate_thread = threading.Thread(target=asyncio.run, args=(get_gate_wallet(),), name='gateTread')
    hb_thread = threading.Thread(target=asyncio.run, args=(get_hb_wallet(),), name='hbTread')
    exchange_t = [okex_thread, bn_thread, gate_thread, hb_thread]
    for t in exchange_t:
        t.start()
    for t in exchange_t:
        t.join()
