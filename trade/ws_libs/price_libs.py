import asyncio
import datetime
import gzip
import ssl
import threading
import time
import traceback
import numpy
import requests
import ujson
import websocket
import websockets
from abcapi_plus import AbcApi
from config import enable_trace, WS_FREQUENCY, WS_EXCEPTION_SLEEP_TIME
from many_configs import global_variable
from libs import libs_config, libs_price_async, senddd, libs_account, decorator
from libs.heartbeat import i_live_transit_station
from libs.utils import transfer_symbols
from loguru import logger
import config
from config import RESTART_DELAY_TIME
from libs.m_aiohttp import G_RequestSession
from many_configs.exchange_config import EXCHANGE_CONFIG
from many_configs.base_config import ExchangeCode
from many_configs import spot_currency_config
from libs import recode_msg
from ws_libs import ws_ping, ping_enhance


@decorator.monitor_handler
async def get_gate_trades(trans_symbols, symbols):
    cur_ex = ExchangeCode.gate.value

    ERROR_SYMBOLS_LIST = []
    thread_name = threading.current_thread().name
    i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
    [i_live_transit_station("item_instance", f"{transfer_symbols(trans_symbols, symbol)}", frequency=WS_FREQUENCY, heart_type=1) for symbol in symbols]
    while True:
        try:
            logger.info(f"{cur_ex}-----start_ws")

            async with websockets.connect(EXCHANGE_CONFIG[cur_ex]['spot_ws'], close_timeout=0.01, ping_interval=15, max_queue=128, compression=None, ssl=ssl._create_unverified_context()) as webs:
                symbols_list = [s.replace("-", "_") for s in symbols]
                symbols_list = list(set(symbols_list) - set(ERROR_SYMBOLS_LIST))
                symbol_send = {
                    "time": int(time.time()),
                    "channel": "spot.trades",
                    "event": "subscribe",  # "unsubscribe" for unsubscription
                    "payload": symbols_list
                }
                logger.info(f"{symbol_send =}")
                asyncio.create_task(webs.send(ujson.dumps(symbol_send)))
                await asyncio.sleep(0.02)  # v3 限制，v4没有
                symbol_depth_send = {
                    "time": int(time.time()),
                    "channel": "spot.order_book",
                    "event": "subscribe",  # "unsubscribe" for unsubscription
                    "payload": ["BTC_USDT", "5", "1000ms"]
                }
                asyncio.create_task(webs.send(ujson.dumps(symbol_depth_send)))
                start_time = time.time()
                while True:
                    message = await asyncio.wait_for(webs.recv(), RESTART_DELAY_TIME)
                    msg = ujson.loads(message)
                    if "error" in msg:
                        logger.error(f"{thread_name} 订阅错误 {msg['error']}")
                        await recode_msg.recode_error_msg(f"{thread_name} 订阅错误 {msg['error']}", 'price')
                        ERROR_SYMBOLS_LIST.append(msg["error"]["message"].split(" ")[-1])
                        raise

                    if msg["event"] == "update" and msg["channel"] == "spot.trades":
                        data = msg["result"]
                        diff_ts = time.time() - int(msg["time"])
                        if diff_ts > 2:
                            # gate的消息如果重新订阅会把以前的数据推送过来
                            logger.info(f"gate-message-receive-timeout,msg:{data},超时{diff_ts}秒")
                            if time.time() - start_time > 10:
                                break
                            else:
                                continue
                        symbol = transfer_symbols(trans_symbols, data["currency_pair"])
                        if not symbol:
                            continue
                        price = float(data["price"])
                        logger.info(f"{symbol} {price}")
                        global_variable.G_SYMBOL_TRADE_PRICES['gate'][symbol] = price
                        i_live_transit_station("item_instance", f"{symbol}", frequency=WS_FREQUENCY, heart_type=1)
                        i_live_transit_station("main_instance", frequency=WS_FREQUENCY)

                    elif msg["event"] == "update" and msg["channel"] == "spot.order_book":
                        i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
                    else:
                        continue

        except asyncio.TimeoutError:
            msg = f"{cur_ex} {RESTART_DELAY_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'price')
        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")
        finally:
            await asyncio.sleep(WS_EXCEPTION_SLEEP_TIME)


