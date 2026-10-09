import asyncio
import datetime
import gzip
import time
import traceback
import websockets
import ujson
import orjson
import ssl
from many_configs.base_config import ExchangeCode
from config import WS_FIXED_FREQUENCY, RESTART_FIXED_TIME
from libs import decorator, recode_msg
from libs.heartbeat import i_live_transit_station
from loguru import logger
from many_configs.exchange_config import EXCHANGE_CONFIG
from many_configs import global_variable, spot_currency_config, contract_currency_config
from ws_libs import ping_enhance


TRADE_POOL_NUM = 20


def data_distribute(currency, trades_dict, latest_update_share,
                    zone_spot_symbols, zone_contract_symbols, quantity):
    if currency not in latest_update_share:
        latest_update_share[currency] = {"sum": 0, "time": time.time()}
    latest_update_share[currency]["sum"] += float(quantity)
    # quantity 可能为0
    now_time = time.time()
    if now_time - latest_update_share[currency]["time"] > 0.2 and latest_update_share[currency]["sum"]:
        cur_sum = latest_update_share[currency]["sum"]
        for zone in zone_spot_symbols:
            abc_symbol = f"{currency}-{zone}"
            base_loop_time = spot_currency_config.special_base_sleep_time.get(abc_symbol, spot_currency_config.base_sleep_time)
            loop_time = spot_currency_config.SYMBOL_SLEEP_TIME.get(abc_symbol, base_loop_time)
            if abc_symbol in zone_spot_symbols[zone]:
                # with global_variable.SHARE_VOLUME_MAKER_SYMBOLS.lock(timeout=0.001, block=True, sleep_time=0.000001):
                #     trades_dict[abc_symbol].append(cur_sum)
                #     trades_dict[abc_symbol] = trades_dict[-TRADE_POOL_NUM:]
                if now_time - trades_dict[f"{abc_symbol}_update"] > loop_time * 10:
                    trades_dict[abc_symbol] = quantity
                else:
                    trades_dict[abc_symbol] += cur_sum

        for zone in zone_contract_symbols:
            abc_symbol = f"{currency}-{zone}"
            if abc_symbol in zone_contract_symbols[zone]:
                base_loop_time = contract_currency_config.special_base_sleep_time.get(abc_symbol, contract_currency_config.base_sleep_time)
                loop_time = contract_currency_config.SYMBOL_SLEEP_TIME.get(abc_symbol, base_loop_time)
                contract_c_symbol = f"c_{abc_symbol}"
                # with global_variable.SHARE_VOLUME_MAKER_SYMBOLS.lock(timeout=0.001, block=True, sleep_time=0.000001):
                #     trades_dict[contract_c_symbol].append(cur_sum)
                #     trades_dict[contract_c_symbol] = trades_dict[-TRADE_POOL_NUM:]
                if now_time - trades_dict[f"{contract_c_symbol}_update"] > loop_time * 10:
                    trades_dict[contract_c_symbol] = quantity
                else:
                    trades_dict[contract_c_symbol] += cur_sum

        latest_update_share[currency]["time"] = time.time()
        latest_update_share[currency]["sum"] = 0


