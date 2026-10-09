# -- 不能注释，此导入为初始化
import initialization
# ---
import sys
import asyncio
from ws_libs.volume_trade_add import cancel_order, add_trade_chief
from ws_libs.volume_trade_add_contract import cancel_contract_order, add_contract_trade_chief
from many_configs.spot_currency_config import volume_zone_symbols, volume_zone_all_symbols, volume_currency_exchange
from many_configs.contract_currency_config import volume_zone_contract_symbols, volume_zone_all_contract_symbols
from ws_libs.ws_abc_depth import async_abc_ask_bid_price_ws
from ws_libs.ws_abc_contract_depth import async_abc_contract_ask_bid_price_ws
from many_configs import initializer
from many_configs.abc_config import abc_accounts
from libs.heartbeat import heart_monitor_async
import traceback

CUR_MAIN_SERVER = "刷量"


async def main_maker(cur_volume_zone):
    try:
        initializer.init_share_memory()

        symbols = volume_zone_symbols.get(cur_volume_zone)
        all_symbols = volume_zone_all_symbols.get(cur_volume_zone)
        contract_symbols = volume_zone_contract_symbols.get(cur_volume_zone)
        all_contract_symbols = volume_zone_all_contract_symbols.get(cur_volume_zone)

        tasks = []
        if symbols:
            tasks.append(asyncio.create_task(
                add_trade_chief(abc_accounts, symbols, volume_currency_exchange,
                                monitor=f"{CUR_MAIN_SERVER}_下单|{cur_volume_zone}现货")))
            tasks.append(asyncio.create_task(
                async_abc_ask_bid_price_ws(symbols,
                                           monitor=f"{CUR_MAIN_SERVER}_ws订阅abc买卖一|{cur_volume_zone}现货")))
        if contract_symbols:
            tasks.append(asyncio.create_task(
                add_contract_trade_chief(contract_symbols, volume_currency_exchange,
                                         monitor=f"{CUR_MAIN_SERVER}_下单|{cur_volume_zone}合约")))
            tasks.append(asyncio.create_task(
                async_abc_contract_ask_bid_price_ws(contract_symbols,
                                                    monitor=f"{CUR_MAIN_SERVER}_ws订阅abc买卖一|{cur_volume_zone}合约")))

        # 自刷量在这里统一进行撤单，all_symbols >= symbols
        if all_symbols:
            tasks.append(asyncio.create_task(cancel_order(abc_accounts, all_symbols, monitor=f"{CUR_MAIN_SERVER}_撤单|现货")))

        if all_contract_symbols:
            tasks.append(asyncio.create_task(cancel_contract_order(all_contract_symbols, monitor=f"{CUR_MAIN_SERVER}_撤单|合约")))
        tasks.append(asyncio.create_task(heart_monitor_async()))

        for t in tasks:
            await t
    except BaseException as e:
        print(f"{traceback.format_exc()}")
    finally:
        pass


if __name__ == '__main__':
    zone = sys.argv[2]
    asyncio.run(main_maker(zone))
