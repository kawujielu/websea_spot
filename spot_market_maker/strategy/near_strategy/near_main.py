import time
import traceback
from strategy.near_strategy import near_base as mm, near_settings as ss
from config import symbols, SPOT_CURRENCY_CONFIG
from abcapi_plus import AbcApi
import asyncio
from many_config import initializer
from many_config.aiohttp_limits import get_aiohttp_limits
from libs import utils


async def run_markets():
    strategy = [asyncio.create_task(utils.subscribe_update_signal())]
    symbol_account = []
    symbol_account_second = []
    # 因为近盘口一般的交易对由远盘口策略分担
    near_symbols = symbols[:len(symbols)//2]
    for symbol in near_symbols:
        currency = symbol.split("-")[0]

        if SPOT_CURRENCY_CONFIG.get(currency, {}).get("use_account", "") == "2":
            symbol_account_second.append(symbol)
        else:
            symbol_account.append(symbol)

    account = AbcApi(**ss.account[0], limit=get_aiohttp_limits(len(symbol_account), ss.NAME))
    account_second = AbcApi(**ss.account[1], limit=get_aiohttp_limits(len(symbol_account_second), ss.NAME))

    for symbol in symbol_account:
        strategy.append(asyncio.create_task(mm.run(symbol, account)))
    for symbol in symbol_account_second:
        strategy.append(asyncio.create_task(mm.run(symbol, account_second)))

    for s in strategy:
        await s


def run():
    while True:
        try:
            initializer.init_share_memory()
            asyncio.run(run_markets())
        except:
            print(f"near-loop - {traceback.format_exc()}")
            time.sleep(2)


if __name__ == '__main__':
    run()
