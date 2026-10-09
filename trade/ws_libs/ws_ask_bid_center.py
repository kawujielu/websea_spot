import asyncio
import gzip
import ssl
import aiohttp
import traceback
from ujson import dumps
from orjson import loads
import websockets
from many_configs.base_config import ExchangeCode
from libs import decorator
from config import WS_FIXED_FREQUENCY, RESTART_FIXED_TIME, WS_NOT_FIXED_FREQUENCY, WS_EXCEPTION_SLEEP_TIME
from libs.m_aiohttp import G_RequestSession
from libs.utils import transfer_symbols
from many_configs import global_variable
from libs.heartbeat import i_live_transit_station
from loguru import logger
from many_configs.exchange_config import EXCHANGE_CONFIG
from time import time
from traceback import format_exc
from libs import recode_msg
from ws_libs import ws_ping, ping_enhance
from libs.proto_libs import PushDataV3ApiWrapper_pb2
from google.protobuf.json_format import MessageToJson


@decorator.monitor_handler
async def get_gate_depth(trans_symbols, symbols):
    cur_ex = ExchangeCode.gate.value

    i_live_transit_station("main_instance", frequency=WS_NOT_FIXED_FREQUENCY)
    [i_live_transit_station("item_instance", f"{transfer_symbols(trans_symbols, symbol)}", frequency=WS_NOT_FIXED_FREQUENCY, heart_type=2) for symbol in symbols]
    ERROR_SYMBOLS_LIST = []

    while True:
        try:
            logger.info(f"{cur_ex}-----start_ws")

            async with websockets.connect(EXCHANGE_CONFIG[cur_ex]['spot_ws'], close_timeout=0.01, ping_interval=15, max_queue=128, compression=None, ssl=ssl._create_unverified_context()) as webs:
                symbols = list(set(symbols) - set(ERROR_SYMBOLS_LIST))
                for symbol in symbols:
                    symbol_send = {
                        "time": int(time()),
                        "channel": "spot.order_book",
                        "event": "subscribe",  # "unsubscribe" for unsubscription
                        "payload": [symbol.replace("-", "_").upper(), "10", "100ms"]
                    }
                    asyncio.create_task(webs.send(dumps(symbol_send)))
                    await asyncio.sleep(0.02)  # v3 限制，v4没有

                # 不改变不会推送前n档数据，所以订阅10档，超时时间设置5min
                symbol_send_add = {"time": int(time()), "channel": "spot.trades", "event": "subscribe", "payload": ["BTC_USDT"]}
                asyncio.create_task(webs.send(dumps(symbol_send_add)))
                start_time = time()
                while True:
                    message = await asyncio.wait_for(webs.recv(), RESTART_FIXED_TIME)
                    msg = loads(message)
                    # logger.info(f"{cur_ex} {time()} {msg}")
                    if "error" in msg:
                        logger.error(f"{cur_ex} 订阅错误 {msg['error']}")
                        await recode_msg.recode_error_msg(f"{cur_ex} 订阅错误 {msg['error']}", 'send_telegram_important_msg_url')
                        ERROR_SYMBOLS_LIST.append(msg["error"]["message"].split(" ")[-1].replace('_', '-'))
                        raise Exception(msg)
                    if msg["event"] == "update" and msg["channel"] == "spot.order_book":
                        data = msg["result"]
                        global_variable.G_SYMBOL_GEAR20[cur_ex][data["s"]] = data
                        # await libs_price_async.rs_update_ask_bid(symbol, "gate", asks[symbol], bids[symbol])
                        if time() - (msg["time_ms"] / 1000) > 0.2:
                            # 订阅成功后会统一推送上一次数据，有可能已经过期很久，不判定为数据阻塞处理不过来，不进行重启
                            if time() - start_time > 10:
                                break
                        else:
                            #
                            i_live_transit_station("item_instance", f"{transfer_symbols(trans_symbols, data['s'])}", frequency=WS_NOT_FIXED_FREQUENCY, heart_type=2)
                            i_live_transit_station("main_instance", frequency=WS_NOT_FIXED_FREQUENCY)
                    elif msg["event"] == "update" and msg["channel"] == "spot.trades":
                        i_live_transit_station("main_instance", frequency=WS_NOT_FIXED_FREQUENCY)
                    else:
                        pass

        except asyncio.TimeoutError:
            msg = f"{cur_ex} {RESTART_FIXED_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'cache_window|spot_ask_bid')
        except Exception as e:
            msg = f"{cur_ex} {e} {format_exc()}"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'cache_window|spot_ask_bid')

        finally:
            await asyncio.sleep(WS_EXCEPTION_SLEEP_TIME)


