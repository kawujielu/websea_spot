import copy
from config import SPOT_CURRENCY_CONFIG

# 默认价差
ASK_BID_PERCENT = 0.002

# 区默认价差
zone_percent = {
    "USDT": ASK_BID_PERCENT,
    "BTC": 0.008,
    "ETH": 0.008,
}
# 区默认平均下单量倍数关系，默认USDT为1
zone_mean_order_size_percent = {
    "USDT": 1,
    "BTC": 1/5,
    "ETH": 1/5,
}

ASK_BID_PERCENT_SPEC = {}
# 平均的档位的下单量
MEAN_ORDER_SIZE = {}
for currency, value in SPOT_CURRENCY_CONFIG.items():
    ASK_BID_PERCENT_SPEC[f"{currency}-USDT"] = zone_percent["USDT"]
    ASK_BID_PERCENT_SPEC[f"{currency}-ETH"] = zone_percent["ETH"]
    ASK_BID_PERCENT_SPEC[f"{currency}-BTC"] = zone_percent["BTC"]
    ASK_BID_PERCENT_SPEC.update(value.get("ask_bid_percent_spec", {}))
    benchmark = value["mean_order_size"][f"{currency}-USDT"]
    MEAN_ORDER_SIZE[f"{currency}-ETH"] = zone_mean_order_size_percent["ETH"] * benchmark
    MEAN_ORDER_SIZE[f"{currency}-BTC"] = zone_mean_order_size_percent["BTC"] * benchmark
    MEAN_ORDER_SIZE.update(value.get("mean_order_size", {}))


ASK_BID_PERCENT_SPEC_ORG = copy.deepcopy(ASK_BID_PERCENT_SPEC)
# 波动最小值

# 行情价差自动调节服务
adj_active = False  # 自动调整价差服务开关
max_adj_percent = 7  # 最大调节倍数
min_adj_value = 0.006 / 2  # 最小调节量
adj_support_list = []  # 支持的交易对

# 档位价差控制
START_END_PRECISION_COMMON = 0.07

START_END_PRECISION = {
    "BTC-USDT": 0.04,
    "ETH-USDT": 0.05,
    "EOS-USDT": 0.05,

    "CTXC-USDT": 0.09,
    "ONT-BTC": 0.09,
    "BTM-USDT": 0.09,
    "ELF-BTC": 0.09,
    "ZIL-USDT": 0.09,
    "ELF-USDT": 0.09,

}

MEAN_ORDER_SIZE_ORG = copy.deepcopy(MEAN_ORDER_SIZE)

# 最小的下单量

ORDER_MIN_QTY_THRESHOLD= {
    symbol: mean_order_size * 0.1 for symbol, mean_order_size in MEAN_ORDER_SIZE.items()
}

ORDER_MIN_QTY_THRESHOLD_ORG = copy.deepcopy(ORDER_MIN_QTY_THRESHOLD)



