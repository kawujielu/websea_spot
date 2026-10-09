import os
from enum import Enum


# --------------------------------------------------- 控制 --------------------------------------------------- #


class ExchangeCode(Enum):
    bn = "bn"
    okex = "okex"
    hb = "hb"
    bitfinex = "bitfinex"
    gate = "gate"
    bkex = "bkex"
    uniswapv2 = "uniswapv2"
    uniswapv3 = "uniswapv3"
    mxc = "mxc"
    bitget = "bitget"
    kraken = "kraken"
    lbank = "lbank"
    abc = "abc"
    pancake = "pancake"
    mdex = "mdex"
    kucoin = "kucoin"
    sushi = "sushi"
    matic = "matic"


EXCHANGE_ACTIVE = {  # 外部交易所现货市场的运行状态
    ExchangeCode.bn.value: True,
    ExchangeCode.okex.value: True,
    ExchangeCode.hb.value: True,
    ExchangeCode.bitfinex.value: True,
    ExchangeCode.gate.value: True,
    ExchangeCode.bkex.value: True,
    ExchangeCode.uniswapv2.value: True,
    ExchangeCode.uniswapv3.value: True,
    ExchangeCode.mxc.value: True,
    ExchangeCode.bitget.value: True,
    ExchangeCode.kraken.value: True,
    ExchangeCode.lbank.value: True,
    ExchangeCode.abc.value: True,
    ExchangeCode.pancake.value: True,
    ExchangeCode.mdex.value: True,
    ExchangeCode.kucoin.value: False,
    ExchangeCode.sushi.value: True,
    ExchangeCode.matic.value: True,
}

CONTRACT_EXCHANGE_ACTIVE = {  # 外部交易所合约市场的运行状态，用于在特殊情况下对标合约盘口
    ExchangeCode.bn.value: True,
    ExchangeCode.okex.value: True,
    ExchangeCode.hb.value: True,
    ExchangeCode.gate.value: True,
}

# --------------------------------------------------- 现货价格服务 --------------------------------------------------- #

# 实时价格 和 深度价格 各个交易所权重
weighting = {
    "okex": 1, "okex_depth": 2,
    "hb": 3, "hb_depth": 2,
    "bitfinex": 3, "bitfinex_depth": 2,
    "gate": 3, "gate_depth": 2,
    "bn": 3, "bn_depth": 2,
    "bkex": 2, "bkex_depth": 2,
    "mxc": 2, "mxc_depth": 2,
    "bitget": 2, "bitget_depth": 2,
    "kraken": 2, "kraken_depth": 2,
    "lbank": 2, "lbank_depth": 2,
    "uniswapv2": 2, "uniswapv2_depth": 2,
    "uniswapv3": 2, "uniswapv3_depth": 2,
    "sushi": 2, "sushi_depth": 2,
    "pancake": 2, "pancake_depth": 2,
    "custom": 2, "custom_depth": 2,
    "mdex": 2, "mdex_depth": 2,
    "abc": 2, "abc_depth": 8,
    "ftx": 2, "ftx_depth": 2,
    "matic": 2, "matic_depth": 2,
}

# 价格服务配置档abc交易对必须和外部对标档交易对相同，如果不同，需要在交易所对标逻辑中特殊处理
# 比如 比如BTC-USDT对标bn档BTC-BUSD，HUSD-USDT对标hb的USDT-HUSD
# 去中心化交易所交易对对应dex_config 里配置池子交易对


