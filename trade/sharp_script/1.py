

from libs import libs_price
from many_configs.base_config import ExchangeCode
from many_configs import global_variable
a = {
    "BLZ-USDT": {
        "price_symbol": {},
        "contract_price_symbol": {ExchangeCode.bn.value: "BLZ-USDT", ExchangeCode.gate.value: "BLZ-USDT", },
        "price_offset": 0,
    },
    "YGG-USDT": {
        "price_symbol": {},
        "contract_price_symbol": {ExchangeCode.bn.value: "YGG-USDT", ExchangeCode.okex.value: "YGG-USDT", },
        "price_offset": 0,
    },
    "HIFI-USDT": {
        "price_symbol": {ExchangeCode.bn.value: "HIFI-USDT", },
        "contract_price_symbol": {ExchangeCode.bn.value: "HIFI-USDT", },
        "price_offset": 0,
    },
    "QNT-USDT": {
        "price_symbol": {ExchangeCode.bn.value: "QNT-USDT", },
        "contract_price_symbol": {ExchangeCode.bn.value: "QNT-USDT", },
        "price_offset": 0,
    },
    "ALGO-USDT": {
        "price_symbol": {},
        "contract_price_symbol": {ExchangeCode.bn.value: "ALGO-USDT", ExchangeCode.okex.value: "ALGO-USDT", },
        "price_offset": 0,
    },
    "KAVA-USDT": {
        "price_symbol": {},
        "contract_price_symbol": {ExchangeCode.bn.value: "KAVA-USDT", ExchangeCode.gate.value: "KAVA-USDT", },
        "price_offset": 0,
    },
    "CHZ-USDT": {
        "price_symbol": {},
        "contract_price_symbol": {ExchangeCode.bn.value: "CHZ-USDT", ExchangeCode.okex.value: "CHZ-USDT", },
        "price_offset": 0,
    },
    "ZEC-USDT": {
        "price_symbol": {},
        "contract_price_symbol": {ExchangeCode.bn.value: "ZEC-USDT", ExchangeCode.gate.value: "ZEC-USDT", },
        "price_offset": 0,
    },
    "KLAY-USDT": {
        "price_symbol": {},
        "contract_price_symbol": {ExchangeCode.bn.value: "KLAY-USDT", ExchangeCode.okex.value: "KLAY-USDT", },
        "price_offset": 0,
    },
    "FXS-USDT": {
        "price_symbol": {},
        "contract_price_symbol": {ExchangeCode.bn.value: "FXS-USDT", ExchangeCode.okex.value: "FXS-USDT", },
        "price_offset": 0,
    },
    "MINA-USDT": {
        "price_symbol": {},
        "contract_price_symbol": {ExchangeCode.bn.value: "MINA-USDT", ExchangeCode.okex.value: "MINA-USDT", },
        "price_offset": 0,
    },
    "BIGTIME-USDT": {
        "price_symbol": {},
        "contract_price_symbol": {ExchangeCode.bn.value: "BIGTIME-USDT", ExchangeCode.okex.value: "BIGTIME-USDT", },
        "price_offset": 0,
    },
    "ASTR-USDT": {
        "price_symbol": {ExchangeCode.okex.value: "ASTR-USDT", },
        "contract_price_symbol": {ExchangeCode.bn.value: "ASTR-USDT", },
        "price_offset": 0,
    },
    "BAND-USDT": {
        "price_symbol": {},
        "contract_price_symbol": {ExchangeCode.bn.value: "BAND-USDT", ExchangeCode.okex.value: "BAND-USDT", },
        "price_offset": 0,
    },
    "LOOM-USDT": {
        "price_symbol": {},
        "contract_price_symbol": {ExchangeCode.bn.value: "LOOM-USDT", ExchangeCode.gate.value: "LOOM-USDT", },
        "price_offset": 0,
    },
    "WOO-USDT": {
        "price_symbol": {},
        "contract_price_symbol": {ExchangeCode.bn.value: "WOO-USDT", ExchangeCode.okex.value: "WOO-USDT", },
        "price_offset": 0,
    },
    "ORBS-USDT": {
        "price_symbol": {},
        "contract_price_symbol": {ExchangeCode.bn.value: "ORBS-USDT", ExchangeCode.okex.value: "ORBS-USDT", },
        "price_offset": 0,
    },
    "WAXP-USDT": {
        "price_symbol": {},
        "contract_price_symbol": {ExchangeCode.bn.value: "WAXP-USDT", ExchangeCode.okex.value: "WAXP-USDT", },
        "price_offset": 0,
    },
    "BNT-USDT": {
        "price_symbol": {},
        "contract_price_symbol": {ExchangeCode.bn.value: "BNT-USDT", ExchangeCode.okex.value: "BNT-USDT", },
        "price_offset": 0,
    },
    "LQTY-USDT": {
        "price_symbol": {},
        "contract_price_symbol": {ExchangeCode.bn.value: "LQTY-USDT", ExchangeCode.okex.value: "LQTY-USDT", },
        "price_offset": 0,
    },
    "SPELL-USDT": {
        "price_symbol": {},
        "contract_price_symbol": {ExchangeCode.bn.value: "SPELL-USDT"},
        "price_offset": 0,
    },
    "MASK-USDT": {
        "price_symbol": {},
        "contract_price_symbol": {ExchangeCode.bn.value: "MASK-USDT", ExchangeCode.okex.value: "MASK-USDT", },
        "price_offset": 0,
    },
    "ACH-USDT": {
        "price_symbol": {},
        "contract_price_symbol": {ExchangeCode.bn.value: "ACH-USDT", ExchangeCode.okex.value: "ACH-USDT", },
        "price_offset": 0,
    },
    "AGLD-USDT": {
        "price_symbol": {},
        "contract_price_symbol": {ExchangeCode.bn.value: "AGLD-USDT", ExchangeCode.okex.value: "AGLD-USDT", },
        "price_offset": 0,
    },
    "LINA-USDT": {
        "price_symbol": {},
        "contract_price_symbol": {ExchangeCode.bn.value: "LINA-USDT", ExchangeCode.gate.value: "LINA-USDT", },
        "price_offset": 0,
    },

}

b = a.keys()
c = []
for i in b:
    p = libs_price.get_contract_weight_price(i)
    price_precision = int(global_variable.SYMBOLS_CONTRACT_CONDITION[i].get("price", 8))
    p = round(p, price_precision) if price_precision else round(p)
    c.append((i, p))
print(c)
