import copy
import libs
from libs import currency_feature

SPOT_CURRENCY_CONFIG = libs.libs_config.SPOT_CURRENCY_CONFIG
volume_zone_all_symbols = libs.libs_config.spot_zone_all_symbols
volume_zone_symbols = libs.libs_config.volume_zone_symbols
volume_zone_exchange_symbols = libs.libs_config.volume_zone_exchange_symbols
volume_exchange_symbols = libs.libs_config.volume_exchange_symbols
volume_currency_exchange = libs.libs_config.volume_currency_exchange
currency_conf_danger_symbols = libs.libs_config.currency_conf_danger_symbols

volume_trans_symbols_currency = libs.libs_config.volume_trans_symbols_currency

volume_self_symbols = libs.libs_config.volume_self_symbols

price_market_ex_symbols = libs.libs_config.price_market_ex_symbols
price_trans_symbols = libs.libs_config.price_trans_symbols
price_depth_ex_symbols = libs.libs_config.price_depth_ex_symbols
price_depth_ex_abc_symbols = libs.libs_config.price_depth_ex_abc_symbols

spec_symbol_rate_mapping = libs.libs_config.SPEC_SYMBOL_RATE_MAPPING

# ------------------------ 现货配置相关 ------------------------ #

# 刷量配置
# 分区循环的的sleep时间的加权值
SLEEP_RAND_WEIGHT_MAPPINGS = {
    "USDT": [1, 3],
    "ETH": [1.5, 2],
    "BTC": [1.5, 2],
    "SELF_TRADE": [0.7, 1.4],
}

base_sleep_time = 2
sleep_ratio = 2
special_base_sleep_time = {
    "BTC-USDT": 0.5,
    "ETH-USDT": 1,
}


self_base_sleep_time = base_sleep_time * sleep_ratio * 3
SYMBOL_SLEEP_TIME = {}
SELF_SYMBOL_SLEEP_TIME = {}
SUBSTITUTE_TIME = {}
for currency in libs.libs_config.SPOT_CURRENCY_CONFIG.keys():
    level = currency_feature.currency_dangerous_level(currency)

    for z, p in [('USDT', 1), ('ETH', 5), ('BTC', 5)]:
        s = f"{currency}-{z}"
        SYMBOL_SLEEP_TIME[s] = special_base_sleep_time.get(s, base_sleep_time) * max(int(p * level * sleep_ratio), 1)  # 时间必须为base_sleep_time整数倍
        SELF_SYMBOL_SLEEP_TIME[s] = self_base_sleep_time * min(p * level, 10)  # 时间必须为self_base_sleep_time整数倍
        SUBSTITUTE_TIME[s] = SELF_SYMBOL_SLEEP_TIME[s]


# 买卖一价格刷量配置，目前没有使用，主动买卖一成交，可能有套利行为
ASK_BID_DISTANCE = {
    "BTC-USDT": 0.0001 / 2,
    "ETH-USDT": 0.0005 / 2,
    "EOS-USDT": 0.0008 / 2,
}

# 刷量对标交易区的数量*1/n
TRADE_AREA_AVG_MAPPINGS = {
    "USDT": 0.6,
    "ETH": 1 / 80,
    "BTC": 1 / 80,
}
TRADE_AREA_AVG_MAPPINGS_INI = copy.deepcopy(TRADE_AREA_AVG_MAPPINGS)

# 对标外部控制
amount_rate = 2  # 对标外部交易所数量系数

# 新上线交易对需要控制刷量，所以设定上线时间让程序知道当前刷量的控制逻辑
OPEN_TIME = libs.libs_config.volume_currency_open_time

# 刷量控制
NORMAL_FOLLOW_CURRENCY = [
    'BTC', 'ETH', 'EOS', 'ADA', 'LTC',
    'TRX', 'XRP', "DASH",
    "QTUM", "BSV", "VET",
    "LINK", "OMG",
    "XLM", "ETC", "ZEC", 'BCH', "FIL"
]


ARBITRAGE_DEFAULT = 0.01

ARBITRAGE_CURRENCY = {
    "MINIDOGE": 0.05,
    "BABYDOGE": 0.05,
    "DOG": 0.05,
    "PIG": 0.03,
    "TRIBE": 0.02,
    "SAKE": 0.035,
    "BAMBOO": 0.035,
    "DPR": 0.03,
    "KISHU": 0.03,
    "YOOSHI": 0.05,
    "DOGEZILLA": 0.05,
}

VOLUME_EXCHANGE_SPOT_KEY_DATA = {"bn": "q",
                                 "hb": "amount",
                                 "okex": "sz",
                                 "gate": "amount",
                                 }
