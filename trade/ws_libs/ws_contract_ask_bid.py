import json
import asyncio
import datetime
import threading
import traceback
from loguru import logger
import websockets
import ujson
from libs import libs_price_async, decorator
from many_configs import global_variable
import ssl
import numpy as np
import time
from libs.heartbeat import i_live_transit_station
from libs.utils import transfer_symbols
from config import WS_FREQUENCY
import gzip
from many_configs.exchange_config import EXCHANGE_CONFIG
from many_configs.base_config import ExchangeCode
from libs import recode_msg
from ws_libs import ws_ping, ping_enhance
# 使用几档计算加权价格
gears = 4
self_timeout = 5

@decorator.monitor_handler
async def get_bn_depth(trans_symbols, symbols):
    cur_ex = ExchangeCode.bn.value
    i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
    [i_live_transit_station("item_instance", f"{transfer_symbols(trans_symbols, symbol)}", frequency=WS_FREQUENCY, heart_type=2) for symbol in symbols]
    while True:
        try:
            busd_usdt_latest_update = 0
            busd_usdt_price = None
            extra_currency = 'busd'
            logger.info(f"{cur_ex}-----start_ws")
            symbol_send_list = [f"{symbol.replace('-', '').lower()}@depth5@100ms" for symbol in symbols]

            async with websockets.connect(EXCHANGE_CONFIG[cur_ex]['contract_ws'], close_timeout=0.01, ping_interval=15,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as websocket:
                asyncio.create_task(websocket.send(
                    ujson.dumps({
                        "method": "SUBSCRIBE",
                        "params": symbol_send_list,
                        "id": int(time.time() * 10 ** 6)}
                    )))
                while True:
                    message = await asyncio.wait_for(websocket.recv(), self_timeout)
                    message = ujson.loads(message)
                    # logger.info(message)
                    if "data" in message:
                        data = message["data"]
                        if time.time() * 1000 - data["E"] > 1000:
                            logger.warning("获取数据超时1s,重连")
                            break
                        a = data["a"][:gears]
                        b = data["b"][:gears]
                        ask1 = np.array([float(i[0]) for i in a]).mean()
                        bid1 = np.array([float(i[0]) for i in b]).mean()
                        symbol_lower = data['s'].lower()
                        symbol = transfer_symbols(trans_symbols, symbol_lower)
                        if not symbol:
                            continue
                        if symbol_lower[-4:] == "busd":
                            if time.time() - busd_usdt_latest_update > 10 or (not busd_usdt_price):
                                busd_usdt_price = float(await libs_price_async.get_weight_price(f'{extra_currency.upper()}-USDT'))
                                busd_usdt_latest_update = time.time()
                            ask1 *= busd_usdt_price
                            bid1 *= busd_usdt_price
                        # logger.info(f"get_bn_ask1_bid1 {symbol} {ask1=} {bid1=}")
                        global_variable.G_CONTRACT_PRICE_BY_CONTRACT_ASK_BID[cur_ex][symbol] = {"price_ask": ask1, "price_bid": bid1, "ts": data["E"] / 1000}  # 时间戳统一为秒级
                        i_live_transit_station("item_instance", f"{symbol}", frequency=WS_FREQUENCY, heart_type=2)
                        i_live_transit_station("main_instance", frequency=WS_FREQUENCY)

        except asyncio.TimeoutError:
            msg = f"{cur_ex} {self_timeout}s未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'cache_window|contract_ask_bid')
        except Exception as e:
            msg = f"{cur_ex} {e} {traceback.format_exc()}"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'cache_window|contract_ask_bid')
        finally:
            await asyncio.sleep(0.2)


