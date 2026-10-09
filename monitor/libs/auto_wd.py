import traceback
import asyncio
from loguru import logger
from libs.database.getredis import rs_wd_instance


auto_wd_log = "[自动化充提] "

SUPPORT_CURRENCIES = ["USDT", "BTC", "ETH", "SOL", "BNB", "SPCX", "TRX", "HOME"]


async def send_wd_signal(currency, quantity, price):
    if currency == "USDT":
        quantity = max(20000, quantity)
    if currency not in SUPPORT_CURRENCIES:
        return
    try:
        ready_quantity = await rs_wd_instance.async_connection.hget("auto_wd_signal", currency)
        ready_quantity = float(ready_quantity) if ready_quantity else 0
        logger.info(f"{auto_wd_log}receive wd signal {currency=} {quantity=} {price=}")
        if ready_quantity < quantity:
            res = await rs_wd_instance.async_connection.hset("auto_wd_signal", currency, f"{quantity:.4f}")
            logger.info(f"{auto_wd_log}send_wd_signal update {res=}")
    except Exception as e:
        msg = f"send_wd_signal {traceback.format_exc()}"
        logger.error(msg)

if __name__ == "__main__":
    asyncio.run(send_wd_signal("USDT", 5, 1))