def get_bitfinex_trades(trans_symbols, symbols):
    cur_ex = ExchangeCode.bitfinex.value

    while True:
        try:
            logger.info(f"{cur_ex}-----start_ws")

            channel_map = {}
            thread_name = threading.current_thread().name

            def start_ws():
                global channel_map
                channel_map = {}
                # websocket.enableTrace(True)
                ws = websocket.WebSocketApp(
                    EXCHANGE_CONFIG[cur_ex]['spot_ws'],
                    on_open=on_open,
                    on_message=on_message,
                    on_error=on_error,
                    on_close=on_close
                )
                if libs_config.MAINLAND_SERVER:
                    ws.run_forever(http_proxy_host="127.0.0.1", http_proxy_port=config.PROXY_PORT, proxy_type=config.PROXY_TYPE)
                else:
                    ws.run_forever()

            def on_message(ws, message):
                msg = ujson.loads(message)
                if "chanId" in msg and "pair" in msg:
                    channel_map[msg["chanId"]] = msg["pair"]

                if "te" in msg:
                    channel_id = msg[0]
                    price = msg[2][3]
                    symbol = transfer_symbols(trans_symbols, channel_map[channel_id])
                    if not symbol:
                        return
                    print(datetime.datetime.now().strftime('%H:%M:%S.%f'), "get_bitfinex_trades", symbol, price)
                    global_variable.G_SYMBOL_TRADE_PRICES['bitfinex'][symbol] = price
                    i_live_transit_station("ZEUS_MONITOR_WS_PRICE", "bitfinex", WS_FREQUENCY)

            def on_error(ws, error):
                print(datetime.datetime.now().strftime('%H:%M:%S.%f'), f"{thread_name} error {error}")
                senddd.send_telegram(f"{thread_name} on_error {error}", 'price', libs_config.DEBUG)

                if ws.keep_running:
                    ws.close()
                time.sleep(5)

            def on_close(ws, close_status_code, close_msg):
                print(datetime.datetime.now().strftime('%H:%M:%S.%f'), f"{thread_name} {close_status_code} {close_msg}")
                senddd.send_telegram(f"{thread_name} {close_msg}", 'price', libs_config.DEBUG)

                if ws.keep_running:
                    ws.close()
                time.sleep(5)

            def on_open(ws):
                for symbol in symbols:
                    symbol_send = symbol.replace("-", '')
                    send = ujson.dumps({"event": "subscribe", "channel": "trades", "symbol": "t{}".format(symbol_send)})
                    ws.send(send)

            start_ws()
        except Exception as e:
            logger.error(f"{e}")
            time.sleep(5)


