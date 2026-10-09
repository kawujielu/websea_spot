
import traceback
import loguru
import time
import json
from config import DEBUG, symbols_USDT, symbols_BTC, symbols_ETH
from libs import libs_price_async

symbols_len = len(symbols_USDT + symbols_BTC + symbols_ETH)
HEART_BEAT_KEY = "HEART_BEAT_TRADE"
SERVER_SEND_LIMIT = {}
SEND_MIN_TIME = 5


async def i_live_well(server, frequency, index, sos="**"):
    try:
        # if (not DEBUG) and (time.time() - SERVER_SEND_LIMIT.get(server, 0) > SEND_MIN_TIME):
        if time.time() - SERVER_SEND_LIMIT.get(server, 0) > SEND_MIN_TIME:
            print("i_live_well----", server, time.time())
            await libs_price_async.redis_db_heart_beat.async_connection.hset(HEART_BEAT_KEY, server, json.dumps({
                                                                                             'send_time': time.time(),
                                                                                             'frequency': frequency,
                                                                                             "index": index, "sos": sos,
                                                                                             "symbols_len": symbols_len
                                                                                         }))

            SERVER_SEND_LIMIT[server] = time.time()
    except BaseException:
        loguru.logger.info(f"i_live_well-error {traceback.format_exc()}")


if __name__ == "__main__":
    import asyncio

    async def main():
        while True:
            await i_live_well("test", 12, 123)
            await asyncio.sleep(1)

    asyncio.run(main())
