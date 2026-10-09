import copy

import redis.asyncio as redisasyncio

from config.infor_load import libs_config, libs_price_async

CONFIG_REDIS = libs_config
RedisAsync = libs_price_async.RedisAsync

redis_config_token = copy.deepcopy(libs_config.RS_CONF_MARKET_PRICE)
redis_config_token['db'] = 9

get_redis = libs_price_async.redis_db_market_price.async_connection
get_redis_contract = libs_price_async.redis_db_contract_price.async_connection
get_redis_heartbate = libs_price_async.redis_db_heart_beat.async_connection
get_redis_swap_kline = libs_price_async.redis_db_vol.async_connection
get_redis_swap_block_number = libs_price_async.redis_db_node.async_connection
get_redis_token = RedisAsync(redis_config_token).async_connection
rs_wd_instance = libs_price_async.redis_db_control

if __name__ == '__main__':
    import asyncio

    print(libs_config.RS_CONF_MARKET_PRICE)
    # d = asyncio.run(get_redis.hgetall('BNB-USDT'))
    print(libs_price_async.redis_db_market_price)
    d = asyncio.run(get_redis.keys())
    print(d)