@decorator.monitor_handler
async def get_bn_trades(trans_symbols, symbols):
    cur_ex = ExchangeCode.bn.value

    thread_name = threading.current_thread().name
    thread_id = threading.current_thread().ident
    i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
    [i_live_transit_station("item_instance", f"{transfer_symbols(trans_symbols, symbol)}", frequency=WS_FREQUENCY, heart_type=1) for symbol in symbols]
    while True:
        try:
            logger.info(f"{cur_ex}-----start_ws")

            extra_symbol_prices = list()  # 装加权的稳定价格
            extra_agv_busd_price = None  # 加权的稳定价格
            busd_usdt_latest_update = 0
            extra_currency = 'busd'
            symbol_send_list = [f"{symbol.replace('-', '').lower()}@ticker" for symbol in symbols]
            logger.info(f"{symbol_send_list =}")
            async with websockets.connect(EXCHANGE_CONFIG[cur_ex]['spot_ws'], close_timeout=0.01, ping_interval=15,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as webs:
                asyncio.create_task(webs.send(
                    ujson.dumps({
                        "method": "SUBSCRIBE",
                        "params": symbol_send_list,
                        "id": int(thread_id)}
                    )))
                while True:
                    message = await asyncio.wait_for(webs.recv(), 120)
                    msg = ujson.loads(message)
                    symbol_lower = msg.get("stream", "")[0:-7]
                    data = msg.get("data")
                    channel = msg.get("stream", "")
                    if symbol_lower and data and "ticker" in channel:
                        # 基础的合成价格 busdusdt_price
                        diff_ts = time.time() - float(data["E"]) / 1000
                        if symbol_lower == f'{extra_currency}usdt':
                            busd_price = float(data["c"])
                            extra_symbol_prices.append(busd_price)
                            # 保证这个列表里的数据总是49个
                            extra_symbol_prices = extra_symbol_prices[-49:]
                            if time.time() - busd_usdt_latest_update > 20:
                                busd_usdt_latest_update = time.time()
                                extra_agv_busd_price = numpy.median(extra_symbol_prices)
                                global_variable.G_SYMBOL_TRADE_PRICES['bn'][f'{extra_currency.upper()}-USDT'] = extra_agv_busd_price
                            else:
                                i_live_transit_station("item_instance", f"{extra_currency.upper()}-USDT",
                                                       frequency=WS_FREQUENCY,
                                                       heart_type=1)

                        else:
                            # 特殊处理 名字和外部名字不一样的交易对
                            avg_symbol_mark = False
                            # 合成对标到basebusd*busdusdt==>baseusdt
                            if symbol_lower[-4:] == "busd":
                                avg_symbol_mark = True
                                base_busd_price = float(data["c"])
                                busd_usdt_price = extra_agv_busd_price
                                # 如果这里没获取到值，busd_busd_price初始化的值为None
                                if not busd_usdt_price:
                                    try:
                                        busd_usdt_price = float(await libs_price_async.get_weight_price(f'{extra_currency.upper()}-USDT'))
                                    except Exception as e:
                                        return
                                base_usdt_price = base_busd_price * busd_usdt_price

                            # 正常的交易对 不需要合成
                            else:
                                base_usdt_price = float(data["c"])
                            symbol = transfer_symbols(trans_symbols, symbol_lower)
                            spec_rate = spot_currency_config.spec_symbol_rate_mapping.get(cur_ex, {}).get(symbol, ("", 1))
                            base_usdt_price *= spec_rate[1]
                            if not symbol:
                                continue
                            logger.info(f"{symbol} {base_usdt_price}")
                            global_variable.G_SYMBOL_TRADE_PRICES['bn'][symbol] = base_usdt_price
                            if diff_ts > 2:
                                logger.warning(f"bn-message-receive-timeout,msg:{data},超时{diff_ts}秒")
                                break
                            else:
                                i_live_transit_station("item_instance", f"{symbol}",
                                                       frequency=WS_FREQUENCY,
                                                       heart_type=1)
                                i_live_transit_station("main_instance", frequency=WS_FREQUENCY)

                    elif symbol_lower and data and "depth" in channel:
                        i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
                    else:
                        continue
        except asyncio.TimeoutError:
            msg = f"{cur_ex} {RESTART_DELAY_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'price')
        except Exception as e:
            logger.error(f"WS ERROR {e} {traceback.format_exc()}")
        finally:
            await asyncio.sleep(WS_EXCEPTION_SLEEP_TIME)


@decorator.monitor_handler
async def get_hb_trades(trans_symbols, symbols):
    thread_name = threading.current_thread().name
    cur_ex = ExchangeCode.hb.value

    i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
    [i_live_transit_station("item_instance", f"{transfer_symbols(trans_symbols, symbol)}", frequency=WS_FREQUENCY, heart_type=1) for symbol in symbols]
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
                        "sub": "market.{}.ticker".format(symbol_send),
                        "id": "id1"
                    }
                    asyncio.create_task(webs.send(ujson.dumps(data)))
                    await asyncio.sleep(0.1)  # 单个连接每两次请求不能小于100ms。
                # send_message(ws, {"sub": "market.btcusdt.bbo", "id": "for_check_connection"})
                while True:
                    message = await asyncio.wait_for(webs.recv(), RESTART_DELAY_TIME)
                    unzipped_data = gzip.decompress(message).decode()
                    msg_dict = ujson.loads(unzipped_data)
                    channel = msg_dict.get("ch", "")
                    if 'ping' in msg_dict:
                        data = {
                            "pong": msg_dict['ping']
                        }
                        logger.info(f"get_hb_trades ping ........")
                        asyncio.create_task(webs.send(ujson.dumps(data)))
                        i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
                        continue
                    elif msg_dict.get('status', '') == "error":
                        logger.error(f"{cur_ex} 订阅错误 {msg_dict['err-msg']}")
                        await recode_msg.recode_error_msg(f"{cur_ex} 订阅错误 {msg_dict}", 'hb_trades')
                        ERROR_SYMBOLS_LIST.append(SYMBOL_SYMBOL[msg_dict['err-msg'].split(' ')[2]])
                        raise Exception(msg_dict)
                    elif msg_dict.get("tick") and ".ticker" in channel:
                        symbol_lower = msg_dict.get("ch", '').split(".")
                        symbol_lower = symbol_lower[1] if symbol_lower else ""
                        data = msg_dict.get("tick", {})
                        if symbol_lower and data:
                            diff_ts = time.time() - float(msg_dict["ts"]) / 1000
                            price = data["lastPrice"]
                            if symbol_lower == "usdthusd":
                                price = 1 / price
                            symbol = transfer_symbols(trans_symbols, symbol_lower)
                            if not symbol:
                                continue
                            logger.info(f"get_hb_trades {symbol} {price =}")
                            global_variable.G_SYMBOL_TRADE_PRICES['hb'][symbol] = price
                            if diff_ts > 2:
                                logger.warning(f"hb-message-receive-timeout,msg:{msg_dict},超时{diff_ts}秒")
                                break
                            else:
                                i_live_transit_station("item_instance", f"{symbol}", frequency=WS_FREQUENCY,
                                                       heart_type=1)
                                i_live_transit_station("main_instance", frequency=WS_FREQUENCY)

                    elif "bbo" in channel:
                        i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
                    else:
                        continue
        except asyncio.TimeoutError:
            msg = f"{cur_ex} {RESTART_DELAY_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'price')
        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")
        finally:
            await asyncio.sleep(WS_EXCEPTION_SLEEP_TIME)