quote_currency = "USDT"  # 每个币的计价货币一定保证为USDT
PRICE_SYMBOL_CONFIG = {
    f"BTC-{quote_currency}": {
        "price_symbol": {ExchangeCode.bn.value: "BTC-USDT"},
        "depth_price": {ExchangeCode.okex.value: "BTC-USDT"},
        "dex_price": {}
    },
    f"ETH-{quote_currency}": {
        "price_symbol": {ExchangeCode.okex.value: "ETH-USDT"},
        "depth_price": {ExchangeCode.bn.value: "ETH-USDT"},
        "dex_price": dict()
    },
    f"TRX-{quote_currency}": {
        "price_symbol": {ExchangeCode.bn.value: "TRX-USDT", },
        "depth_price": {ExchangeCode.okex.value: "TRX-USDT", },
        "dex_price": dict()
    },
    f"BNB-{quote_currency}": {
        "price_symbol": {ExchangeCode.bn.value: "BNB-USDT", },
        "depth_price": {ExchangeCode.okex.value: "BNB-USDT", },
        "dex_price": dict()
    },
    # f"APE-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "APE-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "APE-USDT", },
    #     "dex_price": dict()
    # },
    # f"AXS-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "AXS-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "AXS-USDT", },
    #     "dex_price": dict()
    # },
    # f"ENS-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "ENS-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "ENS-USDT", },
    #     "dex_price": dict()
    # },
    # f"LINK-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "LINK-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "LINK-USDT", },
    #     "dex_price": dict()
    # },
    # f"MANA-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "MANA-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "MANA-USDT", },
    #     "dex_price": dict()
    # },
    # f"SAND-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "SAND-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "SAND-USDT", },
    #     "dex_price": dict()
    # },
    # f"SHIB-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "SHIB-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "SHIB-USDT", },
    #     "dex_price": dict()
    # },
    # f"1INCH-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "1INCH-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "1INCH-USDT", },
    #     "dex_price": dict()
    # },
    # f"AAVE-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "AAVE-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "AAVE-USDT", },
    #     "dex_price": dict()
    # },
    f"COMP-{quote_currency}": {
        "price_symbol": {ExchangeCode.bn.value: "COMP-USDT", },
        "depth_price": {ExchangeCode.okex.value: "COMP-USDT", },
        "dex_price": dict()
    },
    # f"YGG-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "YGG-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "YGG-USDT", },
    #     "dex_price": dict()
    # },
    # f"CRV-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "CRV-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "CRV-USDT", },
    #     "dex_price": dict()
    # },
    # f"MASK-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "MASK-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "MASK-USDT", },
    #     "dex_price": dict()
    # },
    # f"SUSHI-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "SUSHI-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "SUSHI-USDT", },
    #     "dex_price": dict()
    # },
    # f"ANKR-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "ANKR-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "ANKR-USDT", },
    #     "dex_price": dict()
    # },
    # f"BAT-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "BAT-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "BAT-USDT", },
    #     "dex_price": dict()
    # },
    # f"CHZ-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "CHZ-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "CHZ-USDT", },
    #     "dex_price": dict()
    # },
    # f"EGLD-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "EGLD-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "EGLD-USDT", },
    #     "dex_price": dict()
    # },
    # f"INJ-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "INJ-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "INJ-USDT", },
    #     "dex_price": dict()
    # },
    # f"IOTX-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "IOTX-USDT", },
    #     "depth_price": {ExchangeCode.bn.value: "IOTX-USDT", },
    #     "dex_price": dict()
    # },
    # f"QNT-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "QNT-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "QNT-USDT", },
    #     "dex_price": dict()
    # },
    f"UNI-{quote_currency}": {
        "price_symbol": {ExchangeCode.bn.value: "UNI-USDT", },
        "depth_price": {ExchangeCode.okex.value: "UNI-USDT", },
        "dex_price": dict()
    },
    # f"TRB-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "TRB-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "TRB-USDT", },
    #     "dex_price": dict()
    # },
    # f"GLM-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "GLM-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "GLM-USDT", },
    #     "dex_price": dict()
    # },
    # f"TIA-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "TIA-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "TIA-USDT", },
    #     "dex_price": dict()
    # },
    # f"FLOKI-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "FLOKI-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "FLOKI-USDT", },
    #     "dex_price": dict()
    # },
    # f"MEME-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "MEME-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "MEME-USDT", },
    #     "dex_price": dict()
    # },
    # f"FTT-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "FTT-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "FTT-USDT", },
    #     "dex_price": dict()
    # },
    # f"ORDI-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "ORDI-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "ORDI-USDT", },
    #     "dex_price": dict()
    # },
    # f"BSSB-{quote_currency}": {
    #     "price_symbol": {},
    #     "depth_price": {},
    #     "dex_price": {ExchangeCode.uniswapv3.value: "BSSB-ETH", }
    # },
    # f"BEAMX-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "BEAMX-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "BEAMX-USDT", },
    #     "dex_price": dict()
    # },
    f"CAKE-{quote_currency}": {
        "price_symbol": {ExchangeCode.bn.value: "CAKE-USDT", },
        "depth_price": {ExchangeCode.gate.value: "CAKE-USDT", },
        "dex_price": dict()
    },
    # f"GALA-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "GALA-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "GALA-USDT", },
    #     "dex_price": dict()
    # },
    # f"WLD-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "WLD-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "WLD-USDT", },
    #     "dex_price": dict()
    # },
    # f"GRT-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "GRT-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "GRT-USDT", },
    #     "dex_price": dict()
    # },
    # f"PEOPLE-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "PEOPLE-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "PEOPLE-USDT", },
    #     "dex_price": dict()
    # },
    # f"LDO-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "LDO-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "LDO-USDT", },
    #     "dex_price": dict()
    # },
    # f"GMT-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "GMT-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "GMT-USDT", },
    #     "dex_price": dict()
    # },
    # f"ONDO-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.okex.value: "ONDO-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "ONDO-USDT", },
    #     "dex_price": dict()
    # },
    # f"IMX-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "IMX-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "IMX-USDT", },
    #     "dex_price": dict()
    # },
    # f"PENDLE-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "PENDLE-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "PENDLE-USDT", },
    #     "dex_price": dict()
    # },
    # f"LPT-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "LPT-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "LPT-USDT", },
    #     "dex_price": dict()
    # },
    f"OKB-{quote_currency}": {
        "price_symbol": {ExchangeCode.okex.value: "OKB-USDT", },
        "depth_price": {ExchangeCode.gate.value: "OKB-USDT", },
        "dex_price": dict()
    },
    # f"JASMY-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "JASMY-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "JASMY-USDT", },
    #     "dex_price": dict()
    # },
    # f"SUI-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "SUI-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "SUI-USDT", },
    #     "dex_price": dict()
    # },
    # f"ARB-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "ARB-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "ARB-USDT", },
    #     "dex_price": dict()
    # },
    # f"AEVO-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "AEVO-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "AEVO-USDT", },
    #     "dex_price": dict()
    # },
    f"ETHFI-{quote_currency}": {
        "price_symbol": {ExchangeCode.bn.value: "ETHFI-USDT", },
        "depth_price": {ExchangeCode.okex.value: "ETHFI-USDT", },
        "dex_price": dict()
    },
    # f"CFX-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "CFX-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "CFX-USDT", },
    #     "dex_price": dict()
    # },
    # f"ENA-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "ENA-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "ENA-USDT", },
    #     "dex_price": dict()
    # },
    f"SOL-{quote_currency}": {
        "price_symbol": {ExchangeCode.bn.value: "SOL-USDT", },
        "depth_price": {ExchangeCode.okex.value: "SOL-USDT", },
        "dex_price": dict()
    },
    # f"JTO-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "JTO-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "JTO-USDT", },
    #     "dex_price": dict()
    # },
    # f"SAFE-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.okex.value: "SAFE-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "SAFE-USDT", },
    #     "dex_price": dict()
    # },
    # f"NEAR-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "NEAR-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "NEAR-USDT", },
    #     "dex_price": dict()
    # },
    # f"JUP-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "JUP-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "JUP-USDT", },
    #     "dex_price": dict()
    # },
    # f"WIF-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "WIF-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "WIF-USDT", },
    #     "dex_price": dict()
    # },
    # f"PEPE-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "PEPE-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "PEPE-USDT", },
    #     "dex_price": dict()
    # },
    # f"BOME-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "BOME-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "BOME-USDT", },
    #     "dex_price": dict()
    # },
    # f"W-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "W-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "W-USDT", },
    #     "dex_price": dict()
    # },
    # f"RAY-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "RAY-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "RAY-USDT", },
    #     "dex_price": dict()
    # },
    # f"ZRO-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "ZRO-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "ZRO-USDT", },
    #     "dex_price": dict()
    # },
    # f"FET-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "FET-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "FET-USDT", },
    #     "dex_price": dict()
    # },
    f"APT-{quote_currency}": {
        "price_symbol": {ExchangeCode.bn.value: "APT-USDT", },
        "depth_price": {ExchangeCode.okex.value: "APT-USDT", },
        "dex_price": dict()
    },
    # f"RENDER-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "RENDER-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "RENDER-USDT", },
    #     "dex_price": dict()
    # },
    # f"DOGS-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "DOGS-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "DOGS-USDT", },
    #     "dex_price": dict()
    # },
    # f"POL-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "POL-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "POL-USDT", },
    #     "dex_price": dict()
    # },
    # f"PNUT-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "PNUT-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "PNUT-USDT", },
    #     "dex_price": dict()
    # },
    # f"ACT-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "ACT-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "ACT-USDT", },
    #     "dex_price": dict()
    # },
    # f"NEIRO-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "NEIRO-USDT", },
    #     "depth_price": {ExchangeCode.okex.value: "NEIRO-USDT", },
    #     "dex_price": dict()
    # },
    # f"MOVE-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "MOVE-USDT", },
    #     "depth_price": {ExchangeCode.bn.value: "MOVE-USDT", },
    #     "dex_price": dict()
    # },
    # f"PENGU-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "PENGU-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "PENGU-USDT", },
    #     "dex_price": dict()
    # },
    # f"TRUMP-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "TRUMP-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "TRUMP-USDT", },
    #     "dex_price": dict()
    # },
    # f"USDQ-{quote_currency}": {
    #     "price_symbol": {},
    #     "depth_price": {ExchangeCode.kraken.value: "USDQ-USDT", },
    #     "dex_price": dict()
    # },
    # f"USDR-{quote_currency}": {
    #     "price_symbol": {},
    #     "depth_price": {ExchangeCode.kraken.value: "USDR-USDT", },
    #     "dex_price": dict()
    # },
    # f"ORCA-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "ORCA-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "ORCA-USDT", },
    #     "dex_price": dict()
    # },
    # f"BMT-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "BMT-USDT", },
    #     "depth_price": {ExchangeCode.bn.value: "BMT-USDT", },
    #     "dex_price": dict()
    # },
    f"XRP-{quote_currency}": {
        "price_symbol": {ExchangeCode.bn.value: "XRP-USDT", },
        "depth_price": {ExchangeCode.okex.value: "XRP-USDT", },
        "dex_price": dict()
    },
    f"DOGE-{quote_currency}": {
        "price_symbol": {ExchangeCode.bn.value: "DOGE-USDT", },
        "depth_price": {ExchangeCode.okex.value: "DOGE-USDT", },
        "dex_price": dict()
    },
    # f"HYPER-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "HYPER-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "HYPER-USDT", },
    #     "dex_price": dict()
    # },
    # f"LTC-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "LTC-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "LTC-USDT", },
    #     "dex_price": dict()
    # },
    # f"KERNEL-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "KERNEL-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "KERNEL-USDT", },
    #     "dex_price": dict()
    # },
    # f"SXT-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "SXT-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "SXT-USDT", },
    #     "dex_price": dict()
    # },
    # f"NXPC-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "NXPC-USDT", },
    #     "depth_price": {ExchangeCode.bn.value: "NXPC-USDT", },
    #     "dex_price": dict()
    # },
    # f"EURR-{quote_currency}": {
    #     "price_symbol": {},
    #     "depth_price": {ExchangeCode.kraken.value: "EURR-USDT", },
    #     "dex_price": dict()
    # },
    # f"EURQ-{quote_currency}": {
    #     "price_symbol": {},
    #     "depth_price": {ExchangeCode.kraken.value: "EURQ-USDT", },
    #     "dex_price": dict()
    # },
    # f"NEWT-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "NEWT-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "NEWT-USDT", },
    #     "dex_price": dict()
    # },
    # f"HOME-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "HOME-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "HOME-USDT", },
    #     "dex_price": dict()
    # },
    # f"PUMP-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.gate.value: "PUMP-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "PUMP-USDT", },
    #     "dex_price": dict()
    # },
    # f"ERA-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "ERA-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "ERA-USDT", },
    #     "dex_price": dict()
    # },
    # f"C-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "C-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "C-USDT", },
    #     "dex_price": dict()
    # },
    f"USDC-{quote_currency}": {
        "price_symbol": {ExchangeCode.bn.value: "USDC-USDT", },
        "depth_price": {ExchangeCode.gate.value: "USDC-USDT", },
        "dex_price": dict()
    },
    f"WLFI-{quote_currency}": {
        "price_symbol": {ExchangeCode.bn.value: "WLFI-USDT", },
        "depth_price": {ExchangeCode.bn.value: "WLFI-USDT", },
        "dex_price": dict()
    },
    # f"SKY-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "SKY-USDT", },
    #     "depth_price": {ExchangeCode.bn.value: "SKY-USDT", },
    #     "dex_price": dict()
    # },
    f"ASTER-{quote_currency}": {
        "price_symbol": {ExchangeCode.bn.value: "ASTER-USDT", },
        "depth_price": {ExchangeCode.gate.value: "ASTER-USDT", },
        "dex_price": dict()
    },
    f"XAUT-{quote_currency}": {
        "price_symbol": {ExchangeCode.okex.value: "XAUT-USDT", },
        "depth_price": {ExchangeCode.gate.value: "XAUT-USDT", },
        "dex_price": dict()
    },
    # f"GIGGLE-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "GIGGLE-USDT", },
    #     "depth_price": {ExchangeCode.bn.value: "GIGGLE-USDT", },
    #     "dex_price": dict()
    # },
    # f"ESP-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "ESP-USDT", },
    #     "depth_price": {ExchangeCode.bn.value: "ESP-USDT", },
    #     "dex_price": dict()
    # },
    # f"MANTRA-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.bn.value: "MANTRA-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "MANTRA-USDT", },
    #     "dex_price": dict()
    # },
    f"NVDAON-{quote_currency}": {
        "price_symbol": {ExchangeCode.gate.value: "NVDAON-USDT", },
        "depth_price": {ExchangeCode.gate.value: "NVDAON-USDT", },
        "dex_price": dict()
    },
    f"AAPLON-{quote_currency}": {
        "price_symbol": {ExchangeCode.gate.value: "AAPLON-USDT", },
        "depth_price": {ExchangeCode.gate.value: "AAPLON-USDT", },
        "dex_price": dict()
    },
    f"GOOGLON-{quote_currency}": {
        "price_symbol": {ExchangeCode.gate.value: "GOOGLON-USDT", },
        "depth_price": {ExchangeCode.gate.value: "GOOGLON-USDT", },
        "dex_price": dict()
    },
    f"MSFTON-{quote_currency}": {
        "price_symbol": {ExchangeCode.gate.value: "MSFTON-USDT", },
        "depth_price": {ExchangeCode.gate.value: "MSFTON-USDT", },
        "dex_price": dict()
    },
    f"TSLAON-{quote_currency}": {
        "price_symbol": {ExchangeCode.gate.value: "TSLAON-USDT", },
        "depth_price": {ExchangeCode.gate.value: "TSLAON-USDT", },
        "dex_price": dict()
    },
    # f"CRCLON-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.gate.value: "CRCLON-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "CRCLON-USDT", },
    #     "dex_price": dict()
    # },
    # f"AMDON-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.gate.value: "AMDON-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "AMDON-USDT", },
    #     "dex_price": dict()
    # },
    f"KOON-{quote_currency}": {
        "price_symbol": {ExchangeCode.gate.value: "KOON-USDT", },
        "depth_price": {ExchangeCode.gate.value: "KOON-USDT", },
        "dex_price": dict()
    },
    f"SPCX-{quote_currency}": {
        "price_symbol": {ExchangeCode.gate.value: "SPCX-USDT", },
        "depth_price": {ExchangeCode.gate.value: "SPCX-USDT", },
        "dex_price": dict()
    },
    # f"QQQON-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.gate.value: "QQQON-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "QQQON-USDT", },
    #     "dex_price": dict()
    # },
    f"SPCXON-{quote_currency}": {
        "price_symbol": {ExchangeCode.gate.value: "SPCXON-USDT", },
        "depth_price": {ExchangeCode.gate.value: "SPCXON-USDT", },
        "dex_price": dict()
    },
    # f"NFLXON-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.gate.value: "NFLXON-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "NFLXON-USDT", },
    #     "dex_price": dict()
    # },
    # f"CSCOON-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.gate.value: "CSCOON-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "CSCOON-USDT", },
    #     "dex_price": dict()
    # },
    # f"LLYON-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.gate.value: "LLYON-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "LLYON-USDT", },
    #     "dex_price": dict()
    # },
    # f"SBUXON-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.gate.value: "SBUXON-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "SBUXON-USDT", },
    #     "dex_price": dict()
    # },
    # f"PEPON-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.gate.value: "PEPON-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "PEPON-USDT", },
    #     "dex_price": dict()
    # },
    f"GRAM-{quote_currency}": {
        "price_symbol": {ExchangeCode.bn.value: "GRAM-USDT", },
        "depth_price": {ExchangeCode.bn.value: "GRAM-USDT", },
        "dex_price": dict()
    },
    f"SLVON-{quote_currency}": {
        "price_symbol": {ExchangeCode.gate.value: "SLVON-USDT", },
        "depth_price": {ExchangeCode.gate.value: "SLVON-USDT", },
        "dex_price": dict()
    },
    # f"IAUON-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.gate.value: "IAUON-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "IAUON-USDT", },
    #     "dex_price": dict()
    # },
    # f"SPYON-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.gate.value: "SPYON-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "SPYON-USDT", },
    #     "dex_price": dict()
    # },
    # f"HOODON-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.gate.value: "HOODON-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "HOODON-USDT", },
    #     "dex_price": dict()
    # },
    f"AMZNON-{quote_currency}": {
        "price_symbol": {ExchangeCode.gate.value: "AMZNON-USDT", },
        "depth_price": {ExchangeCode.gate.value: "AMZNON-USDT", },
        "dex_price": dict()
    },
    f"METAON-{quote_currency}": {
        "price_symbol": {ExchangeCode.gate.value: "METAON-USDT", },
        "depth_price": {ExchangeCode.gate.value: "METAON-USDT", },
        "dex_price": dict()
    },
    # f"SKHYON-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.gate.value: "SKHYON-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "SKHYON-USDT", },
    #     "dex_price": dict()
    # },
    # f"翻身币-{quote_currency}": {
    #     "price_symbol": {ExchangeCode.gate.value: "SKHYON-USDT", },
    #     "depth_price": {ExchangeCode.gate.value: "SKHYON-USDT", },
    #     "dex_price": dict()
    # },
    
    
}

