
# -- 不能注释，此导入为初始化
import initialization
# ---
import time
import traceback
import asyncio
from ws_libs import price_libs
from libs import libs_price_async, decorator
from many_configs import global_variable
from libs.heartbeat import heart_monitor_async, i_live_transit_station
from many_configs.spot_currency_config import price_market_ex_symbols, price_trans_symbols
from many_configs.base_config import EXCHANGE_MAX_SUB_DEFAULT, EXCHANGE_MAX_SUB_PER_WS
from loguru import logger
from libs import recode_msg
from libs.utils import transfer_symbols


heartbeat_pair = {}


@decorator.monitor_handler
async def symbol_trade_price_2_db():
    i_live_transit_station("main_instance", frequency=0.5)
    [i_live_transit_station("item_instance", f"{exc}-{transfer_symbols(price_trans_symbols[exc], symbol)}", frequency=0.5) for exc in
     heartbeat_pair for symbol in heartbeat_pair[exc]]
    while True:
        try:
            now_time = time.time()
            data_mappings = global_variable.G_SYMBOL_TRADE_PRICES
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
                    i_live_transit_station("item_instance", f"{exchange}-{symbol}", frequency=0.5)
                logger.info(f"{exchange =} {len(symbol_data_mappers)}",)
            await libs_price_async.rs_update_price(send_data)
            if time.time()-now_time < 0.2:
                i_live_transit_station("main_instance", frequency=0.5)
        except Exception as e:
            msg = f'实时成交价存入redis报错 {e} {traceback.format_exc()}'
            logger.error(msg)
            await recode_msg.recode_error_msg(msg, "depth_price")

        finally:
            await asyncio.sleep(0.197)


async def main():
    tasks = []
    for ex, target_ex_symbols in price_market_ex_symbols.items():
        global_variable.G_SYMBOL_TRADE_PRICES[ex] = {}
        if not target_ex_symbols:
            continue
        target_ex_symbols = list(target_ex_symbols)
        heartbeat_pair[ex] = target_ex_symbols
        ex_symbol_number = len(target_ex_symbols)
        part_symbol_number = EXCHANGE_MAX_SUB_PER_WS.get(ex, EXCHANGE_MAX_SUB_DEFAULT)
        for i in range(int(ex_symbol_number / part_symbol_number) + 1):
            target_ex_part_symbol = target_ex_symbols[part_symbol_number * i:part_symbol_number * (i + 1)]
            if not target_ex_part_symbol:
                continue
            if not hasattr(price_libs, f"get_{ex}_trades"):
                continue
            price_libs_function = getattr(price_libs, f"get_{ex}_trades")

            tasks.append(asyncio.create_task(price_libs_function(price_trans_symbols[ex], target_ex_part_symbol,
                                                                 monitor=f"价格服务_中心化|{ex}现货实时成交价订阅服务{i}")))

    # trade_thread_list.extend([Thread(target=get_bitfinex_trades, args=(trans_symbols, libs_config.price_symbols_pair["bitfinex_symbols"])), ])
    tasks.append(asyncio.create_task(symbol_trade_price_2_db(monitor="价格服务_中心化|现货实时成交价存redis"),))
    tasks.append(asyncio.create_task(heart_monitor_async()))

    for i in tasks:
        await i

if __name__ == '__main__':
    asyncio.run(main())
