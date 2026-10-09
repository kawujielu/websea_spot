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
from exchanges.spot_ws.mexc import MEXC_WS_USERDATE_URL, mexc_ws
from exchanges.spot_ws.huobi import HUOBI_WS_USERDATE_URL, huobi_ws
# from many_configs.exchange_config import EXCHANGE_CONFIG

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
    1: 'live',
    2: 'filled',
    3: 'partially_filled',
    4: 'canceled',
    5: 'partially_canceled'
}

huobi_type = {
    'buy-limit': 'BUY',
    'sell-limit': 'SELL'
}


# todo ws订阅正常，数据还需要测试
#  问题： 1、ws推送的数据 插入数据库会不会存在重复
#        2、是否要插入逐笔成交表(trades表)
#        3、ws和restful一起是否会导致数据混乱
async def insert_orders_db(orders):
    select_sql = "SELECT * FROM orders_ws where orderId='{}'".format(orders['orderId'])
    res = await Hedge_MysqlSession.fetch_all(select_sql)
    if res:
        insert_sql = "UPDATE orders_ws set status ='{}'".format(orders['status'].upper())
    else:
        insert_sql = "INSERT ignore INTO orders_ws (exchange,orderId,symbol,price, side, amount,`time`,status) " \
                     "VALUES ('{}','{}','{}','{}','{}','{}','{}','{}')" \
            .format(orders['exchange'], orders['orderId'], orders['symbol'], orders['price'], orders['side'].upper(),
                    orders['amount'], orders['time'], orders['status'].upper())
    await Hedge_MysqlSession.insert(insert_sql)


async def insert_trades_db(trades):
    insert_sql = "INSERT ignore INTO trades_ws (exchange,tradeId,orderId,symbol,price, side, amount,`time`,fee,feecoin) " \
                 "VALUES ('{}','{}','{}','{}','{}','{}','{}','{}','{}','{}')" \
        .format(trades['exchange'], trades['tradeId'], trades['orderId'], trades['symbol'], trades['price'],
                trades['side'].upper(),
                trades['amount'], trades['time'], trades['fee'], trades['feecoin'])
    await Hedge_MysqlSession.insert(insert_sql)


