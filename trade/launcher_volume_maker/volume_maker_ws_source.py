# -- 不能注释，此导入为初始化
import initialization
# ---
import traceback
import asyncio
from ws_libs import ws_volume_market_kline
from many_configs.spot_currency_config import volume_zone_symbols, volume_exchange_symbols, \
    volume_trans_symbols_currency
from many_configs.contract_currency_config import volume_zone_contract_symbols
from many_configs.base_config import EXCHANGE_MAX_SUB_PER_WS, EXCHANGE_MAX_SUB_DEFAULT
from many_configs import global_variable, initializer
from libs.heartbeat import heart_monitor_async
from libs.recode_msg import send_error_msg

CUR_MAIN_SERVER = "刷量"


async def main_maker_ws_source():
    try:
        initializer.init_share_memory()

        for zone in volume_zone_symbols:
            for c_symbol in volume_zone_symbols[zone]:
                if c_symbol not in global_variable.SHARE_VOLUME_MAKER_SYMBOLS:
                    global_variable.SHARE_VOLUME_MAKER_SYMBOLS[c_symbol] = 0
                    global_variable.SHARE_VOLUME_MAKER_SYMBOLS[f"{c_symbol}_update"] = 0

        for zone in volume_zone_contract_symbols:
            for c_symbol in volume_zone_contract_symbols[zone]:
                contract_c_symbol = f"c_{c_symbol}"
                if contract_c_symbol not in global_variable.SHARE_VOLUME_MAKER_SYMBOLS:
                    global_variable.SHARE_VOLUME_MAKER_SYMBOLS[contract_c_symbol] = 0
                    global_variable.SHARE_VOLUME_MAKER_SYMBOLS[f"{contract_c_symbol}_update"] = 0

        tasks = []
        for ex, target_ex_symbols in volume_exchange_symbols.items():
            part_symbol_number = EXCHANGE_MAX_SUB_PER_WS.get(ex, EXCHANGE_MAX_SUB_DEFAULT)

            target_ex_symbol_number = len(target_ex_symbols)
            for i in range(int(target_ex_symbol_number / part_symbol_number) + 1):
                target_ex_part_symbol = target_ex_symbols[part_symbol_number * i:part_symbol_number * (i + 1)]
                if target_ex_part_symbol:
                    if not hasattr(ws_volume_market_kline, f"get_{ex}_trades"):
                        continue
                    volume_maker_function = getattr(ws_volume_market_kline, f"get_{ex}_trades")

                    tasks.append(asyncio.create_task(
                        volume_maker_function(global_variable.SHARE_VOLUME_MAKER_SYMBOLS,
                                              volume_trans_symbols_currency, target_ex_part_symbol,
                                              volume_zone_symbols, volume_zone_contract_symbols,
                                              monitor=f"{CUR_MAIN_SERVER}_ws订阅|{ex}")))

        tasks.append(asyncio.create_task(heart_monitor_async()))
        tasks.append(asyncio.create_task(send_error_msg()))

        for t in tasks:
            await t
    except BaseException as e:
        print(f"{traceback.format_exc()}")
    finally:
        pass


if __name__ == "__main__":
    asyncio.run(main_maker_ws_source())
