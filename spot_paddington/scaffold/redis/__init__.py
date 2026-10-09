import threading
import ssl
from aredis import StrictRedis
from libs import libs_config

if libs_config.DEBUG:
    REDIS_MASTER = ["18.140.249.184", 6379, "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2>r,v9rsl+B-SUsQBQYC6*yA"]
else:
    REDIS_MASTER = ["market-price-001.market-price.sg6zxz.apse1.cache.amazonaws.com",
                    6379,
                    "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2>r,v9rsl+B-SUsQBQYC6*yA"]

RS_CONF_CONTROL = {
    'host': REDIS_MASTER[0], 'port': REDIS_MASTER[1], 'password': REDIS_MASTER[2], 'db': 15
}


class RedisAsync(object):
    @property
    def async_connection(self):
        session_name = threading.current_thread().name
        protocol_ssl = {} if libs_config.DEBUG else {"ssl": True, "ssl_context": ssl._create_unverified_context()}

        if not self._async_connection.get(session_name):
            self._async_connection[session_name] = StrictRedis(host=self.redis_config["host"],
                                                               db=self.redis_config["db"],
                                                               port=self.redis_config["port"],
                                                               password=self.redis_config["password"],
                                                               timeout=3, connect_timeout=3,
                                                               encoding='utf-8',
                                                               decode_responses=True,
                                                               **protocol_ssl)

        return self._async_connection[session_name]

    @property
    def async_pubsub(self):
        session_name = threading.current_thread().name
        if not self._async_pubsub.get(session_name):
            self._async_pubsub[session_name] = self.async_connection.pubsub()
        return self._async_pubsub[session_name]

    def __init__(self, redis_config):
        self.redis_config = redis_config
        self._async_connection = {}
        self._async_pubsub = {}


rs_wd_instance = RedisAsync(RS_CONF_CONTROL)
