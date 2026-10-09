"""
abc 推送指数价格我们做市使用，现在已经不使用，改变方案为我们自己获取市场价格
"""
# -- 不能注释，此导入为初始化
import initialization
# ---
import asyncio
import websockets
import ujson
import traceback
import time
import ssl
from libs import libs_price_async, decorator
from many_configs import abc_config, contract_currency_config, global_variable
from libs.heartbeat import i_live_transit_station, heart_monitor_async
from ws_libs.volume_trade_add_contract import async_contract_price_restful
from libs import recode_msg
from loguru import logger


@decorator.monitor_handler
async def async_contract_price_ws():
    sslcontext = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    sslcontext.check_hostname = False
    sslcontext.verify_mode = ssl.CERT_NONE
    sslcontext.set_ciphers("ALL")

    while True:
        # print("async_contract_price_ws", global_variable.monitor.get())
        i_live_transit_station("main_instance", frequency=6)
        [i_live_transit_station("item_instance", f"{i}", frequency=300) for i in contract_currency_config.CONTRACT_SUPPORT_SYMBOLS]
        try:
            LAST_PRICE = {}
            """
            测试：
            wscat -c wss://coqvws.websea.work/ws/realTime
            {"sub": "market.markprice.BTC-USDT"}
            """
            ws_uri = "{}/ws/realTime".format(abc_config.contract_ws_host, )
            async with websockets.connect(ws_uri, timeout=3, ssl=sslcontext) as ws:
                [asyncio.create_task(ws.send(ujson.dumps({"sub": f"market.markprice.{i}"}))) for i in contract_currency_config.CONTRACT_SUPPORT_SYMBOLS]
                while True:
                    message = await ws.recv()

                    message = ujson.loads(message)
                    symbol = message["symbol"]

                    if int(time.time()) - LAST_PRICE.get(f"{symbol}-update", 0) > 5:
                        LAST_PRICE[f"{symbol}-update"] = int(time.time())
                        logger.info(f"async_contract_price_ws {message}")
                    weight_price = message["markPrice"]
                    ts = message.get("ts", 0)
                    if time.time()-ts/1000 > 20:
                        logger.info(f"{symbol}合约标记价格间隔时间：{time.time()-ts/1000}")
                    if LAST_PRICE.get(symbol, 0) == float(weight_price):
                        i_live_transit_station("item_instance", f"{symbol}", frequency=300, heart_type=1)
                        i_live_transit_station("main_instance", frequency=6)
                        continue
                    if float(weight_price) > 0 and time.time() - ts / 1000 < 80:
                        LAST_PRICE[symbol] = float(weight_price)
                        if symbol == "BTC-USDT":
                            global_variable.MARK_PRICE["BTC-USDT"] = weight_price
                        else:
                            global_variable.MARK_PRICE[symbol] = weight_price
                        i_live_transit_station("item_instance", f"{symbol}", frequency=300, heart_type=1)
                        i_live_transit_station("main_instance", frequency=6)
                        # logger.info(f"async_contract_price_ws-weight_price {symbol}, {weight_price}")
        except (Exception, BaseException) as e:
            await recode_msg.recode_error_msg(f"标记价格ws出现问题 {traceback.format_exc()}", "abc_contract_price")
            logger.error(f"async_contract_price_ws {traceback.format_exc()}")
            await asyncio.sleep(5)


@decorator.monitor_handler
async def mark_price_2_db():
    i_live_transit_station("main_instance", frequency=6)
    last_price = {}
    while True:
        try:
            send_datas = {}
            symbols = list(global_variable.MARK_PRICE.keys())
            for i in symbols:
                price = global_variable.MARK_PRICE[i]
                if last_price.get(i) != price:
                    send_datas[i] = price
                    last_price[i] = price
            if send_datas:
                await libs_price_async.update_contract_price(send_datas)
            i_live_transit_station("main_instance", frequency=6)
        except (Exception, BaseException) as e:
            logger.error(f"mark_price_2_db {traceback.format_exc()}")
            await recode_msg.recode_error_msg(f"标记价格存入redis {traceback.format_exc()}", "abc_contract_price")
        finally:
            await asyncio.sleep(2)



async def main():
    tasks = [asyncio.create_task(heart_monitor_async()),
             asyncio.create_task(async_contract_price_ws(monitor="abc合约标记价格_ws|")),
             asyncio.create_task(async_contract_price_restful(monitor="abc合约标记价格_restful|")),
             asyncio.create_task(mark_price_2_db(monitor="abc合约标记价格_存redis|")),
             ]
    for i in tasks:
        await i


if __name__ == "__main__":
    asyncio.run(main())

