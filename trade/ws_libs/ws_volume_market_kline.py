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
from config import WS_FIXED_FREQUENCY, RESTART_FIXED_TIME, WS_NOT_FIXED_FREQUENCY
from libs import decorator, recode_msg
from libs.heartbeat import i_live_transit_station
from loguru import logger
from many_configs.exchange_config import EXCHANGE_CONFIG
from many_configs import global_variable, spot_currency_config, contract_currency_config
from ws_libs import ws_ping, ping_enhance

'''
kline订阅

BN Kline【FRONT-USDT】
- 可以直接订阅一秒的k线，接口每秒固定推送 - 有K线是否结束参数 
- 成交量为每秒数据，数据核对没有问题
- 有K线是否结束参数

HB kline 【METIS-USDT】 
- 最小订阅一分钟， 接口每分钟固定推送，有成交时会立刻推送
- 成交量为1分钟累计数据，每分钟清零

OKEX kline 【FRONT-USDT】
- 最小订阅一分钟， 接口每分钟固定推送，有成交立刻推送
- 成交量为1分钟累计数据，每分钟清零
- 有K线是否结束参数

GATE Kline 【FRONT-USDT】
- 最小订阅10s，接口10s固定推送，有成交立刻推送
- 成交量为10s累计数据，每10s清零

总结： 几个交易所的订阅，每分钟都会固定推送一次，分钟内时间有成交才会推送。推送的量为累计数量，每分钟会清零
bn可以直接订阅1s，gate可以订阅10s,  其他交易所只能订阅1分钟， 为了统一，可以都订阅1分钟的数据
'''

TRADE_POOL_NUM = 20
KLINE_FIXED_FREQUENCY = 60


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
    i_live_transit_station("main_instance", frequency=KLINE_FIXED_FREQUENCY)
    cur_ex = ExchangeCode.bn.value

    last_vol = {}
    latest_update_share = {}
    while True:
        try:
            logger.info(f"{cur_ex}-----start_ws")

            symbol_send = []
            for symbol in ws_symbols:
                symbol_send.append("{}@kline_1m".format(symbol.replace("-", '').lower()))
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
                    data = msg.get("data")
                    channel = msg.get("stream", "")

                    if data and "kline" in channel:
                        quantity = float(data["k"]["v"])
                        symbol_lower = data['s'].lower()
                        currency = f"{trans_symbols[cur_ex][symbol_lower]}"
                        if quantity - last_vol.get(currency, 0) >= 0:
                            quantity_diff = quantity - last_vol.get(currency, 0)
                        else:
                            quantity_diff = quantity
                        data_distribute(currency, trades_dict, latest_update_share, zone_spot_symbols,
                                        zone_contract_symbols, quantity_diff)
                        last_vol[currency] = quantity
                    else:
                        pass
                    i_live_transit_station("main_instance", frequency=KLINE_FIXED_FREQUENCY)

        except asyncio.TimeoutError:
            msg = f"{cur_ex} {RESTART_FIXED_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'volume')
        except Exception as e:
            logger.error(f"{cur_ex} {e} {traceback.format_exc()}")
            await asyncio.sleep(2)


