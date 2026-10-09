import asyncio
import traceback
from config import MSG_TYPES
from libs import recode_msg
from libs import libs_price_async


async def push_sentry_msg(msg_key, msg):
    await libs_price_async.redis_db_heart_beat.async_connection.lpush(msg_key, msg)
    await libs_price_async.redis_db_heart_beat.async_connection.ltrim(msg_key, 0, 100)


async def get_sentry_msg(msg_key):
    return await libs_price_async.redis_db_heart_beat.async_connection.lrange(msg_key, 0, -1)


async def send_errors():
    while True:
        for msg_type in MSG_TYPES:
            try:
                res = await libs_price_async.redis_db_heart_beat.async_connection.lrange(MSG_TYPES[msg_type], 0, -1)
                await libs_price_async.redis_db_heart_beat.async_connection.delete(MSG_TYPES[msg_type])
                if res:
                    await recode_msg.recode_error_msg(str(res), 'send_telegram_important_msg_url')
            except (Exception, BaseException) as e:
                print(f"{repr(e)} {traceback.format_exc()}")
        await asyncio.sleep(10)


def launcher_errors():
    asyncio.run(send_errors())


if __name__ == "__main__":
    # asyncio.run(push_sentry_msg("TIMEOUT", "test"))
    asyncio.run(send_errors())