@decorator.monitor_handler
async def get_bn_depth(trans_symbols, symbols):
    # 订阅错误交易对，不报警
    cur_ex = ExchangeCode.bn.value

    [i_live_transit_station("item_instance", f"{transfer_symbols(trans_symbols, symbol)}", frequency=WS_NOT_FIXED_FREQUENCY, heart_type=2) for symbol in symbols]
    i_live_transit_station("main_instance", frequency=WS_NOT_FIXED_FREQUENCY)
    while True:
        try:
            interval = 100
            gears = 20
            logger.info(f"{cur_ex}-----start_ws")
            symbol_list = [f"{symbol.replace('-', '').lower()}@depth{gears}@{interval}ms" for symbol in symbols]
            # 订阅推送频率比较高的频道交易对，确保数据能持续性收到
            symbol_list.append("btcusdt@miniTicker")
            async with websockets.connect(EXCHANGE_CONFIG[cur_ex]['spot_ws'], close_timeout=0.01, ping_interval=15,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as webs:
                asyncio.create_task(webs.send(
                    dumps({
                        "method": "SUBSCRIBE",
                        "params": symbol_list,
                        "id": int(time() * 10 ** 6)}  # 防止多个订阅ws重复
                    )))
                start_time = time()
                while True:
                    message = await asyncio.wait_for(webs.recv(), RESTART_FIXED_TIME)
                    msg = loads(message)
                    # logger.info(f"{cur_ex} {time()} {msg}")
                    symbol_lower = msg.get("stream", "").split("@")[0]
                    data = msg.get("data")
                    channel = msg.get("stream", "")
                    if symbol_lower and data and "depth" in channel:
                        try:
                            global_variable.G_SYMBOL_GEAR20[cur_ex][symbol_lower] = data
                            i_live_transit_station("main_instance", frequency=WS_NOT_FIXED_FREQUENCY)
                            i_live_transit_station("item_instance", f"{transfer_symbols(trans_symbols, symbol_lower)}",
                                                   frequency=WS_NOT_FIXED_FREQUENCY, heart_type=2)
                            # 因为收到bn数据没有时间戳，不能判断是否因为阻塞处理不过来超时，故定时10min进行重启
                            if time() - start_time > 10 * 60:
                                break
                        except BaseException as e:
                            logger.error(f"{cur_ex} {data =} {format_exc}")
                            await recode_msg.recode_error_msg(f"{cur_ex} 解析数据出错 %s" % e, 'send_telegram_important_msg_url')
                    elif symbol_lower and data and "trade" in channel:
                        i_live_transit_station("main_instance", frequency=WS_NOT_FIXED_FREQUENCY)
                    else:
                        pass

        except asyncio.TimeoutError:
            msg = f"{cur_ex} {RESTART_FIXED_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'cache_window|spot_ask_bid')
        except Exception as e:
            msg = f"{cur_ex} {e} {format_exc()}"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'cache_window|spot_ask_bid')
        finally:
            await asyncio.sleep(WS_EXCEPTION_SLEEP_TIME)


