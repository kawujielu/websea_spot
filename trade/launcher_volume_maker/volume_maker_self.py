# -- 不能注释，此导入为初始化
import initialization
# ---
import asyncio
from ws_libs.volume_trade_add_contract import add_contract_self_chief
from ws_libs.volume_trade_add import add_trade_self_chief
from ws_libs.ws_abc_depth import async_abc_ask_bid_price_ws
from ws_libs.ws_abc_contract_depth import async_abc_contract_ask_bid_price_ws
from many_configs.abc_config import abc_accounts
from libs.heartbeat import heart_monitor_async
from many_configs.spot_currency_config import volume_self_symbols
from many_configs.contract_currency_config import volume_self_contract_symbols
import traceback

CUR_VOLUME_ZONE = "SELF"
CUR_MAIN_SERVER = "刷量"


async def main_maker_self():
    try:
        tasks = []
        if volume_self_symbols:
            tasks.append(asyncio.create_task(
                add_trade_self_chief(abc_accounts, volume_self_symbols,
                                     monitor=f"{CUR_MAIN_SERVER}_下单|{CUR_VOLUME_ZONE}现货")))
            tasks.append(asyncio.create_task(
                async_abc_ask_bid_price_ws(volume_self_symbols,
                                           monitor=f"{CUR_MAIN_SERVER}_ws订阅abc买卖一|{CUR_VOLUME_ZONE}现货")))
        if volume_self_contract_symbols:
            tasks.append(asyncio.create_task(
                add_contract_self_chief(volume_self_contract_symbols,
                                        monitor=f"{CUR_MAIN_SERVER}_下单|{CUR_VOLUME_ZONE}合约")))
            tasks.append(asyncio.create_task(
                async_abc_contract_ask_bid_price_ws(volume_self_contract_symbols,
                                                    monitor=f"{CUR_MAIN_SERVER}_ws订阅abc买卖一|{CUR_VOLUME_ZONE}合约")))

        tasks.append(asyncio.create_task(heart_monitor_async()))

        for t in tasks:
            await t
    except BaseException as e:
        print(f"{traceback.format_exc()}")
    finally:
        pass


if __name__ == '__main__':
    """
        # 注意：自刷量由对标刷量统一撤单
    """
    asyncio.run(main_maker_self())
