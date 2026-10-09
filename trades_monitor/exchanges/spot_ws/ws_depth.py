import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
import datetime
import asyncio
import traceback
import threading
import ssl
import time
import ujson
import websockets
from many_configs.global_variable import RESTART_DELAY_TIME, GEARS, INTERVAL, trans_okex_symbols, trans_bn_symbols, \
    trans_gateio_symbols, trans_hb_symbols, trans_mexc_symbols
from loguru import logger
from many_configs.exchange_config import EXCHANGE_CONFIG
from many_configs import global_variable
import gzip


async def get_bn_depth(ws_instance_monitor, symbols, is_subscribe='subscribe'):
    exchange = 'bn'
    thread_name = threading.current_thread().name
    thread_id = threading.current_thread().ident
    while True:
        try:
            print(f"{thread_name}-----start_ws")
            symbol_send_list = []
            for symbol in symbols:
                symbol_send = trans_bn_symbols.get(symbol, symbol)
                symbol_send_list.append(
                    "{}@depth{}@{}ms".format(symbol_send.replace("-", '').lower(), GEARS, INTERVAL))
            async with websockets.connect(EXCHANGE_CONFIG['bn']['spot_ws'], close_timeout=0.01, ping_interval=15,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as webs:
                global_variable.EXCHANGE_WS_INSTANCE[exchange] = webs
                asyncio.create_task(webs.send(
                    ujson.dumps({
                        "method": is_subscribe.upper(),
                        "params": symbol_send_list,
                        "id": int(thread_id)}
                    )))
                ws_instance_monitor[thread_name]["ws_instance"] = webs
                while True:
                    message = await asyncio.wait_for(webs.recv(), RESTART_DELAY_TIME)
                    msg = ujson.loads(message)
                    symbol_lower = msg.get("stream", "").split("@")[0]
                    data = msg.get("data")
                    channel = msg.get("stream", "")
                    if symbol_lower and data and "depth" in channel:
                        if symbol_lower[-4:] == "busd":
                            symbol_lower = symbol_lower.replace('busd', 'usdt')
                        try:
                            ask1 = float(data["asks"][0][0])
                            bid1 = float(data["bids"][0][0])
                            if symbol_lower and ask1 and bid1:
                                if symbol_lower.upper().endswith('USDT'):
                                    symbol = symbol_lower.upper()[:-4] + '-USDT'
                                if symbol_lower.upper().endswith('BTC'):
                                    symbol = symbol_lower.upper()[:-3] + '-BTC'
                                gear_data = {"asks": data["asks"], "bids": data["bids"], "ts": int(time.time())}
                                global_variable.SHARE_MEMORY_WS_INSTANCE[exchange][symbol] = gear_data
                            # print(exchange, global_variable.SHARE_MEMORY_WS_INSTANCE[exchange])
                        except BaseException as e:
                            print(f"error:{e}", data)
                    else:
                        continue
                    ws_instance_monitor[thread_name]["last_update"] = time.time()

        except asyncio.TimeoutError:
            msg = f"A {thread_name} {RESTART_DELAY_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")
            await asyncio.sleep(5)


