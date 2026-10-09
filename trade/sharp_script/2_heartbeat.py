from libs import libs_price
from spot_2 import a
symbols_info = list(a.keys())
for symbol in symbols_info:
    for i in ["NEAR", "DEFENSE", "DEPTH"]:
        print(f"{symbol}|{i}")
        libs_price.redis_db_heart_beat.hdel("HEART_BEAT_TRADE", f"{symbol}|{i}")

