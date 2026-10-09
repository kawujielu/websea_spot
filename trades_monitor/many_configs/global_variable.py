WS_FREQUENCY = 30
RESTART_DELAY_TIME = 2 * 60

# 请求速度
INTERVAL = 1000
# 档位数
GEARS = 5

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

# 保持每个交易所实例
EXTERNAL_EXCHANGE_INSTANCES = {}

EXCHANGE_SYMBOLS_MAPPERS = {

}

SERVICE_STATUS = True

ABC_POSITIONS = {}
EXTERNAL_POSITIONS = {}

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

PRECISION = {
    'bn': {},
    'okex': {},
}

# ws 连接实例
EXCHANGE_WS_INSTANCE = {}

SYMBOL_HEDGE_CONFIG_OLDER = {}

# ws启动的交易所
WS_EXCHANGE_ACTIVE = ['okex', 'bn', 'gate', 'mxc', 'hb']

# 错误消息共享内存
SHARE_NOTICE = {}
SHARE_NOTICE_KEY = "share_n_m"
SHARE_EXCHANGE = {}
SHARE_EXCHANGE_KEY = "share_n_m_exchange"
