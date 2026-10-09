import asyncio

WS_FREQUENCY = 30
RESTART_DELAY_TIME = 2 * 60
ORDER_RESTART_DELAY_TIME = 50 * 60

# 请求速度
INTERVAL = 1000
# 档位数
EXCHANGE_GEARS = {
    'bn': 20,
    'okex': 5,
    'hb': 20,
    'gate': 20,
    'mxc': 20,
    'bitget': 15,
    'kraken': 15,
}

# ABC 转other exchange
trans_okex_symbols = {
    'UNISWAP-USDT': 'UNI-USDT'
}
trans_bn_symbols = {
    'GXC-USDT': "GXS-USDT",
    'UNISWAP-USDT': 'UNI-USDT'
}
trans_gateio_symbols = {
    'GTC-USDT': 'GITCOIN-USDT',
    'DOGESWAP-USDT': 'DOG-USDT'
}

trans_hb_symbols = {
    'HUSD-USDT': 'USDT-HUSD',
}

trans_mexc_symbols = {}

trans_bitget_symbols = {}

trans_kraken_symbols = {}

# 保持每个交易所实例
EXTERNAL_EXCHANGE_INSTANCES = {}

EXCHANGE_SYMBOLS_MAPPERS = {

}

SERVICE_STATUS = False
FASTER_HEDGE = False
DEX_ACCOUNT_OR_CURRENCY_STATUS = {
    'ethereum_1': False,
    'bsc_1': False
}

DEX_CURRENCY_ERRORS_PERCENT = {}

ABC_POSITIONS = {}
EXTERNAL_POSITIONS = {}
ABC_POSITIONS_AVG_PRICE = {}
DEPOSIT_WITHDRAW_POSITIONS = {}

# 存放外部交易所钱包数据
WALLET_EXCHANGE_CURRENCY = {
    # todo: hyy 首次订阅是否返回当前资产所有数据
    # "bn":{"BTC": 10},
}

# -- 进程间共享内存 -- #
# 存放外部交易所前N档的档位信息，用于映射盘口，这是一个用于多进程数据共享的实例
SHARE_MEMORY_WS_INSTANCE = {}
# 对冲配置
SHARE_SYMBOL_HEDGE_CONFIG = {}

# ws 连接实例
EXCHANGE_WS_INSTANCE = {}
# ws 监控
EXCHANGE_WS_MONITOR = {}

SYMBOL_HEDGE_CONFIG_OLDER = {}

# ws启动的交易所
WS_EXCHANGE_ACTIVE = ['okex', 'bn', 'gate', 'bitget', 'kraken']
PRECISION = {i: {} for i in WS_EXCHANGE_ACTIVE}
# 错误消息共享内存
SHARE_ERROR_MESSAGES = {}

WS_EXCEPTION_SLEEP_TIME = 2

ASYNC_LOCK = {
    "external_position": asyncio.Lock()

}

WS_LISTEN_KEY = {}

# 存放内部成交均价 {'BTC':{'abc_position': abc_position, 'avg_price': avg_price}}
ABC_ASSET_AVG_PRICE = {
}