async def get_bn_order():
    exchange = 'bn'
    # BN_WS_USERDATE_URL = EXCHANGE_CONFIG[exchange]['private_ws']
    thread_name = threading.current_thread().name
    try:
        print(f"{thread_name}-----start_ws")
        listen_key = (await bn_ws.new_listen_key())['listenKey']
        print(listen_key)
        async with websockets.connect(f'{BN_WS_USERDATE_URL}{listen_key}', close_timeout=0.01,
                                      ping_interval=15,
                                      max_queue=128, compression=None,
                                      ssl=ssl._create_unverified_context()) as webs:
            while True:
                await bn_ws.put_listen_key(listen_key)
                message = await asyncio.wait_for(webs.recv(), 2 * 10000000)
                msg = ujson.loads(message)
                print('bn', msg)
                if msg['e'] == 'executionReport':
                    order = msg
                    symbol = order['s'].upper()
                    if symbol.endswith('USDT'):
                        symbol = symbol[:-4] + '-USDT'
                    if symbol.endswith('BTC'):
                        symbol = symbol[:-3] + '-BTC'
                    status = bn_status.get(order['X'], order['X'])
                    order_info = {'exchange': exchange, 'orderId': order['i'], 'symbol': symbol,
                                  'side': order['S'], 'amount': order['q'], 'price': order['p'], 'status': status,
                                  'time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(order['E'])))}
                    await insert_orders_db(order_info)
                    if status in ['partially_filled', 'filled']:
                        trade_info = {'exchange': exchange, 'orderId': order['i'], 'symbol': order['s'],
                                      'side': order['S'], 'amount': order['l'], 'price': order['L'], 'fee': order['n'],
                                      'feecoin': order['N'], 'tradeId': order['t'],
                                      'time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(order['T'])))}
                        await insert_trades_db(trade_info)
                if msg['e'] == 'balanceUpdate':
                    pass
                if msg['e'] == 'outboundAccountPosition':
                    pass
    except asyncio.TimeoutError:
        msg = f"A {thread_name} 时间未收到数据 触发TimeoutError 重启"
        logger.error(msg)
    except Exception as e:
        logger.error(f"{e} {traceback.format_exc()}")


async def get_okex_order(is_subscribe='subscribe'):
    exchange = 'okex'
    # OKEX_WS_PRIVATE_URL = EXCHANGE_CONFIG[exchange]['private_ws']
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
                            "channel": "orders",
                            "instType": "SPOT",
                        }]
                    }
                )))
            while True:
                message = await asyncio.wait_for(webs.recv(), 2 * 10000000)
                msg = ujson.loads(message)
                print('okex', msg)
                if msg.get('data', []):
                    orders = msg['data']
                    for order in orders:
                        status = okex_status.get(order['state'], order['state'])
                        order_info = {'exchange': exchange, 'orderId': order['ordId'], 'symbol': order['instId'],
                                      'side': order['side'],
                                      'amount': order['sz'], 'price': order['px'], 'status': status,
                                      'time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(order['uTime'])))}
                        await insert_orders_db(order_info)
                        if status in ['partially_filled', 'filled']:
                            trade_info = {'exchange': exchange, 'orderId': order['ordId'], 'symbol': order['instId'],
                                          'side': order['side'], 'amount': order['fillSz'], 'price': order['fillPx'],
                                          'fee': order['fillFee'], 'feecoin': order['fillFeeCcy'],
                                          'tradeId': order['tradeId'],
                                          'time': time.strftime('%Y-%m-%d %H:%M:%S',
                                                                time.localtime(int(order['uTime'])))}
                            await insert_trades_db(trade_info)
    except asyncio.TimeoutError:
        msg = f"A {thread_name} 时间未收到数据 触发TimeoutError 重启"
        logger.error(msg)
    except Exception as e:
        logger.error(f"{e} {traceback.format_exc()}")


async def get_gate_order(is_subscribe='subscribe'):
    exchange = 'gate'
    # GATE_WS_PRIVATE_URL = EXCHANGE_CONFIG[exchange]['private_ws']
    thread_name = threading.current_thread().name
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
            while True:
                message = await asyncio.wait_for(webs.recv(), 2 * 10000000)
                msg = ujson.loads(message)
                print('gate', msg)
                if msg['channel'] == 'spot.orders' and msg['event'] == "update" and msg.get('result', []):
                    orders = msg['result']
                    for order in orders:
                        status = gate_status.get(order['event'], order['event'])
                        order_info = {'exchange': exchange, 'orderId': order['id'],
                                      'symbol': order['currency_pair'].replace('_', '-'),
                                      'side': order['side'],
                                      'amount': order['amount'], 'price': order['price'], 'status': status,
                                      'time': time.strftime('%Y-%m-%d %H:%M:%S',
                                                            time.localtime(int(order['update_time'])))}
                        print('order_info', order_info)
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
                        print('trade_info', trade_info)
                        await insert_trades_db(trade_info)
    except asyncio.TimeoutError:
        msg = f"A {thread_name} 时间未收到数据 触发TimeoutError 重启"
        logger.error(msg)
    except Exception as e:
        logger.error(f"{e} {traceback.format_exc()}")


async def get_hb_order(is_subscribe='subscribe'):
    exchange = 'hb'
    # HUOBI_WS_USERDATE_URL = EXCHANGE_CONFIG[exchange]['private_ws']
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
            sub = 'sub' if is_subscribe == 'subscribe' else 'unsub'
            asyncio.create_task(webs.send(
                ujson.dumps({
                    "action": sub,
                    "ch": "orders#*"
                })))
            while True:
                message = await asyncio.wait_for(webs.recv(), 2 * 10000000)
                msg = ujson.loads(message)
                print('hb', msg)
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
                        print('order_info', order_info)
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

                        print('trade_info', trade_info)
                        await insert_trades_db(trade_info)
    except asyncio.TimeoutError:
        msg = f"A {thread_name} 时间未收到数据 触发TimeoutError 重启"
        logger.error(msg)
    except Exception as e:
        logger.error(f"{e} {traceback.format_exc()}")


async def get_mxc_order(is_subscribe='subscribe'):
    exchange = 'mxc'
    # MEXC_WS_USERDATE_URL = EXCHANGE_CONFIG[exchange]['private_ws']
    thread_name = threading.current_thread().name
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
                            "spot@private.deals.v3.api",
                            "spot@private.orders.v3.api"
                        ]
                    }
                )))
            while True:
                await mexc_ws.put_listen_key(listen_key)
                message = await asyncio.wait_for(webs.recv(), 2 * 10000000)
                msg = ujson.loads(message)
                print('mxc', msg)
                if msg.get('c', '') == 'spot@private.orders.v3.api' and msg.get('d', {}):
                    order = msg['d']
                    symbol = msg['s']
                    if symbol.endswith('USDT'):
                        symbol = symbol.upper()[:-4] + '-USDT'
                    if symbol.upper().endswith('BTC'):
                        symbol = symbol.upper()[:-3] + '-BTC'
                    status = mexc_status.get(order['s'], order['s'])
                    order_info = {'exchange': exchange, 'orderId': order['i'],
                                  'symbol': symbol,
                                  'side': 'buy' if order['S'] == 1 else 'sell',
                                  'amount': order['v'], 'price': order['p'], 'status': status,
                                  'time': time.strftime('%Y-%m-%d %H:%M:%S',
                                                        time.localtime(int(msg['t'] / 1000)))}
                    print('order_info', order_info)
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
                                  'fee': None, 'feecoin': None,
                                  'tradeId': trade['t'],
                                  'time': time.strftime('%Y-%m-%d %H:%M:%S',
                                                        time.localtime(int(msg['t'] / 1000)))}
                    print('trade_info', trade_info)
                    await insert_trades_db(trade_info)
    except asyncio.TimeoutError:
        msg = f"A {thread_name} 时间未收到数据 触发TimeoutError 重启"
        logger.error(msg)
    except Exception as e:
        logger.error(f"{e} {traceback.format_exc()}")


if __name__ == '__main__':
    is_subscribe = 'subscribe'
    okex_thread = threading.Thread(target=asyncio.run, args=(get_okex_order(),), name="okTread")
    bn_thread = threading.Thread(target=asyncio.run, args=(get_bn_order(),), name='bnTread')
    gate_thread = threading.Thread(target=asyncio.run, args=(get_gate_order(),), name='gateTread')
    hb_thread = threading.Thread(target=asyncio.run, args=(get_hb_order(),), name='bnTread')
    mxc_thread = threading.Thread(target=asyncio.run, args=(get_mxc_order(),), name='mxcTread')
    exchange_t = [okex_thread, bn_thread, gate_thread, hb_thread, mxc_thread]
    for t in exchange_t:
        t.start()
    for t in exchange_t:
        t.join()
