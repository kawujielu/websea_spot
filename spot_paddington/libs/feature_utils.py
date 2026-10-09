from many_configs import global_variable
from loguru import logger


async def get_currency_exposure(currency):
    return (float(global_variable.ABC_POSITIONS.get(currency, 0)) +
            float(global_variable.EXTERNAL_POSITIONS.get(currency, 0)) +
            float(global_variable.DEPOSIT_WITHDRAW_POSITIONS.get(currency, 0)))


async def in_threshold_decision(currency, mark_price):
    if currency in ["EURQ", "EURR", "DYDX"]:
        return False
    in_threshold_pnl_section = [0.01, 0.02]
    min_market_value = 50
    exposure = await get_currency_exposure(currency)
    avg_price = global_variable.ABC_POSITIONS_AVG_PRICE.get(currency, 0)

    if mark_price * abs(exposure) < min_market_value or (not avg_price):
        return False
    # 如果对冲需要买入 亏损大于x1 or 盈利大于x2
    if exposure < 0 and (mark_price / avg_price - 1 > in_threshold_pnl_section[0] or avg_price / mark_price - 1 > in_threshold_pnl_section[1]):
        logger.info(f"{currency=} {exposure=} {mark_price=} {avg_price=} exceed threshold value")
        return True
    # 如果对冲需要卖出，亏损大于x1 or 盈利大于x2
    elif exposure > 0 and (avg_price / mark_price - 1 > in_threshold_pnl_section[0] or mark_price / avg_price - 1 > in_threshold_pnl_section[1]):
        logger.info(f"{currency=} {exposure=} {mark_price=} {avg_price=} exceed threshold value")
        return True
    else:
        return False
