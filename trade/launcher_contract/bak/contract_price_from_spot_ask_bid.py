# -- 不能注释，此导入为初始化
import initialization
# ---
import time
import asyncio
import traceback
import numpy as np
from datetime import datetime
from threading import Thread
from ws_libs import ws_ask_bid
from ws_libs.funding_rate import funding_rate_fetch, get_funding_rate
from many_configs.contract_currency_config import CONTRACT_ASK_BID_PRICE_SYMBOL_EXCHANGES, contract_price_ex_symbols, \
    contract_price_trans_symbols, contract_price_ex_abc_symbols
from many_configs import global_variable
from libs import libs_price_async, decorator
from libs.heartbeat import i_live_transit_station, heart_monitor


@decorator.monitor_handler
async def symbol_ask1_bid1_2_db():
    i_live_transit_station("main_instance", frequency=6)
    activate_symbols = set()
    for exchange, symbols in contract_price_ex_abc_symbols.items():
        activate_symbols.update(symbols)
        for symbol in symbols:
            i_live_transit_station("item_instance", f"{exchange}{symbol}", frequency=6)
    while True:
        try:
            now_time = time.time()
            data_mappings = global_variable.G_SYMBOL_ASK_BID_PRICES
            send_data = []
            for symbol in activate_symbols:
                try:
                    price_tmp = []
                    exchanges_tmp = CONTRACT_ASK_BID_PRICE_SYMBOL_EXCHANGES.get(symbol, [])
                    for exchange in exchanges_tmp:
                        if not data_mappings.get(exchange):
                            print(f"{datetime.now()} 合约买卖一价格{exchange} 未创建")
                            price_tmp.clear()
                            break
                        if not data_mappings[exchange].get(symbol):
                            print(f"{datetime.now()} 合约买卖一价格{exchange} {symbol} 未创建")
                            price_tmp.clear()
                            break
                        if time.time() - data_mappings[exchange][symbol]['ts'] > 50:
                            print(f"{datetime.now()} 合约买卖一价格{exchange} {symbol} 时间超过5s, 实际为"
                                  f"{time.time() - data_mappings[exchange][symbol]['ts']}s")
                            price_tmp.clear()
                            break

                        ask1 = float(data_mappings[exchange][symbol]["ask1"])
                        bid1 = float(data_mappings[exchange][symbol]["bid1"])
                        # print(f"{exchange} {symbol} 合约买卖一 ask1: {ask1} bid1: {bid1} {(ask1+bid1)/2}")
                        if ask1 > 0 and bid1 > 0:
                            price_tmp.append((ask1 + bid1) / 2)
                            last_update = data_mappings[exchange][symbol]['ts']
                            # 合约对标价格和通过现货对标的合约价格心跳应该保持一致，两个文件可能轮换启动
                            i_live_transit_station("item_instance", f"{exchange}{symbol}", frequency=6, last_update =last_update)
                        else:
                            price_tmp.clear()
                        print(f"exchange:{exchange}", len(data_mappings[exchange].keys()))
                    if price_tmp:
                        weight_price = np.mean(price_tmp)
                        # todo 是否会影响性能
                        funding_rate = await get_funding_rate(symbol)
                        funding_rate_weight_price = weight_price * (1 + funding_rate)
                        print(f"{datetime.now()} {symbol} : {price_tmp} {weight_price} {funding_rate_weight_price}")
                        send_data.append({"symbol": symbol, "price": funding_rate_weight_price})
                    else:
                        print(f"{datetime.now()} {symbol} 合约买卖一价格未正常写入redis")

                except Exception as e:
                    print(f'{datetime.now()} {symbol}合约买卖一价格获取错误', e, traceback.format_exc())

            await libs_price_async.update_contract_ask_bid_price(send_data)
            print('total_time:', "%0.2f" % (time.time()-now_time))
            i_live_transit_station("main_instance", frequency=6)
        except Exception as e:
            print('存入redis报错', e, traceback.format_exc())
        finally:
            await asyncio.sleep(0.2)


if __name__ == '__main__':
    trade_thread_list = []
    for ex, target_ex_symbols in contract_price_ex_symbols.items():
        if not target_ex_symbols:
            continue
        target_ex_symbols = list(target_ex_symbols)
        part_symbol_number = 20
        global_variable.G_SYMBOL_GEAR20[ex] = {}
        global_variable.G_SYMBOL_ASK_BID_PRICES[ex] = {}
        if ex == 'hb':
            part_symbol_number = 30
        ex_symbol_number = len(target_ex_symbols)
        for i in range(int(ex_symbol_number / part_symbol_number) + 1):
            target_ex_part_symbol = target_ex_symbols[part_symbol_number * i:part_symbol_number * (i + 1)]
            if target_ex_part_symbol:
                t = Thread(target=asyncio.run,
                           args=(getattr(ws_ask_bid, f"get_{ex}_depth")(contract_price_trans_symbols[ex], target_ex_part_symbol, monitor=f"合约对标价格_获取价格|{ex}现货买卖价|{i}"),),)
                trade_thread_list.append(t)

    trade_thread_list.append(Thread(target=asyncio.run, args=(symbol_ask1_bid1_2_db(monitor="合约对标价格_数据库|"), )))
    trade_thread_list.append(Thread(target=asyncio.run, args=(funding_rate_fetch(monitor="合约对标价格_资金费率|"), ),))
    trade_thread_list.append(Thread(target=heart_monitor, args=()))

    for t in trade_thread_list:
        t.start()
    for t in trade_thread_list:
        t.join()