@decorator.monitor_handler
async def get_hb_depth(trans_symbols, symbols):
    # 每100ms 更新才推送前n档数据，额外订阅btcusdt k线数据，保证RESTART_FIXED_TIME时间范围内大概率有数据推送
    # 单个连接每两次请求不能小于100ms。
    cur_ex = ExchangeCode.hb.value
    [i_live_transit_station("item_instance", f"{transfer_symbols(trans_symbols, symbol)}", frequency=WS_NOT_FIXED_FREQUENCY, heart_type=2) for symbol in symbols]
    i_live_transit_station("main_instance", frequency=WS_NOT_FIXED_FREQUENCY)
    ERROR_SYMBOLS_LIST = []
    SYMBOL_SYMBOL = {}

    while True:
        try:
            logger.info(f"{cur_ex}-----start_ws")
            async with websockets.connect(EXCHANGE_CONFIG[cur_ex]['spot_ws'], close_timeout=0.01, ping_interval=15, max_queue=128, compression=None, ssl=ssl._create_unverified_context()) as webs:
                symbols = list(set(symbols) - set(ERROR_SYMBOLS_LIST))
                for symbol in symbols:
                    symbol_send = symbol.replace("-", '').lower()
                    SYMBOL_SYMBOL[symbol_send] = symbol
                    data = {
                        "sub": "market.{}.mbp.refresh.20".format(symbol_send),
                        "id": f"{int(time() * 10 ** 6)}"
                    }
                    asyncio.create_task(webs.send(dumps(data)))
                    await asyncio.sleep(0.1)  # 单个连接每两次请求不能小于100ms。
                asyncio.create_task(webs.send(dumps({"sub": "market.btcusdt.ticker"})))
                start_time = time()
                while True:
                    message = await asyncio.wait_for(webs.recv(), RESTART_FIXED_TIME)
                    unzipped_data = gzip.decompress(message).decode()
                    msg_dict = loads(unzipped_data)
                    # logger.info(f"{cur_ex} {time()} {msg_dict}")
                    channel = msg_dict.get("ch", "")
                    if 'ping' in msg_dict:
                        data = {
                            "pong": msg_dict['ping']
                        }
                        asyncio.create_task(webs.send(dumps(data)))
                        continue
                    elif msg_dict.get('status', '') == "error":
                        logger.error(f"{cur_ex} 订阅错误 {msg_dict['err-msg']}")
                        await recode_msg.recode_error_msg(f"{cur_ex} 订阅错误 {msg_dict}", 'send_telegram_important_msg_url')
                        ERROR_SYMBOLS_LIST.append(SYMBOL_SYMBOL[msg_dict['err-msg'].split(' ')[2]])
                        raise Exception(msg_dict)
                    elif msg_dict.get("tick") and "mbp" in channel:
                        symbol_lower = channel.split(".")
                        symbol_lower = symbol_lower[1] if symbol_lower else ""
                        try:
                            ts = float(msg_dict["ts"]) / 1000
                            global_variable.G_SYMBOL_GEAR20[cur_ex][symbol_lower] = msg_dict["tick"]
                            if time() - ts < 0.2:
                                i_live_transit_station("main_instance", frequency=WS_NOT_FIXED_FREQUENCY)
                                i_live_transit_station("item_instance", f"{transfer_symbols(trans_symbols, symbol_lower)}",
                                                       frequency=WS_NOT_FIXED_FREQUENCY, heart_type=2)
                            else:
                                # 订阅成功后会统一推送上一次数据，有可能已经过期很久，不判定为数据阻塞处理不过来，不进行重启
                                if time() - start_time > 10:
                                    break
                        except BaseException as e:
                            logger.error(f"{cur_ex} {msg_dict} {e} {format_exc()}")
                            await recode_msg.recode_error_msg(f"{cur_ex} 解析数据出错 %s" % e, 'depth_price')
                    elif "trade" in channel:
                        i_live_transit_station("main_instance", frequency=WS_NOT_FIXED_FREQUENCY)
                    else:
                        pass
        except asyncio.TimeoutError:
            msg = f"{cur_ex} {RESTART_FIXED_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'cache_window|spot_ask_bid')
        except Exception as e:
            msg = f"{cur_ex} {e} {format_exc()}"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'cache_window|spot_ask_bid')
        finally:
            await asyncio.sleep(WS_EXCEPTION_SLEEP_TIME)


