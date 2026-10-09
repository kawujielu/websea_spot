import time
import json
import redis
from libs.database.getredis import get_redis_heartbate

HEART_BEAT_KEY = "HEART_BEAT"
SERVER_SEND_LIMIT = {}
SEND_MIN_TIME = 5


async def i_live_well(server, frequency, index):
    if time.time() - SERVER_SEND_LIMIT.get(server, 0) > SEND_MIN_TIME:
        await get_redis_heartbate.hset(HEART_BEAT_KEY, server, json.dumps({'send_time': time.time(),
                                                                           'frequency': frequency,
                                                                           "index": index,
                                                                           "sos": "cc"}))

        SERVER_SEND_LIMIT[server] = time.time()


async def i_live_not_well(error_msg, server, frequency, ts, index):
    # error_msg = "、".join(error_msg)
    error_server = server + "_error_update"
    if (time.time() - SERVER_SEND_LIMIT.get(error_server, 0) > SEND_MIN_TIME):
        print("i_live_not_well----", time.time())
        await get_redis_heartbate.hset(HEART_BEAT_KEY, server,
                                       json.dumps({'send_time': ts,
                                                   'frequency': frequency,
                                                   "index": index,
                                                   "sos": "cc",
                                                   "note": error_msg}))

        SERVER_SEND_LIMIT[error_server] = time.time()
