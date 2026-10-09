import ujson
import asyncio
from UltraDict import UltraDict
from many_configs.share_memory_config import SHARE_MEMORY_WS_KEY, SHARE_MEMORY_HEDGE_CONFIG_KEY, \
    SHARE_ERROR_MESSAGES_KEY
from many_configs import global_variable
from core_external.market import update_ws_subscribe
from core_internal.abc_asset import abc_asset_position_instance
from core_external.external_asset import external_asset_position_instance
from core_external.deposit_withdraw_fee import deposit_withdraw_positions_instance
from scaffold.mysql import Hedge_MysqlSession
import loguru


# 没有用到
# async def reload_then_trigger():
#     # global_variable.SHARE_SYMBOL_HEDGE_CONFIG 推导 global_variable.EXCHANGE_SYMBOLS_MAPPERS
#     global_variable.EXCHANGE_SYMBOLS_MAPPERS = {}
#     for currency, hedge_config in global_variable.SHARE_SYMBOL_HEDGE_CONFIG.items():
#         # 获取增减的交易所和币种
#         hedge_exchanges = hedge_config.get('exchanges', {})
#         for ex, value in hedge_exchanges.items():
#             symbol = value['symbol']
#             symbols = global_variable.EXCHANGE_SYMBOLS_MAPPERS.get(ex, [])
#             symbols.append(symbol)
#             global_variable.EXCHANGE_SYMBOLS_MAPPERS.update({ex: symbols})
#
#     # await some_fun()
#     # 如果是ws数据订阅服务，调用其订阅or取消订阅更新交易对档订阅
#     for ex, symbols in global_variable.EXCHANGE_SYMBOLS_MAPPERS.items():
#         await update_ws_subscribe(symbols=symbols, exchange=ex, is_subscribe='subscribe')
#
#     # 如果是对冲主服务
#     # await some_hedge_fun()


async def init_share_memory():
    """
        recurse=False  只能使用 {"key1": []} 或者 {"key1": ""} 结构

    """
    global_variable.SHARE_MEMORY_WS_INSTANCE = UltraDict(name=SHARE_MEMORY_WS_KEY, auto_unlink=False,
                                                         shared_lock=True, buffer_size=500_000)
    global_variable.SHARE_SYMBOL_HEDGE_CONFIG = UltraDict(name=SHARE_MEMORY_HEDGE_CONFIG_KEY, auto_unlink=False,
                                                          shared_lock=True, buffer_size=200_000)
    global_variable.SHARE_ERROR_MESSAGES = UltraDict(name=SHARE_ERROR_MESSAGES_KEY, auto_unlink=False,
                                                     shared_lock=True, buffer_size=300_000)
    loguru.logger.info("init_share_memory -- ok")


async def init_currency_hedge():
    sql = f"SELECT * from hedge_config"
    db_config = await Hedge_MysqlSession.fetch_all(sql)
    for config in db_config:
        global_variable.SHARE_SYMBOL_HEDGE_CONFIG[config[0]] = ujson.loads(config[1])
    loguru.logger.info("init_currency_hedge -- ok")


async def init():
    await asyncio.gather(
        init_share_memory(),
        # 初始化交易对对冲配置信息
        init_currency_hedge(),
        # 初始化内部资产对冲缺口
        abc_asset_position_instance.init_position(),
        # 初始化外部资产对冲缺口
        external_asset_position_instance.init_position(),
        # 初始化外部钱包数据
        external_asset_position_instance.init_wallet(),
        # 初始化充提手续费
        deposit_withdraw_positions_instance.init_position()
    )
    loguru.logger.info("init -- ok")


async def init_for_ws():
    await asyncio.gather(
        init_share_memory(),
        # 初始化交易对对冲配置信息
        init_currency_hedge()
    )
    loguru.logger.info("init_for_ws -- ok")


if __name__ == "__main__":
    asyncio.run(init())
