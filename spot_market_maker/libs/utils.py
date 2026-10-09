import numpy as np
import traceback
import asyncio
from many_config import global_variable
from libs import libs_price_async
import ujson
from loguru import logger


def digit_to_string(d):
    return np.format_float_positional(d, trim='-')


async def subscribe_update_signal():
    while True:
        try:
            await libs_price_async.redis_db_contract_price.async_pubsub.subscribe("publish_contract_signal")
            while True:
                message = await libs_price_async.redis_db_contract_price.async_pubsub.listen()
                logger.info(f"subscribe_update_signal {message}")
                if message["type"] == "message" and message["channel"] == "publish_contract_signal":
                    data = ujson.loads(message["data"])
                    for i in data["currencies"]:
                        global_variable.PRICE_UPDATE_SIGNAL[i] = data["update_time"]
                await asyncio.sleep(0.01)
        except Exception as e:
            logger.error(f"{traceback.format_exc()}")
            await asyncio.sleep(1)
