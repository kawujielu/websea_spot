import random
import datetime
import asyncio
import traceback
import threading
import ssl
import time
import ujson
import websockets
from many_configs.global_variable import RESTART_DELAY_TIME, EXCHANGE_GEARS, INTERVAL, trans_okex_symbols, trans_bn_symbols, \
    trans_gateio_symbols, trans_hb_symbols, trans_mexc_symbols
from loguru import logger
from many_configs.exchange_config import EXCHANGE_CONFIG
from many_configs import global_variable
import gzip
from libs import heartbeat
from libs.recode_msg import recode_error_msg
from async_timeout import timeout
from scaffold.libs import ping_enhance


WS_FREQUENCY = 30


async def monitor():
    error_msg = []
    for name, value in global_variable.EXCHANGE_WS_MONITOR.items():
        if value['last_update'] - time.time() >= 60:
            error_msg.append(name)
    try:
        if error_msg:
            await heartbeat.i_live_not_well(error_msg, "对冲_ws订阅", WS_FREQUENCY, 4)
        else:
            await heartbeat.i_live_well("对冲_ws订阅", WS_FREQUENCY, 4)
    except Exception as error:
        logger.error(f'failed to connect redis {traceback.format_exc()}')


async def get_bn_depth(ws_instance_monitor, symbols, is_subscribe='subscribe', thread_name='bnThread'):
    exchange = 'bn'
    GEARS = EXCHANGE_GEARS[exchange]
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
                        "id": random.randint(1, 10000)}
                    )))
                ws_instance_monitor[thread_name]["ws_instance"] = webs
                while True:
                    async with timeout(RESTART_DELAY_TIME):
                        message = await webs.recv()
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
                                await monitor()
                                if symbol_lower.upper().endswith('USDT'):
                                    symbol = symbol_lower.upper()[:-4] + '-USDT'
                                if symbol_lower.upper().endswith('BTC'):
                                    symbol = symbol_lower.upper()[:-3] + '-BTC'
                                if symbol_lower.upper().endswith('ETH'):
                                    symbol = symbol_lower.upper()[:-3] + '-ETH'
                                gear_data = {"asks": data["asks"], "bids": data["bids"], "ts": int(time.time())}
                                global_variable.SHARE_MEMORY_WS_INSTANCE[exchange].update({symbol: gear_data})
                                global_variable.SHARE_MEMORY_WS_INSTANCE[exchange] = \
                                    global_variable.SHARE_MEMORY_WS_INSTANCE[exchange]
                            # print(exchange, global_variable.SHARE_MEMORY_WS_INSTANCE[exchange])
                        except BaseException as e:
                            logger.error(f"get_kraken_depth:{traceback.format_exc()} {data}")
                    else:
                        continue
                    global_variable.EXCHANGE_WS_MONITOR[exchange] = {'last_update': time.time()}
                    ws_instance_monitor[thread_name]["last_update"] = time.time()

        except asyncio.TimeoutError:
            msg = f"A {thread_name} {RESTART_DELAY_TIME} 时间未收到数据 触发TimeoutError 重启"
            await recode_error_msg(msg, server="spot_hedge")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")
            await asyncio.sleep(5)


async def get_okex_depth(ws_instance_monitor, symbols, is_subscribe='subscribe', thread_name='okexThread'):
    exchange = 'okex'
    GEARS = EXCHANGE_GEARS[exchange]
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
                    async with timeout(RESTART_DELAY_TIME):
                        message = await webs.recv()
                    if message == "pong":  # 判断推送来的消息类型：如果是服务器的心跳
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
                                await monitor()
                                gear_data = {'asks': asks, "bids": bids, "ts": int(time.time())}
                                global_variable.SHARE_MEMORY_WS_INSTANCE[exchange].update({symbol: gear_data})
                                global_variable.SHARE_MEMORY_WS_INSTANCE[exchange] = \
                                    global_variable.SHARE_MEMORY_WS_INSTANCE[exchange]
                            # print(exchange, global_variable.SHARE_MEMORY_WS_INSTANCE[exchange])
                        except BaseException as e:
                            logger.error(f"get_kraken_depth:{traceback.format_exc()} {data}")
                    elif "trades" in channel:
                        pass
                    else:
                        continue
                    global_variable.EXCHANGE_WS_MONITOR[exchange] = {'last_update': time.time()}
                    ws_instance_monitor[thread_name]["last_update"] = time.time()
        except asyncio.TimeoutError:
            msg = f"depth {thread_name} {RESTART_DELAY_TIME} 时间未收到数据 触发TimeoutError 重启"
            await recode_error_msg(msg, server="spot_hedge")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")
            await asyncio.sleep(5)


