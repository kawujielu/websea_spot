from config import AIOHTTP_LIMITS_STRATEGY, AIOHTTP_BASE_SYMBOL_LIMITS


def get_aiohttp_limits(symbols_lens, strategy_name):
    limits = int(symbols_lens * AIOHTTP_BASE_SYMBOL_LIMITS * AIOHTTP_LIMITS_STRATEGY[strategy_name])
    limits = max(limits, 10)
    limits = min(limits, 500)
    return limits
