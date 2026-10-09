import libs

ExchangeCode = libs.libs_config.ExchangeCode
EXCHANGE_ACTIVE = libs.libs_config.EXCHANGE_ACTIVE

EXCHANGE_MAX_SUB_DEFAULT = 120
EXCHANGE_MAX_SUB_PER_WS = {
    ExchangeCode.mxc.value: 25,  # 正常情况下一个ws只能订阅30个交易对，考虑到可能会额外订阅其他channel交易对，所以传入少一些
}