@decorator.monitor_handler
async def get_okex_trades(trans_symbols, symbols):
    cur_ex = ExchangeCode.okex.value

    thread_name = threading.current_thread().name
    i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
    [i_live_transit_station("item_instance", f"{transfer_symbols(trans_symbols, symbol)}", frequency=WS_FREQUENCY, heart_type=1) for symbol in symbols]
    ERROR_SYMBOLS_LIST = []
    while True:
        try:
            logger.info(f"{cur_ex}-----start_ws")

            async with websockets.connect(EXCHANGE_CONFIG[cur_ex]['spot_ws'], close_timeout=0.01, ping_interval=15, max_queue=128, compression=None, ssl=ssl._create_unverified_context()) as webs:
                symbols = list(set(symbols) - set(ERROR_SYMBOLS_LIST))
                args = [{"channel": "tickers", "instId": symbol_send} for symbol_send in symbols]
                if args:
                    sub_data = {
                        "op": "subscribe",
                        "args": args,
                    }
                    asyncio.create_task(webs.send(ujson.dumps(sub_data)))
                    await asyncio.sleep(0.1)
                    asyncio.create_task(webs.send(ujson.dumps({
                        "op": "subscribe",
                        "args": [{
                            "channel": "trades",
                            "instId": "BTC-USDT"
                        }]
                    })))
                webs.ping = ping_enhance(webs, "ping")
                while True:
                    message = await asyncio.wait_for(webs.recv(), 35)
                    # if "error" in message:
                    #     asyncio.create_task(recode_msg.recode_error_msg(f"{cur_ex} {message}", 'depth_price'))
                    #     continue
                    if message == "pong":  # 判断推送来的消息类型：如果是服务器的心跳
                        logger.info("get_okex_trades pong received.")
                        i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
                        continue
                    msg_dict = ujson.loads(message)
                    if "error" == msg_dict.get('event', ''):
                        error_symbol = msg_dict['msg'].split(':')[2].split(' ')[0]
                        ERROR_SYMBOLS_LIST.append(error_symbol)
                        logger.error(f"{cur_ex} 订阅错误 {msg_dict['msg']}")
                        await recode_msg.recode_error_msg(f"{cur_ex} 订阅错误 {msg_dict['msg']}", 'okex_trades')

                        raise Exception(msg_dict)
                    data = msg_dict.get("data", [])
                    channel = msg_dict.get("arg", {}).get("channel", "")
                    if data and "tickers" in channel:
                        data = data[0]
                        ts = float(data["ts"])
                        diff_ts = time.time() - ts / 1000
                        symbol = transfer_symbols(trans_symbols, data["instId"])
                        if not symbol:
                            continue
                        price = data["last"]
                        logger.info(f"{symbol} {price}")
                        global_variable.G_SYMBOL_TRADE_PRICES['okex'][symbol] = price
                        if diff_ts > 2:
                            logger.warning(f"okex-message-receive-timeout,msg:{data},超时{diff_ts}秒")
                            break
                        else:
                            i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
                            i_live_transit_station("item_instance", f"{symbol}", frequency=WS_FREQUENCY, heart_type=1)

                    elif "trades" in channel:
                        i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
                    else:
                        continue
        except asyncio.TimeoutError:
            msg = f"{cur_ex} {RESTART_DELAY_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'price')
        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")
        finally:
            await asyncio.sleep(WS_EXCEPTION_SLEEP_TIME)


