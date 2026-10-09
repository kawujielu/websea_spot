import ssl
import datetime
from libs import libs_config, decorator
from many_configs import global_variable, abc_config
from libs.heartbeat import i_live_transit_station
import asyncio
import websockets
import ujson
import traceback
import time
from datetime import datetime
from libs import recode_msg
from loguru import logger
from config import RESTART_FIXED_TIME


async def subscribe_abc_ask_bid_price(symbols):
    i_live_transit_station("main_instance", frequency=10)
    [i_live_transit_station("item_instance", f"{i}", 60 * 5, heart_type=3) for i in symbols]

    sslcontext = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    sslcontext.check_hostname = False
    sslcontext.verify_mode = ssl.CERT_NONE
    sslcontext.set_ciphers("ALL")

    while True:
        try:
            ws_uri = "{}/ws/depth".format(abc_config.spot_depth_ws_host, )
            print(ws_uri)
            async with websockets.connect(ws_uri, close_timeout=0.01, ping_interval=15,
                                          max_queue=128, compression=None, ssl=sslcontext) as ws:
                [await ws.send(ujson.dumps({"sub": f"market.depth.{i}"})) for i in symbols]
                while True:
                    message = await asyncio.wait_for(ws.recv(), RESTART_FIXED_TIME)
                    #logger.info(f"abc交易所现货买卖一深度ws订阅数据验证: {message}")
                    try:
                        message = ujson.loads(message)
                        symbol = message["symbol"]
                        asks = message["asks"]
                        bids = message["bids"]
                        if not asks or not bids:
                            global_variable.ABC_ASK_BID_PRICE_CONTAINER[symbol] = {}
                        ask = float(asks[0]["price"])
                        bid = float(bids[0]["price"])
                        ask_amount = float(asks[0]["number"])
                        bid_amount = float(bids[0]["number"])
                        ts = float(message.get("ts", 0)) / 1000
                        #ts = time.time()
                        #logger.info(f"数据验证:{ts} {time.time()}")

                        if ask and bid and time.time() - ts < 5:
                            i_live_transit_station("main_instance", frequency=10)
                            i_live_transit_station("item_instance", f"{symbol}", 60 * 5, heart_type=3, last_update=ts)

                            global_variable.ABC_ASK_BID_PRICE_CONTAINER[symbol] = {
                                "ask": float(ask), "bid": float(bid), "bid_amount": float(bid_amount),
                                "ask_amount": float(ask_amount), "ts": ts
                            }  # print(datetime.now(), "abc-ask-bid price", symbol, ask, bid, ts)
                    except BaseException as e:
                        logger.error(f"abc交易所 现货 买卖一深度ws订阅 {traceback.format_exc()} - {message}")
        except asyncio.TimeoutError:
            msg = f"abc交易所 现货 买卖一深度ws订阅 {RESTART_FIXED_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'volume')
        except:
            logger.error(f"abc交易所 现货 买卖一深度ws订阅 {traceback.format_exc()}")

            await recode_msg.recode_error_msg(
                f"abc交易所 现货 买卖一深度ws订阅 {traceback.format_exc()}", "async_abc_ask_bid_price_ws")
            await asyncio.sleep(1)


@decorator.monitor_handler
async def async_abc_ask_bid_price_ws(symbols_set):
    tasks = []
    part_symbol_number = 60
    symbols = list(symbols_set)
    for i in range(int(len(symbols) / part_symbol_number) + 1):
        target_abc_symbol = symbols[part_symbol_number * i:part_symbol_number * (i + 1)]
        if not target_abc_symbol:
            continue
        tasks.append(asyncio.create_task(subscribe_abc_ask_bid_price(target_abc_symbol)))

    for i in tasks:
        await i


if __name__ == "__main__":
    pass


