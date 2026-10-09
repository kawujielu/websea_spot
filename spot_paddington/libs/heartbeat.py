import time
import json
import libs


HEART_BEAT_KEY = "HEART_BEAT"
SERVER_SEND_LIMIT = {}
SEND_MIN_TIME = 5

redis_db = libs.libs_price_async.redis_db_heart_beat


async def i_live_well(server, frequency, index):
    if time.time() - SERVER_SEND_LIMIT.get(server, 0) > SEND_MIN_TIME:
        await redis_db.async_connection.hset(HEART_BEAT_KEY, server, json.dumps({'send_time': time.time(),
                                                                                 'frequency': frequency,
                                                                                 "index": index,
                                                                                 "sos": "**"}))

        SERVER_SEND_LIMIT[server] = time.time()


async def i_live_not_well(error_msg, server, frequency, index, sos="**"):
    error_msg = "、".join(error_msg)
    error_server = server + "_error_update"
    if (not libs.libs_config.DEBUG) and (time.time() - SERVER_SEND_LIMIT.get(error_server, 0) > SEND_MIN_TIME):
        print("i_live_not_well----", time.time())
        await redis_db.async_connection.hset(HEART_BEAT_KEY, server,
                                             json.dumps({'send_time': 0,
                                                         'frequency': frequency,
                                                         "index": index,
                                                         "sos": sos,
                                                         "note": error_msg}))

        SERVER_SEND_LIMIT[error_server] = time.time()