def get_bkex_trades(trans_symbols, symbols):
    thread_name = threading.current_thread().name
    cur_ex = ExchangeCode.bkex.value

    while True:
        try:
            logger.info(f"{cur_ex}-----start_ws")

            def send_heart_beat(ws):

                ping = 'ping'
                while True:
                    if not ws.sock:
                        print(datetime.datetime.now().strftime('%H:%M:%S.%f'), "get_bkex_trades breakbeat ", ws.sock)
                        senddd.send_telegram("get_bkex_depth send_heart_beat break", 'depth_price', libs_config.DEBUG)
                        break
                    print(datetime.datetime.now().strftime('%H:%M:%S.%f'), "get_bkex_trades threading ", threading.current_thread(), ws.sock)
                    time.sleep(20)  # 每隔20秒交易所服务器发送心跳信息
                    ws.send(ping)

            def on_message(ws, message):
                if message == "40":
                    ws.send('40/quotation')
                if message == "40/quotation":
                    ws.send('42/quotation,["quotationDealConnect",{"pair": "BTC_USDT"}]')
                    # ws.send('42/quotation,["subOrderDepth",{"pair": "BTC_USDT", "number": 1}]')
                if "42/quotation" in message and "quotationListDeal" in message:
                    msg = ujson.loads(message[13:])[1][0]
                    price = msg["p"]
                    print(price)

                    if price > 0:
                        symbol = transfer_symbols(trans_symbols, msg["pair"])
                        if not symbol:
                            return
                        global_variable.G_SYMBOL_TRADE_PRICES['bkex'][symbol] = price
                i_live_transit_station("ZEUS_MONITOR_WS_PRICE", "bkex", WS_FREQUENCY)

            def on_error(ws, error):
                print("error", error)
                if ws.keep_running:
                    ws.close()
                time.sleep(5)

            def on_close(ws, close_status_code, close_msg):
                print(datetime.datetime.now().strftime('%H:%M:%S.%f'), f"{thread_name} {close_status_code} {close_msg}")
                senddd.send_telegram(f"{thread_name} {close_msg}", 'price', libs_config.DEBUG)

                if ws.keep_running:
                    ws.close()
                time.sleep(5)

            def on_open(ws):
                pass

            def start_ws():
                # websocket.enableTrace(True)
                ws = websocket.WebSocketApp(
                    EXCHANGE_CONFIG[cur_ex]['spot_ws'],
                    on_open=on_open,
                    on_message=on_message,
                    on_error=on_error,
                    on_close=on_close
                )
                ws.run_forever()

            start_ws()
        except Exception as e:
            logger.error(f"{e}")
            time.sleep(5)


