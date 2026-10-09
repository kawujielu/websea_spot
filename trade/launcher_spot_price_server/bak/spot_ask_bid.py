# -- 不能注释，此导入为初始化
import initialization
# ---
import time
import asyncio
import loguru
import traceback
from threading import Thread
from ws_libs import ws_ask_bid
from many_configs import global_variable
from libs import libs_price_async, decorator
from libs.heartbeat import heart_monitor, i_live_transit_station
from many_configs.spot_currency_config import price_market_ex_symbols, price_depth_ex_symbols, price_trans_symbols


ask_bid_pair = {}
heartbeat_ask_bid_pair = {}

all_ex = list(set(list(price_market_ex_symbols.keys()) + list(price_depth_ex_symbols.keys())))
for ex in all_ex:
    ask_bid_pair[ex] = list(price_market_ex_symbols.get(ex, set() | price_depth_ex_symbols.get(ex, set())))


@decorator.monitor_handler
async def symbol_ask1_bid1_2_db():
    i_live_transit_station("main_instance", frequency=0.5)
    [i_live_transit_station("item_instance", f"{exc}{symbol}", frequency=0.5)
     for exc in heartbeat_ask_bid_pair for symbol in heartbeat_ask_bid_pair[exc]]
    while True:
        try:
            now_time = time.time()
            data_mappings = global_variable.G_SYMBOL_ASK_BID_PRICES
            exchanges = list(data_mappings.keys())
            send_data = []
            for exchange in exchanges:
                if not data_mappings[exchange]:
                    continue
                symbol_data_mappers = list(data_mappings[exchange].keys())
                for symbol in symbol_data_mappers:
                    data = data_mappings[exchange][symbol]
                    if not data:
                        continue
                    send_data.append({"symbol": symbol, "exchange": exchange, "ask1": data["ask1"], "bid1": data["bid1"]})
                    i_live_transit_station("item_instance", f"{exchange}{symbol}", frequency=0.5)
                    i_live_transit_station("main_instance", frequency=0.5)
                print(f"exchange:{exchange}", len(symbol_data_mappers))
            await libs_price_async.rs_update_ask_bid(send_data)
            print('total_time:', "%0.2f" % (time.time() - now_time))
        except Exception as e:
            print('存入redis报错', e, traceback.format_exc())
        finally:
            await asyncio.sleep(0.2)


@decorator.monitor_handler
async def symbol_gear20_2_db():
    i_live_transit_station("main_instance", frequency=0.5)
    # item_instance 不进行初始化，属于买卖一子集，不是所有交易对都有订阅
    while True:
        try:
            now_time = time.time()
            data_mappings = global_variable.G_SYMBOL_GEAR20
            exchanges = list(data_mappings.keys())
            send_data = []
            for exchange in exchanges:
                if not data_mappings[exchange]:
                    continue
                symbol_data_mappers = list(data_mappings[exchange].keys())
                for symbol in symbol_data_mappers:
                    asks = data_mappings[exchange][symbol]["asks"]
                    bids = data_mappings[exchange][symbol]["bids"]
                    if asks and bids:
                        send_data.append({"symbol": symbol, "exchange": exchange, "asks": str(asks), "bids": str(bids)})
                        last_update = data_mappings[exchange][symbol]['ts']
                        i_live_transit_station("item_instance", f"{exchange}{symbol}", frequency=0.5)
                        i_live_transit_station("main_instance", frequency=0.5)
                print(f"exchange:{exchange}", len(symbol_data_mappers))
            await libs_price_async.rs_update_gear(send_data)
            print('total_time:', "%0.2f" % (time.time() - now_time))
        except Exception as e:
            print('档位信息存入redis报错', e, traceback.format_exc())
        finally:
            await asyncio.sleep(5)


if __name__ == '__main__':
    trade_thread_list = []
    part_symbol_number = 40
    for ex, target_ex_symbols in ask_bid_pair.items():
        global_variable.G_SYMBOL_ASK_BID_PRICES[ex] = {}
        global_variable.G_SYMBOL_GEAR20[ex] = {}
        if not target_ex_symbols:
            continue
        heartbeat_ask_bid_pair[ex] = target_ex_symbols
        # loguru.logger.info(f'{ex} depth symbols {target_ex_symbols}')
        ex_symbol_number = len(target_ex_symbols)
        for i in range(int(ex_symbol_number / part_symbol_number) + 1):
            target_ex_part_symbol = target_ex_symbols[part_symbol_number * i:part_symbol_number * (i + 1)]
            if not target_ex_part_symbol:
                continue
            if not hasattr(ws_ask_bid, f"get_{ex}_depth"):
                continue
            spot_ask_bid_function = getattr(ws_ask_bid, f"get_{ex}_depth")

            t = Thread(target=asyncio.run,
                       args=(spot_ask_bid_function(price_trans_symbols[ex],
                                                   target_ex_part_symbol,
                                                   monitor=f"价格服务_中心化|{ex}现货买卖一订阅服务{i}"),),)
            trade_thread_list.append(t)

    trade_thread_list.append(Thread(target=asyncio.run, args=(symbol_gear20_2_db(monitor="价格服务_中心化|现货二十档存redis"),)))
    trade_thread_list.append(Thread(target=asyncio.run, args=(symbol_ask1_bid1_2_db(monitor="价格服务_中心化|现货买卖一存redis"),)))
    trade_thread_list.append(Thread(target=heart_monitor, args=()))

    for t in trade_thread_list:
        t.start()
    for t in trade_thread_list:
        t.join()
