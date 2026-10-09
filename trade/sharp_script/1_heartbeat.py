from libs import libs_price
#symbols_info = [('BLZ-USDT', 0.15401), ('YGG-USDT', 0.49455), ('HIFI-USDT', 0.5185), ('QNT-USDT', 70.021), ('ALGO-USDT', 0.1425), ('KAVA-USDT', 0.36532), ('CHZ-USDT', 0.06091), ('ZEC-USDT', 41.44), ('KLAY-USDT', 0.1738), ('FXS-USDT', 2.2582), ('MINA-USDT', 0.50697), ('BIGTIME-USDT', 0.0901), ('ASTR-USDT', 0.074034), ('BAND-USDT', 1.2387), ('LOOM-USDT', 0.0501), ('WOO-USDT', 0.17965), ('ORBS-USDT', 0.02654), ('WAXP-USDT', 0.03618), ('BNT-USDT', 0.537), ('LQTY-USDT', 0.9342), ('SPELL-USDT', 0.00059015), ('MASK-USDT', 2.2629), ('ACH-USDT', 0.021724), ('AGLD-USDT', 0.93583), ('LINA-USDT', 0.004793)]
symbols_info =  [('BTC-USDT', None), ('ETH-USDT', None), ('ADA-USDT', None)]
for symbol, price in symbols_info:
    for i in ["NEAR", "DEFENSE", "DEPTH"]:
        libs_price.redis_db_heart_beat.hdel("HEART_BEAT_CONTRACT_TRADE", f"{symbol}|{i}")