@decorator.monitor_handler
async def get_bn_trades(trades_dict, trans_symbols, ws_symbols, zone_spot_symbols, zone_contract_symbols):
    i_live_transit_station("main_instance", frequency=WS_FIXED_FREQUENCY)
    cur_ex = ExchangeCode.bn.value

    latest_update_share = {
        # "currency": {"sum": 1, "time": 0}
    }
    while True:
        try:
            logger.info(f"{cur_ex}-----start_ws")
            symbol_send = []
            for symbol in ws_symbols:
                symbol_send.append("{}@trade".format(symbol.replace("-", '').lower()))
            # 订阅推送频率比较高的频道交易对，确保数据能持续性收到
            symbol_send.append("btcusdt@miniTicker")
            async with websockets.connect(EXCHANGE_CONFIG[cur_ex]['spot_ws'], close_timeout=0.01, ping_interval=15,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as webs:
                asyncio.create_task(webs.send(
                    ujson.dumps({
                        "method": "SUBSCRIBE",
                        "params": symbol_send,
                        "id": int(time.time() * 10 ** 6)}  # 防止多个订阅ws重复
                    )))
                while True:
                    message = await asyncio.wait_for(webs.recv(), RESTART_FIXED_TIME)
                    msg = orjson.loads(message)
                    symbol_lower = msg.get("stream", "")[0:-6]
                    data = msg.get("data")
                    channel = msg.get("stream", "")

                    if symbol_lower and data and "trade" in channel:
                        quantity = float(data["q"])
                        currency = f"{trans_symbols[cur_ex][symbol_lower]}"
                        data_distribute(currency, trades_dict, latest_update_share, zone_spot_symbols,
                                        zone_contract_symbols, quantity)

                    elif symbol_lower and data and "depth" in channel:
                        pass
                    else:
                        pass
                    i_live_transit_station("main_instance", frequency=WS_FIXED_FREQUENCY)

        except asyncio.TimeoutError:
            msg = f"{cur_ex} {RESTART_FIXED_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'volume')
        except Exception as e:
            logger.error(f"{cur_ex} {e} {traceback.format_exc()}")
            await asyncio.sleep(2)


@decorator.monitor_handler
async def get_gate_trades(trades_dict, trans_symbols, symbols, zone_spot_symbols, zone_contract_symbols):
    cur_ex = ExchangeCode.gate.value

    latest_update_share = {
        # "currency": {"sum": 1, "time": 0}
    }

    ERROR_SYMBOLS_LIST = []
    i_live_transit_station("main_instance", frequency=WS_FIXED_FREQUENCY)
    while True:
        try:
            logger.info(f"{cur_ex}-----start_ws")

            async with websockets.connect(EXCHANGE_CONFIG[cur_ex]['spot_ws'], close_timeout=0.01, ping_interval=15,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as webs:
                symbols_list = [s.replace("-", "_") for s in symbols]
                symbols_list = list(set(symbols_list) - set(ERROR_SYMBOLS_LIST))
                symbol_send = {
                    "time": int(time.time()),
                    "channel": "spot.trades",
                    "event": "subscribe",  # "unsubscribe" for unsubscription
                    "payload": symbols_list
                }
                # print(symbol_send)
                asyncio.create_task(webs.send(ujson.dumps(symbol_send)))
                await asyncio.sleep(0.02)  # v3 限制，v4没有
                symbol_depth_send = {
                    "time": int(time.time()),
                    "channel": "spot.order_book",
                    "event": "subscribe",  # "unsubscribe" for unsubscription
                    "payload": ["BTC_USDT", "5", "1000ms"]
                }
                asyncio.create_task(webs.send(ujson.dumps(symbol_depth_send)))
                while True:
                    message = await asyncio.wait_for(webs.recv(), RESTART_FIXED_TIME)
                    msg = orjson.loads(message)
                    if msg.get("error"):
                        if "unknown currency pair" in msg["error"].get("message"):
                            remove_pair = msg["error"]["message"].split(" ")[-1]
                            ERROR_SYMBOLS_LIST.append(remove_pair)
                            error_msg = f"{cur_ex} unknown currency pair {remove_pair}, 可能已下架，需要确认，ws trade 订阅剔除该交易对并重启"
                            logger.error(error_msg)
                            await recode_msg.recode_error_msg(error_msg, 'volume')
                            raise
                        else:
                            error_msg = f"{cur_ex} {msg}"
                            logger.error(error_msg)
                            await recode_msg.recode_error_msg(error_msg, 'volume')

                    if msg["event"] == "update" and msg["channel"] == "spot.trades":
                        data = msg["result"]
                        diff_ts = time.time() - int(msg["time"])
                        if diff_ts > 5:
                            print(f"gate-message-receive-timeout,msg:{data},超时{diff_ts}秒")
                        currency = f"{trans_symbols[cur_ex][data['currency_pair']]}"
                        quantity = float(data["amount"])
                        data_distribute(currency, trades_dict, latest_update_share, zone_spot_symbols,
                                        zone_contract_symbols, quantity)
                    elif msg["event"] == "update" and msg["channel"] == "spot.order_book":
                        pass
                    else:
                        pass
                    i_live_transit_station("main_instance", frequency=WS_FIXED_FREQUENCY)

        except asyncio.TimeoutError:
            msg = f"{cur_ex} {RESTART_FIXED_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'volume')
        except Exception as e:
            logger.error(f"{cur_ex} {e} {traceback.format_exc()}")
            await asyncio.sleep(2)


@decorator.monitor_handler
async def get_okex_trades(trades_dict, trans_symbols, ws_symbols, zone_spot_symbols, zone_contract_symbols):
    cur_ex = ExchangeCode.okex.value

    latest_update_share = {
        # "currency": {"sum": 1, "time": 0}
    }

    i_live_transit_station("main_instance", frequency=WS_FIXED_FREQUENCY)
    ERROR_SYMBOLS_LIST = []
    while True:
        try:
            logger.info(f"{cur_ex}-----start_ws")

            async with websockets.connect(EXCHANGE_CONFIG[cur_ex]['spot_ws'], close_timeout=0.01, ping_interval=15,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as webs:
                args = []
                symbols = list(set(symbols) - set(ERROR_SYMBOLS_LIST))
                for symbol in ws_symbols:
                    symbol_send = symbol
                    args.append({
                        "channel": "trades", "instId": symbol_send
                    })
                if args:
                    sub_data = {
                        "op": "subscribe",
                        "args": args,
                    }
                    asyncio.create_task(webs.send(ujson.dumps(sub_data)))
                    asyncio.create_task(webs.send(ujson.dumps({
                        "op": "subscribe",
                        "args": [{
                            "channel": "tickers",
                            "instId": "BTC-USDT"
                        }]
                    })))
                webs.ping = ping_enhance(webs, "ping")
                while True:
                    message = await asyncio.wait_for(webs.recv(), RESTART_FIXED_TIME)
                    if message == "pong":  # 判断推送来的消息类型：如果是服务器的心跳
                        logger.info("get_okex_trades pong received.")
                        continue
                    msg_dict = orjson.loads(message)
                    if "error" == msg_dict.get('event', ''):
                        error_symbol = msg_dict['msg'].split(':')[2].split(' ')[0]
                        ERROR_SYMBOLS_LIST.append(error_symbol)
                        logger.error(f"{cur_ex} 订阅错误 {msg_dict['msg']}")
                        await recode_msg.recode_error_msg(f"{cur_ex} 订阅错误 {msg_dict['msg']}", 'volume')
                        raise Exception(msg_dict)
                    data = msg_dict.get("data", [])
                    channel = msg_dict.get("arg", {}).get("channel", "")

                    if data and "trades" in channel:
                        currency = f"{trans_symbols[cur_ex][data[0]['instId']]}"
                        quantity = float(data["sz"])
                        data_distribute(currency, trades_dict, latest_update_share, zone_spot_symbols,
                                        zone_contract_symbols, quantity)

                    elif "tickers" in channel:
                        pass
                    else:
                        pass
                    i_live_transit_station("main_instance", frequency=WS_FIXED_FREQUENCY)

        except asyncio.TimeoutError:
            msg = f"{cur_ex} {RESTART_FIXED_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'volume')
        except Exception as e:
            logger.error(f"{cur_ex} {e} {traceback.format_exc()}")
            await asyncio.sleep(2)


@decorator.monitor_handler
async def get_hb_trades(trades_dict, trans_symbols, ws_symbols, zone_spot_symbols, zone_contract_symbols):
    cur_ex = ExchangeCode.hb.value

    latest_update_share = {
        # "currency": {"sum": 1, "time": 0}
    }

    i_live_transit_station("main_instance", frequency=WS_FIXED_FREQUENCY)
    ERROR_SYMBOLS_LIST = []
    SYMBOL_SYMBOL = {}
    while True:
        try:
            logger.info(f"{cur_ex}-----start_ws")
            async with websockets.connect(EXCHANGE_CONFIG[cur_ex]['spot_ws'], close_timeout=0.01, ping_interval=15,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as webs:
                symbols = list(set(symbols) - set(ERROR_SYMBOLS_LIST))
                for symbol in ws_symbols:
                    symbol_send = symbol.replace("-", '').lower()
                    SYMBOL_SYMBOL[symbol_send] = symbol
                    data = {
                        "sub": "market.{}.trade.detail".format(symbol_send),
                        "id": f"{int(time.time() * 10 ** 6)}"
                    }
                    asyncio.create_task(webs.send(ujson.dumps(data)))
                    await asyncio.sleep(0.1)  # 单个连接每两次请求不能小于100ms。
                while True:
                    message = await asyncio.wait_for(webs.recv(), RESTART_FIXED_TIME)
                    unzipped_data = gzip.decompress(message).decode()
                    msg_dict = ujson.loads(unzipped_data)
                    # logger.info(f"{msg_dict}")
                    channel = msg_dict.get("ch", "")
                    if 'ping' in msg_dict:
                        data = {
                            "pong": msg_dict['ping']
                        }
                        asyncio.create_task(webs.send(ujson.dumps(data)))
                        continue
                    elif msg_dict.get('status', '') == "error":
                        logger.error(f"{cur_ex} 订阅错误 {msg_dict['err-msg']}")
                        await recode_msg.recode_error_msg(f"{cur_ex} 订阅错误 {msg_dict}", 'volume')
                        ERROR_SYMBOLS_LIST.append(SYMBOL_SYMBOL[msg_dict['err-msg'].split(' ')[2]])
                        raise Exception(msg_dict)
                    elif msg_dict.get("tick") and "trade" in channel:
                        symbol_lower = msg_dict.get("ch", '').split(".")
                        symbol_lower = symbol_lower[1] if symbol_lower else ""

                        data = msg_dict.get("tick", {}).get("data", [])

                        if symbol_lower and data:
                            currency = f"{trans_symbols[cur_ex][symbol_lower]}"
                            quantity = float(data["amount"])
                            data_distribute(currency, trades_dict, latest_update_share, zone_spot_symbols,
                                            zone_contract_symbols, quantity)

                    elif "bbo" in channel:
                        pass
                    else:
                        pass
                    i_live_transit_station("main_instance", frequency=WS_FIXED_FREQUENCY)

        except asyncio.TimeoutError:
            msg = f"{cur_ex} {RESTART_FIXED_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'volume')
        except Exception as e:
            logger.error(f"{cur_ex} {e} {traceback.format_exc()}")
            await asyncio.sleep(2)


if __name__ == "__main__":
    while True:
        pass
