from libs import libs_price
from spot_2 import a
symbols_info = list(a.keys())
for symbol in symbols_info:
    print(symbol)
    libs_price.redis_db_market_price.delete(symbol)
    libs_price.redis_db_askbid_price.delete(symbol)
    libs_price.redis_db_gears.delete(symbol)