@decorator.monitor_handler
async def get_hb_depth(trans_symbols, symbols):
    cur_ex = ExchangeCode.hb.value

    i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
    [i_live_transit_station("item_instance", f"{transfer_symbols(trans_symbols, symbol)}", frequency=WS_FREQUENCY, heart_type=2) for symbol in symbols]
    ERROR_SYMBOLS_LIST = []
    while True:
        try:
            wid = int(time.time() * 10 ** 6)
            logger.info(f"{cur_ex}-----start_ws")
            symbols = list(set(symbols) - set(ERROR_SYMBOLS_LIST))
            symbol_send_list = [f"market.{symbol}.depth.step6" for symbol in symbols]

            async with websockets.connect(EXCHANGE_CONFIG[cur_ex]['contract_ws'], close_timeout=0.01, ping_interval=1,
                                          max_queue=40, compression=None,
                                          ssl=ssl._create_unverified_context()) as websocket:
                for i in symbol_send_list:
                    asyncio.create_task(websocket.send(
                        ujson.dumps({
                            "sub": i,
                            "id": wid
                        }
                        )))
                while True:
                    message = await asyncio.wait_for(websocket.recv(), self_timeout)
                    result = gzip.decompress(message).decode('utf-8')
                    message = ujson.loads(result)
                    # logger.info(message)
                    if message.get('status', '') == "error":
                        logger.error(f"{cur_ex} 订阅错误 {message['err-msg']}")
                        asyncio.create_task(recode_msg.recode_error_msg(f"{cur_ex} 订阅错误 {message}", 'depth'))
                        ERROR_SYMBOLS_LIST.append(message['err-msg'].split('.')[1])
                        raise Exception(message)
                    if "tick" in message:
                        data = message["tick"]
                        if time.time() * 1000 - data["ts"] > 1000:
                            logger.warning("获取数据超时1s,重连")
                            break
                        a = data["asks"][:gears]
                        b = data["bids"][:gears]
                        ask1 = np.array([float(i[0]) for i in a]).mean()
                        bid1 = np.array([float(i[0]) for i in b]).mean()
                        symbol_lower = data['ch'].split('.')[1].replace('-', '').lower()
                        symbol = transfer_symbols(trans_symbols, symbol_lower)
                        if not symbol:
                            continue
                        global_variable.G_CONTRACT_PRICE_BY_CONTRACT_ASK_BID[cur_ex][symbol] = \
                            {"price_ask": ask1, "price_bid": bid1, "ts": data["ts"] / 1000}  # 时间戳统一为秒级
                        i_live_transit_station("item_instance", f"{symbol}", frequency=WS_FREQUENCY, heart_type=2)
                        i_live_transit_station("main_instance", frequency=WS_FREQUENCY)

        except asyncio.TimeoutError:
            msg = f"{cur_ex} {self_timeout}s未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'cache_window|contract_ask_bid')
        except Exception as e:
            msg = f"{cur_ex} {e} {traceback.format_exc()}"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'cache_window|contract_ask_bid')
        finally:
            await asyncio.sleep(0.2)


@decorator.monitor_handler
async def get_okex_depth(trans_symbols, symbols):
    cur_ex = ExchangeCode.okex.value
    i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
    [i_live_transit_station("item_instance", f"{transfer_symbols(trans_symbols, symbol)}", frequency=WS_FREQUENCY, heart_type=2) for symbol in symbols]
    ERROR_SYMBOLS_LIST = []
    while True:
        try:
            logger.info(f"{cur_ex}-----start_ws")
            symbol_send_list = []
            symbols = list(set(symbols) - set(ERROR_SYMBOLS_LIST))
            for symbol in symbols:
                symbol_send = symbol + '-SWAP'
                symbol_send_list.append({
                    "channel": "books5",
                    "instId": symbol_send
                })

            async with websockets.connect(EXCHANGE_CONFIG[cur_ex]['contract_ws'], close_timeout=0.01, ping_interval=1,
                                          max_queue=240, compression=None,
                                          ssl=ssl._create_unverified_context()) as websocket:
                asyncio.create_task(websocket.send(
                    ujson.dumps({
                        "op": "subscribe",
                        "args": symbol_send_list,
                        "id": int(time.time() * 10 ** 6)}
                    )))
                websocket.ping = ping_enhance(websocket, "ping")
                while True:
                    message = await asyncio.wait_for(websocket.recv(), self_timeout)
                    if message == "pong":  # 判断推送来的消息类型：如果是服务器的心跳
                        # logger.info("get_okex_trades pong received.")
                        i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
                        continue
                    message = ujson.loads(message)
                    if "error" == message.get('event', ''):
                        error_symbol = message['msg'].split(':')[2].split('-SWAP')[0]
                        ERROR_SYMBOLS_LIST.append(error_symbol)
                        logger.error(f"{cur_ex} 订阅错误 {message['msg']}")
                        asyncio.create_task(
                            recode_msg.recode_error_msg(f"{cur_ex} 订阅错误 {message['msg']}", 'depth'))

                        raise Exception(message)
                    if "data" in message:
                        data = message["data"]
                        if time.time() * 1000 - float(data[0]["ts"]) > 1000:
                            logger.warning("获取数据超时1s,重连")
                            break
                        a = data[0]["asks"][:gears]
                        b = data[0]["bids"][:gears]
                        ask1 = np.array([float(i[0]) for i in a]).mean()
                        bid1 = np.array([float(i[0]) for i in b]).mean()
                        symbol_lower = message['arg']['instId'].split('-SWAP')[0].replace('-', '').lower()
                        symbol = transfer_symbols(trans_symbols, symbol_lower)
                        if not symbol:
                            continue
                        global_variable.G_CONTRACT_PRICE_BY_CONTRACT_ASK_BID[cur_ex][symbol] = \
                            {"price_ask": ask1, "price_bid": bid1, "ts": float(data[0]["ts"]) / 1000}  # 时间戳统一为秒级
                        i_live_transit_station("item_instance", f"{symbol}", frequency=WS_FREQUENCY, heart_type=2)
                        i_live_transit_station("main_instance", frequency=WS_FREQUENCY)

        except asyncio.TimeoutError:
            msg = f"{cur_ex} 0.2s未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'cache_window|contract_ask_bid')
        except Exception as e:
            msg = f"{cur_ex} {e} {traceback.format_exc()}"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'cache_window|contract_ask_bid')
        finally:
            await asyncio.sleep(0.2)


