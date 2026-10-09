# -- 不能注释，此导入为初始化
import initialization
# ---
import time
import traceback
import loguru
import asyncio
from threading import Thread
from ws_libs import ws_depth
from many_configs import global_variable
from libs import libs_price_async, decorator
from libs.heartbeat import heart_monitor, i_live_transit_station
from many_configs.spot_currency_config import price_depth_ex_symbols, price_trans_symbols

@decorator.monitor_handler
async def symbol_depth_price_2_db():
    i_live_transit_station("main_instance", frequency=0.5)
    while True:
        try:
            now_time = time.time()
            data_mappings = global_variable.G_SYMBOL_DEPTH_PRICES
            exchanges = list(data_mappings.keys())
            send_data = []
            for exchange in exchanges:
                if not data_mappings[exchange]:
                    continue
                symbol_data_mappers = list(data_mappings[exchange].keys())
                for symbol in symbol_data_mappers:
                    price = data_mappings[exchange][symbol]
                    if not price:
                        continue
                    send_data.append({"symbol": symbol, "exchange": exchange, "price": price})
                print(f"exchange:{exchange}", len(symbol_data_mappers))
            await libs_price_async.rs_update_price(send_data)
            print('total_time:', "%0.2f" % (time.time()-now_time))
            i_live_transit_station("main_instance", frequency=0.5)
        except Exception as e:
            print('存入redis报错', e, traceback.format_exc())
        finally:
            await asyncio.sleep(0.2)


if __name__ == '__main__':
    trade_thread_list = []
    part_symbol_number = 40
    for ex, target_ex_symbols in price_depth_ex_symbols.items():
        if not target_ex_symbols:
            continue
        target_ex_symbols = list(target_ex_symbols)
        global_variable.G_SYMBOL_DEPTH_PRICES[f"{ex}_depth"] = {}
        # loguru.logger.info(f'{ex} depth_price symbols {target_ex_symbols}')
        ex_symbol_number = len(target_ex_symbols)
        for i in range(int(ex_symbol_number / part_symbol_number) + 1):
            target_ex_part_symbol = target_ex_symbols[part_symbol_number * i:part_symbol_number * (i + 1)]
            if not target_ex_part_symbol:
                continue
            if not hasattr(ws_depth, f"get_{ex}_depth"):
                continue
            ws_depth_function = getattr(ws_depth, f"get_{ex}_depth")
            thread_name = f"{ex}_depth_{i}"
            t = Thread(target=asyncio.run, args=(ws_depth_function(price_trans_symbols[ex],
                                                                   target_ex_part_symbol,
                                                                   monitor=f"价格服务_中心化|{ex}-depth-ws订阅{i}-"),),
                       name=thread_name)
            trade_thread_list.append(t)
        if ex == "abc":
            global_variable.G_SYMBOL_DEPTH_PRICES[f"{ex}_depth"] = {}
            # 特殊处理
            global_variable.G_SYMBOL_DEPTH_PRICES[ex] = {}
            t = Thread(target=asyncio.run, args=(ws_depth.get_abc_depth(price_trans_symbols[ex],
                                                                        target_ex_symbols,
                                                                        monitor="价格服务_中心化|abc-depth"),))
            trade_thread_list.append(t)

    trade_thread_list.append(Thread(target=asyncio.run,
                                    args=(symbol_depth_price_2_db(monitor="价格服务_中心化|depth价格存入redis"),)))
    trade_thread_list.append(Thread(target=heart_monitor, args=()))

    for t in trade_thread_list:
        t.start()
    for t in trade_thread_list:
        t.join()