@decorator.monitor_handler
async def get_kucoin_trades(trans_symbols, symbols):
    thread_name = threading.current_thread().name
    cur_ex = ExchangeCode.kucoin.value
    logger.info(f"{cur_ex}-----start_ws")

    async def get_token():
        base_url = f"{EXCHANGE_CONFIG[cur_ex]['spot_restful']}/api/v1/bullet-public"
        headers = {
            'user-agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
        }
        async with G_RequestSession.request.post(base_url, timeout=10) as r:
            res = await r.text()
            res = ujson.loads(res)
            ws_url = res["data"]["instanceServers"][0]["endpoint"]
            token = res["data"]["token"]
            return ws_url, token

    i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
    [i_live_transit_station("item_instance", f"{transfer_symbols(trans_symbols, symbol)}", frequency=WS_FREQUENCY, heart_type=1) for symbol in symbols]
    while True:
        try:
            logger.info(f"{cur_ex}-----start_ws")

            ws_url, token = await get_token()
            async with websockets.connect(f"{ws_url}?token={token}", close_timeout=0.01, ping_interval=15, max_queue=128, compression=None, ssl=ssl._create_unverified_context()) as webs:
                topic = ""
                for symbol in symbols:
                    topic += f"{symbol},"
                topic = topic[:-1]
                data = {
                    "id": "sub_depth_price",
                    "type": "subscribe",
                    "topic": f"/market/match:{topic}",
                    "privateChannel": False,
                    "response": True
                }
                asyncio.create_task(webs.send(ujson.dumps(data)))
                asyncio.create_task(webs.send(ujson.dumps({
                    "id": "sub_depth_price",
                    "type": "subscribe",
                    "topic": "/market/ticker:BTC-USDT",
                    "privateChannel": False,
                    "response": True
                })))
                while True:
                    message = await asyncio.wait_for(webs.recv(), RESTART_DELAY_TIME)
                    msg_dict = ujson.loads(message)
                    channel = msg_dict.get("topic", "")
                    if msg_dict.get("data") and "/market/match" in channel:
                        symbol = transfer_symbols(trans_symbols, channel.split(":")[1])
                        if not symbol:
                            continue
                        try:
                            price = msg_dict["data"].get("price")
                            ts = float(msg_dict.get("data", {})["time"]) / 1000
                            if symbol and price:
                                diff_ts = time.time() - ts
                                logger.info(f"get_kucoin_trades {symbol} {price =}")
                                global_variable.G_SYMBOL_TRADE_PRICES['kucoin'][symbol] = price
                                if diff_ts > 2:
                                    logger.warning(f"{thread_name} {symbol} price:{price} 超时{diff_ts}秒")
                                    break
                                else:
                                    i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
                                    [i_live_transit_station("item_instance", f"{symbol}", frequency=WS_FREQUENCY, heart_type=1) for symbol in symbols]
                        except BaseException as e:
                            logger.error(f"{msg_dict =} {e} {traceback.format_exc()}")
                            await recode_msg.recode_error_msg(f"get_kucoin_trades on_error {e}", 'depth_price')
                    elif "/market/ticker" in channel:
                        i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
                    else:
                        continue
        except asyncio.TimeoutError:
            msg = f"{cur_ex} {RESTART_DELAY_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'price')
        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")
        finally:
            await asyncio.sleep(WS_EXCEPTION_SLEEP_TIME)