price_trans_symbols = {}
price_market_ex_symbols = {}
price_depth_ex_symbols = {}
price_depth_ex_abc_symbols = {}
price_dex_price_ex_symbols = {}
price_dex_price_ex_transfer_symbols = {}
price_all_symbols = set()

for i, v in PRICE_SYMBOL_CONFIG.items():
    price_all_symbols.add(i)

    for ex, sy in v["price_symbol"].items():
        if not EXCHANGE_ACTIVE.get(ex):
            continue
        if not price_market_ex_symbols.get(ex):
            price_market_ex_symbols[ex] = set()
        price_market_ex_symbols[ex].add(sy)
        if ex not in price_trans_symbols:
            price_trans_symbols[ex] = {}
        price_trans_symbols[ex][sy.replace("-", '').lower()] = i
        price_trans_symbols[ex][sy.replace("-", "_")] = i
        price_trans_symbols[ex][sy] = i
        price_trans_symbols[ex][sy.replace("-", '')] = i
        price_trans_symbols[ex][sy.replace("-", '/')] = i

    for ex, sy in v["depth_price"].items():
        if not EXCHANGE_ACTIVE.get(ex):
            continue
        if not price_depth_ex_symbols.get(ex):
            price_depth_ex_symbols[ex] = set()
        price_depth_ex_symbols[ex].add(sy)

        if not price_depth_ex_abc_symbols.get(ex):
            price_depth_ex_abc_symbols[ex] = set()
        price_depth_ex_abc_symbols[ex].add(i)

        if ex not in price_trans_symbols:
            price_trans_symbols[ex] = {}
        price_trans_symbols[ex][sy.replace("-", '').lower()] = i
        price_trans_symbols[ex][sy.replace("-", "_")] = i
        price_trans_symbols[ex][sy] = i
        price_trans_symbols[ex][sy.replace("-", '')] = i
        price_trans_symbols[ex][sy.replace("-", '/')] = i

    for ex, sy in v["dex_price"].items():
        if not EXCHANGE_ACTIVE.get(ex):
            continue
        if not price_dex_price_ex_symbols.get(ex):
            price_dex_price_ex_symbols[ex] = set()
        price_dex_price_ex_symbols[ex].add(sy)
        if not price_dex_price_ex_transfer_symbols.get(ex):
            price_dex_price_ex_transfer_symbols[ex] = {}
        price_dex_price_ex_transfer_symbols[ex][sy] = i

        if ex not in price_trans_symbols:
            price_trans_symbols[ex] = {}
        price_trans_symbols[ex][sy.replace("-", '').lower()] = i
        price_trans_symbols[ex][sy.replace("-", "_")] = i
        price_trans_symbols[ex][sy] = i
        price_trans_symbols[ex][sy.replace("-", '')] = i
        price_trans_symbols[ex][sy.replace("-", '/')] = i

# --------------------------------------------------- 合约价格服务 --------------------------------------------------- #

CONTRACT_PRICE_SYMBOL_CONFIG = {}

# 以下为对标现货买卖n
contract_price_trans_symbols = {}
contract_price_ex_symbols = {}  # {"外部ex": {"外部symbol", }}
contract_price_ex_abc_symbols = {}  # {"外部ex": {"abc symbol", }}
CONTRACT_ASK_BID_PRICE_SYMBOL_EXCHANGES = {}  # {"abc symbol": {"外部ex",}}
# 以下为对标合约买卖n
CONTRACT_ABC_SYMBOL_EXCHANGES_FROM_CONTRACT = {}
contract_price_trans_symbols_from_contract = {}
contract_price_all_symbols_from_contract = set()
contract_price_ex_symbols_from_contract = {}
contract_price_all_symbols = set()

for i, v in CONTRACT_PRICE_SYMBOL_CONFIG.items():
    contract_price_all_symbols.add(i)

    CONTRACT_ASK_BID_PRICE_SYMBOL_EXCHANGES[i] = set()
    for ex, sy in v["price_symbol"].items():
        if not EXCHANGE_ACTIVE.get(ex):
            continue
        CONTRACT_ASK_BID_PRICE_SYMBOL_EXCHANGES[i].add(ex)
        if not contract_price_ex_symbols.get(ex):
            contract_price_ex_symbols[ex] = set()
        contract_price_ex_symbols[ex].add(sy)
        if not contract_price_ex_abc_symbols.get(ex):
            contract_price_ex_abc_symbols[ex] = set()
        contract_price_ex_abc_symbols[ex].add(i)
        if ex not in contract_price_trans_symbols:
            contract_price_trans_symbols[ex] = {}
        contract_price_trans_symbols[ex][sy.replace("-", '').lower()] = i
        contract_price_trans_symbols[ex][sy.replace("-", "_")] = i
        contract_price_trans_symbols[ex][sy] = i
        contract_price_trans_symbols[ex][sy.replace("-", '')] = i
        contract_price_trans_symbols[ex][sy.replace("-", '/')] = i

    CONTRACT_ABC_SYMBOL_EXCHANGES_FROM_CONTRACT[i] = set()
    for ex, sy in v["contract_price_symbol"].items():
        if not CONTRACT_EXCHANGE_ACTIVE.get(ex):
            continue
        CONTRACT_ABC_SYMBOL_EXCHANGES_FROM_CONTRACT[i].add(ex)
        contract_price_all_symbols_from_contract.add(i)
        if not contract_price_ex_symbols_from_contract.get(ex):
            contract_price_ex_symbols_from_contract[ex] = set()
        contract_price_ex_symbols_from_contract[ex].add(sy)
        if ex not in contract_price_trans_symbols_from_contract:
            contract_price_trans_symbols_from_contract[ex] = {}
        contract_price_trans_symbols_from_contract[ex][sy.replace("-", '').lower()] = i
        contract_price_trans_symbols_from_contract[ex][sy.replace("-", "_")] = i
        contract_price_trans_symbols_from_contract[ex][sy] = i
        contract_price_trans_symbols_from_contract[ex][sy.replace("-", '')] = i
        contract_price_trans_symbols_from_contract[ex][sy.replace("-", '/')] = i

# ---------------------------------------------- 合约currency配置 ---------------------------------------------- #

CONTRACT_CURRENCY_CONFIG = {}

contract_zone_all_symbols = {}
contract_all_symbols = set()
volume_zone_contract_symbols = {}
volume_self_contract_symbols = set()
for c_currency, v in CONTRACT_CURRENCY_CONFIG.items():
    for zone in v["zone"]:
        c_symbol = f"{c_currency}-{zone}"
        contract_all_symbols.add(c_symbol)
        if zone not in contract_zone_all_symbols:
            contract_zone_all_symbols[zone] = []
        contract_zone_all_symbols[zone].append(c_symbol)

        if zone not in volume_zone_contract_symbols:
            volume_zone_contract_symbols[zone] = []
        volume_zone_contract_symbols[zone].append(c_symbol)

    if v["self"]:
        for c in v["self_zone"]:
            volume_self_contract_symbols.add(f"{c_currency}-{c}")

# ---------------------------------------------- 现货currency配置 ---------------------------------------------- #