async def get_okex_depth(ws_instance_monitor, symbols, is_subscribe='subscribe'):
    exchange = 'okex'
    thread_name = threading.current_thread().name
    while True:
        try:
            print(f"{thread_name}-----start_ws")
            async with websockets.connect(EXCHANGE_CONFIG['okex']['spot_ws'], close_timeout=0.01, ping_interval=15,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as webs:
                global_variable.EXCHANGE_WS_INSTANCE[exchange] = webs
                ws_instance_monitor[thread_name]["ws_instance"] = webs
                symbol_send_list = []
                for symbol in symbols:
                    symbol_send = trans_okex_symbols.get(symbol, symbol)
                    symbol_send_list.append({
                        "channel": f"books{GEARS}",
                        "instId": symbol_send
                    })
                if symbol_send_list:
                    await webs.send(ujson.dumps({
                        "op": is_subscribe,
                        "args": symbol_send_list,
                    }))
                while True:
                    message = await asyncio.wait_for(webs.recv(), RESTART_DELAY_TIME)
                    if message == "pong":  # 判断推送来的消息类型：如果是服务器的心跳
                        print(datetime.datetime.now().strftime('%H:%M:%S.%f'), "get_okex_trades pong received.")
                        continue
                    msg_dict = ujson.loads(message)
                    data = msg_dict.get("data", [])
                    channel = msg_dict.get("arg", {}).get("channel", "")
                    symbol = msg_dict.get("arg", {}).get("instId", "")
                    if data and f"books{GEARS}" in channel:
                        data = data[0]
                        try:
                            ask1 = float(data["asks"][0][0])
                            bid1 = float(data["bids"][0][0])
                            asks, bids = [], []
                            for ask in data['asks']:
                                asks.append(ask[:2])
                            for bid in data['bids']:
                                bids.append(bid[:2])
                            if symbol and ask1 and bid1:
                                gear_data = {'asks': asks, "bids": bids, "ts": int(time.time())}
                                global_variable.SHARE_MEMORY_WS_INSTANCE[exchange][symbol] = gear_data
                            # print(exchange, global_variable.SHARE_MEMORY_WS_INSTANCE[exchange])
                        except BaseException as e:
                            print(f"error:{e}", data)
                    elif "trades" in channel:
                        pass
                    else:
                        continue
                    ws_instance_monitor[thread_name]["last_update"] = time.time()
        except asyncio.TimeoutError:
            msg = f"A {thread_name} {RESTART_DELAY_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")
            await asyncio.sleep(5)


async def get_gate_depth(ws_instance_monitor, symbols, is_subscribe='subscribe'):
    exchange = 'gate'
    thread_name = threading.current_thread().name
    ERROR_SYMBOLS_LIST = []

    while True:
        try:
            print(f"{thread_name}-----start_ws")
            async with websockets.connect(EXCHANGE_CONFIG['gate']['spot_ws'], close_timeout=0.01,
                                          ping_interval=15,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as webs:
                global_variable.EXCHANGE_WS_INSTANCE[exchange] = webs
                ws_instance_monitor[thread_name]["ws_instance"] = webs
                symbols = list(set(symbols) - set(ERROR_SYMBOLS_LIST))
                for s in symbols:
                    symbol = trans_gateio_symbols.get(s, s)
                    symbol_send = {
                        "time": int(time.time()),
                        "channel": "spot.order_book",
                        "event": is_subscribe,  # "unsubscribe" for unsubscription
                        "payload": [symbol.replace("-", "_").upper(), f"{GEARS}", f"{INTERVAL}ms"]
                    }
                    asyncio.create_task(webs.send(ujson.dumps(symbol_send)))
                    await asyncio.sleep(0.02)
                while True:
                    message = await asyncio.wait_for(webs.recv(), RESTART_DELAY_TIME)
                    msg = ujson.loads(message)
                    if "error" in msg:
                        logger.error(f"{thread_name} 订阅错误 {msg['error']}")
                        ERROR_SYMBOLS_LIST.append(msg["error"]["message"].split(" ")[-1].replace('_', '-'))
                        raise
                    if msg["event"] == "update" and msg["channel"] == "spot.order_book":
                        data = msg["result"]
                        symbol = data["s"].replace("_", "-")
                        if symbol == "GITCOIN-USDT":
                            symbol = "GTC-USDT"
                        if symbol == "DOG-USDT":
                            symbol = "DOGESWAP-USDT"

                        ask1 = float(data["asks"][0][0])
                        bid1 = float(data["bids"][0][0])
                        if ask1 and bid1 and symbol:
                            gear_data = {'asks': data["asks"], "bids": data["bids"], "ts": int(msg["time_ms"] / 1000)}
                            global_variable.SHARE_MEMORY_WS_INSTANCE[exchange][symbol] = gear_data
                        # print(exchange, global_variable.SHARE_MEMORY_WS_INSTANCE[exchange])
                    else:
                        continue
                    ws_instance_monitor[thread_name]["last_update"] = time.time()
        except asyncio.TimeoutError:
            msg = f"A {thread_name} {RESTART_DELAY_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")
            await asyncio.sleep(5)