@decorator.monitor_handler
async def get_okex_depth(trans_symbols, symbols):
    # books5首次推5档快照数据，以后定量推送，每100毫秒当5档快照数据有变化推送一次5档数据
    cur_ex = ExchangeCode.okex.value

    [i_live_transit_station("item_instance", f"{transfer_symbols(trans_symbols, symbol)}", frequency=WS_NOT_FIXED_FREQUENCY, heart_type=2) for symbol in symbols]
    i_live_transit_station("main_instance", frequency=WS_NOT_FIXED_FREQUENCY)
    ERROR_SYMBOLS_LIST = []
    while True:
        try:
            logger.info(f"{cur_ex}-----start_ws")
            async with websockets.connect(EXCHANGE_CONFIG[cur_ex]['spot_ws'], close_timeout=0.01, ping_interval=15, max_queue=128, compression=None, ssl=ssl._create_unverified_context()) as webs:
                symbols = list(set(symbols) - set(ERROR_SYMBOLS_LIST))
                args = [{"channel": "books5", "instId": symbol} for symbol in symbols]
                if args:
                    asyncio.create_task(webs.send(dumps({
                        "op": "subscribe",
                        "args": args,
                    })))
                    asyncio.create_task(webs.send(dumps({
                        "op": "subscribe",
                        "args": [{
                            "channel": "tickers",
                            "instId": "BTC-USDT"
                        }]
                    })))
                start_time = time()
                webs.ping = ping_enhance(webs, "ping")
                while True:
                    message = await asyncio.wait_for(webs.recv(), 35)
                    # if "error" in message:
                    #     asyncio.create_task(
                    #         recode_msg.recode_error_msg(f"{cur_ex} {message}", 'depth_price'))
                    #     continue
                    if message == "pong":  # 判断推送来的消息类型：如果是服务器的心跳
                        # logger.info("get_okex_trades pong received.")
                        i_live_transit_station("main_instance", frequency=WS_NOT_FIXED_FREQUENCY)
                        continue
                    msg_dict = loads(message)
                    # logger.info(f"{cur_ex} {time()} {msg_dict}")
                    if "error" == msg_dict.get('event', ''):
                        error_symbol = msg_dict['msg'].split(':')[2].split(' ')[0]
                        ERROR_SYMBOLS_LIST.append(error_symbol)
                        logger.error(f"{cur_ex} 订阅错误 {msg_dict['msg']}")
                        await recode_msg.recode_error_msg(f"{cur_ex} 订阅错误 {msg_dict['msg']}", 'send_telegram_important_msg_url')

                        raise Exception(msg_dict)
                    data = msg_dict.get("data", [])
                    channel = msg_dict.get("arg", {}).get("channel", "")
                    if data and "books5" in channel:
                        data = data[0]
                        try:
                            symbol = msg_dict.get("arg", {}).get("instId", "")
                            if not symbol:
                                continue
                            global_variable.G_SYMBOL_GEAR20[cur_ex][symbol] = data
                            ts = float(data["ts"]) / 1000
                            if time() - ts < 0.2:
                                i_live_transit_station("item_instance", f"{transfer_symbols(trans_symbols, symbol)}",
                                                       frequency=WS_NOT_FIXED_FREQUENCY, heart_type=2)
                                i_live_transit_station("main_instance", frequency=WS_NOT_FIXED_FREQUENCY)
                            else:
                                # 防止订阅成功后会统一推送上一次数据，有可能已经过期很久，不判定为数据阻塞处理不过来，不进行重启
                                if time() - start_time > 10:
                                    break
                        except BaseException as e:
                            logger.error(f"{cur_ex} {data =} {format_exc()}")
                            await recode_msg.recode_error_msg(f"{cur_ex} 解析数据出错 {e}", 'depth_price')
                    elif "trades" in channel:
                        i_live_transit_station("main_instance", frequency=WS_NOT_FIXED_FREQUENCY)
                    else:
                        pass
        except asyncio.TimeoutError:
            msg = f"{cur_ex} {RESTART_FIXED_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'cache_window|spot_ask_bid')
        except Exception as e:
            msg = f"{cur_ex}  {e} {format_exc()}"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'cache_window|spot_ask_bid')
        finally:
            await asyncio.sleep(WS_EXCEPTION_SLEEP_TIME)


