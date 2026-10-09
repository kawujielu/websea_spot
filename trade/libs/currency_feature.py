import time
from libs import libs_price_async, libs_config
import random

price_cache_update = {}


async def update_currency_market_value(currency):
    symbol = f"{currency}-USDT"
    try:
        update_time = price_cache_update.get(symbol, {}).get("update_time", 0)
        time_now = time.time()
        # 错峰请求，12小时到24小时随机更新时间
        if time_now - update_time > random.uniform(60 * 60 * 12, 60 * 60 * 24):
            avg_price = await libs_price_async.get_weight_price(symbol)
            price_cache_update[symbol] = {
                "update_time": time.time(),
                "price": avg_price
            }
        return price_cache_update[symbol]["price"]
    except BaseException as e:
        print("update_currency_market_value", repr(e))


def currency_dangerous_level(currency):
    contract_level = libs_config.CONTRACT_CURRENCY_CONFIG.get(currency, {}).get("dangerous_level", 1)
    spot_level = libs_config.SPOT_CURRENCY_CONFIG.get(currency, {}).get("dangerous_level", 1)
    level = max(int(contract_level), int(spot_level))
    return level


async def get_currency_rate_cache(symbol):
    from many_configs import global_variable

    if time.time() - global_variable.CURRENCY_RATE_CACHE.get(f"{symbol}update", 0) > 600:
        try:
            price = await libs_price_async.get_weight_price(symbol)
            global_variable.CURRENCY_RATE_CACHE[symbol] = price
            global_variable.CURRENCY_RATE_CACHE[f"{symbol}update"] = time.time()
        except BaseException as e:
            if symbol in global_variable.CURRENCY_RATE_CACHE:
                return global_variable.CURRENCY_RATE_CACHE[symbol]
            else:
                raise e

    return global_variable.CURRENCY_RATE_CACHE[symbol]


async def get_currency_price_u(symbol, price):
    quote = symbol.split("-")[1]
    if quote == "USDT":
        price_u = price
    else:
        rate = await get_currency_rate_cache(f"{quote}-USDT")
        price_u = price * rate

    return price_u