async def get_hb_depth(ws_instance_monitor, symbols, is_subscribe='subscribe'):
    exchange = 'hb'
    thread_name = threading.current_thread().name
    thread_id = threading.current_thread().ident
    while True:
        try:
            print(f"{thread_name}-----start_ws")
            async with websockets.connect(EXCHANGE_CONFIG['hb']['spot_ws'], close_timeout=0.01, ping_interval=15,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as webs:
                global_variable.EXCHANGE_WS_INSTANCE[exchange] = webs
                ws_instance_monitor[thread_name]["ws_instance"] = webs
                for symbol in symbols:
                    symbol_send = trans_hb_symbols.get(symbol, symbol)
                    symbol_send = symbol_send.replace("-", '').lower()
                    param = 'sub' if is_subscribe == 'subscribe' else 'unsub'
                    data = {
                        f"{param}": "market.{}.mbp.refresh.{}".format(symbol_send, GEARS),
                        "id": str(thread_id),
                    }
                    asyncio.create_task(webs.send(ujson.dumps(data)))
                    await asyncio.sleep(0.1)  # 单个连接每两次请求不能小于100ms。
                while True:
                    message = await asyncio.wait_for(webs.recv(), RESTART_DELAY_TIME)
                    unzipped_data = gzip.decompress(message).decode()
                    msg_dict = ujson.loads(unzipped_data)
                    channel = msg_dict.get("ch", "")
                    if 'ping' in msg_dict:
                        data = {
                            "pong": msg_dict['ping']
                        }
                        await webs.send(ujson.dumps(data))
                        continue
                    elif msg_dict.get("tick") and "mbp" in channel:
                        symbol_lower = msg_dict.get("ch", '').split(".")
                        symbol_lower = symbol_lower[1] if symbol_lower else ""
                        try:
                            ask = float(msg_dict.get("tick", {})["asks"][0][0])
                            bid = float(msg_dict.get("tick", {})["bids"][0][0])
                            if symbol_lower and ask and bid:
                                if symbol_lower.upper().endswith('USDT'):
                                    symbol = symbol_lower.upper()[:-4] + '-USDT'
                                if symbol_lower.upper().endswith('BTC'):
                                    symbol = symbol_lower.upper()[:-3] + '-BTC'
                                data = msg_dict.get("tick", {})
                                gear_data = {"asks": data["asks"], "bids": data["bids"], "ts": int(time.time())}
                                global_variable.SHARE_MEMORY_WS_INSTANCE[exchange][symbol] = gear_data
                                # print(exchange, global_variable.SHARE_MEMORY_WS_INSTANCE[exchange])
                        except BaseException as e:
                            print(f"error:{e}", data)
                    else:
                        continue
                    ws_instance_monitor[thread_name]["last_update"] = time.time()
        except asyncio.TimeoutError:
            msg = f"A {thread_name} {RESTART_DELAY_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")
            await asyncio.sleep(5)