SPOT_CURRENCY_CONFIG = {
    "BTC": {
        "dangerous_level": 1,  # 1 等级越小的危险系数越小
        "hedge_threshold": "threshold_1",  # 对冲阈值级别
        "use_account": "1",  # 使用哪个账号
        "exchange": [(ExchangeCode.bn.value, "BTC-USDT",), (ExchangeCode.okex.value, "BTC-USDT",)],  # 刷量对应顺序
        "mean_order_size": {"BTC-USDT": 1},  # 做市档位量配置，如果只配置u区其他区自动计算
        "ask_bid_percent_spec": {"BTC-USDT": 0.00001, "BTC-USDT_PRICE": 0.1},  # 买卖一价差配置，如果只配置u区其他区会自动计算
        "zone": ["USDT"],  # 现货所有上线的zone
        "self_zone": ["USDT"],  # 现货自刷量开启的zone
        "self": 2,  # 0 不启用 1 主力刷量 2 非主力刷量
        "self_market_value": 500,  # 自每次自刷量价值u
        "open_time": "2021-8-9 14:02:55"
    },
    "ETH": {
        "dangerous_level": 1,
        "hedge_threshold": "threshold_1",
        "use_account": "1",  # 使用哪个账号
        "exchange": [(ExchangeCode.bn.value, "ETH-USDT",), (ExchangeCode.okex.value, "ETH-USDT",)],
        "mean_order_size": {"ETH-USDT": 20, "ETH-BTC": 1},
        "ask_bid_percent_spec": {"ETH-USDT": 0.00001, "ETH-USDT_PRICE": 0.01, "ETH-BTC": 0.01},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 500,
        "open_time": "2021-8-9 14:02:55"
    },
    "TRX": {
        "dangerous_level": 2,
        "hedge_threshold": "threshold_2",
        "use_account": "1",
        "exchange": [(ExchangeCode.bn.value, "TRX-USDT",), (ExchangeCode.okex.value, "TRX-USDT",)],
        "mean_order_size": {"TRX-USDT": 12000, "TRX-BTC": 1800},
        "ask_bid_percent_spec": {"TRX-USDT": 0.00008, "TRX-BTC": 0.01},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 200,
        "open_time": "2021-8-9 14:02:55"
    },
    # "APE": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "APE-USDT",), (ExchangeCode.okex.value, "APE-USDT",)],
    #     "mean_order_size": {"APE-USDT": 2000, "APE-BTC": 40},
    #     "ask_bid_percent_spec": {"APE-USDT": 0.0001, "APE-BTC": 0.01},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 250,
    #     "open_time": "2021-8-9 14:02:55"
    # },
    "BNB": {
        "dangerous_level": 2,
        "hedge_threshold": "threshold_2",
        "use_account": "1",
        "exchange": [(ExchangeCode.bn.value, "BNB-USDT",), (ExchangeCode.okex.value, "BNB-USDT",)],
        "mean_order_size": {"BNB-USDT": 8, "BNB-BTC": 0.4},
        "ask_bid_percent_spec": {"BNB-USDT": 0.00005, "BNB-BTC": 0.01},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 300,
        "open_time": "2021-8-9 14:02:55"
    },
    # "AXS": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "AXS-USDT",), (ExchangeCode.okex.value, "AXS-USDT",)],
    #     "mean_order_size": {"AXS-USDT": 1500, "AXS-BTC": 18},
    #     "ask_bid_percent_spec": {"AXS-USDT": 0.0002, "AXS-BTC": 0.01},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 250,
    #     "open_time": "2021-8-9 14:02:55"
    # },
    # "ENS": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_2",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "ENS-USDT",), (ExchangeCode.okex.value, "ENS-USDT",)],
    #     "mean_order_size": {"ENS-USDT": 96, "ENS-BTC": 10},
    #     "ask_bid_percent_spec": {"ENS-USDT": 0.0002, "ENS-BTC": 0.01},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 300,
    #     "open_time": "2021-8-9 14:02:55"
    # },
    # "LINK": {
    #     "dangerous_level": 2,
    #     "hedge_threshold": "threshold_2",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "LINK-USDT",), (ExchangeCode.okex.value, "LINK-USDT",)],
    #     "mean_order_size": {"LINK-USDT": 360, "LINK-BTC": 18},
    #     "ask_bid_percent_spec": {"LINK-USDT": 0.00005, "LINK-BTC": 0.01},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 300,
    #     "open_time": "2021-8-9 14:02:55"
    # },
    # "MANA": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "MANA-USDT",), (ExchangeCode.okex.value, "MANA-USDT",)],
    #     "mean_order_size": {"MANA-USDT": 2000, "MANA-BTC": 200},
    #     "ask_bid_percent_spec": {"MANA-USDT": 0.0003, "MANA-BTC": 0.01},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 300,
    #     "open_time": "2021-8-9 14:02:55"
    # },
    # "SAND": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "SAND-USDT",), (ExchangeCode.okex.value, "SAND-USDT",)],
    #     "mean_order_size": {"SAND-USDT": 200, "SAND-BTC": 20},
    #     "ask_bid_percent_spec": {"SAND-USDT": 0.05, "SAND-BTC": 0.5},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 250,
    #     "open_time": "2021-8-9 14:02:55"
    # },
    # "SHIB": {
    #     "dangerous_level": 2,
    #     "hedge_threshold": "threshold_2",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "SHIB-USDT",), (ExchangeCode.okex.value, "SHIB-USDT",)],
    #     "mean_order_size": {"SHIB-USDT": 300000000},
    #     "ask_bid_percent_spec": {"SHIB-USDT": 0.0003},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 300,
    #     "open_time": "2021-8-9 14:02:55"
    # },
    # "1INCH": {
    #     "dangerous_level": 2,
    #     "hedge_threshold": "threshold_2",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "1INCH-USDT",), (ExchangeCode.okex.value, "1INCH-USDT",)],
    #     "mean_order_size": {"1INCH-USDT": 4110, "1INCH-BTC": 411},
    #     "ask_bid_percent_spec": {"1INCH-USDT": 0.0004, "1INCH-BTC": 0.01},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 300,
    #     "open_time": "2021-8-9 14:02:55"
    # },
    # "AAVE": {
    #     "dangerous_level": 2,
    #     "hedge_threshold": "threshold_2",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "AAVE-USDT",), (ExchangeCode.okex.value, "AAVE-USDT",)],
    #     "mean_order_size": {"AAVE-USDT": 36, "AAVE-BTC": 2},
    #     "ask_bid_percent_spec": {"AAVE-USDT": 0.0002, "AAVE-BTC": 0.01},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 300,
    #     "open_time": "2021-8-9 14:02:55"
    # },
    "COMP": {
        "dangerous_level": 3,
        "hedge_threshold": "threshold_3",
        "use_account": "1",
        "exchange": [(ExchangeCode.bn.value, "COMP-USDT",), (ExchangeCode.okex.value, "COMP-USDT",)],
        "mean_order_size": {"COMP-USDT": 250, "COMP-BTC": 2.5},
        "ask_bid_percent_spec": {"COMP-USDT": 0.0002, "COMP-BTC": 0.01},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 250,
        "open_time": "2021-8-9 14:02:55"
    },
    # "YGG": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "YGG-USDT",), (ExchangeCode.okex.value, "YGG-USDT",)],
    #     "mean_order_size": {"YGG-USDT": 4780, "YGG-BTC": 478},
    #     "ask_bid_percent_spec": {"YGG-USDT": 0.0004, "YGG-BTC": 0.01},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 300,
    #     "open_time": "2021-8-9 14:02:55"
    # },
    # "CRV": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "CRV-USDT",), (ExchangeCode.okex.value, "CRV-USDT",)],
    #     "mean_order_size": {"CRV-USDT": 120000, "CRV-BTC": 218},
    #     "ask_bid_percent_spec": {"CRV-USDT": 0.0002, "CRV-BTC": 0.01},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 250,
    #     "open_time": "2021-8-9 14:02:55"
    # },
    # "MASK": {
    #     "dangerous_level": 2,
    #     "hedge_threshold": "threshold_2",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "MASK-USDT",), (ExchangeCode.okex.value, "MASK-USDT",)],
    #     "mean_order_size": {"MASK-USDT": 380, "MASK-BTC": 38},
    #     "ask_bid_percent_spec": {"MASK-USDT": 0.0007, "MASK-BTC": 0.01},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 300,
    #     "open_time": "2021-8-9 14:02:55"
    # },
    # "SUSHI": {
    #     "dangerous_level": 2,
    #     "hedge_threshold": "threshold_2",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "SUSHI-USDT",), (ExchangeCode.okex.value, "SUSHI-USDT",)],
    #     "mean_order_size": {"SUSHI-USDT": 1700, "SUSHI-BTC": 170},
    #     "ask_bid_percent_spec": {"SUSHI-USDT": 0.0005, "SUSHI-BTC": 0.015},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 300,
    #     "open_time": "2021-8-9 14:02:55"
    # },
    # "ANKR": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "ANKR-USDT",), (ExchangeCode.gate.value, "ANKR-USDT",)],
    #     "mean_order_size": {"ANKR-USDT": 56000},
    #     "ask_bid_percent_spec": {"ANKR-USDT": 0.0005},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 300,
    #     "open_time": "2021-8-9 14:02:55"
    # },
    # "BAT": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "BAT-USDT",), (ExchangeCode.okex.value, "BAT-USDT",)],
    #     "mean_order_size": {"BAT-USDT": 6000},
    #     "ask_bid_percent_spec": {"BAT-USDT": 0.0005},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 300,
    #     "open_time": "2021-8-9 14:02:55"
    # },
    # "CHZ": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "CHZ-USDT",), (ExchangeCode.okex.value, "CHZ-USDT",)],
    #     "mean_order_size": {"CHZ-USDT": 100000},
    #     "ask_bid_percent_spec": {"CHZ-USDT": 0.0003},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 250,
    #     "open_time": "2021-8-9 14:02:55"
    # },
    # "EGLD": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "EGLD-USDT",), (ExchangeCode.okex.value, "EGLD-USDT",)],
    #     "mean_order_size": {"EGLD-USDT": 42},
    #     "ask_bid_percent_spec": {"EGLD-USDT": 0.0004},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 300,
    #     "open_time": "2021-8-9 14:02:55"
    # },
    # "INJ": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "INJ-USDT",), (ExchangeCode.gate.value, "INJ-USDT",)],
    #     "mean_order_size": {"INJ-USDT": 50},
    #     "ask_bid_percent_spec": {"INJ-USDT": 0.0001},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 300,
    #     "open_time": "2021-8-9 14:02:55"
    # },
    # "IOTX": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "IOTX-USDT",)],  #, (ExchangeCode.gate.value, "IOTX-USDT",)],
    #     "mean_order_size": {"IOTX-USDT": 25000},
    #     "ask_bid_percent_spec": {"IOTX-USDT": 0.0004},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 300,
    #     "open_time": "2021-8-9 14:02:55"
    # },
    # "QNT": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "QNT-USDT",), (ExchangeCode.gate.value, "QNT-USDT",)],
    #     "mean_order_size": {"QNT-USDT": 12},
    #     "ask_bid_percent_spec": {"QNT-USDT": 0.0008},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 300,
    #     "open_time": "2021-8-9 14:02:55"
    # },
    "UNI": {
        "dangerous_level": 3,
        "hedge_threshold": "threshold_3",
        "use_account": "1",
        "exchange": [(ExchangeCode.bn.value, "UNI-USDT",), (ExchangeCode.okex.value, "UNI-USDT",)],
        "mean_order_size": {"UNI-USDT": 1000},
        "ask_bid_percent_spec": {"UNI-USDT": 0.0002},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 300,
        "open_time": "2021-8-9 14:02:55"
    },
    # "TRB": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "TRB-USDT",), (ExchangeCode.okex.value, "TRB-USDT",)],
    #     "mean_order_size": {"TRB-USDT": 3000},
    #     "ask_bid_percent_spec": {"TRB-USDT": 0.0005},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 250,
    #     "open_time": "2021-8-9 14:02:55"
    # },
    # "GLM": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "GLM-USDT",), (ExchangeCode.okex.value, "GLM-USDT",)],
    #     "mean_order_size": {"GLM-USDT": 4000},
    #     "ask_bid_percent_spec": {"GLM-USDT": 0.0008},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 300,
    #     "open_time": "2023-10-20 15:30:00"
    # },
    # "TIA": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "TIA-USDT",), (ExchangeCode.okex.value, "TIA-USDT",)],
    #     "mean_order_size": {"TIA-USDT": 3000},
    #     "ask_bid_percent_spec": {"TIA-USDT": 0.0005},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 300,
    #     "open_time": "2023-11-01 00:30:00"
    # },
    # "FLOKI": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "FLOKI-USDT",), (ExchangeCode.okex.value, "FLOKI-USDT",)],
    #     "mean_order_size": {"FLOKI-USDT": 34000000},
    #     "ask_bid_percent_spec": {"FLOKI-USDT": 0.0004},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 300,
    #     "open_time": "2023-11-03 19:00:00"
    # },
    # "MEME": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "MEME-USDT",), (ExchangeCode.okex.value, "MEME-USDT",)],
    #     "mean_order_size": {"MEME-USDT": 42000},
    #     "ask_bid_percent_spec": {"MEME-USDT": 0.0004},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 250,
    #     "open_time": "2023-11-04 19:00:00"
    # },
    # "FTT": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "FTT-USDT",), (ExchangeCode.gate.value, "FTT-USDT",)],
    #     "mean_order_size": {"FTT-USDT": 100},
    #     "ask_bid_percent_spec": {"FTT-USDT": 0.001},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 300,
    #     "open_time": "2023-11-12 14:00:00"
    # },
    # "ORDI": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "ORDI-USDT",), (ExchangeCode.okex.value, "ORDI-USDT",)],
    #     "mean_order_size": {"ORDI-USDT": 1500},
    #     "ask_bid_percent_spec": {"ORDI-USDT": 0.0006},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 250,
    #     "open_time": "2023-11-25 20:00:00"
    # },
    # "BEAMX": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "BEAMX-USDT",), (ExchangeCode.gate.value, "BEAMX-USDT",)],
    #     "mean_order_size": {"BEAMX-USDT": 50000},
    #     "ask_bid_percent_spec": {"BEAMX-USDT": 0.0001},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 30,
    #     "open_time": "2023-12-26 19:00:00"
    # },
    "CAKE": {
        "dangerous_level": 3,
        "hedge_threshold": "threshold_3",
        "use_account": "1",
        "exchange": [(ExchangeCode.bn.value, "CAKE-USDT",), (ExchangeCode.gate.value, "CAKE-USDT",)],
        "mean_order_size": {"CAKE-USDT": 340},
        "ask_bid_percent_spec": {"CAKE-USDT": 0.0003},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 30,
        "open_time": "2023-12-26 19:00:00"
    },
    # "GALA": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "GALA-USDT",), (ExchangeCode.okex.value, "GALA-USDT",)],
    #     "mean_order_size": {"GALA-USDT": 30000},
    #     "ask_bid_percent_spec": {"GALA-USDT": 0.001},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 30,
    #     "open_time": "2023-12-26 19:00:00"
    # },
    # "WLD": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "WLD-USDT",), (ExchangeCode.okex.value, "WLD-USDT",)],
    #     "mean_order_size": {"WLD-USDT": 280},
    #     "ask_bid_percent_spec": {"WLD-USDT": 0.0003},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 30,
    #     "open_time": "2024-1-4 17:00:00"
    # },
    # "GRT": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "GRT-USDT",), (ExchangeCode.okex.value, "GRT-USDT",)],
    #     "mean_order_size": {"GRT-USDT": 4800},
    #     "ask_bid_percent_spec": {"GRT-USDT": 0.0004},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 30,
    #     "open_time": "2024-1-4 17:00:00"
    # },
    # "PEOPLE": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "PEOPLE-USDT",), (ExchangeCode.okex.value, "PEOPLE-USDT",)],
    #     "mean_order_size": {"PEOPLE-USDT": 28000},
    #     "ask_bid_percent_spec": {"PEOPLE-USDT": 0.0005},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 30,
    #     "open_time": "2024-1-9 17:00:00"
    # },
    # "LDO": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "LDO-USDT",), (ExchangeCode.okex.value, "LDO-USDT",)],
    #     "mean_order_size": {"LDO-USDT": 1000},
    #     "ask_bid_percent_spec": {"LDO-USDT": 0.0003},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 30,
    #     "open_time": "2024-1-9 17:00:00"
    # },
    # "GMT": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "GMT-USDT",), (ExchangeCode.okex.value, "GMT-USDT",)],
    #     "mean_order_size": {"GMT-USDT": 3200},
    #     "ask_bid_percent_spec": {"GMT-USDT": 0.0003},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 30,
    #     "open_time": "2024-1-19 17:00:00"
    # },
    # "ONDO": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_4",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.okex.value, "ONDO-USDT",), (ExchangeCode.gate.value, "ONDO-USDT",)],
    #     "mean_order_size": {"ONDO-USDT": 262},
    #     "ask_bid_percent_spec": {"ONDO-USDT": 0.0008},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 150,
    #     "open_time": "2024-1-19 19:00:00"
    # },
    # "IMX": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "IMX-USDT",), (ExchangeCode.okex.value, "IMX-USDT",)],
    #     "mean_order_size": {"IMX-USDT": 540},
    #     "ask_bid_percent_spec": {"IMX-USDT": 0.0005},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 30,
    #     "open_time": "2024-1-22 17:00:00"
    # },
    # "PENDLE": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "PENDLE-USDT",), (ExchangeCode.gate.value, "PENDLE-USDT",)],
    #     "mean_order_size": {"PENDLE-USDT": 400},
    #     "ask_bid_percent_spec": {"PENDLE-USDT": 0.0002},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 30,
    #     "open_time": "2024-1-26 17:00:00"
    # },
    # "LPT": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "LPT-USDT",), (ExchangeCode.okex.value, "LPT-USDT",)],
    #     "mean_order_size": {"LPT-USDT": 146},
    #     "ask_bid_percent_spec": {"LPT-USDT": 0.0004},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 30,
    #     "open_time": "2024-1-26 17:00:00"
    # },
    "OKB": {
        "dangerous_level": 3,
        "hedge_threshold": "threshold_4",
        "use_account": "1",
        "exchange": [(ExchangeCode.okex.value, "OKB-USDT",), (ExchangeCode.gate.value, "OKB-USDT",)],
        "mean_order_size": {"OKB-USDT": 3},
        "ask_bid_percent_spec": {"OKB-USDT": 0.0008},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 150,
        "open_time": "2024-2-28 17:00:00"
    },
    # "JASMY": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_4",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "JASMY-USDT",), (ExchangeCode.gate.value, "JASMY-USDT",)],
    #     "mean_order_size": {"JASMY-USDT": 45200},
    #     "ask_bid_percent_spec": {"JASMY-USDT": 0.0002},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 30,
    #     "open_time": "2024-2-29 17:00:00"
    # },
    # "SUI": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_4",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "SUI-USDT",), (ExchangeCode.okex.value, "SUI-USDT",)],
    #     "mean_order_size": {"SUI-USDT": 2000},
    #     "ask_bid_percent_spec": {"SUI-USDT": 0.0001},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 30,
    #     "open_time": "2024-3-11 17:00:00"
    # },
    # "ARB": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_4",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "ARB-USDT",), (ExchangeCode.okex.value, "ARB-USDT",)],
    #     "mean_order_size": {"ARB-USDT": 4000},
    #     "ask_bid_percent_spec": {"ARB-USDT": 0.0001},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 25,
    #     "open_time": "2024-3-15 17:00:00"
    # },
    # "AEVO": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_4",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "AEVO-USDT",), (ExchangeCode.okex.value, "AEVO-USDT",)],
    #     "mean_order_size": {"AEVO-USDT": 440},
    #     "ask_bid_percent_spec": {"AEVO-USDT": 0.0008},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 30,
    #     "open_time": "2024-3-19 17:30:00"
    # },
    "ETHFI": {
        "dangerous_level": 3,
        "hedge_threshold": "threshold_4",
        "use_account": "1",
        "exchange": [(ExchangeCode.bn.value, "ETHFI-USDT",), (ExchangeCode.okex.value, "ETHFI-USDT",)],
        "mean_order_size": {"ETHFI-USDT": 320},
        "ask_bid_percent_spec": {"ETHFI-USDT": 0.0003},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 30,
        "open_time": "2024-3-20 17:00:00"
    },
    # "CFX": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "CFX-USDT",), (ExchangeCode.okex.value, "CFX-USDT",)],
    #     "mean_order_size": {"CFX-USDT": 50000},
    #     "ask_bid_percent_spec": {"CFX-USDT": 0.0003},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 25,
    #     "open_time": "2024-4-3 17:00:00"
    # },
    # "ENA": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "ENA-USDT",), (ExchangeCode.gate.value, "ENA-USDT",)],
    #     "mean_order_size": {"ENA-USDT": 5000},
    #     "ask_bid_percent_spec": {"ENA-USDT": 0.0008},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 25,
    #     "open_time": "2024-4-9 17:00:00"
    # },
    "SOL": {
        "dangerous_level": 2,
        "hedge_threshold": "threshold_2",
        "use_account": "1",
        "exchange": [(ExchangeCode.bn.value, "SOL-USDT",), (ExchangeCode.okex.value, "SOL-USDT",)],
        "mean_order_size": {"SOL-USDT": 80},
        "ask_bid_percent_spec": {"SOL-USDT": 0.0001},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 150,
        "open_time": "2024-4-30 20:03:00"
    },
    # "JTO": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "JTO-USDT",), (ExchangeCode.okex.value, "JTO-USDT",)],
    #     "mean_order_size": {"JTO-USDT": 300},
    #     "ask_bid_percent_spec": {"JTO-USDT": 0.005},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 150,
    #     "open_time": "2024-4-30 20:03:00"
    # },
    # "SAFE": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_4",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.okex.value, "SAFE-USDT",), (ExchangeCode.gate.value, "SAFE-USDT",)],
    #     "mean_order_size": {"SAFE-USDT": 600},
    #     "ask_bid_percent_spec": {"SAFE-USDT": 0.001},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 150,
    #     "open_time": "2024-5-6 18:00:00"
    # },
    # "NEAR": {
    #     "dangerous_level": 2,
    #     "hedge_threshold": "threshold_2",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "NEAR-USDT",), (ExchangeCode.okex.value, "NEAR-USDT",)],
    #     "mean_order_size": {"NEAR-USDT": 520},
    #     "ask_bid_percent_spec": {"NEAR-USDT": 0.0001},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 150,
    #     "open_time": "2024-5-7 17:00:00"
    # },
    # "JUP": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "JUP-USDT",), (ExchangeCode.okex.value, "JUP-USDT",)],
    #     "mean_order_size": {"JUP-USDT": 1800},
    #     "ask_bid_percent_spec": {"JUP-USDT": 0.0003},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 150,
    #     "open_time": "2024-5-10 19:00:00"
    # },
    # "WIF": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "WIF-USDT",), (ExchangeCode.okex.value, "WIF-USDT",)],
    #     "mean_order_size": {"WIF-USDT": 630},
    #     "ask_bid_percent_spec": {"WIF-USDT": 0.0001},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 150,
    #     "open_time": "2024-5-10 19:00:00"
    # },
    # "PEPE": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "PEPE-USDT",), (ExchangeCode.okex.value, "PEPE-USDT",)],
    #     "mean_order_size": {"PEPE-USDT": 100000000},
    #     "ask_bid_percent_spec": {"PEPE-USDT": 0.0003},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 100,
    #     "open_time": "2024-5-11 17:00:00"
    # },
    # "BOME": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "BOME-USDT",), (ExchangeCode.gate.value, "BOME-USDT",)],
    #     "mean_order_size": {"BOME-USDT": 200000},
    #     "ask_bid_percent_spec": {"BOME-USDT": 0.0003},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 100,
    #     "open_time": "2024-5-17 17:00:00"
    # },
    # "W": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "W-USDT",), (ExchangeCode.okex.value, "W-USDT",)],
    #     "mean_order_size": {"W-USDT": 35000},
    #     "ask_bid_percent_spec": {"W-USDT": 0.001},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 50,
    #     "open_time": "2024-5-21 17:00:00"
    # },
    # "RAY": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "RAY-USDT",), (ExchangeCode.okex.value, "RAY-USDT",)],
    #     "mean_order_size": {"RAY-USDT": 250},
    #     "ask_bid_percent_spec": {"RAY-USDT": 0.0008},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 90,
    #     "open_time": "2024-5-30 18:00:00"
    # },
    # "ZRO": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_4",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "ZRO-USDT",), (ExchangeCode.okex.value, "ZRO-USDT",)],
    #     "mean_order_size": {"ZRO-USDT": 100},
    #     "ask_bid_percent_spec": {"ZRO-USDT": 0.01},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 150,
    #     "open_time": "2024-6-26 17:00:00"
    # },
    # "FET": {
    #     "dangerous_level": 2,
    #     "hedge_threshold": "threshold_2",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "FET-USDT",), (ExchangeCode.okex.value, "FET-USDT",)],
    #     "mean_order_size": {"FET-USDT": 8000},
    #     "ask_bid_percent_spec": {"FET-USDT": 0.0002},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 300,
    #     "open_time": "2023-12-01 17:00:00"
    # },
    "APT": {
        "dangerous_level": 3,
        "hedge_threshold": "threshold_4",
        "use_account": "1",
        "exchange": [(ExchangeCode.bn.value, "APT-USDT",), (ExchangeCode.okex.value, "APT-USDT",)],
        "mean_order_size": {"APT-USDT": 500},
        "ask_bid_percent_spec": {"APT-USDT": 0.0002},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 100,
        "open_time": "2023-07-19 17:00:00"
    },
    # "RENDER": {
    #     "dangerous_level": 4,
    #     "hedge_threshold": "threshold_5",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "RENDER-USDT",), (ExchangeCode.okex.value, "RENDER-USDT",)],
    #     "mean_order_size": {"RENDER-USDT": 330},
    #     "ask_bid_percent_spec": {"RENDER-USDT": 0.0005},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 150,
    #     "open_time": "2023-07-31 17:00:00"
    # },
    # "DOGS": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "DOGS-USDT",), (ExchangeCode.gate.value, "DOGS-USDT",)],
    #     "mean_order_size": {"DOGS-USDT": 9000000},
    #     "ask_bid_percent_spec": {"DOGS-USDT": 0.0002},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 150,
    #     "open_time": "2023-08-05 17:00:00"
    # },
    # "POL": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "POL-USDT",), (ExchangeCode.okex.value, "POL-USDT",)],
    #     "mean_order_size": {"POL-USDT": 3000},
    #     "ask_bid_percent_spec": {"POL-USDT": 0.0002},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 150,
    #     "open_time": "2023-08-05 17:00:00"
    # },
    # "PNUT": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "PNUT-USDT",), (ExchangeCode.gate.value, "PNUT-USDT",)],
    #     "mean_order_size": {"PNUT-USDT": 100000},
    #     "ask_bid_percent_spec": {"PNUT-USDT": 0.0008},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 100,
    #     "open_time": "2023-08-05 17:00:00"
    # },
    # "ACT": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "ACT-USDT",), (ExchangeCode.gate.value, "ACT-USDT",)],
    #     "mean_order_size": {"ACT-USDT": 1000},
    #     "ask_bid_percent_spec": {"ACT-USDT": 0.0005},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 150,
    #     "open_time": "2023-08-05 17:00:00"
    # },
    # "NEIRO": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "NEIRO-USDT",), (ExchangeCode.okex.value, "NEIRO-USDT",)],
    #     "mean_order_size": {"NEIRO-USDT": 30000000},
    #     "ask_bid_percent_spec": {"NEIRO-USDT": 0.0005},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 150,
    #     "open_time": "2024-11-27 10:00:00"
    # },
    # "MOVE": {
    #     "dangerous_level": 2,
    #     "hedge_threshold": "threshold_2",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "MOVE-USDT",), (ExchangeCode.okex.value, "MOVE-USDT",)],
    #     "mean_order_size": {"MOVE-USDT": 6000},
    #     "ask_bid_percent_spec": {"MOVE-USDT": 0.005},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 100,
    #     "open_time": "2024-11-27 10:00:00"
    # },
    # "PENGU": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "PENGU-USDT",), (ExchangeCode.gate.value, "PENGU-USDT",)],
    #     "mean_order_size": {"PENGU-USDT": 100000},
    #     "ask_bid_percent_spec": {"PENGU-USDT": 0.0008},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 100,
    #     "open_time": "2024-11-27 10:00:00"
    # },
    # "TRUMP": {
    #     "dangerous_level": 2,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "TRUMP-USDT",), (ExchangeCode.bitget.value, "TRUMP-USDT",)],
    #     "mean_order_size": {"TRUMP-USDT": 20},
    #     "ask_bid_percent_spec": {"TRUMP-USDT": 0.0003},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 150,
    #     "open_time": "2024-11-27 10:00:00"
    # },
    # "USDQ": {
    #     "dangerous_level": 4,
    #     "hedge_threshold": "threshold_4",
    #     "use_account": "1",
    #     "exchange": [],
    #     "mean_order_size": {"USDQ-USDT": 100},
    #     "ask_bid_percent_spec": {"USDQ-USDT": 0.002},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 1,
    #     "self_market_value": 30,
    #     "open_time": "2024-11-27 10:00:00",
    #     "is_stable_coin": True,
    # },
    # "USDR": {
    #     "dangerous_level": 4,
    #     "hedge_threshold": "threshold_4",
    #     "use_account": "1",
    #     "exchange": [],
    #     "mean_order_size": {"USDR-USDT": 100},
    #     "ask_bid_percent_spec": {"USDR-USDT": 0.002},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 1,
    #     "self_market_value": 59,
    #     "open_time": "2024-11-27 10:00:00",
    #     "is_stable_coin": True,
    # },
    # "ORCA": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "ORCA-USDT",), ],
    #     "mean_order_size": {"ORCA-USDT": 800},
    #     "ask_bid_percent_spec": {"ORCA-USDT": 0.001},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 150,
    #     "open_time": "2024-11-27 10:00:00"
    # },
    # "BMT": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "BMT-USDT",), ],
    #     "mean_order_size": {"BMT-USDT": 8000},
    #     "ask_bid_percent_spec": {"BMT-USDT": 0.0015},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 150,
    #     "open_time": "2024-11-27 10:00:00"
    # },
    "XRP": {
        "dangerous_level": 2,
        "hedge_threshold": "threshold_2",
        "use_account": "1",
        "exchange": [(ExchangeCode.bn.value, "XRP-USDT",), (ExchangeCode.okex.value, "XRP-USDT",)],
        "mean_order_size": {"XRP-USDT": 4000},
        "ask_bid_percent_spec": {"XRP-USDT": 0.0002},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 150,
        "open_time": "2024-11-27 10:00:00"
    },
    "DOGE": {
        "dangerous_level": 2,
        "hedge_threshold": "threshold_2",
        "use_account": "1",
        "exchange": [(ExchangeCode.bn.value, "DOGE-USDT",), (ExchangeCode.okex.value, "DOGE-USDT",)],
        "mean_order_size": {"DOGE-USDT": 10000},
        "ask_bid_percent_spec": {"DOGE-USDT": 0.0002},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 100,
        "open_time": "2024-11-27 10:00:00"
    },
    # "HYPER": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "HYPER-USDT",), (ExchangeCode.gate.value, "HYPER-USDT",)],
    #     "mean_order_size": {"HYPER-USDT": 2000},
    #     "ask_bid_percent_spec": {"HYPER-USDT": 0.0008},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 150,
    #     "open_time": "2024-11-27 10:00:00"
    # },
    # "LTC": {
    #     "dangerous_level": 2,
    #     "hedge_threshold": "threshold_2",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "LTC-USDT",), (ExchangeCode.okex.value, "LTC-USDT",)],
    #     "mean_order_size": {"LTC-USDT": 60},
    #     "ask_bid_percent_spec": {"LTC-USDT": 0.0001},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 150,
    #     "open_time": "2024-11-27 10:00:00"
    # },
    # "KERNEL": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "KERNEL-USDT",), (ExchangeCode.gate.value, "KERNEL-USDT",)],
    #     "mean_order_size": {"KERNEL-USDT": 200000},
    #     "ask_bid_percent_spec": {"KERNEL-USDT": 0.0016},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 100,
    #     "open_time": "2024-11-27 10:00:00"
    # },
    # "SXT": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "SXT-USDT",), (ExchangeCode.gate.value, "SXT-USDT",)],
    #     "mean_order_size": {"SXT-USDT": 10000},
    #     "ask_bid_percent_spec": {"SXT-USDT": 0.0012},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 150,
    #     "open_time": "2024-11-27 10:00:00"
    # },
    # "NXPC": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "NXPC-USDT",), ],
    #     "mean_order_size": {"NXPC-USDT": 600},
    #     "ask_bid_percent_spec": {"NXPC-USDT": 0.0012},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 150,
    #     "open_time": "2024-11-27 10:00:00"
    # },
    # "EURR": {
    #     "dangerous_level": 4,
    #     "hedge_threshold": "threshold_4",
    #     "use_account": "1",
    #     "exchange": [],
    #     "mean_order_size": {"EURR-USDT": 100},
    #     "ask_bid_percent_spec": {"EURR-USDT": 0.0025},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 1,
    #     "self_market_value": 30,
    #     "open_time": "2024-11-27 10:00:00",
    #     "is_stable_coin": True,
    # },
    # "EURQ": {
    #     "dangerous_level": 4,
    #     "hedge_threshold": "threshold_4",
    #     "use_account": "1",
    #     "exchange": [],
    #     "mean_order_size": {"EURQ-USDT": 30},
    #     "ask_bid_percent_spec": {"EURQ-USDT": 0.003},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 1,
    #     "self_market_value": 59,
    #     "open_time": "2024-11-27 10:00:00",
    #     "is_stable_coin": True,
    # },
    # "NEWT": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "NEWT-USDT",), (ExchangeCode.gate.value, "NEWT-USDT",)],
    #     "mean_order_size": {"NEWT-USDT": 2500},
    #     "ask_bid_percent_spec": {"NEWT-USDT": 0.005},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 30,
    #     "open_time": "2024-11-27 10:00:00",
    # },
    # "HOME": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "HOME-USDT",), (ExchangeCode.gate.value, "HOME-USDT",)],
    #     "mean_order_size": {"HOME-USDT": 30000},
    #     "ask_bid_percent_spec": {"HOME-USDT": 0.0008},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 59,
    #     "open_time": "2024-11-27 10:00:00",
    # },
    # "PUMP": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_4",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.gate.value, "PUMP-USDT",)],
    #     "mean_order_size": {"PUMP-USDT": 100000},
    #     "ask_bid_percent_spec": {"PUMP-USDT": 0.0008},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 59,
    #     "open_time": "2024-11-27 10:00:00",
    # },
    # "ERA": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "ERA-USDT",), (ExchangeCode.gate.value, "ERA-USDT",)],
    #     "mean_order_size": {"ERA-USDT": 800},
    #     "ask_bid_percent_spec": {"ERA-USDT": 0.001},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 59,
    #     "open_time": "2024-11-27 10:00:00",
    # },
    # "C": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "C-USDT",), (ExchangeCode.gate.value, "C-USDT",)],
    #     "mean_order_size": {"C-USDT": 30000},
    #     "ask_bid_percent_spec": {"C-USDT": 0.0008},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 50,
    #     "open_time": "2024-11-27 10:00:00",
    # },
    "USDC": {
        "dangerous_level": 3,
        "hedge_threshold": "threshold_u",
        "use_account": "1",
        "exchange": [(ExchangeCode.gate.value, "USDC-USDT",), (ExchangeCode.bn.value, "USDC-USDT",), ],
        "mean_order_size": {"USDC-USDT": 10000},
        "ask_bid_percent_spec": {"USDC-USDT": 0.0001},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 59,
        "open_time": "2024-11-27 10:00:00",
    },
    "WLFI": {
        "dangerous_level": 3,
        "hedge_threshold": "threshold_3",
        "use_account": "1",
        "exchange": [(ExchangeCode.bn.value, "WLFI-USDT",), (ExchangeCode.gate.value, "WLFI-USDT",), ],
        "mean_order_size": {"WLFI-USDT": 2000},
        "ask_bid_percent_spec": {"WLFI-USDT": 0.0001},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 59,
        "open_time": "2024-11-27 10:00:00",
    },
    # "SKY": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "SKY-USDT",), ],
    #     "mean_order_size": {"SKY-USDT": 6000},
    #     "ask_bid_percent_spec": {"SKY-USDT": 0.0001},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 59,
    #     "open_time": "2024-11-27 10:00:00",
    # },
    "ASTER": {
        "dangerous_level": 3,
        "hedge_threshold": "threshold_3",
        "use_account": "1",
        "exchange": [(ExchangeCode.bn.value, "ASTER-USDT",), ],
        "mean_order_size": {"ASTER-USDT": 600},
        "ask_bid_percent_spec": {"ASTER-USDT": 0.001},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 59,
        "open_time": "2024-11-27 10:00:00",
    },
    "XAUT": {
        "dangerous_level": 3,
        "hedge_threshold": "threshold_3",
        "use_account": "1",
        "exchange": [(ExchangeCode.okex.value, "XAUT-USDT",), (ExchangeCode.gate.value, "XAUT-USDT",)],
        "mean_order_size": {"XAUT-USDT": 4},
        "ask_bid_percent_spec": {"XAUT-USDT": 0.001},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 50,
        "open_time": "2024-11-27 10:00:00",
    },
    # "GIGGLE": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "GIGGLE-USDT",),],
    #     "mean_order_size": {"GIGGLE-USDT": 300},
    #     "ask_bid_percent_spec": {"GIGGLE-USDT": 0.0003},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 50,
    #     "open_time": "2024-11-27 10:00:00",
    # },
    # "ESP": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "ESP-USDT",),],
    #     "mean_order_size": {"ESP-USDT": 5000},
    #     "ask_bid_percent_spec": {"ESP-USDT": 0.001},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 59,
    #     "open_time": "2026-03-03 19:00:00",
    # },
    # "MANTRA": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.bn.value, "MANTRA-USDT",), (ExchangeCode.gate.value, "MANTRA-USDT",)],
    #     "mean_order_size": {"MANTRA-USDT": 10000},
    #     "ask_bid_percent_spec": {"MANTRA-USDT": 0.001},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 59,
    #     "open_time": "2026-03-04 16:00:00",
    # },
    "NVDAON": {
        "dangerous_level": 3,
        "hedge_threshold": "threshold_3",
        "use_account": "1",
        "exchange": [(ExchangeCode.gate.value, "NVDAON-USDT",)],
        "mean_order_size": {"NVDAON-USDT": 2000},
        "ask_bid_percent_spec": {"NVDAON-USDT": 0.002},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 59,
        "open_time": "2026-06-03 16:00:00",
    },
    "AAPLON": {
        "dangerous_level": 3,
        "hedge_threshold": "threshold_3",
        "use_account": "1",
        "exchange": [(ExchangeCode.gate.value, "AAPLON-USDT",)],
        "mean_order_size": {"AAPLON-USDT": 5000},
        "ask_bid_percent_spec": {"AAPLON-USDT": 0.003},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 59,
        "open_time": "2026-06-04 16:00:00",
    },
    "GOOGLON": {
        "dangerous_level": 3,
        "hedge_threshold": "threshold_3",
        "use_account": "1",
        "exchange": [(ExchangeCode.gate.value, "GOOGLON-USDT",)],
        "mean_order_size": {"GOOGLON-USDT": 5000},
        "ask_bid_percent_spec": {"GOOGLON-USDT": 0.004},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 59,
        "open_time": "2026-06-04 16:00:00",
    },
    "MSFTON": {
        "dangerous_level": 3,
        "hedge_threshold": "threshold_3",
        "use_account": "1",
        "exchange": [(ExchangeCode.gate.value, "MSFTON-USDT",)],
        "mean_order_size": {"MSFTON-USDT": 10000},
        "ask_bid_percent_spec": {"MSFTON-USDT": 0.002},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 59,
        "open_time": "2026-06-08 18:00:00",
    },
    "TSLAON": {
        "dangerous_level": 3,
        "hedge_threshold": "threshold_3",
        "use_account": "1",
        "exchange": [(ExchangeCode.gate.value, "TSLAON-USDT",)],
        "mean_order_size": {"TSLAON-USDT": 10000},
        "ask_bid_percent_spec": {"TSLAON-USDT": 0.003},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 59,
        "open_time": "2026-06-09 16:00:00",
    },
    # "CRCLON": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.gate.value, "CRCLON-USDT",)],
    #     "mean_order_size": {"CRCLON-USDT": 5000},
    #     "ask_bid_percent_spec": {"CRCLON-USDT": 0.004},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 59,
    #     "open_time": "2026-06-09 16:00:00",
    # },
    # "AMDON": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.gate.value, "AMDON-USDT",)],
    #     "mean_order_size": {"AMDON-USDT": 5000},
    #     "ask_bid_percent_spec": {"AMDON-USDT": 0.003},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 59,
    #     "open_time": "2026-06-10 16:00:00",
    # },
    "KOON": {
        "dangerous_level": 3,
        "hedge_threshold": "threshold_3",
        "use_account": "1",
        "exchange": [(ExchangeCode.gate.value, "KOON-USDT",)],
        "mean_order_size": {"KOON-USDT": 10000},
        "ask_bid_percent_spec": {"KOON-USDT": 0.003},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 59,
        "open_time": "2026-06-10 16:00:00",
    },
    "SPCX": {
        "dangerous_level": 3,
        "hedge_threshold": "threshold_3",
        "use_account": "1",
        "exchange": [(ExchangeCode.gate.value, "SPCX-USDT",)],
        "mean_order_size": {"SPCX-USDT": 500},
        "ask_bid_percent_spec": {"SPCX-USDT": 0.002},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 59,
        "open_time": "2026-06-10 16:00:00",
    },
    # "QQQON": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.gate.value, "QQQON-USDT",)],
    #     "mean_order_size": {"QQQON-USDT": 5000},
    #     "ask_bid_percent_spec": {"QQQON-USDT": 0.002},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 59,
    #     "open_time": "2026-06-10 16:00:00",
    # },
    "SPCXON": {
        "dangerous_level": 3,
        "hedge_threshold": "threshold_3",
        "use_account": "1",
        "exchange": [(ExchangeCode.gate.value, "SPCXON-USDT",)],
        "mean_order_size": {"SPCXON-USDT": 5000},
        "ask_bid_percent_spec": {"SPCXON-USDT": 0.002},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 59,
        "open_time": "2026-06-10 16:00:00",
    },
    # "NFLXON": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.gate.value, "NFLXON-USDT",)],
    #     "mean_order_size": {"NFLXON-USDT": 5000},
    #     "ask_bid_percent_spec": {"NFLXON-USDT": 0.003},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 59,
    #     "open_time": "2026-06-10 16:00:00",
    # },
    # "CSCOON": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.gate.value, "CSCOON-USDT",)],
    #     "mean_order_size": {"CSCOON-USDT": 10000},
    #     "ask_bid_percent_spec": {"CSCOON-USDT": 0.001},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 59,
    #     "open_time": "2026-06-10 16:00:00",
    # },
    # "LLYON": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.gate.value, "LLYON-USDT",)],
    #     "mean_order_size": {"LLYON-USDT": 5000},
    #     "ask_bid_percent_spec": {"LLYON-USDT": 0.006},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 59,
    #     "open_time": "2026-06-10 16:00:00",
    # },
    # "SBUXON": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.gate.value, "SBUXON-USDT",)],
    #     "mean_order_size": {"SBUXON-USDT": 5000},
    #     "ask_bid_percent_spec": {"SBUXON-USDT": 0.005},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 59,
    #     "open_time": "2026-06-10 16:00:00",
    # },
    # "PEPON": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.gate.value, "PEPON-USDT",)],
    #     "mean_order_size": {"PEPON-USDT": 8000},
    #     "ask_bid_percent_spec": {"PEPON-USDT": 0.005},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 59,
    #     "open_time": "2026-06-10 16:00:00",
    # },
    "GRAM": {
        "dangerous_level": 3,
        "hedge_threshold": "threshold_3",
        "use_account": "1",
        "exchange": [(ExchangeCode.bn.value, "GRAM-USDT",)],
        "mean_order_size": {"GRAM-USDT": 5000},
        "ask_bid_percent_spec": {"GRAM-USDT": 0.001},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 59,
        "open_time": "2026-07-01 16:00:00",
    },
    "SLVON": {
        "dangerous_level": 3,
        "hedge_threshold": "threshold_3",
        "use_account": "1",
        "exchange": [(ExchangeCode.gate.value, "SLVON-USDT",)],
        "mean_order_size": {"SLVON-USDT": 5000},
        "ask_bid_percent_spec": {"SLVON-USDT": 0.002},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 59,
        "open_time": "2026-07-08 16:00:00",
    },
    # "IAUON": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.gate.value, "IAUON-USDT",)],
    #     "mean_order_size": {"IAUON-USDT": 10000},
    #     "ask_bid_percent_spec": {"IAUON-USDT": 0.003},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 59,
    #     "open_time": "2026-07-08 16:00:00",
    # },
    # "SPYON": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.gate.value, "SPYON-USDT",)],
    #     "mean_order_size": {"SPYON-USDT": 3000},
    #     "ask_bid_percent_spec": {"SPYON-USDT": 0.0003},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 59,
    #     "open_time": "2026-07-08 16:00:00",
    # },
    # "HOODON": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.gate.value, "HOODON-USDT",)],
    #     "mean_order_size": {"HOODON-USDT": 5000},
    #     "ask_bid_percent_spec": {"HOODON-USDT": 0.0003},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 59,
    #     "open_time": "2026-07-08 16:00:00",
    # },
    "AMZNON": {
        "dangerous_level": 3,
        "hedge_threshold": "threshold_3",
        "use_account": "1",
        "exchange": [(ExchangeCode.gate.value, "AMZNON-USDT",)],
        "mean_order_size": {"AMZNON-USDT": 5000},
        "ask_bid_percent_spec": {"AMZNON-USDT": 0.003},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 59,
        "open_time": "2026-07-21 17:00:00",
    },
    "METAON": {
        "dangerous_level": 3,
        "hedge_threshold": "threshold_3",
        "use_account": "1",
        "exchange": [(ExchangeCode.gate.value, "METAON-USDT",)],
        "mean_order_size": {"METAON-USDT": 5000},
        "ask_bid_percent_spec": {"METAON-USDT": 0.0015},
        "zone": ["USDT"],
        "self_zone": ["USDT"],
        "self": 2,
        "self_market_value": 59,
        "open_time": "2026-07-21 17:00:00",
    },
    # "SKHYON": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.gate.value, "SKHYON-USDT",)],
    #     "mean_order_size": {"SKHYON-USDT": 5000},
    #     "ask_bid_percent_spec": {"SKHYON-USDT": 0.008},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 59,
    #     "open_time": "2026-07-24 17:00:00",
    # },
    # "翻身币": {
    #     "dangerous_level": 3,
    #     "hedge_threshold": "threshold_3",
    #     "use_account": "1",
    #     "exchange": [(ExchangeCode.gate.value, "SKHYON-USDT",)],
    #     "mean_order_size": {"SKHYON-USDT": 5000},
    #     "ask_bid_percent_spec": {"SKHYON-USDT": 0.008},
    #     "zone": ["USDT"],
    #     "self_zone": ["USDT"],
    #     "self": 2,
    #     "self_market_value": 59,
    #     "open_time": "2026-07-24 17:00:00",
    # },
}


