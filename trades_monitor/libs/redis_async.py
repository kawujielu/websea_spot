from redis import StrictRedis as SyncStrictRedis
from aredis import StrictRedis

# CONFIG_REDIS = {
#     "host": "market-price-1-001.market-price-1.sg6zxz.apse1.cache.amazonaws.com",
#     "password": "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2>r,v9rsl+B-SUsQBQYC6*yA",
#     "db": 15,
#     "port": 6379,
# }

CONFIG_REDIS = {
    "host": "54.95.241.223",
    "password": "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2>r,v9rsl+B-SUsQBQYC6*yA",
    "db": 15,
    "port": 6379,
}

# CONFIG_PRICE_REDIS = {
#     "host": "market-price-1-001.market-price-1.sg6zxz.apse1.cache.amazonaws.com",
#     "password": "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2>r,v9rsl+B-SUsQBQYC6*yA",
#     "db": 1,
#     "port": 6379,
# }

CONFIG_PRICE_REDIS = {
    "host": "54.95.241.223",
    "password": "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2>r,v9rsl+B-SUsQBQYC6*yA",
    "db": 1,
    "port": 6379,
}


class RedisAsync(object):

    async def async_connection(self):
        if self._async_connection is None:
            self._async_connection = StrictRedis(host=self.redis_config["host"],
                                                 db=self.redis_config["db"],
                                                 port=self.redis_config["port"],
                                                 password=self.redis_config["password"],
                                                 connect_timeout=3,
                                                 timeout=3,
                                                 encoding='utf-8',
                                                 decode_responses=True)

        return self._async_connection

    def __init__(self, redis_config):
        self.redis_config = redis_config
        self._async_connection = None


redisClient = SyncStrictRedis(host=CONFIG_PRICE_REDIS["host"],
                              password=CONFIG_PRICE_REDIS["password"],
                              port=CONFIG_PRICE_REDIS["port"],
                              db=CONFIG_PRICE_REDIS["db"],
                              decode_responses=True,
                              socket_connect_timeout=2,
                              socket_timeout=2)

redis_db = RedisAsync(CONFIG_REDIS)
