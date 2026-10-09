from libs import libs_config, currency_feature

volume_zone_all_contract_symbols = libs_config.contract_zone_all_symbols
volume_zone_contract_symbols = libs_config.volume_zone_contract_symbols
volume_self_contract_symbols = libs_config.volume_self_contract_symbols

contract_symbols = volume_zone_contract_symbols.get("USDT", [])

CONTRACT_SUPPORT_SYMBOLS = contract_symbols


# 跟随的资金费率有一个默认的顺序，此处为配置特殊情况
FOLLOW_EXCHANGE_FUNDING_RATE_SPEC = {

}

# 跟随的资金费率默认的顺序
FOLLOW_EXCHANGE_ORDER_REVERSE = ["bn", "okex", "huobi"]
FOLLOW_EXCHANGE_ORDER_REVERSE.reverse()

CONTRACT_ASK_BID_PRICE_SYMBOL_EXCHANGES = libs_config.CONTRACT_ASK_BID_PRICE_SYMBOL_EXCHANGES
contract_price_ex_abc_symbols = libs_config.contract_price_ex_abc_symbols
contract_price_ex_symbols = libs_config.contract_price_ex_symbols
contract_price_trans_symbols = libs_config.contract_price_trans_symbols
contract_price_trans_symbols_from_contract = libs_config.contract_price_trans_symbols_from_contract
CONTRACT_ABC_SYMBOL_EXCHANGES_FROM_CONTRACT = libs_config.CONTRACT_ABC_SYMBOL_EXCHANGES_FROM_CONTRACT
contract_price_all_symbols_from_contract = libs_config.contract_price_all_symbols_from_contract
contract_price_ex_symbols_from_contract = libs_config.contract_price_ex_symbols_from_contract
CONTRACT_PRICE_SYMBOL_CONFIG = libs_config.CONTRACT_PRICE_SYMBOL_CONFIG
contract_all_symbols = libs_config.contract_all_symbols
CONTRACT_CURRENCY_CONFIG = libs_config.CONTRACT_CURRENCY_CONFIG
spec_contract_symbol_rate_mapping = libs_config.SPEC_CONTRACT_SYMBOL_RATE_MAPPING
# ------------------------ 合约配置相关 ------------------------ #

base_sleep_time = 0.75
sleep_ratio = 2
special_base_sleep_time = {

}

self_base_sleep_time = base_sleep_time * sleep_ratio * 10
SYMBOL_SLEEP_TIME = {}
SELF_SYMBOL_SLEEP_TIME = {}
SUBSTITUTE_TIME = {}
for currency in CONTRACT_CURRENCY_CONFIG.keys():
    level = currency_feature.currency_dangerous_level(currency)

    for z, p in [('USDT', 1), ('ETH', 5), ('BTC', 5)]:
        s = f"{currency}-{z}"
        SYMBOL_SLEEP_TIME[s] = special_base_sleep_time.get(s, base_sleep_time) * max(int(p * level * sleep_ratio), 1)  # 时间必须为base_sleep_time整数倍
        SELF_SYMBOL_SLEEP_TIME[s] = self_base_sleep_time * min(p * level, 10)  # 时间必须为self_base_sleep_time整数倍
        SUBSTITUTE_TIME[s] = SELF_SYMBOL_SLEEP_TIME[s]


# 做市合约下单倍数
CONTRACT_LEVER_RATE = 5

amount_rate = 8  # 对标外部交易所数量系数

VOLUME_EXCHANGE_CONTRACT_KEY_DATA = {"bn": "q",
                                     "hb": "amount",
                                     "okex": "size",
                                     }

contract_close_time = ["00:00:00", "08:00:00", "16:00:00"]