async def get_gate_depth(ws_instance_monitor, symbols, is_subscribe='subscribe', thread_name='gateThread'):
    exchange = 'gate'
    GEARS = EXCHANGE_GEARS[exchange]
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
                    async with timeout(RESTART_DELAY_TIME):
                        message = await webs.recv()
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
                            await monitor()
                            gear_data = {'asks': data["asks"], "bids": data["bids"], "ts": int(msg["time_ms"] / 1000)}
                            global_variable.SHARE_MEMORY_WS_INSTANCE[exchange].update({symbol: gear_data})
                            global_variable.SHARE_MEMORY_WS_INSTANCE[exchange] = \
                                global_variable.SHARE_MEMORY_WS_INSTANCE[exchange]
                        # print(exchange, global_variable.SHARE_MEMORY_WS_INSTANCE[exchange])
                    else:
                        continue
                    global_variable.EXCHANGE_WS_MONITOR[exchange] = {'last_update': time.time()}
                    ws_instance_monitor[thread_name]["last_update"] = time.time()
        except asyncio.TimeoutError:
            msg = f"depth {thread_name} {RESTART_DELAY_TIME} 时间未收到数据 触发TimeoutError 重启"
            await recode_error_msg(msg, server="spot_hedge")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")
            await asyncio.sleep(5)


async def get_hb_depth(ws_instance_monitor, symbols, is_subscribe='subscribe', thread_name='hbThread'):
    exchange = 'hb'
    GEARS = EXCHANGE_GEARS[exchange]
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
                        "id": str(random.randint(1, 10000)),
                    }
                    asyncio.create_task(webs.send(ujson.dumps(data)))
                    await asyncio.sleep(0.1)  # 单个连接每两次请求不能小于100ms。
                while True:
                    async with timeout(RESTART_DELAY_TIME):
                        message = await webs.recv()
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
                                await monitor()
                                if symbol_lower.upper().endswith('USDT'):
                                    symbol = symbol_lower.upper()[:-4] + '-USDT'
                                if symbol_lower.upper().endswith('BTC'):
                                    symbol = symbol_lower.upper()[:-3] + '-BTC'
                                data = msg_dict.get("tick", {})
                                gear_data = {"asks": data["asks"], "bids": data["bids"], "ts": int(time.time())}
                                global_variable.SHARE_MEMORY_WS_INSTANCE[exchange].update({symbol: gear_data})
                                global_variable.SHARE_MEMORY_WS_INSTANCE[exchange] = \
                                    global_variable.SHARE_MEMORY_WS_INSTANCE[exchange]
                                # print(exchange, global_variable.SHARE_MEMORY_WS_INSTANCE[exchange])
                        except BaseException as e:
                            logger.error(f"get_kraken_depth:{traceback.format_exc()} {data}")
                    else:
                        continue
                    global_variable.EXCHANGE_WS_MONITOR[exchange] = {'last_update': time.time()}
                    ws_instance_monitor[thread_name]["last_update"] = time.time()
        except asyncio.TimeoutError:
            msg = f"depth {thread_name} {RESTART_DELAY_TIME} 时间未收到数据 触发TimeoutError 重启"
            await recode_error_msg(msg, server="spot_hedge")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")
            await asyncio.sleep(5)