@decorator.monitor_handler
async def get_gate_depth(trans_symbols, symbols):
    cur_ex = ExchangeCode.gate.value
    ERROR_SYMBOLS_LIST = []
    i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
    [i_live_transit_station("item_instance", f"{transfer_symbols(trans_symbols, symbol)}", frequency=WS_FREQUENCY, heart_type=2) for symbol in symbols]
    while True:
        try:
            logger.info(f"{cur_ex}-----start_ws")
            wid = int(time.time() * 10 ** 6)
            async with websockets.connect(EXCHANGE_CONFIG[cur_ex]['contract_ws'], close_timeout=0.01, ping_interval=15,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as websocket:
                symbols = list(set(symbols) - set(ERROR_SYMBOLS_LIST))
                for symbol in symbols:
                    symbol_send = {"time": wid, "channel": "futures.order_book",
                                   "event": "subscribe", "payload": [symbol.replace("-", "_").upper(), "5", "0"]}
                    await websocket.send(ujson.dumps(symbol_send))
                    await asyncio.sleep(0.02)  # v3 限制，v4没有

                while True:
                    message = await asyncio.wait_for(websocket.recv(), self_timeout)
                    msg = ujson.loads(message)
                    if "subscribe" in message:
                        if "error" in message:
                            logger.error(f"{cur_ex} 订阅错误 {msg['error']}")
                            await recode_msg.recode_error_msg(f"{cur_ex} 订阅错误 {msg['error']}", 'depth')
                            ERROR_SYMBOLS_LIST.append(msg["error"]["message"].split(" ")[-1].replace('_', '-'))
                            raise Exception(msg)
                        else:
                            continue
                    elif msg['channel'] == "futures.order_book" and msg['event'] == "all":
                        data = msg["result"]
                        if time.time() * 1000 - msg["time_ms"] > 1000:
                            logger.warning("获取数据超时1s,重连")
                            break
                        a = data["asks"][:gears]
                        b = data["bids"][:gears]
                        ask1 = np.array([float(i['p']) for i in a]).mean()
                        bid1 = np.array([float(i['p']) for i in b]).mean()
                        symbol_lower = data["contract"]
                        symbol = transfer_symbols(trans_symbols, symbol_lower)
                        if not symbol:
                            continue
                        global_variable.G_CONTRACT_PRICE_BY_CONTRACT_ASK_BID[cur_ex][symbol] = {"price_ask": ask1, "price_bid": bid1, "ts": msg["time_ms"] / 1000 }  # 时间戳统一为秒级
                        i_live_transit_station("item_instance", f"{symbol}", frequency=WS_FREQUENCY, heart_type=2)
                        i_live_transit_station("main_instance", frequency=WS_FREQUENCY)

        except asyncio.TimeoutError:
            msg = f"{cur_ex} {self_timeout}s未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'cache_window|contract_ask_bid')
        except Exception as e:
            msg = f"{cur_ex} {e} {traceback.format_exc()}"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'cache_window|contract_ask_bid')
        finally:
            await asyncio.sleep(0.2)


if __name__ == '__main__':
    global_variable.G_CONTRACT_PRICE_BY_CONTRACT_ASK_BID["gate"] = {}
    t = threading.Thread(target=asyncio.run,
                         args=(get_gate_depth({"BTC_USDT": "BTC-USDT"}, ["BTC-USDT", "AFEFE—ASFA"], monitor=f"合约对标价格_获取价格|okex合约买卖价"),),
                         name="test")
    t.start()
    t.join()