@decorator.monitor_handler
async def get_gate_trades(trades_dict, trans_symbols, ws_symbols, zone_spot_symbols, zone_contract_symbols):
    cur_ex = ExchangeCode.gate.value
    last_vol = {}
    latest_update_share = {}

    ERROR_SYMBOLS_LIST = []
    i_live_transit_station("main_instance", frequency=KLINE_FIXED_FREQUENCY)
    while True:
        try:
            logger.info(f"{cur_ex}-----start_ws")
            async with websockets.connect(EXCHANGE_CONFIG[cur_ex]['spot_ws'], close_timeout=0.01, ping_interval=15,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as webs:
                symbols_list = [s.replace("-", "_") for s in ws_symbols]
                symbols_list = list(set(symbols_list) - set(ERROR_SYMBOLS_LIST))
                symbols = list(set(symbols_list) - set(ERROR_SYMBOLS_LIST))
                for s in symbols:
                    symbol_send = {
                        "time": int(time.time()),
                        "channel": "spot.candlesticks",
                        "event": "subscribe",  # "unsubscribe" for unsubscription
                        "payload": ['1m', s.replace("-", "_").upper()]
                    }
                    asyncio.create_task(webs.send(ujson.dumps(symbol_send)))
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

                    if msg["event"] == "update" and msg["channel"] == "spot.candlesticks":
                        data = msg["result"]
                        diff_ts = time.time() - int(msg["time"])
                        if diff_ts > 5:
                            print(f"gate-message-receive-timeout,msg:{data},超时{diff_ts}秒")
                        currency_pair = data['n'].replace('1m_', '')
                        currency = f"{trans_symbols[cur_ex][currency_pair]}"
                        quantity = float(data["a"])
                        if quantity - last_vol.get(currency, 0) >= 0:
                            quantity_diff = quantity - last_vol.get(currency, 0)
                        else:
                            quantity_diff = quantity
                        data_distribute(currency, trades_dict, latest_update_share, zone_spot_symbols,
                                        zone_contract_symbols, quantity_diff)
                        last_vol[currency] = quantity
                    else:
                        pass
                    i_live_transit_station("main_instance", frequency=KLINE_FIXED_FREQUENCY)

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
    last_vol = {}
    latest_update_share = {}
    i_live_transit_station("main_instance", frequency=KLINE_FIXED_FREQUENCY)
    ERROR_SYMBOLS_LIST = []
    while True:
        try:
            logger.info(f"{cur_ex}-----start_ws")

            # 部分频道（包含kline）迁移到wss://ws.okx.com:8443/ws/v5/business
            async with websockets.connect('wss://ws.okx.com:8443/ws/v5/business', close_timeout=0.1, ping_interval=15,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as webs:
                args = []
                symbols = list(set(ws_symbols) - set(ERROR_SYMBOLS_LIST))
                for symbol in symbols:
                    symbol_send = symbol
                    args.append({
                        "channel": "candle1m", "instId": symbol_send
                    })
                if args:
                    sub_data = {
                        "op": "subscribe",
                        "args": args,
                    }
                    asyncio.create_task(webs.send(ujson.dumps(sub_data)))
                webs.ping = ping_enhance(webs, "ping")
                while True:
                    # 存在timeout超时，最快1s推送一次
                    message = await asyncio.wait_for(webs.recv(), 35)
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
                    instId = msg_dict.get("arg", {}).get("instId", "")

                    if data and "candle1m" in channel:
                        currency = f"{trans_symbols[cur_ex][instId]}"
                        quantity = float(data[0][5])
                        if quantity - last_vol.get(currency, 0) >= 0:
                            quantity_diff = quantity - last_vol.get(currency, 0)
                        else:
                            quantity_diff = quantity
                        data_distribute(currency, trades_dict, latest_update_share, zone_spot_symbols,
                                        zone_contract_symbols, quantity_diff)
                        last_vol[currency] = quantity
                    else:
                        pass
                    i_live_transit_station("main_instance", frequency=KLINE_FIXED_FREQUENCY)

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

    last_vol = {}
    latest_update_share = {}

    i_live_transit_station("main_instance", frequency=KLINE_FIXED_FREQUENCY)
    ERROR_SYMBOLS_LIST = []
    SYMBOL_SYMBOL = {}
    while True:
        try:
            logger.info(f"{cur_ex}-----start_ws")
            async with websockets.connect(EXCHANGE_CONFIG[cur_ex]['spot_ws'], close_timeout=0.01, ping_interval=15,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as webs:
                symbols = list(set(ws_symbols) - set(ERROR_SYMBOLS_LIST))
                for symbol in symbols:
                    symbol_send = symbol.replace("-", '').lower()
                    SYMBOL_SYMBOL[symbol_send] = symbol
                    data = {
                        "sub": "market.{}.kline.1min".format(symbol_send),
                        "id": "id1"
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
                    elif msg_dict.get("tick") and "kline" in channel:
                        symbol_lower = msg_dict.get("ch", '').split(".")
                        symbol_lower = symbol_lower[1] if symbol_lower else ""

                        data = msg_dict.get("tick", {})

                        if symbol_lower and data:
                            currency = f"{trans_symbols[cur_ex][symbol_lower]}"
                            quantity = float(data["amount"])
                            if quantity - last_vol.get(currency, 0) >= 0:
                                quantity_diff = quantity - last_vol.get(currency, 0)
                            else:
                                quantity_diff = quantity
                            data_distribute(currency, trades_dict, latest_update_share, zone_spot_symbols,
                                            zone_contract_symbols, quantity_diff)
                            last_vol[currency] = quantity
                    else:
                        pass
                    i_live_transit_station("main_instance", frequency=KLINE_FIXED_FREQUENCY)

        except asyncio.TimeoutError:
            msg = f"{cur_ex} {RESTART_FIXED_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'volume')
        except Exception as e:
            logger.error(f"{cur_ex} {e} {traceback.format_exc()}")
            await asyncio.sleep(2)


@decorator.monitor_handler
async def get_bitget_trades(trades_dict, trans_symbols, ws_symbols, zone_spot_symbols, zone_contract_symbols):
    cur_ex = ExchangeCode.bitget.value

    last_vol = {}
    latest_update_share = {}
    i_live_transit_station("main_instance", frequency=KLINE_FIXED_FREQUENCY)
    ERROR_SYMBOLS_LIST = []
    while True:
        try:
            logger.info(f"{cur_ex}-----start_ws")

            async with websockets.connect(EXCHANGE_CONFIG[cur_ex]['spot_ws'], close_timeout=0.01, ping_interval=28,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as webs:
                symbols = list(set(ws_symbols) - set(ERROR_SYMBOLS_LIST))
                args = []
                for symbol in symbols:
                    symbol = symbol.replace("-", "")
                    params = {
                        "instType": "sp",
                        "channel": "candle1m",
                        "instId": f"{symbol}"
                    }
                    args.append(params)
                if args:
                    asyncio.create_task(webs.send(ujson.dumps({
                        "op": "subscribe",
                        "args": args,
                    })))
                webs.ping = ping_enhance(webs, "ping")
                # webs.keepalive_ping_task = asyncio.create_task(ws_ping(webs, "ping", 30))
                while True:
                    try:
                        message = await asyncio.wait_for(webs.recv(), RESTART_FIXED_TIME)
                    except TimeoutError:
                        await webs.send('ping')
                        continue
                    if message == "pong":  # 判断推送来的消息类型：如果是服务器的心跳
                        i_live_transit_station("main_instance", frequency=KLINE_FIXED_FREQUENCY)
                        continue
                    msg_dict = ujson.loads(message)
                    if "error" == msg_dict.get('event', ''):
                        error_symbol = msg_dict.get("arg", {}).get("instId", "")
                        error_symbol = trans_symbols[cur_ex][error_symbol]
                        ERROR_SYMBOLS_LIST.append(error_symbol)
                        logger.error(f"{cur_ex} 订阅错误 {msg_dict['msg']}")
                        await recode_msg.recode_error_msg(f"{cur_ex} 订阅错误 {msg_dict['msg']}", 'volume')

                        raise Exception(msg_dict)
                    data = msg_dict.get("data", [])
                    channel = msg_dict.get("arg", {}).get("channel", "")
                    instId = msg_dict.get("arg", {}).get("instId", "")

                    if data and "candle1m" in channel:
                        currency = f"{trans_symbols[cur_ex][instId]}"
                        quantity = float(data[-1][5])
                        if quantity - last_vol.get(currency, 0) >= 0:
                            quantity_diff = quantity - last_vol.get(currency, 0)
                        else:
                            quantity_diff = quantity
                        data_distribute(currency, trades_dict, latest_update_share, zone_spot_symbols,
                                        zone_contract_symbols, quantity_diff)
                        last_vol[currency] = quantity
                    else:
                        pass
                    i_live_transit_station("main_instance", frequency=KLINE_FIXED_FREQUENCY)

        except asyncio.TimeoutError:
            msg = f"{cur_ex} {RESTART_FIXED_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'volume')
        except Exception as e:
            logger.error(f"{cur_ex} {e} {traceback.format_exc()}")
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(get_bitget_trades({}, {'bitget': {"busdusdt": "BUSD-USDT", 'BIGTIMEUSDT': 'BIGTIME-USDT'}}, ['BIGTIME-USDT'], {}, {},
                                  monitor="价格服务_中心化|现货二十档存redis"))