spot_zone_all_symbols = {}  # 每个区包括自刷的所有交易对
volume_zone_symbols = {}  # 每个区需要去对标的交易对
volume_zone_exchange_symbols = {}
volume_exchange_symbols = {}
volume_currency_exchange = {}
volume_currency_open_time = {}
currency_conf_danger_symbols = []
currency_conf_danger_currency = set()
volume_trans_symbols_currency = {}
volume_self_symbols = set()

# 合约和现货统一订阅
volume_need_ws_currency = set(list(SPOT_CURRENCY_CONFIG.keys()) + list(CONTRACT_CURRENCY_CONFIG.keys()))
for c_currency in volume_need_ws_currency:
    spot_v = SPOT_CURRENCY_CONFIG.get(c_currency, {})
    contract_v = CONTRACT_CURRENCY_CONFIG.get(c_currency, {})
    ws_exchanges = spot_v.get("exchange", []) + contract_v.get("exchange", [])
    ws_zones = set(spot_v.get("zone", []) + contract_v.get("zone", []))
    # 不管是现货还是合约，都需要订阅
    for ex_collector in ws_exchanges:
        ex = ex_collector[0]
        ex_s = ex_collector[1]
        if not EXCHANGE_ACTIVE.get(ex):
            continue
        # 计算不同区交易所和该交易所对应的交易对
        for zone in ws_zones:
            if zone not in volume_zone_exchange_symbols:
                volume_zone_exchange_symbols[zone] = {}
            if ex not in volume_zone_exchange_symbols[zone]:
                volume_zone_exchange_symbols[zone] = {ex: []}
            volume_zone_exchange_symbols[zone][ex].append(ex_s)
        # 计算交易所和该交易所对应的交易对
        if ex not in volume_exchange_symbols:
            volume_exchange_symbols[ex] = []
        volume_exchange_symbols[ex].append(ex_s)

        # 计算abc交易对和刷量对标交易所
        volume_currency_exchange[c_currency] = ex
        if ex not in volume_trans_symbols_currency:
            volume_trans_symbols_currency[ex] = {}

        volume_trans_symbols_currency[ex][ex_s.replace("-", '').lower()] = c_currency
        volume_trans_symbols_currency[ex][ex_s.replace("-", "_")] = c_currency
        volume_trans_symbols_currency[ex][ex_s] = c_currency
        volume_trans_symbols_currency[ex][ex_s.replace("-", '')] = c_currency
        break