@decorator.monitor_handler
async def get_mxc_depth(trans_symbols, symbols):
    # 订阅错误，返回数据：{'id': 0, 'code': 0, 'msg': 'no subscription success'}
    cur_ex = ExchangeCode.mxc.value

    [i_live_transit_station("item_instance", f"{transfer_symbols(trans_symbols, symbol)}", frequency=WS_FIXED_FREQUENCY, heart_type=2) for symbol in symbols]
    i_live_transit_station("main_instance", frequency=WS_FIXED_FREQUENCY)
    while True:
        try:
            logger.info(f"{cur_ex}-----start_ws")
            async with websockets.connect(EXCHANGE_CONFIG[cur_ex]['spot_ws'], close_timeout=0.01, ping_interval=15,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as webs:
                num = len(symbols) // 10
                for i in range(num + 1):
                    data = {"method": "SUBSCRIPTION", "params": []}
                    # params 长度不能太长，最好不要超过20个交易对，且一个WS链接一共只能订阅30个，分次发送，总计不能超过30
                    # 固定500ms推送
                    for symbol in symbols[10 * i: 10 * i + 10]:
                        symbol = symbol.replace("-", "")
                        data["params"].append(f"spot@public.limit.depth.v3.api.pb@{symbol}@5")
                    if data["params"]:
                        asyncio.create_task(webs.send(dumps(data)))
                start_time = time()
                webs.ping = ping_enhance(webs, dumps({"method": "PING"}))
                while True:
                    message = await asyncio.wait_for(webs.recv(), RESTART_FIXED_TIME)

                    if isinstance(message, bytes):
                        try:
                            result = PushDataV3ApiWrapper_pb2.PushDataV3ApiWrapper()
                            result.ParseFromString(message)
                            message = loads(MessageToJson(result))
                            print(message)
                            channel = message.get("channel", "")
                            if "spot@public.limit.depth.v3.api.pb" not in channel:
                                continue
                            symbol = message["symbol"]
                            ts = int(message["sendTime"]) / 1000
                            data = message["publicLimitDepths"]
                            global_variable.G_SYMBOL_GEAR20[cur_ex][symbol] = data

                            if time() - ts < 0.8:  # 500ms推送一次，所以时间为0.6
                                i_live_transit_station("item_instance", f"{transfer_symbols(trans_symbols, symbol)}",
                                                       frequency=WS_FIXED_FREQUENCY, heart_type=2)
                                i_live_transit_station("main_instance", frequency=WS_FIXED_FREQUENCY)
                            else:
                                # 防止订阅成功后会统一推送上一次数据，有可能已经过期很久，不判定为数据阻塞处理不过来，不进行重启
                                if time() - start_time > 10:
                                    break
                        except BaseException as e:
                            logger.error(f"{cur_ex} {message =} {format_exc()}")
                            await recode_msg.recode_error_msg("get_mxc_trades on_error %s" % e, 'depth_price')
                    else:
                        logger.info(f"{message}")
                        message = loads(message)
                        if "Not Subscribed" in message.get('msg', ''):
                            logger.error(f"{cur_ex} 订阅错误 {message['msg']}")
                            await recode_msg.recode_error_msg(f"{cur_ex} 订阅错误 {message}",
                                                              'send_telegram_important_msg_url')
                            raise Exception(message)
        except asyncio.TimeoutError:
            msg = f"{cur_ex} {RESTART_FIXED_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'cache_window|spot_ask_bid')
        except Exception as e:
            msg = f"{cur_ex} {e} {format_exc()}"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'cache_window|spot_ask_bid')
        finally:
            await asyncio.sleep(WS_EXCEPTION_SLEEP_TIME)


