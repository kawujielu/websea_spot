from many_configs.spot_currency_config import SPOT_CURRENCY_CONFIG
from many_configs.contract_currency_config import CONTRACT_CURRENCY_CONFIG
from many_configs.precision_config import spot_price_precision, contract_price_precision
import contextvars

# A 的现货盘口ws推送过来的买卖一价格
ABC_ASK_BID_PRICE_CONTAINER = {}

# A 合约盘口ws推送过来的买卖一价格
ABC_CONTRACT_ASK_BID_PRICE_CONTAINER = {}

# 存放外部交易所对标的买卖一价格，供现货保存买卖一价格提供各交易所最大买卖一，以及合约计算对标价格
G_SYMBOL_ASK_BID_PRICES = {}

# 存放外部交易所前N档的档位信息，用于映射盘口
G_SYMBOL_GEAR20 = {}

# 存放现货对标外部交易所的实时成交价
G_SYMBOL_TRADE_PRICES = {}

# 存放现货对标外部交易所的买卖一计算的市场价
G_SYMBOL_DEPTH_PRICES = {}

# 存放交易对跟随外部交易所的资金费率的值
G_FOLLOW_EXCHANGE_FUNDING_RATE = {}

# 存放合约外部交易所买卖加权价格
G_CONTRACT_PRICE_BY_CONTRACT_ASK_BID = {}

# 现货上一次的买卖一的价格
LAST_SYMBOLS_AB_MAPPINGS = {}

# 上次下单的时间
LAST_ORDER_TIME_MAPPING = {
    "symbols": {},
    "part": "None"

}

# 现货 合约价格精度
SYMBOLS_ORDER_CONDITION = spot_price_precision()
SYMBOLS_CONTRACT_CONDITION = contract_price_precision()

# ----------- 刷量控制相关全局变量 -----------  #
G_TRADE_CURRENCY_CONFIG = SPOT_CURRENCY_CONFIG
G_CONTRACT_TRADE_CURRENCY_CONFIG = CONTRACT_CURRENCY_CONFIG

# ----------- 热更新相关全局变量 -----------  #

# 去中心化节点
BLOCK_NODE = {}
BLOCK_NODE_LAST = {}

# -----------  心跳监控全局变量 ----------- #
# 保存线程和心跳记录的关系
ZEUS_MONITOR_THREAD_MAPPER = {

}
ZEUS_MONITOR = {

}

AUTO_ADJ_FREQUENCY = {
    "MARKET_PRICE": {
        # "BTC": {"diff_list": [], "latest_rev": 123456}
    }
}

# 监控山下文变量
monitor = contextvars.ContextVar('monitor')
monitor.set({})

#  刷量服务进程间数据共享
SHARE_VOLUME_MAKER_SYMBOLS = {}
SHARE_VOLUME_MAKER_SYMBOLS_KEY = "share_v_m_s"

# 错误消息共享内存
SHARE_ERROR_MESSAGES = {}
SHARE_ERROR_MESSAGES_KEY = "share_e_m"

# 行情价格数据
SYMBOLS_PRICE_5MIN = {}

# 因为下单太小，合并多次下单
SYMBOLS_SMALL_ORDER_TIMES = {
    "contract": {}
}

# 做市价差
PRICE_PERCENT = {}
REDIS_PRICE_PERCENT = {}

# 标记价格
MARK_PRICE = {}

# 特殊币种价格缓存
CURRENCY_RATE_CACHE = {}