@decorator.monitor_handler
async def get_mxc_trades(trans_symbols, symbols):
    cur_ex = ExchangeCode.mxc.value

    thread_name = threading.current_thread().name
    i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
    [i_live_transit_station("item_instance", f"{transfer_symbols(trans_symbols, symbol)}", frequency=WS_FREQUENCY, heart_type=1) for symbol in symbols]
    while True:
        try:
            logger.info(f"{cur_ex}-----start_ws")
            # 1个 ws 连接最多30个订阅
            async with websockets.connect(EXCHANGE_CONFIG[cur_ex]['spot_ws'], close_timeout=0.01, ping_interval=15, max_queue=128, compression=None, ssl=ssl._create_unverified_context()) as webs:
                data = {"method": "SUBSCRIPTION", "params": []}
                for symbol in symbols:  # 交易对数量最好不准超过20个
                    symbol = symbol.replace("-", "")
                    logger.info(f"into open {symbol}")
                    data["params"].append(f"spot@public.deals.v3.api@{symbol}")
                data["params"].append(f"spot@public.limit.depth.v3.api@BTCUSDT@5")
                asyncio.create_task(webs.send(ujson.dumps(data)))
                webs.ping = ping_enhance(webs, ujson.dumps({"method": "PING"}))

                while True:
                    message = await asyncio.wait_for(webs.recv(), RESTART_DELAY_TIME)
                    msg_dict = ujson.loads(message)
                    if msg_dict.get('msg', '') == "no subscription success":
                        logger.error(f"{cur_ex} 订阅错误 {msg_dict['msg']}")
                        await recode_msg.recode_error_msg(f"{cur_ex} 订阅错误 {msg_dict}", 'mxc_trades')
                        raise Exception(msg_dict)
                    channel = msg_dict.get("c", "")
                    if msg_dict.get("d") and "deals" in channel:
                        s = msg_dict.get("s")
                        data = msg_dict.get("d", {})["deals"]
                        if s and data:
                            symbol = transfer_symbols(trans_symbols, s)
                            if not symbol:
                                continue
                            diff_ts = time.time() - float(data[0]["t"]) / 1000
                            logger.info(f"get_mxc_trades {symbol}, {data[0]['p']}")
                            global_variable.G_SYMBOL_TRADE_PRICES['mxc'][symbol] = data[0]["p"]
                            if diff_ts > 2:
                                logger.warning(f"mxc-message-receive-timeout,msg:{msg_dict},超时{diff_ts}秒")
                                break
                            else:
                                i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
                                i_live_transit_station("item_instance", f"{symbol}", frequency=WS_FREQUENCY,
                                                       heart_type=1)

                    elif "depth" in channel:
                        i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
                    else:
                        continue
        except asyncio.TimeoutError:
            msg = f"{cur_ex} {RESTART_DELAY_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'price')
        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")
        finally:
            await asyncio.sleep(WS_EXCEPTION_SLEEP_TIME)