for c_currency, v in SPOT_CURRENCY_CONFIG.items():
    if v["self"]:
        for c in v["self_zone"]:
            volume_self_symbols.add(f"{c_currency}-{c}")

    for zone in v["zone"]:
        c_symbol = f"{c_currency}-{zone}"

        if v["dangerous_level"] >= 4:
            currency_conf_danger_symbols.append(c_symbol)
            currency_conf_danger_currency.add(c_currency)
        volume_currency_open_time[c_symbol] = v["open_time"]

        if zone not in spot_zone_all_symbols:
            spot_zone_all_symbols[zone] = []
        spot_zone_all_symbols[zone].append(c_symbol)
        # 现货可能存在有些交易对没有可以订阅档ws，使用自刷量进行刷量
        if volume_currency_exchange.get(c_currency):
            if zone not in volume_zone_symbols:
                volume_zone_symbols[zone] = []
            volume_zone_symbols[zone].append(c_symbol)

SPEC_SYMBOL_RATE_MAPPING = {
    ExchangeCode.bn.value: {
        "SATS-USDT": ("1000SATS-USDT", 1 / 1000),
        "BABYDOGE-USDT": ("1MBABYDOGE-USDT", 1 / 1000000),
    },
}

SPEC_CONTRACT_SYMBOL_RATE_MAPPING = {
    ExchangeCode.bn.value: {
        "XEC-USDT": ("1000XEC-USDT", 1 / 1000),
        "PEPE-USDT": ("1000PEPE-USDT", 1 / 1000),
        "BONK-USDT": ("1000BONK-USDT", 1 / 1000),
        "FLOKI-USDT": ("1000FLOKI-USDT", 1 / 1000),
        "LUNC-USDT": ("1000LUNC-USDT", 1 / 1000),
        "SHIB-USDT": ("1000SHIB-USDT", 1 / 1000),
    }
}

