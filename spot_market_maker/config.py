import sys
from many_config import risk_control_c
from many_config.precision_config import get_spot_precision
from libs import libs_account, libs_config


SPOT_CURRENCY_CONFIG = libs_config.SPOT_CURRENCY_CONFIG

symbols_USDT = libs_config.spot_zone_all_symbols.get("USDT", [])
symbols_BTC = libs_config.spot_zone_all_symbols.get("BTC", [])
symbols_ETH = libs_config.spot_zone_all_symbols.get("ETH", [])

ALL_SYMBOLS = symbols_USDT + symbols_BTC + symbols_ETH
ALL_CURRENCYS = list(SPOT_CURRENCY_CONFIG.keys())

# 使用买卖一中间件作为市场价，MAX(买卖一价差, 自设定基础)作为盘口价差
SYMBOLS_USE_ASK1_BID1 = [i.split("-")[0] for i in ALL_SYMBOLS if i.split("-")[0] not in ["BTC", "ETH", "USDT", ]]

ExchangeCode = libs_config.ExchangeCode
# 对标火币 币安等交易所的前N档深度
except_symbols = ["USDC-USDT", "BUSD-USDT", "HUSD-USDT"]
USE_GEAR_SYMBOLS = libs_config.price_market_ex_symbols.get(ExchangeCode.bn.value, set()) | libs_config.price_depth_ex_symbols.get(ExchangeCode.bn.value, set())
USE_GEAR_SYMBOLS = list(set([i.split("-")[0] for i in USE_GEAR_SYMBOLS if i not in except_symbols]))
USE_GEAR_SYMBOLS = [f"{ii}-{i}" for i in ["USDT"] for ii in USE_GEAR_SYMBOLS]

currency_conf_danger_currency = libs_config.currency_conf_danger_currency


# try:
#     sys.argv[2]
# except:
#     DEBUG = True
#     # raise KeyError
# else:
#     DEBUG = True if sys.argv[2] == "DEBUG=True" else False

DEBUG = libs_config.DEBUG

try:
    serverArgv = sys.argv[2]
except:
    raise KeyError('启动参数必须携带sys.argv[2]')
else:
    server = serverArgv.split("=")[1]

if DEBUG:
    CancelWarningTime = 10
    # host = "https://exq.wbstests.net"  # test env
    host = "https://exq.wbspre.net"  # pre env

    ipMapping = {}

else:
    CancelWarningTime = 3.9
    host = "https://exqv.websea.work"

    USDT_amount = 1

    ipMapping = {
        # ip link | grep link/ether 查看设备，因为测试环境和线上环境不在同一个局域网内，使用ip判断可能有冲突

        # USDT交易对
        "ip-10-0-208-182-1": symbols_USDT[:50],
        "ip-10-0-209-47-1": symbols_USDT[50:],

        "ip-10-0-208-197-1": symbols_BTC[:],

        # "06:38:a6:33:73:7b-2": [i for i in symbols_USDT if symbols_USDT.index(i) % USDT_amount == 1],


    }


# 获取对应策略账号
near_strategy_account = [
    {'token': libs_account["maker_near"]["token"], 'secret_key': libs_account["maker_near"]["sk"]},
    {'token': libs_account["maker_near_second"]["token"],
     'secret_key': libs_account["maker_near_second"]["sk"]}, ]  # maker_near
depth_strategy_account = [
    {"token": libs_account["maker_depth"]["token"], "secret_key": libs_account["maker_depth"]["sk"]},
    {"token": libs_account["maker_depth_second"]["token"], "secret_key": libs_account["maker_depth_second"]["sk"]},
]  # maker_depth
defense_strategy_account = [
    {'token': libs_account["maker_defense"]["token"], 'secret_key': libs_account["maker_defense"]["sk"]},
    {'token': libs_account["maker_defense_second"]["token"], 'secret_key': libs_account["maker_defense_second"]["sk"]},

]  # maker_defense

accounts = [near_strategy_account[0], depth_strategy_account[0], defense_strategy_account[0]]

# 获取当前服务器运行的交易对
default_symbols = ["BTC-USDT", "ETH-USDT"]
symbols = ipMapping.get(f"{libs_config.IMPRINGTING}-{server}", default_symbols)

SYMBOLS_ORDER_CONDITION = get_spot_precision(host)

"""

不同的价格变化比 对应的最小者调整系数和最大者调整系数
    rate:       （最新价格-上次价格)/上次价格
    min_rate：   档位最小加权倍数
    max_rate：   档位最大加权倍数
"""
price_rate_configs = [
    # 请保持rate的顺序排序
    {'rate': 0, 'min_rate': 0.95, "max_rate": 1.11},
    {'rate': 0.0003, 'min_rate': 0.9, "max_rate": 1.15},
    {'rate': 0.0005, 'min_rate': 0.87, "max_rate": 1.19},
    {'rate': 0.0007, 'min_rate': 0.85, "max_rate": 1.25},
    {'rate': 0.0009, 'min_rate': 0.8, "max_rate": 1.3},
]

price_rate_configs = sorted(price_rate_configs, key=lambda i: i['rate'])

# 支持闪单的交易对
NEAR_FLASH_SYMBOL = symbols_USDT


# 大单价值U
LARGE_ORDER_VALUE_DEFAULT = 20000
large_order_value = {
    "OKT": 19000,
    "OKB": 36000,
    "BIGTIME": 17000,
    "ALCX": 35000,
    "TOKEN": 46000,
    "SLN": 2300,
}

# 大单价差位置
BIG_ORDER_PERCENT_DEFAULT = 0.06
BIG_ORDER_PERCENT = {
    "OKT": 0.016,
    "OKB": 0.016,
    "BIGTIME": 0.014,
    "ALCX": 0.014,
    "TOKEN": 0.014,
    "SLN": 0.016,
}

# 根据币种危险等级处理其大单价值
for i in currency_conf_danger_currency:
    dangerous_level = SPOT_CURRENCY_CONFIG[i]["dangerous_level"]
    risk_control = risk_control_c.dangerous_scaled_percent[dangerous_level]["near"]
    
    if i not in large_order_value:
        large_order_value[i] = LARGE_ORDER_VALUE_DEFAULT * max(min(1.0, 1 / risk_control), 0.1)
    if i not in BIG_ORDER_PERCENT:
        BIG_ORDER_PERCENT[i] = BIG_ORDER_PERCENT_DEFAULT * risk_control * 1.5


DEPTH_BIG_ORDER_PERCENT_DEFAULT = 0.5
DEPTH_BIG_ORDER_PERCENT = {

}

BIG_ORDERS = {
    BIG_ORDER_PERCENT_DEFAULT: BIG_ORDER_PERCENT,
    DEPTH_BIG_ORDER_PERCENT_DEFAULT: DEPTH_BIG_ORDER_PERCENT,
}


ask1_bid1_add_percent = 1.1  # 价差是外部对标的价差的1.1倍

AIOHTTP_LIMITS_STRATEGY = {
    "DEPTH": 1,
    "DEFENSE": 1,
    "NEAR": 3,
}

AIOHTTP_BASE_SYMBOL_LIMITS = 4

MSG_TYPES = {
    "TIMEOUT": "TIMEOUT",
    "EXCEPTION": "EXCEPTION"
}

print("测试环境运行中" if DEBUG else "线上环境运行中")