@decorator.monitor_handler
async def get_kucoin_depth(trans_symbols, symbols):
    # todo:   https://docs.kucoin.com/#level-2-market-data   Topic: /spotMarket/level2Depth5:{symbol},{symbol}...
    # 推送頻率: 最快100ms一次，不更新不推送
    # 每次返回前五檔的深度數據，此數據爲每100毫秒的快照數據，更新才推送，快照當前時刻市場買賣盤的5檔深度數據並推送
    # 随意发订阅交易对，交易所不会报错
    cur_ex = ExchangeCode.kucoin.value

    [i_live_transit_station("item_instance", f"{transfer_symbols(trans_symbols, symbol)}", frequency=WS_NOT_FIXED_FREQUENCY, heart_type=2) for symbol in symbols]
    i_live_transit_station("main_instance", frequency=WS_NOT_FIXED_FREQUENCY)
    async def get_token():
        base_url = f"{EXCHANGE_CONFIG[cur_ex]['spot_restful']}/api/v1/bullet-public"
        async with G_RequestSession.request.post(base_url, timeout=10) as r:
            res = await r.text()
            res = loads(res)
            ws_url = res["data"]["instanceServers"][0]["endpoint"]
            token = res["data"]["token"]
            return ws_url, token

    while True:
        try:
            ws_url, token = await get_token()
            logger.info(f"{cur_ex}-----start_ws")
            async with websockets.connect(f"{ws_url}?token={token}", close_timeout=0.01, ping_interval=15, max_queue=128, compression=None, ssl=ssl._create_unverified_context()) as webs:
                num = len(symbols) // 10
                for i in range(num + 1):
                    topic = ','.join(symbols[10 * i: 10 * i + 10])
                    data = {
                        "id": "sub_depth_price",
                        "type": "subscribe",
                        # "topic": f"/market/ticker:{topic}",
                        "topic": f"/spotMarket/level2Depth5:{topic}",
                        "privateChannel": False,
                        "response": True
                    }
                    asyncio.create_task(webs.send(dumps(data)))

                asyncio.create_task(webs.send(dumps({
                    "id": "sub_depth_price",
                    "type": "subscribe",
                    "topic": "/market/snapshot:BTC-USDT",
                    "privateChannel": False,
                    "response": True
                })))

                start_time = time()
                while True:
                    message = await asyncio.wait_for(webs.recv(), RESTART_FIXED_TIME)
                    msg_dict = loads(message)
                    # logger.info(f"{cur_ex} {time()} {msg_dict}")
                    channel = msg_dict.get("topic", "")
                    if msg_dict.get("data") and "/spotMarket/" in channel:
                        symbol = channel.split(":")[1]
                        if not symbol:
                            continue
                        try:
                            ts = float(msg_dict["data"]["timestamp"]) / 1000
                            global_variable.G_SYMBOL_GEAR20[cur_ex][symbol] = msg_dict["data"]
                            diff_ts = time() - ts
                            if diff_ts < 0.2:
                                i_live_transit_station("item_instance", f"{transfer_symbols(trans_symbols, symbol)}",
                                                       frequency=WS_NOT_FIXED_FREQUENCY, heart_type=2)
                                i_live_transit_station("main_instance", frequency=WS_NOT_FIXED_FREQUENCY)
                            else:
                                # 防止订阅成功后会统一推送上一次数据，有可能已经过期很久，不判定为数据阻塞处理不过来，不进行重启
                                if time() - start_time > 10:
                                    break

                        except BaseException as e:
                            logger.error(f"{cur_ex} {msg_dict} {format_exc()}")
                            await recode_msg.recode_error_msg("get_kucoin_trades on_error %s" % e, 'send_telegram_important_msg_url')
                    elif "/market/match" in channel:
                        i_live_transit_station("main_instance", frequency=WS_NOT_FIXED_FREQUENCY)
                    else:
                        pass
        except asyncio.TimeoutError:
            msg = f"{cur_ex} {RESTART_FIXED_TIME} s时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'cache_window|spot_ask_bid')
        except Exception as e:
            msg = f"{cur_ex} {e} {format_exc()}"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'cache_window|spot_ask_bid')
        finally:
            await asyncio.sleep(WS_EXCEPTION_SLEEP_TIME)