@decorator.monitor_handler
async def get_bitget_trades(trans_symbols, symbols):
    # 获取最近的成交数据，有成交数据就推送
    cur_ex = ExchangeCode.bitget.value

    thread_name = threading.current_thread().name
    i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
    [i_live_transit_station("item_instance", f"{transfer_symbols(trans_symbols, symbol)}", frequency=WS_FREQUENCY, heart_type=1) for symbol in symbols]
    ERROR_SYMBOLS_LIST = []
    while True:
        try:
            logger.info(f"{cur_ex}-----start_ws")

            async with websockets.connect(EXCHANGE_CONFIG[cur_ex]['spot_ws'], close_timeout=0.01, ping_interval=28,
                                          max_queue=128, compression=None,
                                          ssl=ssl._create_unverified_context()) as webs:
                symbols = list(set(symbols) - set(ERROR_SYMBOLS_LIST))
                args = []
                for symbol in symbols:
                    symbol = symbol.replace("-", "")
                    params = {
                        "instType": "sp",
                        "channel": "trade",
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
                        message = await asyncio.wait_for(webs.recv(), RESTART_DELAY_TIME)
                    except TimeoutError:
                        await webs.send('ping')
                        continue
                    if message == "pong":  # 判断推送来的消息类型：如果是服务器的心跳
                        i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
                        continue
                    msg_dict = ujson.loads(message)
                    if "error" == msg_dict.get('event', ''):
                        error_symbol = msg_dict.get("arg", {}).get("instId", "")
                        error_symbol = transfer_symbols(trans_symbols, error_symbol)
                        ERROR_SYMBOLS_LIST.append(error_symbol)
                        logger.error(f"{cur_ex} 订阅错误 {msg_dict['msg']}")
                        await recode_msg.recode_error_msg(f"{cur_ex} 订阅错误 {msg_dict['msg']}", 'bitget_trades')

                        raise Exception(msg_dict)
                    data = msg_dict.get("data", [])
                    ts = msg_dict.get("ts", 0)
                    channel = msg_dict.get("arg", {}).get("channel", "")
                    if data and "trade" in channel:
                        data = data[0]
                        diff_ts = time.time() - ts / 1000
                        symbol = transfer_symbols(trans_symbols, msg_dict.get("arg", {}).get("instId", ""))
                        if not symbol:
                            continue
                        price = data[1]
                        logger.info(f"get_bitget_trades {symbol} {price =}")
                        global_variable.G_SYMBOL_TRADE_PRICES[cur_ex][symbol] = price
                        if diff_ts > 2:
                            logger.warning(f"bitget-message-receive-timeout,msg:{data},超时{diff_ts}秒")
                            break
                        else:
                            i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
                            i_live_transit_station("item_instance", f"{symbol}", frequency=WS_FREQUENCY, heart_type=1)
                    else:
                        continue
        except asyncio.TimeoutError:
            msg = f"{cur_ex} {RESTART_DELAY_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'price')
        except Exception as e:
            logger.error(f"{e} {traceback.format_exc()}")
        finally:
            await asyncio.sleep(WS_EXCEPTION_SLEEP_TIME)


@decorator.monitor_handler
def get_mxc_trade_price_restful(mxc_symbols):
    cur_ex = ExchangeCode.mxc.value

    mxc_symbols = [i.replace("-", "_").upper() for i in mxc_symbols]  # eg:"BTC_USDT"
    mxc_base_url = EXCHANGE_CONFIG[cur_ex]['spot_restful']
    error_times = 0
    i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
    [i_live_transit_station("item_instance", f'{symbol.replace("_", "-")}', frequency=WS_FREQUENCY, heart_type=1) for symbol in mxc_symbols]
    while True:
        for symbol in mxc_symbols:
            data = {
                "symbol": symbol,
                "limit": 1,
            }
            symbol = symbol.replace("_", "-")
            try:
                r = requests.get(f"{mxc_base_url}/open/api/v2/market/deals", params=data, timeout=2).json()
                if r.get("code", 0) == 200 and r.get("data", {}):
                    trade_price = float(r["data"][0]["trade_price"])
                    logger.info(f"mxc获取到数据,symbol:{symbol}, trade_price:{trade_price}")
                    global_variable.G_SYMBOL_TRADE_PRICES['mxc'][symbol] = trade_price
                    i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
                    i_live_transit_station("item_instance", f'{symbol}', frequency=WS_FREQUENCY, heart_type=1)
                    error_times = 0
            except:
                logger.error(f"mxc_trade_price_restful  {traceback.format_exc()}")
                error_times += 1
                if error_times > 5:
                    recode_msg.recode_error_msg_sync("MXC Price Error 连续5次报警", "price")
            time.sleep(2)


@decorator.monitor_handler
async def get_abc_trade_price(abc_symbols):
    abc_symbols = [i.replace("/", "-").upper() for i in abc_symbols]  # eg:"BTC-USDT"
    abc = AbcApi(token=libs_account["contract_volume"]["token"], secret_key=libs_account["contract_volume"]["sk"])
    error_times = 0
    logger.info("into get_abc_trade_price")
    for symbol in abc_symbols:
        i_live_transit_station("item_instance", f'abc_{symbol}', frequency=WS_FREQUENCY, heart_type=1)

    i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
    while True:
        for symbol in abc_symbols:
            try:
                r = await abc.trades(symbol, 1)
                if r.get("errno") == 0 and r.get("result"):
                    trade_price = float(r["result"]["data"][0]["price"])
                    logger.info(f"abc获取到数据,symbol:{symbol}, trade_price:{trade_price}")
                    global_variable.G_SYMBOL_TRADE_PRICES['abc'][symbol] = trade_price
                    i_live_transit_station("item_instance", f'abc_{symbol}', frequency=WS_FREQUENCY, heart_type=1)
                    i_live_transit_station("main_instance", frequency=WS_FREQUENCY)
                    error_times = 0
                else:
                    raise Exception(r)
            except Exception as e:
                logger.error(f"abc_trade_price_restful {e} {traceback.format_exc()}")
                error_times += 1
                if error_times > 5:
                    await recode_msg.recode_error_msg("ABC Price Error 连续5次报警", 'price')
            await asyncio.sleep(2)


if __name__ == '__main__':
    global_variable.G_SYMBOL_TRADE_PRICES['bitget'] = {}
    asyncio.run(get_bitget_trades({"busdusdt": "BUSD-USDT", 'AWTUSDT': 'AWT-USDT'}, ['AWT-USDT'],
                                 monitor="价格服务_中心化|现货二十档存redis"))