# --------------------------------------- 价格服务转换关系 --------------------------------------- #

# 标识基础交易对顺序，不需要改动！！
base_symbols_order = ["BTC-AQ", "ETH-AQ", "USDT-AQ", "OT-AQ",
                      "BTC-USDT", "ETH-USDT", "OT-USDT",
                      "BTC-ETH",
                      "BTC-OT", "ETH-OT", ]
base_symbols_rate_forward = [("BTC", "AQ"), ("ETH", "AQ"), ("USDT", "AQ"), ("OT", "AQ"),
                             ("BTC", "USDT"), ("ETH", "USDT"), ("OT", "USDT"),
                             ("BTC", "ETH"),
                             ("BTC", "OT"), ("ETH", "OT"), ]
spot_contract_all_symbols = price_all_symbols | contract_price_all_symbols
symbol_base_mapper = {pair.split("-")[0]: pair.split("-")[1] for pair in spot_contract_all_symbols}


# --------------------------------------- 其他配置 --------------------------------------- #


def launch_env():
    """
        trading : ip-10-0-209-181
        spot_paddington : ip-10-0-209-218
        spot_market_maker : ip-10-0-208-182
        spot_market_maker2 : ip-10-0-209-47
        contract_market_maker : ip-10-0-209-105
        contract_market_maker2 : ip-10-0-209-133
        contract_market_maker3 : ip-10-0-208-132
        management : ip-10-0-208-223
        spot_market_maker_btc : "ip-10-0-208-197"
    """

    online_server_list = ("ip-10-0-209-181",
                          "ip-10-0-209-218",
                          "ip-10-0-208-182", "ip-10-0-209-47",
                          "ip-10-0-209-105", "ip-10-0-209-133", "ip-10-0-208-132",
                          "ip-10-0-208-223", "ip-10-0-208-197")

    # mine = os.popen('/sbin/ifconfig eth0 | grep "inet 172"').read()
    # if not mine:
    #     # aws ec2
    #     mine = os.popen('/sbin/ifconfig ens5 | grep "inet 172"').read()
    # mine = os.popen('/sbin/ip link | grep link/ether').read()
    #
    # imprinting = [ip for ip in mine.strip().split(" ") if ip]
    # imprinting = imprinting[1] if imprinting else ""
    mine = os.popen('hostname').read()
    imprinting = mine.rstrip()

    debug = True if not imprinting or imprinting not in online_server_list else False
    mainland_server = True if not imprinting else False  # 如果my_ip是空的为True表示我的mac电脑，需要开启代理
    print(f"当前模式信息 imprinting: {imprinting} - debug: {debug} - mainland_server: {mainland_server}")
    return debug, mainland_server, imprinting