async def get_mxc_depth(ws_instance_monitor, symbols, is_subscribe='subscribe', thread_name='mxcThread'):
    exchange = 'mxc'
    GEARS = EXCHANGE_GEARS[exchange]
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
                webs.ping = ping_enhance(webs, ujson.dumps({"method": "PING"}))
                while True:
                    async with timeout(RESTART_DELAY_TIME):
                        message = await webs.recv()
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
                                await monitor()
                                asks, bids = [], []
                                for i in message.get("d", {}).get('asks', {}):
                                    asks.append([i['p'], i['v']])
                                for i in message.get("d", {}).get('bids', {}):
                                    bids.append([i['p'], i['v']])
                                ts = message.get('d', {}).get('t', int(time.time()))
                                gear_data = {"asks": asks, "bids": bids, "ts": ts}
                                global_variable.SHARE_MEMORY_WS_INSTANCE[exchange].update({symbol: gear_data})
                                global_variable.SHARE_MEMORY_WS_INSTANCE[exchange] = \
                                    global_variable.SHARE_MEMORY_WS_INSTANCE[exchange]
                                # print(exchange, global_variable.SHARE_MEMORY_WS_INSTANCE[exchange])
                        except BaseException as e:
                            logger.error(f"get_kraken_depth:{traceback.format_exc()}")
                    else:
                        continue
                    global_variable.EXCHANGE_WS_MONITOR[exchange] = {'last_update': time.time()}
                    ws_instance_monitor[thread_name]["last_update"] = time.time()
        except asyncio.TimeoutError:
            msg = f"depth {thread_name} {RESTART_DELAY_TIME} 时间未收到数据 触发TimeoutError 重启"
            await recode_error_msg(msg, server="spot_hedge")
            await asyncio.sleep(5)
        except Exception as e:
            msg = f"{e} {traceback.format_exc()}"
            await recode_error_msg(msg, server="spot_hedge")
            await asyncio.sleep(5)