@decorator.monitor_handler
async def get_bitget_depth(trans_symbols, symbols):
    # 连接上ws后30s内订阅或订阅后30s内用户未发送ping指令，系统会自动断开连接
    # books5首次推5档快照数据，以后全量推送，有深度变化推送一次5档数据，即每次都推送5档数据(测试不活跃币种每次推送不超过1分钟)
    # 240次/小时, 单个连接最多可以订阅 1000 个Streams, 单个IP最多可以创建100个连接
    cur_ex = ExchangeCode.bitget.value

    [i_live_transit_station("item_instance", f"{transfer_symbols(trans_symbols, symbol)}", frequency=WS_NOT_FIXED_FREQUENCY, heart_type=2) for symbol in symbols]
    i_live_transit_station("main_instance", frequency=WS_NOT_FIXED_FREQUENCY)
    ERROR_SYMBOLS_LIST = []
    while True:
        try:
            logger.info(f"{cur_ex}-----start_ws")
            async with websockets.connect(EXCHANGE_CONFIG[cur_ex]['spot_ws'], close_timeout=0.01, ping_interval=28, max_queue=128, compression=None, ssl=ssl._create_unverified_context()) as webs:
                symbols = list(set(symbols) - set(ERROR_SYMBOLS_LIST))
                args = []
                for symbol in symbols:
                    symbol = symbol.replace("-", "")
                    params = {
                        "instType": "sp",
                        "channel": "books5",
                        "instId": f"{symbol}"
                    }
                    args.append(params)
                if args:
                    asyncio.create_task(webs.send(dumps({
                        "op": "subscribe",
                        "args": args,
                    })))
                start_time = time()
                webs.ping = ping_enhance(webs, "ping")
                # webs.keepalive_ping_task = asyncio.create_task(ws_ping(webs, "ping", 30))
                while True:
                    try:
                        message = await asyncio.wait_for(webs.recv(), RESTART_FIXED_TIME)
                    except TimeoutError:
                        await webs.send('ping')
                        continue
                    if message == "pong":  # 判断推送来的消息类型：如果是服务器的心跳
                        i_live_transit_station("main_instance", frequency=WS_NOT_FIXED_FREQUENCY)
                        continue
                    msg_dict = loads(message)
                    if "error" == msg_dict.get('event', ''):
                        error_symbol = msg_dict.get("arg", {}).get("instId", "")
                        error_symbol = transfer_symbols(trans_symbols, error_symbol)
                        ERROR_SYMBOLS_LIST.append(error_symbol)
                        logger.error(f"{cur_ex} 订阅错误 {msg_dict['msg']}")
                        await recode_msg.recode_error_msg(f"{cur_ex} 订阅错误 {msg_dict['msg']}", 'send_telegram_important_msg_url')

                        raise Exception(msg_dict)
                    data = msg_dict.get("data", [])
                    ts = msg_dict.get("ts", 0)
                    channel = msg_dict.get("arg", {}).get("channel", "")
                    if data and "books5" in channel:
                        data = data[0]
                        try:
                            symbol = msg_dict.get("arg", {}).get("instId", "")  # 'BIGTIMEUSDT'
                            if not symbol:
                                continue
                            cur_symbol = symbol
                            global_variable.G_SYMBOL_GEAR20[cur_ex][cur_symbol] = data
                            if time() - ts < 0.2:
                                i_live_transit_station("item_instance", f"{transfer_symbols(trans_symbols, symbol)}",
                                                       frequency=WS_NOT_FIXED_FREQUENCY, heart_type=2)
                                i_live_transit_station("main_instance", frequency=WS_NOT_FIXED_FREQUENCY)
                            else:
                                # 防止订阅成功后会统一推送上一次数据，有可能已经过期很久，不判定为数据阻塞处理不过来，不进行重启
                                if time() - start_time > 10:
                                    break
                        except BaseException as e:
                            logger.error(f"{cur_ex} {data =} {format_exc()}")
                            await recode_msg.recode_error_msg(f"{cur_ex} 解析数据出错 {e}", 'depth_price')
                    elif "trades" in channel:
                        i_live_transit_station("main_instance", frequency=WS_NOT_FIXED_FREQUENCY)
                    else:
                        pass
        except asyncio.TimeoutError:
            msg = f"{cur_ex} {RESTART_FIXED_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'cache_window|spot_ask_bid')
        except Exception as e:
            msg = f"{cur_ex}  {e} {format_exc()}"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'cache_window|spot_ask_bid')
        finally:
            await asyncio.sleep(WS_EXCEPTION_SLEEP_TIME)