DEBUG, MAINLAND_SERVER, IMPRINGTING = launch_env()
CONTRACT_MAX_OFFSET_PERCENT = 0.001  # 合约盘口价格相对标记价格偏移量
CONTRACT_MAX_ASKBID_OFFSET_PERCENT = 0.001  # 合约买卖一价格相对对标过来价格偏移量

PRICE_ADJ = {  # 现货价格和买卖一价格偏移量，小于1为低于折价，大于1为溢价
    "XX-USDT": 0.99,
    "XX1-USDT": 1.01,
}

adj_support_list = ["BTC", "ETH", "LTC", "BSV", "BCH", "DASH", "ETC", "XRP", "TRX"]  # 行情变化过大需要自动调整

# ---------------------------------------------- Redis服务、缓存时间 ---------------------------------------------- #

CACHE_TIME = 20  # usdt-aq 多长时间去redis更新一次数据
MAX_VALID_TIME = 30 * 60  # usdt-aq redis在此时间端内认为是可用的
MAX_SPOST_ASK_BID_VALID_TIME = 15 * 60  # 现货买卖一 redis在此时间端内认为是可用的
MAX_CONTRACT_VALID_TIME = 60  # 合约价格 redis在此时间段内认为是可用的
MAX_CONTRACT_ASK_BID_VALID_TIME = 15  # 合约买卖一价格 redis在此时间段内认为是可用的

if DEBUG:
    REDIS_MASTER = ["18.140.249.184", 6379, "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2>r,v9rsl+B-SUsQBQYC6*yA"]
else:
    REDIS_MASTER = ["market-price-001.market-price.sg6zxz.apse1.cache.amazonaws.com",
                    6379,
                    "A(?xvw8~v(ke0(O,=Se!W(!UGBujuh(XkBHuQTRu2>r,v9rsl+B-SUsQBQYC6*yA"]

RS_CONF_MARKET_PRICE = {
    'host': REDIS_MASTER[0], 'port': REDIS_MASTER[1], 'password': REDIS_MASTER[2], 'db': 1
}
RS_CONF_MARKET_PRICE_2 = {
    'host': REDIS_MASTER[0], 'port': REDIS_MASTER[1], 'password': REDIS_MASTER[2], 'db': 1
}

RS_CONF_CONTRACT_PRICE = {
    'host': REDIS_MASTER[0], 'port': REDIS_MASTER[1], 'password': REDIS_MASTER[2], 'db': 2
}
RS_CONF_CONTRACT_PRICE_2 = {
    'host': REDIS_MASTER[0], 'port': REDIS_MASTER[1], 'password': REDIS_MASTER[2], 'db': 2
}

RS_CONF_ASKBID_PRICE = {
    'host': REDIS_MASTER[0], 'port': REDIS_MASTER[1], 'password': REDIS_MASTER[2], 'db': 3
}
RS_CONF_ASKBID_PRICE_2 = {
    'host': REDIS_MASTER[0], 'port': REDIS_MASTER[1], 'password': REDIS_MASTER[2], 'db': 3
}

RS_CONF_GEAR = {
    'host': REDIS_MASTER[0], 'port': REDIS_MASTER[1], 'password': REDIS_MASTER[2], 'db': 4
}

RS_CONF_HEART_BEAT = {
    'host': REDIS_MASTER[0], 'port': REDIS_MASTER[1], 'password': REDIS_MASTER[2], 'db': 7
}

RS_CONF_ADJ = {
    'host': REDIS_MASTER[0], 'port': REDIS_MASTER[1], 'password': REDIS_MASTER[2], 'db': 12}

RS_CONF_VOL = {
    'host': REDIS_MASTER[0], 'port': REDIS_MASTER[1], 'password': REDIS_MASTER[2], 'db': 13
}

RS_CONF_NODE = {
    'host': REDIS_MASTER[0], 'port': REDIS_MASTER[1], 'password': REDIS_MASTER[2], 'db': 14
}

RS_CONF_CONTROL = {
    'host': REDIS_MASTER[0], 'port': REDIS_MASTER[1], 'password': REDIS_MASTER[2], 'db': 15
}

# --------------------------------------- 测试环境定义区 --------------------------------------- #
# 防止测试修改部分出现异常，捕捉错误，确保不影响线上部分
try:
    if DEBUG:
        pass
except:
    print("-------------- 测试配置文件存在异常！")
    pass
