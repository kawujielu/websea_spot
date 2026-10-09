import time
import config
from libs import libs_price, libs_config


def polaris_scale(symbol):
    return 1
    currency = symbol.split("-")[0]
    currency_update = "{}-update".format(currency, )
    if currency in libs_config.adj_support_list:
        if int(time.time()) - config.price_polaris.get(currency_update, 0) > 6:
            try:
                val = libs_price.redis_db_adj.get("polaris-{}".format(currency, ))
                config.price_polaris[currency] = float(val) if val else 1
            except:
                config.price_polaris[currency] = 1
            config.price_polaris[currency_update] = int(time.time())

        scale = min(float(config.price_polaris.get(currency, 1)), config.max_adj_scale)
    else:
        scale = 1
    return scale
