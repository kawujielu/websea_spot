import ssl
from libs import decorator
from many_configs import global_variable, abc_config, contract_currency_config
from libs.heartbeat import i_live_transit_station
import asyncio
import websockets
import ujson
import traceback
import time
from libs import recode_msg
from loguru import logger
from config import RESTART_FIXED_TIME


async def subscribe_abc_contract_ask_bid_price(symbols):
    i_live_transit_station("main_instance", frequency=10)
    [i_live_transit_station("item_instance", f"{i}", 60 * 5, heart_type=3) for i in symbols]

    sslcontext = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    sslcontext.check_hostname = False
    sslcontext.verify_mode = ssl.CERT_NONE
    sslcontext.set_ciphers("ALL")

    while True:
        try:
            ws_uri = "{}/ws/realTime".format(abc_config.contract_depth_ws_host, )
            logger.info(f"async_abc_contract_ask_bid_price_ws {ws_uri} {symbols}")
            async with websockets.connect(ws_uri, close_timeout=0.01, ping_interval=15,
                                          max_queue=128, compression=None, ssl=sslcontext) as ws:
                [await ws.send(ujson.dumps({"sub": f"market.depth.{i}"})) for i in symbols]
                while True:
                    message = await asyncio.wait_for(ws.recv(), RESTART_FIXED_TIME)
                    try:
                        message = ujson.loads(message)
                        symbol = message["symbol"]
                        ask = float(message["asks"][0]["price"])
                        bid = float(message["bids"][0]["price"])
                    except:
                        msg = f"合约买卖一价格订阅服务 {message} {traceback.format_exc()}"
                        logger.error(msg)
                        i_live_transit_station("main_instance", frequency=10)
                        continue
                    ts = float(message.get("ts", 0)) / 1000
                    if ask and bid and time.time() - ts < 5:
                        i_live_transit_station("item_instance", f"{symbol}", 60 * 5, heart_type=3, last_update=ts)
                        global_variable.ABC_CONTRACT_ASK_BID_PRICE_CONTAINER[symbol] = {"ask": ask, "bid": bid, "ts": ts}

                        # print(datetime.now(), "abc-contract-ask-bid price", symbol, ask, bid, ts)
                    elif not ask or not bid:
                        global_variable.ABC_CONTRACT_ASK_BID_PRICE_CONTAINER[symbol] = {}
                    else:
                        logger.info(f"{symbol} contract_ask_bid_price_timeout {time.time() - ts}")
                    i_live_transit_station("main_instance", frequency=10)
        except asyncio.TimeoutError:
            msg = f"abc合约买卖一价格订阅服务 {RESTART_FIXED_TIME} 时间未收到数据 触发TimeoutError 重启"
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, 'volume')
            await asyncio.sleep(1)
        except:
            logger.error(f"合约买卖一价格订阅服务 {traceback.format_exc()}")
            await recode_msg.recode_error_msg(f"abc合约买卖一价格订阅服务 {traceback.format_exc()}",
                                              "async_abc_contract_ask_bid_price_ws")
            await asyncio.sleep(1)


@decorator.monitor_handler
async def async_abc_contract_ask_bid_price_ws(symbols_set):
    tasks = []
    part_symbol_number = 60
    symbols = list(symbols_set)
    for i in range(int(len(symbols) / part_symbol_number) + 1):
        target_abc_symbol = symbols[part_symbol_number * i:part_symbol_number * (i + 1)]
        if not target_abc_symbol:
            continue
        tasks.append(asyncio.create_task(subscribe_abc_contract_ask_bid_price(target_abc_symbol)))

    for i in tasks:
        await i

if __name__ == "__main__":
    from threading import Thread

    all_symbols = contract_currency_config.contract_symbols