@decorator.monitor_handler
async def get_kraken_depth(trans_symbols, symbols):
    cur_ex = ExchangeCode.kraken.value

    async def fetch_trade_volume(s_k):
        # url = "https://api.kraken.com/0/public/Depth?pair=BTC/USDT"
        url = f"{EXCHANGE_CONFIG[cur_ex]['spot_restful']}/0/public/Depth?pair={s_k}"
        try:
            async with aiohttp.ClientSession() as k_session:
                async with k_session.get(url, timeout=5) as response:
                    if response.status == 200:
                        res_data = await response.json()
                        ask_bid_res = res_data["result"].get(s_k, {})
                        if s_k == "EURQ/USD":
                            s_k = "EURQ/USDT"
                        if s_k == "USDQ/USD":
                            s_k = "USDQ/USDT"
                        if s_k == "EURR/USD":
                            s_k = "EURR/USDT"

                        global_variable.G_SYMBOL_GEAR20[cur_ex][s_k] = ask_bid_res
                        print(global_variable.G_SYMBOL_GEAR20[cur_ex][s_k])
                        i_live_transit_station("item_instance", f"{transfer_symbols(trans_symbols, s_k)}",
                                               frequency=WS_NOT_FIXED_FREQUENCY, heart_type=2)
                        return ask_bid_res
        except Exception as e:
            msg = f"get_kraken_depth {traceback.format_exc()}"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'cache_window|spot_ask_bid')


    [i_live_transit_station("item_instance", f"{transfer_symbols(trans_symbols, symbol)}", frequency=WS_NOT_FIXED_FREQUENCY, heart_type=2) for symbol in symbols]
    i_live_transit_station("main_instance", frequency=WS_NOT_FIXED_FREQUENCY)
    restful_support_symbols = ["USDQ/USDT", "USDR/USDT", "EURR/USDT", "EURQ/USDT"]
    while True:
        tasks = []
        for s in symbols:
            t_s = s.replace("-", "/")
            if t_s in restful_support_symbols:
                t_s = "EURQ/USD" if t_s == "EURQ/USDT" else t_s
                t_s = "USDQ/USD" if t_s == "USDQ/USDT" else t_s
                t_s = "EURR/USD" if t_s == "EURR/USDT" else t_s
                tasks.append(asyncio.create_task(fetch_trade_volume(t_s)))

        for t in tasks:
            await t
        i_live_transit_station("main_instance", frequency=WS_NOT_FIXED_FREQUENCY)
        await asyncio.sleep(5)



if __name__ == '__main__':
    ex = 'bitget'
    global_variable.G_SYMBOL_ASK_BID_PRICES[ex] = {}
    global_variable.G_SYMBOL_GEAR20[ex] = {}
    # asyncio.run(globals()[f'get_{ex}_depth']({"MainThread": {}}, {"busdusdt": "BUSD-USDT",'btcusdt': 'BTC-USDT'}, ['BTC-USDT']))
    asyncio.run(get_bitget_depth({"busdusdt": "BUSD-USDT", 'BIGTIMEUSDT': 'BIGTIME-USDT'}, ['BIGTIME-USDT'], monitor="价格服务_中心化|现货二十档存redis"))