async def get_mxc_depth(ws_instance_monitor, symbols, is_subscribe='subscribe'):
    exchange = 'mxc'
    thread_name = threading.current_thread().name
    while True:
        try:
            print(f"{thread_name}-----start_ws")
            async with websockets.connect(EXCHANGE_CONFIG['mxc']['spot_ws'], close_timeout=0.01, ping_interval=15,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as webs:
                global_variable.EXCHANGE_WS_INSTANCE[exchange] = webs
                ws_instance_monitor[thread_name]["ws_instance"] = webs
                symbol_send_list = []
                for symbol in symbols:
                    symbol_send = trans_mexc_symbols.get(symbol, symbol)
                    symbol = symbol_send.replace("-", "")
                    symbol_send_list.append(
                        f"spot@public.limit.depth.v3.api@{symbol}@{GEARS}")
                if symbol_send_list:
                    sub = "SUBSCRIPTION" if is_subscribe == 'subscribe' else 'UNSUBSCRIPTION'
                    await webs.send(ujson.dumps({
                        "method": sub,
                        "params": symbol_send_list,
                    }))
                while True:
                    message = await asyncio.wait_for(webs.recv(), RESTART_DELAY_TIME)
                    message = ujson.loads(message)
                    if message.get("d"):
                        symbol = message.get("s", '')
                        if symbol.upper().endswith('USDT'):
                            symbol = symbol.upper()[:-4] + '-USDT'
                        if symbol.upper().endswith('BTC'):
                            symbol = symbol.upper()[:-3] + '-BTC'
                        try:
                            bid = float(message.get("d", {}).get("bids")[0]['v'])
                            ask = float(message.get("d", {}).get("asks")[0]['v'])
                            if symbol and ask and bid:
                                asks, bids = [], []
                                for i in message.get("d", {}).get('asks', {}):
                                    asks.append([i['p'], i['v']])
                                for i in message.get("d", {}).get('bids', {}):
                                    bids.append([i['p'], i['v']])
                                ts = message.get('d', {}).get('t', int(time.time()))
                                gear_data = {"asks": asks, "bids": bids, "ts": ts}
                                global_variable.SHARE_MEMORY_WS_INSTANCE[exchange][symbol] = gear_data
                                # print(exchange, global_variable.SHARE_MEMORY_WS_INSTANCE[exchange])
                        except BaseException as e:
                            print(f"on message error, {e}", message)
                    else:
                        continue
                    ws_instance_monitor[thread_name]["last_update"] = time.time()
        except asyncio.TimeoutError:
            msg = f"A {thread_name} {RESTART_DELAY_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")
            await asyncio.sleep(5)


if __name__ == '__main__':
    global_variable.EXCHANGE_WS_INSTANCE = {'hb': {}, 'okex': {}, 'gateio': {}, 'bn': {}, 'mec': {}}
    global_variable.SHARE_MEMORY_WS_INSTANCE = {'hb': {}, 'okex': {}, 'gateio': {}, 'bn': {}, 'mxc': {}}
    subscribe_symbols = ['BTC-USDT']
    un_subscribe_symbols = ['BTC-USDT']
    is_subscribe = 'subscribe'  # unsubscribe
    okex_thread = threading.Thread(
        target=asyncio.run,
        args=(get_okex_depth({"okTread": {}}, subscribe_symbols, is_subscribe),),
        name="okTread")
    bn_thread = threading.Thread(
        target=asyncio.run,
        args=(get_bn_depth({"bnTread": {}}, subscribe_symbols, is_subscribe),),
        name='bnTread')
    gate_thread = threading.Thread(
        target=asyncio.run,
        args=(get_gate_depth({"gateTread": {}}, subscribe_symbols, is_subscribe),),
        name='gateTread')
    hb_thread = threading.Thread(
        target=asyncio.run,
        args=(get_hb_depth({"hbTread": {}}, subscribe_symbols, is_subscribe),),
        name='hbTread')
    mxc_thread = threading.Thread(
        target=asyncio.run,
        args=(get_mxc_depth({"mexcTread": {}}, subscribe_symbols, is_subscribe),),
        name='mxcTread')
    exchange_t = [okex_thread, bn_thread, gate_thread, hb_thread, mxc_thread]
    for t in exchange_t:
        t.start()
    for t in exchange_t:
        t.join()