async def get_bitget_depth(ws_instance_monitor, symbols, is_subscribe='subscribe', thread_name='bitgetThread'):
    exchange = 'bitget'
    GEARS = EXCHANGE_GEARS[exchange]
    while True:
        try:
            print(f"{thread_name}-----start_ws")
            async with websockets.connect(EXCHANGE_CONFIG['bitget']['spot_ws'], close_timeout=0.01, ping_interval=15,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as webs:
                global_variable.EXCHANGE_WS_INSTANCE[exchange] = webs
                ws_instance_monitor[thread_name]["ws_instance"] = webs
                symbol_send_list = []
                for symbol in symbols:
                    symbol_send = symbol.replace('-', '')
                    symbol_send_list.append({
                        "instType": "SPOT",
                        "channel": f"books{GEARS}",
                        "instId": symbol_send
                    })
                if symbol_send_list:
                    await webs.send(ujson.dumps({
                        "op": is_subscribe,
                        "args": symbol_send_list,
                    }))
                webs.ping = ping_enhance(webs, "ping")

                while True:
                    try:
                        async with timeout(RESTART_DELAY_TIME):
                            message = await webs.recv()
                    except TimeoutError:
                        await webs.send('ping')
                        continue
                    if message == "pong":  # 判断推送来的消息类型：如果是服务器的心跳
                        print(datetime.datetime.now().strftime('%H:%M:%S.%f'), "get_bitget_trades pong received.")
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
                                await monitor()
                                if symbol.upper().endswith('USDT'):
                                    symbol = symbol.upper()[:-4] + '-USDT'
                                if symbol.upper().endswith('BTC'):
                                    symbol = symbol.upper()[:-3] + '-BTC'
                                gear_data = {'asks': asks, "bids": bids, "ts": int(time.time())}
                                global_variable.SHARE_MEMORY_WS_INSTANCE[exchange].update({symbol: gear_data})
                                global_variable.SHARE_MEMORY_WS_INSTANCE[exchange] = \
                                    global_variable.SHARE_MEMORY_WS_INSTANCE[exchange]
                            # print(exchange, global_variable.SHARE_MEMORY_WS_INSTANCE[exchange])
                        except BaseException as e:
                            logger.error(f"get_kraken_depth:{traceback.format_exc()} {data}",)
                    else:
                        continue
                    global_variable.EXCHANGE_WS_MONITOR[exchange] = {'last_update': time.time()}
                    ws_instance_monitor[thread_name]["last_update"] = time.time()
        except asyncio.TimeoutError:
            msg = f"depth {thread_name} {RESTART_DELAY_TIME} 时间未收到数据 触发TimeoutError 重启"
            await recode_error_msg(msg, server="spot_hedge")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")
            await asyncio.sleep(5)


async def get_kraken_depth(ws_instance_monitor, symbols, is_subscribe='subscribe', thread_name='krakenThread'):
    exchange = 'kraken'
    GEARS = EXCHANGE_GEARS[exchange]
    while True:
        try:
            print(f"{thread_name}-----start_ws")
            async with websockets.connect(EXCHANGE_CONFIG[exchange]['spot_ws'], close_timeout=0.01, ping_interval=15,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as webs:
                global_variable.EXCHANGE_WS_INSTANCE[exchange] = webs
                ws_instance_monitor[thread_name]["ws_instance"] = webs
                subscribe = "subscribe" if is_subscribe == 'subscribe' else 'unsubscribe'
                new_symbols = [i.replace("-", "/") for i in symbols]
                s_data = {"method": subscribe, "params": {"channel": "ticker", "symbol": new_symbols}}
                if symbols:
                    await webs.send(ujson.dumps(s_data))
                webs.ping = ping_enhance(webs, ujson.dumps({"method": "ping", "req_id": 101}))

                while True:
                    try:
                        async with timeout(RESTART_DELAY_TIME):
                            message = await webs.recv()
                    except TimeoutError:
                        await webs.send('ping')
                        continue
                    if message == "pong":  # 判断推送来的消息类型：如果是服务器的心跳
                        logger.info("get_kraken_depth pong received.")
                        continue
                    msg_dict = ujson.loads(message)
                    logger.info(f"get_kraken_depth {msg_dict=}")
                    data = msg_dict.get("data", [])
                    channel = msg_dict.get("channel")
                    type = msg_dict.get("type")
                    if type not in ["snapshot", "update"] or channel not in ["ticker"]:
                        continue
                    if data:
                        data = data[0]
                        try:
                            ss = data["symbol"].replace("/", "-")
                            ask1 = float(data["ask"])
                            bid1 = float(data["bid"])
                            if ss and ask1 and bid1:
                                await monitor()
                                gear_data = {'asks': [ask1], "bids": [bid1], "ts": int(time.time())}
                                global_variable.SHARE_MEMORY_WS_INSTANCE[exchange].update({ss: gear_data})
                                global_variable.SHARE_MEMORY_WS_INSTANCE[exchange] = \
                                    global_variable.SHARE_MEMORY_WS_INSTANCE[exchange]
                                logger.info(f"{get_kraken_depth} {global_variable.SHARE_MEMORY_WS_INSTANCE[exchange]=}")
                        except BaseException as e:
                            logger.error(f"get_kraken_depth:{traceback.format_exc()} {data}")
                    else:
                        continue
                    global_variable.EXCHANGE_WS_MONITOR[exchange] = {'last_update': time.time()}
                    ws_instance_monitor[thread_name]["last_update"] = time.time()
        except asyncio.TimeoutError:
            msg = f"depth {thread_name} {RESTART_DELAY_TIME} 时间未收到数据 触发TimeoutError 重启"
            await recode_error_msg(msg, server="spot_hedge")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")
            await asyncio.sleep(5)


if __name__ == '__main__':
    subscribe_symbols = ['BTC-USDT']
    is_subscribe = 'subscribe'
    asyncio.run(get_kraken_depth({"krakenThread": {}}, subscribe_symbols, is_subscribe))